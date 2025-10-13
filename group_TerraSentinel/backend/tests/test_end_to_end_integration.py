"""
End-to-end integration tests for Terra Pulse-Dify workflow.
Tests complete workflow from request to response, including fallback scenarios.
"""

import pytest
import json
import time
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from flask import Flask
import requests

# Import the app and services
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock the CachedDifyService if import fails
try:
    from app import app, terra_pulse_service, dify_service
except ImportError as e:
    if 'CachedDifyService' in str(e):
        # Create a mock CachedDifyService for testing
        class MockCachedDifyService:
            def __init__(self, config=None):
                from backend.services.dify_service import DifyService
                self.dify_service = DifyService()
            
            def execute_workflow(self, workflow_input):
                return self.dify_service.process_workflow_with_fallback(workflow_input)
        
        # Patch the import
        import services.cached_dify_service
        services.cached_dify_service.CachedDifyService = MockCachedDifyService
        
        # Now import the app
        from app import app, terra_pulse_service, dify_service
    else:
        raise
from backend.services.terra_pulse_service import PredictionOutput, PredictionInput
from backend.services.dify_service import DifyWorkflowInput, DifyWorkflowResponse
from backend.services.data_processor import EnhancedPredictionRequest
from backend.services.response_formatter import ResponseFormatter
from backend.config.settings import get_config


class TestEndToEndIntegration:
    """End-to-end integration tests for complete workflow."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    @pytest.fixture
    def config(self):
        """Get application configuration."""
        return get_config()
    
    @pytest.fixture
    def valid_farmer_request(self):
        """Valid farmer prediction request."""
        return {
            "NDVI_mean_early": 0.45,
            "NDVI_median_early": 0.43,
            "NDVI_std_early": 0.12,
            "NDVI_mean_late": 0.38,
            "NDVI_median_late": 0.36,
            "NDVI_std_late": 0.15,
            "NDVI_delta_mean": -0.07,
            "location": "Baringo County, Kenya",
            "user_context": "smallholder_farmer",
            "user_type": "farmer"
        }
    
    @pytest.fixture
    def valid_official_request(self):
        """Valid official prediction request."""
        return {
            "NDVI_mean_early": 0.52,
            "NDVI_median_early": 0.50,
            "NDVI_std_early": 0.08,
            "NDVI_mean_late": 0.35,
            "NDVI_median_late": 0.33,
            "NDVI_std_late": 0.18,
            "NDVI_delta_mean": -0.17,
            "location": "Turkana County, Kenya",
            "user_context": "government_official",
            "user_type": "official"
        }
    
    @pytest.fixture
    def api_key(self):
        """Valid API key."""
        return "test-integration-key-12345"
    
    @pytest.fixture
    def mock_terra_pulse_high_risk(self):
        """Mock Terra Pulse result for high risk scenario."""
        return PredictionOutput(
            degradation_risk=85,
            risk_factors=["bare_soil_increase", "low_ndvi", "significant_vegetation_decline"],
            recommended_action_key="emergency_soil_protection",
            confidence=0.92,
            location="Baringo County, Kenya",
            user_context="smallholder_farmer",
            raw_prediction=0.85,
            processing_time_ms=120.0
        )
    
    @pytest.fixture
    def mock_terra_pulse_medium_risk(self):
        """Mock Terra Pulse result for medium risk scenario."""
        return PredictionOutput(
            degradation_risk=55,
            risk_factors=["moderate_ndvi_drop"],
            recommended_action_key="increase_soil_cover",
            confidence=0.78,
            location="Turkana County, Kenya",
            user_context="government_official",
            raw_prediction=0.55,
            processing_time_ms=95.0
        )
    
    @pytest.fixture
    def mock_dify_success_farmer(self):
        """Mock successful Dify response for farmer."""
        return {
            'status': 'success',
            'workflow_run_id': 'farmer-workflow-123',
            'enhanced_recommendations': [
                'Apply crop residue mulch immediately to protect exposed soil',
                'Plant drought-resistant sorghum varieties for next season',
                'Create simple water harvesting structures using local materials'
            ],
            'risk_assessment': 'Critical soil erosion risk detected. Immediate action needed to prevent permanent damage.',
            'timeline': 'Emergency measures within 3 days, full implementation within 2 weeks',
            'cost_estimate': 'Low cost using available farm materials (under $50)',
            'success_probability': 0.82,
            'additional_insights': {
                'seasonal_timing': 'Act before next rains to maximize effectiveness',
                'local_resources': 'Use available crop residue and stones for protection'
            },
            'processing_time': 1.8
        }
    
    @pytest.fixture
    def mock_dify_success_official(self):
        """Mock successful Dify response for official."""
        return {
            'status': 'success',
            'workflow_run_id': 'official-workflow-456',
            'enhanced_recommendations': [
                'Deploy emergency soil conservation teams to affected areas',
                'Activate drought response protocols for Turkana County',
                'Coordinate with NGOs for immediate farmer support programs'
            ],
            'risk_assessment': 'Moderate degradation risk across 15% of county area. Coordinated response required.',
            'timeline': 'Policy activation within 24 hours, field deployment within 1 week',
            'cost_estimate': 'Medium budget allocation required ($10,000-50,000)',
            'success_probability': 0.75,
            'additional_insights': {
                'affected_area': '~2,500 hectares requiring intervention',
                'policy_recommendations': 'Activate emergency agricultural support fund'
            },
            'processing_time': 2.1
        }


class TestCompleteWorkflowSuccess(TestEndToEndIntegration):
    """Test complete successful workflows for different user types."""
    
    def test_farmer_complete_workflow_high_risk(self, client, valid_farmer_request, api_key,
                                              mock_terra_pulse_high_risk, mock_dify_success_farmer):
        """Test complete workflow for farmer with high degradation risk."""
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_pulse_high_risk), \
             patch.object(dify_service, 'execute_workflow', return_value=mock_dify_success_farmer):
            
            response = client.post('/enhanced-predict',
                                 data=json.dumps(valid_farmer_request),
                                 content_type='application/json',
                                 headers={'X-API-Key': api_key})
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            # Validate complete response structure
            assert 'terra_pulse_prediction' in data
            assert 'ai_insights' in data
            assert 'formatted_response' in data
            assert 'metadata' in data
            
            # Validate Terra Pulse integration
            terra_data = data['terra_pulse_prediction']
            assert terra_data['degradation_risk'] == 85
            assert terra_data['location'] == "Baringo County, Kenya"
            assert terra_data['confidence'] == 0.92
            assert "bare_soil_increase" in terra_data['risk_factors']
            
            # Validate Dify AI insights
            ai_data = data['ai_insights']
            assert ai_data['status'] == 'success'
            assert len(ai_data['enhanced_recommendations']) == 3
            assert 'crop residue mulch' in ai_data['enhanced_recommendations'][0]
            assert ai_data['success_probability'] == 0.82
            assert 'Emergency measures within 3 days' in ai_data['timeline']
            
            # Validate farmer-specific formatting
            formatted = data['formatted_response']
            assert formatted['user_type'] == 'farmer'
            assert 'title' in formatted
            assert 'summary' in formatted
            assert 'action_items' in formatted
            assert len(formatted['action_items']) >= 3
            
            # Validate metadata
            metadata = data['metadata']
            assert metadata['dify_success'] is True
            assert metadata['endpoint'] == 'enhanced-predict'
            assert metadata['total_processing_time_ms'] > 0
            assert metadata['api_version'] == '1.0'
    
    def test_official_complete_workflow_medium_risk(self, client, valid_official_request, api_key,
                                                  mock_terra_pulse_medium_risk, mock_dify_success_official):
        """Test complete workflow for official with medium degradation risk."""
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_pulse_medium_risk), \
             patch.object(dify_service, 'execute_workflow', return_value=mock_dify_success_official):
            
            response = client.post('/enhanced-predict',
                                 data=json.dumps(valid_official_request),
                                 content_type='application/json',
                                 headers={'X-API-Key': api_key})
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            # Validate Terra Pulse data
            terra_data = data['terra_pulse_prediction']
            assert terra_data['degradation_risk'] == 55
            assert terra_data['location'] == "Turkana County, Kenya"
            
            # Validate AI insights for official context
            ai_data = data['ai_insights']
            assert 'Deploy emergency soil conservation teams' in ai_data['enhanced_recommendations'][0]
            assert 'Policy activation within 24 hours' in ai_data['timeline']
            assert '$10,000-50,000' in ai_data['cost_estimate']
            
            # Validate official-specific formatting
            formatted = data['formatted_response']
            assert formatted['user_type'] == 'official'
            assert 'policy_recommendations' in formatted
            assert 'technical_details' in formatted
            assert 'budget_implications' in formatted
            
            # Check for policy-specific content
            assert any('policy' in item.lower() for item in formatted['action_items'])


class TestFallbackScenarios(TestEndToEndIntegration):
    """Test fallback scenarios when external services fail."""
    
    def test_dify_service_unavailable_fallback(self, client, valid_farmer_request, api_key,
                                             mock_terra_pulse_high_risk):
        """Test fallback when Dify service is unavailable."""
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_pulse_high_risk), \
             patch.object(dify_service, 'execute_workflow', side_effect=requests.exceptions.ConnectionError("Dify API unreachable")):
            
            response = client.post('/enhanced-predict',
                                 data=json.dumps(valid_farmer_request),
                                 content_type='application/json',
                                 headers={'X-API-Key': api_key})
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            # Should still have Terra Pulse data
            assert data['terra_pulse_prediction']['degradation_risk'] == 85
            
            # Should have fallback AI insights
            ai_data = data['ai_insights']
            assert ai_data['fallback_used'] is True
            assert 'AI processing unavailable' in ai_data['risk_assessment']
            assert len(ai_data['enhanced_recommendations']) == 0
            
            # Metadata should indicate Dify failure
            assert data['metadata']['dify_success'] is False
            
            # Should still have formatted response
            assert 'formatted_response' in data
            assert data['formatted_response']['user_type'] == 'farmer'
    
    def test_dify_timeout_fallback(self, client, valid_official_request, api_key,
                                 mock_terra_pulse_medium_risk):
        """Test fallback when Dify service times out."""
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_pulse_medium_risk), \
             patch.object(dify_service, 'execute_workflow', side_effect=requests.exceptions.Timeout("Dify API timeout")):
            
            response = client.post('/enhanced-predict',
                                 data=json.dumps(valid_official_request),
                                 content_type='application/json',
                                 headers={'X-API-Key': api_key})
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            # Verify fallback behavior
            assert data['ai_insights']['fallback_used'] is True
            assert data['metadata']['dify_success'] is False
            
            # Should still provide basic Terra Pulse predictions
            assert data['terra_pulse_prediction']['degradation_risk'] == 55
            assert data['formatted_response']['user_type'] == 'official'
    
    def test_terra_pulse_service_failure(self, client, valid_farmer_request, api_key):
        """Test behavior when Terra Pulse service fails."""
        with patch.object(terra_pulse_service, 'predict', side_effect=Exception("Model loading failed")):
            
            response = client.post('/enhanced-predict',
                                 data=json.dumps(valid_farmer_request),
                                 content_type='application/json',
                                 headers={'X-API-Key': api_key})
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data
            assert 'Enhanced prediction failed' in data['error']
    
    def test_partial_dify_response_handling(self, client, valid_farmer_request, api_key,
                                          mock_terra_pulse_high_risk):
        """Test handling of partial/malformed Dify responses."""
        partial_dify_response = {
            'status': 'success',
            'workflow_run_id': 'partial-123',
            'enhanced_recommendations': ['Only one recommendation'],
            # Missing other expected fields
        }
        
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_pulse_high_risk), \
             patch.object(dify_service, 'execute_workflow', return_value=partial_dify_response):
            
            response = client.post('/enhanced-predict',
                                 data=json.dumps(valid_farmer_request),
                                 content_type='application/json',
                                 headers={'X-API-Key': api_key})
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            # Should handle partial response gracefully
            ai_data = data['ai_insights']
            assert len(ai_data['enhanced_recommendations']) == 1
            assert ai_data.get('risk_assessment', '') != ''  # Should have default/fallback values
            assert ai_data.get('timeline', '') != ''


class TestUserPersonaFormatting(TestEndToEndIntegration):
    """Test response formatting for different user personas."""
    
    def test_farmer_response_formatting(self, client, valid_farmer_request, api_key,
                                      mock_terra_pulse_high_risk, mock_dify_success_farmer):
        """Test farmer-specific response formatting."""
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_pulse_high_risk), \
             patch.object(dify_service, 'execute_workflow', return_value=mock_dify_success_farmer):
            
            response = client.post('/enhanced-predict',
                                 data=json.dumps(valid_farmer_request),
                                 content_type='application/json',
                                 headers={'X-API-Key': api_key})
            
            data = json.loads(response.data)
            formatted = data['formatted_response']
            
            # Farmer responses should be practical and actionable
            assert formatted['user_type'] == 'farmer'
            assert 'title' in formatted
            assert 'summary' in formatted
            assert 'action_items' in formatted
            
            # Check for farmer-friendly language
            summary = formatted['summary'].lower()
            assert any(word in summary for word in ['soil', 'crop', 'farm', 'protect'])
            
            # Action items should be practical
            action_items = [item.lower() for item in formatted['action_items']]
            assert any('mulch' in item or 'cover' in item for item in action_items)
    
    def test_official_response_formatting(self, client, valid_official_request, api_key,
                                        mock_terra_pulse_medium_risk, mock_dify_success_official):
        """Test official-specific response formatting."""
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_pulse_medium_risk), \
             patch.object(dify_service, 'execute_workflow', return_value=mock_dify_success_official):
            
            response = client.post('/enhanced-predict',
                                 data=json.dumps(valid_official_request),
                                 content_type='application/json',
                                 headers={'X-API-Key': api_key})
            
            data = json.loads(response.data)
            formatted = data['formatted_response']
            
            # Official responses should include policy and technical details
            assert formatted['user_type'] == 'official'
            assert 'policy_recommendations' in formatted
            assert 'technical_details' in formatted
            assert 'budget_implications' in formatted
            
            # Check for policy-oriented language
            policy_recs = ' '.join(formatted['policy_recommendations']).lower()
            assert any(word in policy_recs for word in ['policy', 'program', 'coordinate', 'deploy'])
            
            # Technical details should be present
            tech_details = formatted['technical_details'].lower()
            assert any(word in tech_details for word in ['ndvi', 'degradation', 'risk', 'confidence'])


class TestDataValidationAndSanitization(TestEndToEndIntegration):
    """Test data validation and sanitization throughout the workflow."""
    
    def test_input_sanitization_success(self, client, api_key, mock_terra_pulse_high_risk, mock_dify_success_farmer):
        """Test successful input sanitization."""
        # Request with extra whitespace and potential XSS
        dirty_request = {
            "NDVI_mean_early": 0.45,
            "NDVI_median_early": 0.43,
            "NDVI_std_early": 0.12,
            "NDVI_mean_late": 0.38,
            "NDVI_median_late": 0.36,
            "NDVI_std_late": 0.15,
            "NDVI_delta_mean": -0.07,
            "location": "  Baringo County, Kenya  ",  # Extra whitespace
            "user_context": "smallholder_farmer<script>alert('xss')</script>",  # XSS attempt
            "user_type": "farmer"
        }
        
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_pulse_high_risk), \
             patch.object(dify_service, 'execute_workflow', return_value=mock_dify_success_farmer):
            
            response = client.post('/enhanced-predict',
                                 data=json.dumps(dirty_request),
                                 content_type='application/json',
                                 headers={'X-API-Key': api_key})
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            # Verify sanitization occurred
            terra_data = data['terra_pulse_prediction']
            assert terra_data['location'] == "Baringo County, Kenya"  # Whitespace trimmed
            assert '<script>' not in terra_data['user_context']  # XSS removed
    
    def test_invalid_ndvi_ranges(self, client, api_key):
        """Test validation of NDVI value ranges."""
        invalid_request = {
            "NDVI_mean_early": 2.5,  # Invalid: > 1.0
            "NDVI_median_early": 0.43,
            "NDVI_std_early": 0.12,
            "NDVI_mean_late": -1.5,  # Invalid: < -1.0
            "NDVI_median_late": 0.36,
            "NDVI_std_late": 0.15,
            "NDVI_delta_mean": -0.07,
            "location": "Test Location",
            "user_context": "test_user",
            "user_type": "farmer"
        }
        
        response = client.post('/enhanced-predict',
                             data=json.dumps(invalid_request),
                             content_type='application/json',
                             headers={'X-API-Key': api_key})
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Validation failed' in data['error']
    
    def test_missing_required_fields(self, client, api_key):
        """Test validation of required fields."""
        incomplete_request = {
            "NDVI_mean_early": 0.45,
            "location": "Test Location",
            "user_type": "farmer"
            # Missing other required NDVI fields
        }
        
        response = client.post('/enhanced-predict',
                             data=json.dumps(incomplete_request),
                             content_type='application/json',
                             headers={'X-API-Key': api_key})
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data


class TestPerformanceAndTiming(TestEndToEndIntegration):
    """Test performance characteristics and timing."""
    
    def test_response_timing_metadata(self, client, valid_farmer_request, api_key,
                                    mock_terra_pulse_high_risk, mock_dify_success_farmer):
        """Test that response includes accurate timing metadata."""
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_pulse_high_risk), \
             patch.object(dify_service, 'execute_workflow', return_value=mock_dify_success_farmer):
            
            start_time = time.time()
            response = client.post('/enhanced-predict',
                                 data=json.dumps(valid_farmer_request),
                                 content_type='application/json',
                                 headers={'X-API-Key': api_key})
            end_time = time.time()
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            # Verify timing metadata
            metadata = data['metadata']
            assert 'total_processing_time_ms' in metadata
            assert metadata['total_processing_time_ms'] > 0
            
            # Should be reasonable (less than actual elapsed time in ms)
            actual_elapsed_ms = (end_time - start_time) * 1000
            assert metadata['total_processing_time_ms'] <= actual_elapsed_ms * 1.1  # Allow 10% margin
    
    def test_concurrent_request_handling(self, client, valid_farmer_request, api_key,
                                       mock_terra_pulse_high_risk, mock_dify_success_farmer):
        """Test handling of concurrent requests."""
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_pulse_high_risk), \
             patch.object(dify_service, 'execute_workflow', return_value=mock_dify_success_farmer):
            
            # Simulate concurrent requests
            import threading
            import queue
            
            results = queue.Queue()
            
            def make_request():
                response = client.post('/enhanced-predict',
                                     data=json.dumps(valid_farmer_request),
                                     content_type='application/json',
                                     headers={'X-API-Key': api_key})
                results.put(response.status_code)
            
            # Start multiple threads
            threads = []
            for _ in range(5):
                thread = threading.Thread(target=make_request)
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # Check all requests succeeded
            status_codes = []
            while not results.empty():
                status_codes.append(results.get())
            
            assert len(status_codes) == 5
            assert all(code == 200 for code in status_codes)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])