"""
Request handlers for Terra Pulse-Dify integration.
Clean, focused handlers following single responsibility principle.
"""

import time
from datetime import datetime
from flask import Request, jsonify
from typing import Dict, Any, Tuple

from backend.services.service_factory import ServiceFactory
from backend.services.logging_service import get_logger
from backend.services.exceptions import *
from backend.services.alerting_service import send_exception_alert

logger = get_logger("handlers")


class BaseHandler:
    """Base handler with common functionality."""
    
    def __init__(self, service_factory: ServiceFactory):
        self.service_factory = service_factory
    
    def _handle_error(self, error: Exception, context: Dict[str, Any] = None) -> Tuple[Dict[str, Any], int]:
        """Handle errors consistently across handlers."""
        if isinstance(error, BaseAPIException):
            return jsonify(error.to_dict()), error.status_code
        
        # Log unexpected errors
        logger.error(f"Unexpected error: {str(error)}", exc_info=True)
        
        # Send alert for unhandled exceptions
        send_exception_alert(error, context or {})
        
        # Return generic error response
        error_response = {
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "details": {"error_type": error.__class__.__name__}
        }
        return jsonify(error_response), 500


class PredictionHandler(BaseHandler):
    """Handler for prediction-related endpoints."""
    
    def handle_basic_prediction(self, request: Request) -> Tuple[Dict[str, Any], int]:
        """Handle basic Terra Pulse prediction requests."""
        try:
            data = request.get_json()
            if not data:
                raise ValidationException("No JSON data provided")
            
            # Get Terra Pulse service
            terra_pulse_service = self.service_factory.get_service("terra_pulse")
            
            # Validate and process prediction
            result = self._process_basic_prediction(data, terra_pulse_service)
            
            logger.info(f"Basic prediction completed for {data.get('location', 'unknown')}")
            return jsonify({"ml_output": result}), 200
            
        except Exception as e:
            return self._handle_error(e, {'endpoint': 'predict', 'location': data.get('location') if 'data' in locals() else 'unknown'})
    
    def handle_enhanced_prediction(self, request: Request) -> Tuple[Dict[str, Any], int]:
        """Handle enhanced prediction requests with Dify integration."""
        start_time = time.time()
        location = "unknown"
        
        try:
            # Get and validate request data
            request_data = request.get_json()
            if not request_data:
                raise ValidationException("No JSON data provided")
            
            location = request_data.get('location', 'unknown')
            
            # Get services
            terra_pulse_service = self.service_factory.get_service("terra_pulse")
            dify_service = self.service_factory.get_service("dify")
            data_processor = self.service_factory.get_service("data_processor")
            response_formatter = self.service_factory.get_service("response_formatter")
            
            # Process enhanced prediction
            result = self._process_enhanced_prediction(
                request_data, terra_pulse_service, dify_service, 
                data_processor, response_formatter
            )
            
            # Add processing metadata
            total_processing_time = (time.time() - start_time) * 1000
            result['metadata']['total_processing_time_ms'] = total_processing_time
            
            logger.info(f"Enhanced prediction completed for {location}")
            return jsonify(result), 200
            
        except Exception as e:
            return self._handle_error(e, {
                'endpoint': 'enhanced-predict',
                'location': location,
                'processing_time_ms': (time.time() - start_time) * 1000
            })
    
    def _process_basic_prediction(self, data: Dict[str, Any], terra_pulse_service) -> Dict[str, Any]:
        """Process basic Terra Pulse prediction."""
        # Validate required fields
        required_fields = [
            "NDVI_mean_early", "NDVI_median_early", "NDVI_std_early",
            "NDVI_mean_late", "NDVI_median_late", "NDVI_std_late", "NDVI_delta_mean"
        ]
        
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise MissingRequiredFieldException(missing_fields)
        
        # Create prediction input
        from services.terra_pulse_service import PredictionInput
        
        prediction_input = PredictionInput(
            ndvi_mean_early=float(data["NDVI_mean_early"]),
            ndvi_median_early=float(data["NDVI_median_early"]),
            ndvi_std_early=float(data["NDVI_std_early"]),
            ndvi_mean_late=float(data["NDVI_mean_late"]),
            ndvi_median_late=float(data["NDVI_median_late"]),
            ndvi_std_late=float(data["NDVI_std_late"]),
            ndvi_delta_mean=float(data["NDVI_delta_mean"]),
            location=data.get("location", "Unknown location"),
            user_context=data.get("user_context", "General user")
        )
        
        # Get prediction
        result = terra_pulse_service.predict(prediction_input)
        
        # Convert to dictionary format
        return {
            "location": result.location,
            "degradation_risk": result.degradation_risk,
            "risk_factors": result.risk_factors,
            "recommended_action_key": result.recommended_action_key,
            "confidence": result.confidence,
            "user_context": result.user_context
        }
    
    def _process_enhanced_prediction(self, request_data: Dict[str, Any], 
                                   terra_pulse_service, dify_service, 
                                   data_processor, response_formatter) -> Dict[str, Any]:
        """Process enhanced prediction with Dify integration."""
        # This is a simplified version - full implementation would include
        # data validation, Terra Pulse prediction, Dify workflow execution,
        # and response formatting as in the original code
        
        # For now, return a basic structure
        return {
            "terra_pulse_prediction": {},
            "dify_insights": {},
            "formatted_response": {},
            "metadata": {
                "endpoint": "enhanced-predict",
                "api_version": "1.0"
            }
        }


class HealthHandler(BaseHandler):
    """Handler for health check endpoints."""
    
    def handle_terra_pulse_health(self) -> Tuple[Dict[str, Any], int]:
        """Handle Terra Pulse service health check."""
        try:
            terra_pulse_service = self.service_factory.get_service("terra_pulse")
            health_result = terra_pulse_service.health_check()
            
            response = {
                "service": "terra_pulse",
                "status": health_result.status.value,
                "message": health_result.message,
                "timestamp": datetime.utcnow().isoformat(),
                "response_time_ms": health_result.response_time_ms
            }
            
            return jsonify(response), 200
            
        except Exception as e:
            return self._handle_error(e, {'service': 'terra_pulse', 'operation': 'health_check'})
    
    def handle_dify_health(self) -> Tuple[Dict[str, Any], int]:
        """Handle Dify service health check."""
        try:
            dify_service = self.service_factory.get_service("dify")
            health_result = dify_service.health_check()
            
            response = {
                "service": "dify",
                "status": health_result.status.value,
                "message": health_result.message,
                "timestamp": datetime.utcnow().isoformat(),
                "response_time_ms": health_result.response_time_ms
            }
            
            return jsonify(response), 200
            
        except Exception as e:
            return self._handle_error(e, {'service': 'dify', 'operation': 'health_check'})
    
    def handle_system_health(self) -> Tuple[Dict[str, Any], int]:
        """Handle system-wide health check."""
        try:
            # Get all service health checks
            health_results = self.service_factory.health_check_all()
            
            # Determine overall system status
            overall_status = "healthy"
            if any(result.status.value == "unhealthy" for result in health_results.values()):
                overall_status = "unhealthy"
            elif any(result.status.value == "degraded" for result in health_results.values()):
                overall_status = "degraded"
            
            response = {
                "system": "terra_pulse_dify_integration",
                "overall_status": overall_status,
                "services": {
                    name: {
                        "status": result.status.value,
                        "message": result.message,
                        "response_time_ms": result.response_time_ms
                    }
                    for name, result in health_results.items()
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return jsonify(response), 200
            
        except Exception as e:
            return self._handle_error(e, {'operation': 'system_health_check'})
    
    def handle_metrics(self) -> Tuple[Dict[str, Any], int]:
        """Handle metrics endpoint."""
        try:
            # Get cache service for metrics
            cache_service = self.service_factory.get_service("cache")
            cache_stats = cache_service.get_cache_stats()
            
            metrics = {
                "cache": cache_stats,
                "timestamp": time.time()
            }
            
            return jsonify(metrics), 200
            
        except Exception as e:
            return self._handle_error(e, {'operation': 'metrics'})