"""
Data processing and transformation utilities for Terra Pulse-Dify integration.
Handles data transformation, response merging, and validation.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime
from pydantic import BaseModel, Field, validator

from backend.services.terra_pulse_service import PredictionOutput
from backend.services.dify_service import DifyWorkflowInput, DifyWorkflowResponse
from backend.services.security_validator import SecurityValidator, SecureEnhancedPredictionRequest


logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of data validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]


class EnhancedPredictionRequest(BaseModel):
    """Enhanced prediction request model with validation."""
    ndvi_mean_early: float = Field(..., ge=-2.0, le=2.0, description="Early season NDVI mean")
    ndvi_median_early: float = Field(..., ge=-2.0, le=2.0, description="Early season NDVI median")
    ndvi_std_early: float = Field(..., ge=0.0, le=2.0, description="Early season NDVI standard deviation")
    ndvi_mean_late: float = Field(..., ge=-2.0, le=2.0, description="Late season NDVI mean")
    ndvi_median_late: float = Field(..., ge=-2.0, le=2.0, description="Late season NDVI median")
    ndvi_std_late: float = Field(..., ge=0.0, le=2.0, description="Late season NDVI standard deviation")
    ndvi_delta_mean: float = Field(..., ge=-4.0, le=4.0, description="NDVI mean change")
    location: str = Field(..., min_length=1, max_length=200, description="Location information")
    user_context: str = Field(default="general", description="User context")
    user_type: str = Field(default="farmer", description="User type")
    
    @validator('user_type')
    def validate_user_type(cls, v):
        if v not in ['farmer', 'official']:
            raise ValueError('user_type must be either "farmer" or "official"')
        return v
    
    @validator('location')
    def validate_location(cls, v):
        # Basic sanitization - remove potentially harmful characters
        sanitized = ''.join(char for char in v if char.isalnum() or char in ' ,-.')
        return sanitized.strip()


class EnhancedPredictionResponse(BaseModel):
    """Complete enhanced prediction response model."""
    terra_pulse_prediction: Dict[str, Any]
    ai_insights: Dict[str, Any]
    formatted_response: Dict[str, str]
    metadata: Dict[str, Any]


class DataProcessor:
    """
    Data processing and transformation utilities for Terra Pulse-Dify integration.
    Handles conversion between different data formats and response merging.
    """
    
    def __init__(self):
        """Initialize data processor."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.security_validator = SecurityValidator()
    
    def validate_prediction_request(self, request_data: Dict[str, Any]) -> ValidationResult:
        """
        Validate incoming prediction request data with security checks.
        
        Args:
            request_data: Raw request data to validate
            
        Returns:
            ValidationResult: Validation result with errors and warnings
        """
        errors = []
        warnings = []
        
        try:
            # Use security validator for comprehensive validation
            validated_request = self.security_validator.validate_and_sanitize_request(request_data)
            
            # Additional business logic validation
            if abs(validated_request.ndvi_delta_mean) > 1.0:
                warnings.append(f"Large NDVI change detected: {validated_request.ndvi_delta_mean}")
            
            if validated_request.ndvi_std_early > 0.5 or validated_request.ndvi_std_late > 0.5:
                warnings.append("High NDVI variability detected")
            
            # Check for suspicious patterns
            if (validated_request.ndvi_mean_early < -0.5 and 
                validated_request.ndvi_mean_late < -0.5):
                warnings.append("Consistently low NDVI values - verify data quality")
            
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings
            )
            
        except Exception as e:
            errors.append(f"Validation failed: {str(e)}")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings
            )
    
    def sanitize_input_data(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize input data using security validator.
        
        Args:
            request_data: Raw request data
            
        Returns:
            Dict[str, Any]: Sanitized request data
        """
        try:
            # Use security validator for comprehensive sanitization
            validated_request = self.security_validator.validate_and_sanitize_request(request_data)
            
            # Convert back to dictionary format
            return {
                'ndvi_mean_early': validated_request.ndvi_mean_early,
                'ndvi_median_early': validated_request.ndvi_median_early,
                'ndvi_std_early': validated_request.ndvi_std_early,
                'ndvi_mean_late': validated_request.ndvi_mean_late,
                'ndvi_median_late': validated_request.ndvi_median_late,
                'ndvi_std_late': validated_request.ndvi_std_late,
                'ndvi_delta_mean': validated_request.ndvi_delta_mean,
                'location': validated_request.location,
                'user_context': validated_request.user_context,
                'user_type': validated_request.user_type
            }
            
        except Exception as e:
            self.logger.error(f"Failed to sanitize input data: {str(e)}")
            raise
    
    def convert_terra_pulse_to_dify_input(self, terra_pulse_result: PredictionOutput, 
                                        user_type: str = "farmer") -> DifyWorkflowInput:
        """
        Convert Terra Pulse prediction result to Dify workflow input format.
        
        Args:
            terra_pulse_result: Terra Pulse prediction output
            user_type: Type of user (farmer or official)
            
        Returns:
            DifyWorkflowInput: Formatted input for Dify workflow
        """
        try:
            # Convert PredictionOutput to dictionary if needed
            if isinstance(terra_pulse_result, PredictionOutput):
                result_dict = asdict(terra_pulse_result)
            else:
                result_dict = terra_pulse_result
            
            # Create additional context with relevant metadata
            additional_context = {
                'raw_prediction': result_dict.get('raw_prediction', 0.0),
                'processing_time_ms': result_dict.get('processing_time_ms', 0.0),
                'timestamp': datetime.utcnow().isoformat(),
                'source': 'terra_pulse_onnx_model'
            }
            
            # Create Dify workflow input
            dify_input = DifyWorkflowInput(
                degradation_risk=result_dict['degradation_risk'],
                risk_factors=result_dict['risk_factors'],
                location=result_dict['location'],
                user_context=result_dict['user_context'],
                confidence=result_dict['confidence'],
                recommended_action_key=result_dict['recommended_action_key'],
                user_type=user_type,
                additional_context=additional_context
            )
            
            self.logger.info(f"Converted Terra Pulse result to Dify input for {user_type}")
            return dify_input
            
        except Exception as e:
            self.logger.error(f"Failed to convert Terra Pulse result to Dify input: {str(e)}")
            raise ValueError(f"Data conversion failed: {str(e)}")
    
    def merge_terra_pulse_and_dify_results(self, terra_pulse_result: PredictionOutput,
                                         dify_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge Terra Pulse predictions with Dify AI insights into a unified response.
        
        Args:
            terra_pulse_result: Original Terra Pulse prediction
            dify_response: Processed Dify workflow response
            
        Returns:
            Dict[str, Any]: Merged response with both predictions and AI insights
        """
        try:
            # Convert Terra Pulse result to dictionary
            if isinstance(terra_pulse_result, PredictionOutput):
                terra_dict = asdict(terra_pulse_result)
            else:
                terra_dict = terra_pulse_result
            
            # Extract AI insights from Dify response
            ai_insights = {
                'enhanced_recommendations': dify_response.get('enhanced_recommendations', []),
                'risk_assessment': dify_response.get('risk_assessment', ''),
                'timeline': dify_response.get('timeline', ''),
                'cost_estimate': dify_response.get('cost_estimate', ''),
                'success_probability': dify_response.get('success_probability', 0.0),
                'additional_insights': dify_response.get('additional_insights', {})
            }
            
            # Create metadata
            metadata = {
                'processing_time': terra_dict.get('processing_time_ms', 0.0) + dify_response.get('processing_time', 0.0),
                'dify_workflow_id': dify_response.get('workflow_run_id', 'unknown'),
                'dify_status': dify_response.get('status', 'unknown'),
                'cache_hit': False,  # Will be set by caching layer
                'timestamp': datetime.utcnow().isoformat(),
                'terra_pulse_confidence': terra_dict.get('confidence', 0.0),
                'ai_enhancement_available': dify_response.get('status') == 'success'
            }
            
            # If Dify failed, add fallback information
            if dify_response.get('status') != 'success':
                metadata['fallback_reason'] = dify_response.get('error', 'Dify processing failed')
                ai_insights['fallback_used'] = True
            
            merged_result = {
                'terra_pulse_prediction': terra_dict,
                'ai_insights': ai_insights,
                'metadata': metadata
            }
            
            self.logger.info(f"Successfully merged Terra Pulse and Dify results")
            return merged_result
            
        except Exception as e:
            self.logger.error(f"Failed to merge results: {str(e)}")
            # Return Terra Pulse only result as fallback
            return {
                'terra_pulse_prediction': asdict(terra_pulse_result) if isinstance(terra_pulse_result, PredictionOutput) else terra_pulse_result,
                'ai_insights': {
                    'enhanced_recommendations': [],
                    'risk_assessment': 'AI processing unavailable',
                    'timeline': 'Manual assessment required',
                    'cost_estimate': 'Variable',
                    'success_probability': 0.0,
                    'additional_insights': {},
                    'fallback_used': True
                },
                'metadata': {
                    'processing_time': terra_pulse_result.processing_time_ms if isinstance(terra_pulse_result, PredictionOutput) else 0.0,
                    'dify_workflow_id': 'merge_failed',
                    'dify_status': 'failed',
                    'cache_hit': False,
                    'timestamp': datetime.utcnow().isoformat(),
                    'error': f"Merge failed: {str(e)}"
                }
            }
    
    def validate_merged_response(self, merged_response: Dict[str, Any]) -> ValidationResult:
        """
        Validate the structure and content of a merged response.
        
        Args:
            merged_response: Merged response to validate
            
        Returns:
            ValidationResult: Validation result
        """
        errors = []
        warnings = []
        
        # Check required top-level keys
        required_keys = ['terra_pulse_prediction', 'ai_insights', 'metadata']
        for key in required_keys:
            if key not in merged_response:
                errors.append(f"Missing required key: {key}")
        
        # Validate Terra Pulse prediction structure
        if 'terra_pulse_prediction' in merged_response:
            terra_pred = merged_response['terra_pulse_prediction']
            required_terra_keys = ['degradation_risk', 'risk_factors', 'location', 'confidence']
            for key in required_terra_keys:
                if key not in terra_pred:
                    errors.append(f"Missing Terra Pulse key: {key}")
            
            # Validate degradation risk range
            if 'degradation_risk' in terra_pred:
                risk = terra_pred['degradation_risk']
                if not isinstance(risk, (int, float)) or not 0 <= risk <= 100:
                    errors.append(f"Invalid degradation_risk: {risk}")
        
        # Validate AI insights structure
        if 'ai_insights' in merged_response:
            ai_insights = merged_response['ai_insights']
            expected_keys = ['enhanced_recommendations', 'risk_assessment', 'timeline']
            for key in expected_keys:
                if key not in ai_insights:
                    warnings.append(f"Missing AI insight key: {key}")
        
        # Validate metadata
        if 'metadata' in merged_response:
            metadata = merged_response['metadata']
            if 'timestamp' not in metadata:
                warnings.append("Missing timestamp in metadata")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def extract_key_metrics(self, merged_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract key metrics from merged response for monitoring and analytics.
        
        Args:
            merged_response: Merged response data
            
        Returns:
            Dict[str, Any]: Key metrics for monitoring
        """
        try:
            terra_pred = merged_response.get('terra_pulse_prediction', {})
            ai_insights = merged_response.get('ai_insights', {})
            metadata = merged_response.get('metadata', {})
            
            metrics = {
                'degradation_risk': terra_pred.get('degradation_risk', 0),
                'confidence': terra_pred.get('confidence', 0.0),
                'risk_factors_count': len(terra_pred.get('risk_factors', [])),
                'recommendations_count': len(ai_insights.get('enhanced_recommendations', [])),
                'processing_time_ms': metadata.get('processing_time', 0.0),
                'ai_enhancement_used': metadata.get('ai_enhancement_available', False),
                'fallback_used': ai_insights.get('fallback_used', False),
                'success_probability': ai_insights.get('success_probability', 0.0),
                'timestamp': metadata.get('timestamp', datetime.utcnow().isoformat())
            }
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Failed to extract metrics: {str(e)}")
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }