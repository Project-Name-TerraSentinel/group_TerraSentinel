"""
Unit tests for data processing and transformation utilities.
Tests data transformation accuracy, validation, and edge cases.
"""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock, patch

from backend.services.data_processor import (
    DataProcessor, ValidationResult, EnhancedPredictionRequest, 
    EnhancedPredictionResponse
)
from backend.services.terra_pulse_service import PredictionOutput
from backend.services.dify_service import DifyWorkflowInput


class TestDataProcessor:
    """Test suite for DataProcessor class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = DataProcessor()
        
        # Sample Terra Pulse result
        self.sample_terra_result = PredictionOutput(
            location="Baringo County, Kenya",
            degradation_risk=75,
            risk_factors=["bare_soil_increase", "low_ndvi"],
            recommended_action_key="mulch_crop_residue",
            confidence=0.85,
            user_context="smallholder_farmer",
            raw_prediction=0.75,
            processing_time_ms=120.5
        )
        
        # Sample Dify response
        self.sample_dify_response = {
            'status': 'success',
            'workflow_run_id': 'workflow_123',
            'enhanced_recommendations': [
                'Apply crop residue mulch within 2 weeks',
                'Consider drought-resistant maize varieties',
                'Implement contour farming on slopes'
            ],
            'risk_assessment': 'High degradation risk due to recent drought conditions',
            'timeline': 'Immediate action required within 14 days',
            'cost_estimate': 'Low cost - use existing crop residue',
            'success_probability': 0.78,
            'additional_insights': {'climate_factor': 'drought_stress'},
            'processing_time': 2.3
        }
        
        # Sample request data
        self.sample_request = {
            'ndvi_mean_early': 0.45,
            'ndvi_median_early': 0.43,
            'ndvi_std_early': 0.12,
            'ndvi_mean_late': 0.38,
            'ndvi_median_late': 0.36,
            'ndvi_std_late': 0.15,
            'ndvi_delta_mean': -0.07,
            'location': 'Baringo County, Kenya',
            'user_context': 'smallholder_farmer',
            'user_type': 'farmer'
        }


class TestValidation:
    """Test validation functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = DataProcessor()
    
    def test_validate_prediction_request_valid_data(self):
        """Test validation with valid request data."""
        valid_request = {
            'ndvi_mean_early': 0.45,
            'ndvi_median_early': 0.43,
            'ndvi_std_early': 0.12,
            'ndvi_mean_late': 0.38,
            'ndvi_median_late': 0.36,
            'ndvi_std_late': 0.15,
            'ndvi_delta_mean': -0.07,
            'location': 'Test Location',
            'user_context': 'test_user',
            'user_type': 'farmer'
        }
        
        result = self.processor.validate_prediction_request(valid_request)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_prediction_request_invalid_user_type(self):
        """Test validation with invalid user type."""
        invalid_request = {
            'ndvi_mean_early': 0.45,
            'ndvi_median_early': 0.43,
            'ndvi_std_early': 0.12,
            'ndvi_mean_late': 0.38,
            'ndvi_median_late': 0.36,
            'ndvi_std_late': 0.15,
            'ndvi_delta_mean': -0.07,
            'location': 'Test Location',
            'user_context': 'test_user',
            'user_type': 'invalid_type'
        }
        
        result = self.processor.validate_prediction_request(invalid_request)
        
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert any('user_type' in error for error in result.errors)
    
    def test_validate_prediction_request_out_of_range_ndvi(self):
        """Test validation with NDVI values out of range."""
        invalid_request = {
            'ndvi_mean_early': 5.0,  # Out of range
            'ndvi_median_early': 0.43,
            'ndvi_std_early': 0.12,
            'ndvi_mean_late': 0.38,
            'ndvi_median_late': 0.36,
            'ndvi_std_late': 0.15,
            'ndvi_delta_mean': -0.07,
            'location': 'Test Location',
            'user_type': 'farmer'
        }
        
        result = self.processor.validate_prediction_request(invalid_request)
        
        assert result.is_valid is False
        assert len(result.errors) > 0
    
    def test_validate_prediction_request_negative_std(self):
        """Test validation with negative standard deviation."""
        invalid_request = {
            'ndvi_mean_early': 0.45,
            'ndvi_median_early': 0.43,
            'ndvi_std_early': -0.12,  # Negative std
            'ndvi_mean_late': 0.38,
            'ndvi_median_late': 0.36,
            'ndvi_std_late': 0.15,
            'ndvi_delta_mean': -0.07,
            'location': 'Test Location',
            'user_type': 'farmer'
        }
        
        result = self.processor.validate_prediction_request(invalid_request)
        
        assert result.is_valid is False
        assert len(result.errors) > 0
    
    def test_validate_prediction_request_warnings(self):
        """Test validation warnings for suspicious data."""
        warning_request = {
            'ndvi_mean_early': 0.45,
            'ndvi_median_early': 0.43,
            'ndvi_std_early': 0.6,  # High variability
            'ndvi_mean_late': 0.38,
            'ndvi_median_late': 0.36,
            'ndvi_std_late': 0.15,
            'ndvi_delta_mean': -1.2,  # Large change
            'location': 'Test Location',
            'user_type': 'farmer'
        }
        
        result = self.processor.validate_prediction_request(warning_request)
        
        assert result.is_valid is True
        assert len(result.warnings) > 0


class TestSanitization:
    """Test input sanitization functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = DataProcessor()
    
    def test_sanitize_input_data_normal(self):
        """Test sanitization with normal data."""
        input_data = {
            'ndvi_mean_early': 0.45,
            'ndvi_median_early': 0.43,
            'ndvi_std_early': 0.12,
            'ndvi_mean_late': 0.38,
            'ndvi_median_late': 0.36,
            'ndvi_std_late': 0.15,
            'ndvi_delta_mean': -0.07,
            'location': 'Baringo County, Kenya',
            'user_context': 'smallholder_farmer',
            'user_type': 'farmer'
        }
        
        sanitized = self.processor.sanitize_input_data(input_data)
        
        assert sanitized['ndvi_mean_early'] == 0.45
        assert sanitized['location'] == 'Baringo County, Kenya'
        assert sanitized['user_type'] == 'farmer'
    
    def test_sanitize_input_data_malicious_location(self):
        """Test sanitization with potentially malicious location data."""
        input_data = {
            'ndvi_mean_early': 0.45,
            'location': 'Test<script>alert("xss")</script>Location',
            'user_type': 'farmer'
        }
        
        sanitized = self.processor.sanitize_input_data(input_data)
        
        # Should remove script tags and other harmful characters
        assert '<script>' not in sanitized['location']
        assert 'TestscriptalertxssscriptLocation' == sanitized['location']
    
    def test_sanitize_input_data_out_of_range_values(self):
        """Test sanitization with out-of-range numeric values."""
        input_data = {
            'ndvi_mean_early': 10.0,  # Way out of range
            'ndvi_std_early': -5.0,   # Negative std
            'location': 'Test Location',
            'user_type': 'farmer'
        }
        
        sanitized = self.processor.sanitize_input_data(input_data)
        
        # Should clamp to valid ranges
        assert sanitized['ndvi_mean_early'] == 2.0  # Clamped to max
        assert sanitized['ndvi_std_early'] == 0.0   # Clamped to min (0)
    
    def test_sanitize_input_data_invalid_user_type(self):
        """Test sanitization with invalid user type."""
        input_data = {
            'ndvi_mean_early': 0.45,
            'location': 'Test Location',
            'user_type': 'hacker'
        }
        
        sanitized = self.processor.sanitize_input_data(input_data)
        
        # Should default to farmer
        assert sanitized['user_type'] == 'farmer'
    
    def test_sanitize_input_data_long_location(self):
        """Test sanitization with overly long location string."""
        long_location = 'A' * 300  # 300 characters
        input_data = {
            'location': long_location,
            'user_type': 'farmer'
        }
        
        sanitized = self.processor.sanitize_input_data(input_data)
        
        # Should truncate to 200 characters
        assert len(sanitized['location']) <= 200


class TestDataTransformation:
    """Test data transformation functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = DataProcessor()
        self.sample_terra_result = PredictionOutput(
            location="Baringo County, Kenya",
            degradation_risk=75,
            risk_factors=["bare_soil_increase", "low_ndvi"],
            recommended_action_key="mulch_crop_residue",
            confidence=0.85,
            user_context="smallholder_farmer",
            raw_prediction=0.75,
            processing_time_ms=120.5
        )
    
    def test_convert_terra_pulse_to_dify_input(self):
        """Test conversion of Terra Pulse result to Dify input format."""
        dify_input = self.processor.convert_terra_pulse_to_dify_input(
            self.sample_terra_result, 
            user_type="farmer"
        )
        
        assert isinstance(dify_input, DifyWorkflowInput)
        assert dify_input.degradation_risk == 75
        assert dify_input.risk_factors == ["bare_soil_increase", "low_ndvi"]
        assert dify_input.location == "Baringo County, Kenya"
        assert dify_input.user_type == "farmer"
        assert dify_input.confidence == 0.85
        assert 'raw_prediction' in dify_input.additional_context
    
    def test_convert_terra_pulse_to_dify_input_official(self):
        """Test conversion for official user type."""
        dify_input = self.processor.convert_terra_pulse_to_dify_input(
            self.sample_terra_result, 
            user_type="official"
        )
        
        assert dify_input.user_type == "official"
        assert dify_input.degradation_risk == 75
    
    def test_convert_terra_pulse_to_dify_input_dict(self):
        """Test conversion with dictionary input instead of PredictionOutput."""
        terra_dict = {
            'location': 'Test Location',
            'degradation_risk': 60,
            'risk_factors': ['test_factor'],
            'recommended_action_key': 'test_action',
            'confidence': 0.7,
            'user_context': 'test_context',
            'raw_prediction': 0.6,
            'processing_time_ms': 100.0
        }
        
        dify_input = self.processor.convert_terra_pulse_to_dify_input(
            terra_dict, 
            user_type="farmer"
        )
        
        assert isinstance(dify_input, DifyWorkflowInput)
        assert dify_input.degradation_risk == 60
        assert dify_input.location == 'Test Location'
    
    def test_convert_terra_pulse_to_dify_input_missing_fields(self):
        """Test conversion with missing required fields."""
        incomplete_result = {
            'location': 'Test Location',
            'degradation_risk': 60
            # Missing other required fields
        }
        
        with pytest.raises(ValueError):
            self.processor.convert_terra_pulse_to_dify_input(
                incomplete_result, 
                user_type="farmer"
            )


class TestResponseMerging:
    """Test response merging functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = DataProcessor()
        self.sample_terra_result = PredictionOutput(
            location="Baringo County, Kenya",
            degradation_risk=75,
            risk_factors=["bare_soil_increase", "low_ndvi"],
            recommended_action_key="mulch_crop_residue",
            confidence=0.85,
            user_context="smallholder_farmer",
            raw_prediction=0.75,
            processing_time_ms=120.5
        )
        
        self.sample_dify_response = {
            'status': 'success',
            'workflow_run_id': 'workflow_123',
            'enhanced_recommendations': [
                'Apply crop residue mulch within 2 weeks',
                'Consider drought-resistant maize varieties'
            ],
            'risk_assessment': 'High degradation risk due to recent drought conditions',
            'timeline': 'Immediate action required within 14 days',
            'cost_estimate': 'Low cost - use existing crop residue',
            'success_probability': 0.78,
            'additional_insights': {'climate_factor': 'drought_stress'},
            'processing_time': 2.3
        }
    
    def test_merge_terra_pulse_and_dify_results_success(self):
        """Test successful merging of Terra Pulse and Dify results."""
        merged = self.processor.merge_terra_pulse_and_dify_results(
            self.sample_terra_result,
            self.sample_dify_response
        )
        
        assert 'terra_pulse_prediction' in merged
        assert 'ai_insights' in merged
        assert 'metadata' in merged
        
        # Check Terra Pulse data
        terra_pred = merged['terra_pulse_prediction']
        assert terra_pred['degradation_risk'] == 75
        assert terra_pred['location'] == "Baringo County, Kenya"
        
        # Check AI insights
        ai_insights = merged['ai_insights']
        assert len(ai_insights['enhanced_recommendations']) == 2
        assert ai_insights['risk_assessment'] == 'High degradation risk due to recent drought conditions'
        assert ai_insights['success_probability'] == 0.78
        
        # Check metadata
        metadata = merged['metadata']
        assert metadata['dify_workflow_id'] == 'workflow_123'
        assert metadata['dify_status'] == 'success'
        assert 'timestamp' in metadata
        assert metadata['ai_enhancement_available'] is True
    
    def test_merge_terra_pulse_and_dify_results_dify_failed(self):
        """Test merging when Dify processing failed."""
        failed_dify_response = {
            'status': 'failed',
            'workflow_run_id': 'failed_workflow',
            'error': 'Dify API timeout',
            'enhanced_recommendations': [],
            'risk_assessment': '',
            'timeline': '',
            'cost_estimate': '',
            'success_probability': 0.0,
            'additional_insights': {},
            'processing_time': 0.0
        }
        
        merged = self.processor.merge_terra_pulse_and_dify_results(
            self.sample_terra_result,
            failed_dify_response
        )
        
        assert merged['metadata']['dify_status'] == 'failed'
        assert merged['metadata']['ai_enhancement_available'] is False
        assert 'fallback_reason' in merged['metadata']
        assert merged['ai_insights']['fallback_used'] is True
    
    def test_merge_terra_pulse_and_dify_results_exception_handling(self):
        """Test merging with invalid data that causes exceptions."""
        invalid_dify_response = None  # This should cause an exception
        
        merged = self.processor.merge_terra_pulse_and_dify_results(
            self.sample_terra_result,
            invalid_dify_response
        )
        
        # Should return fallback response
        assert 'terra_pulse_prediction' in merged
        assert merged['ai_insights']['fallback_used'] is True
        assert 'error' in merged['metadata']
    
    def test_merge_terra_pulse_and_dify_results_dict_input(self):
        """Test merging with dictionary Terra Pulse input."""
        terra_dict = {
            'location': 'Test Location',
            'degradation_risk': 60,
            'risk_factors': ['test_factor'],
            'confidence': 0.7,
            'processing_time_ms': 100.0
        }
        
        merged = self.processor.merge_terra_pulse_and_dify_results(
            terra_dict,
            self.sample_dify_response
        )
        
        assert merged['terra_pulse_prediction']['degradation_risk'] == 60
        assert merged['terra_pulse_prediction']['location'] == 'Test Location'


class TestResponseValidation:
    """Test merged response validation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = DataProcessor()
        
        self.valid_merged_response = {
            'terra_pulse_prediction': {
                'location': 'Test Location',
                'degradation_risk': 75,
                'risk_factors': ['test_factor'],
                'confidence': 0.85
            },
            'ai_insights': {
                'enhanced_recommendations': ['test recommendation'],
                'risk_assessment': 'test assessment',
                'timeline': 'test timeline'
            },
            'metadata': {
                'timestamp': '2024-01-01T00:00:00Z',
                'dify_workflow_id': 'test_workflow'
            }
        }
    
    def test_validate_merged_response_valid(self):
        """Test validation of valid merged response."""
        result = self.processor.validate_merged_response(self.valid_merged_response)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_merged_response_missing_top_level_keys(self):
        """Test validation with missing top-level keys."""
        invalid_response = {
            'terra_pulse_prediction': {
                'degradation_risk': 75
            }
            # Missing ai_insights and metadata
        }
        
        result = self.processor.validate_merged_response(invalid_response)
        
        assert result.is_valid is False
        assert len(result.errors) >= 2  # Missing ai_insights and metadata
    
    def test_validate_merged_response_invalid_degradation_risk(self):
        """Test validation with invalid degradation risk."""
        invalid_response = self.valid_merged_response.copy()
        invalid_response['terra_pulse_prediction']['degradation_risk'] = 150  # Out of range
        
        result = self.processor.validate_merged_response(invalid_response)
        
        assert result.is_valid is False
        assert any('degradation_risk' in error for error in result.errors)
    
    def test_validate_merged_response_missing_terra_pulse_fields(self):
        """Test validation with missing Terra Pulse fields."""
        invalid_response = self.valid_merged_response.copy()
        del invalid_response['terra_pulse_prediction']['confidence']
        
        result = self.processor.validate_merged_response(invalid_response)
        
        assert result.is_valid is False
        assert any('confidence' in error for error in result.errors)
    
    def test_validate_merged_response_warnings(self):
        """Test validation warnings for missing optional fields."""
        response_with_warnings = self.valid_merged_response.copy()
        del response_with_warnings['ai_insights']['timeline']
        del response_with_warnings['metadata']['timestamp']
        
        result = self.processor.validate_merged_response(response_with_warnings)
        
        assert result.is_valid is True  # Still valid
        assert len(result.warnings) > 0


class TestMetricsExtraction:
    """Test metrics extraction functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = DataProcessor()
        
        self.sample_merged_response = {
            'terra_pulse_prediction': {
                'degradation_risk': 75,
                'confidence': 0.85,
                'risk_factors': ['factor1', 'factor2']
            },
            'ai_insights': {
                'enhanced_recommendations': ['rec1', 'rec2', 'rec3'],
                'success_probability': 0.78,
                'fallback_used': False
            },
            'metadata': {
                'processing_time': 122.8,
                'ai_enhancement_available': True,
                'timestamp': '2024-01-01T00:00:00Z'
            }
        }
    
    def test_extract_key_metrics_success(self):
        """Test successful metrics extraction."""
        metrics = self.processor.extract_key_metrics(self.sample_merged_response)
        
        assert metrics['degradation_risk'] == 75
        assert metrics['confidence'] == 0.85
        assert metrics['risk_factors_count'] == 2
        assert metrics['recommendations_count'] == 3
        assert metrics['processing_time_ms'] == 122.8
        assert metrics['ai_enhancement_used'] is True
        assert metrics['fallback_used'] is False
        assert metrics['success_probability'] == 0.78
        assert 'timestamp' in metrics
    
    def test_extract_key_metrics_missing_data(self):
        """Test metrics extraction with missing data."""
        incomplete_response = {
            'terra_pulse_prediction': {
                'degradation_risk': 60
                # Missing other fields
            },
            'ai_insights': {},
            'metadata': {}
        }
        
        metrics = self.processor.extract_key_metrics(incomplete_response)
        
        # Should handle missing data gracefully with defaults
        assert metrics['degradation_risk'] == 60
        assert metrics['confidence'] == 0.0  # Default
        assert metrics['risk_factors_count'] == 0  # Empty list
        assert metrics['recommendations_count'] == 0  # Empty list
        assert metrics['ai_enhancement_used'] is False  # Default
    
    def test_extract_key_metrics_exception_handling(self):
        """Test metrics extraction with invalid data."""
        invalid_response = None
        
        metrics = self.processor.extract_key_metrics(invalid_response)
        
        assert 'error' in metrics
        assert 'timestamp' in metrics


# Integration tests
class TestDataProcessorIntegration:
    """Integration tests for complete data processing workflows."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = DataProcessor()
    
    def test_complete_processing_workflow(self):
        """Test complete data processing workflow from request to metrics."""
        # Start with raw request
        raw_request = {
            'ndvi_mean_early': 0.45,
            'ndvi_median_early': 0.43,
            'ndvi_std_early': 0.12,
            'ndvi_mean_late': 0.38,
            'ndvi_median_late': 0.36,
            'ndvi_std_late': 0.15,
            'ndvi_delta_mean': -0.07,
            'location': 'Baringo County, Kenya',
            'user_context': 'smallholder_farmer',
            'user_type': 'farmer'
        }
        
        # Step 1: Validate request
        validation_result = self.processor.validate_prediction_request(raw_request)
        assert validation_result.is_valid is True
        
        # Step 2: Sanitize input
        sanitized_request = self.processor.sanitize_input_data(raw_request)
        assert sanitized_request['location'] == 'Baringo County, Kenya'
        
        # Step 3: Simulate Terra Pulse processing
        terra_result = PredictionOutput(
            location=sanitized_request['location'],
            degradation_risk=75,
            risk_factors=["bare_soil_increase", "low_ndvi"],
            recommended_action_key="mulch_crop_residue",
            confidence=0.85,
            user_context=sanitized_request['user_context'],
            raw_prediction=0.75,
            processing_time_ms=120.5
        )
        
        # Step 4: Convert to Dify input
        dify_input = self.processor.convert_terra_pulse_to_dify_input(
            terra_result, 
            sanitized_request['user_type']
        )
        assert isinstance(dify_input, DifyWorkflowInput)
        
        # Step 5: Simulate Dify response
        dify_response = {
            'status': 'success',
            'workflow_run_id': 'workflow_123',
            'enhanced_recommendations': ['Apply mulch', 'Use cover crops'],
            'risk_assessment': 'High risk area',
            'timeline': 'Immediate action needed',
            'cost_estimate': 'Low cost',
            'success_probability': 0.78,
            'additional_insights': {},
            'processing_time': 2.3
        }
        
        # Step 6: Merge results
        merged_response = self.processor.merge_terra_pulse_and_dify_results(
            terra_result, 
            dify_response
        )
        
        # Step 7: Validate merged response
        validation_result = self.processor.validate_merged_response(merged_response)
        assert validation_result.is_valid is True
        
        # Step 8: Extract metrics
        metrics = self.processor.extract_key_metrics(merged_response)
        assert metrics['degradation_risk'] == 75
        assert metrics['ai_enhancement_used'] is True
        
        # Verify complete workflow
        assert 'terra_pulse_prediction' in merged_response
        assert 'ai_insights' in merged_response
        assert 'metadata' in merged_response
        assert merged_response['metadata']['ai_enhancement_available'] is True


if __name__ == '__main__':
    pytest.main([__file__])