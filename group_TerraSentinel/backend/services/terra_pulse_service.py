"""
Terra Pulse service abstraction for land degradation prediction.
Refactors existing ONNX model code into a dedicated service class with proper error handling and logging.
"""

import os
import sys
import logging
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import numpy as np
import onnxruntime as ort

from .base_service import BaseService, ServiceHealthCheck, ServiceStatus, ServiceError, retry_with_backoff, RetryConfig
from backend.config.settings import AppConfig


@dataclass
class PredictionInput:
    """Input data for Terra Pulse prediction."""
    ndvi_mean_early: float
    ndvi_median_early: float
    ndvi_std_early: float
    ndvi_mean_late: float
    ndvi_median_late: float
    ndvi_std_late: float
    ndvi_delta_mean: float
    location: str = "Unknown location"
    user_context: str = "General user"


@dataclass
class PredictionOutput:
    """Output data from Terra Pulse prediction."""
    location: str
    degradation_risk: int
    risk_factors: List[str]
    recommended_action_key: str
    confidence: float
    user_context: str
    raw_prediction: float
    processing_time_ms: float


class TerraPulseModelError(ServiceError):
    """Exception raised for Terra Pulse model-specific errors."""
    pass


class TerraPulseService(BaseService[PredictionOutput]):
    """
    Terra Pulse service for land degradation prediction using ONNX model.
    Provides abstraction over ONNX runtime with proper error handling and health checks.
    """
    
    def __init__(self, config: AppConfig, retry_config: RetryConfig = None):
        """
        Initialize Terra Pulse service.
        
        Args:
            config: Application configuration
            retry_config: Retry configuration for model operations
        """
        # Set attributes before calling super() since _validate_configuration needs them
        self.config = config
        self.model_path = config.terra_pulse_model_path
        self._session: Optional[ort.InferenceSession] = None
        self._model_loaded = False
        
        super().__init__("terra_pulse", retry_config)
        
        # Initialize model on startup
        self._load_model()
    
    def _validate_configuration(self) -> bool:
        """
        Validate Terra Pulse service configuration.
        
        Returns:
            bool: True if configuration is valid
            
        Raises:
            ServiceValidationError: If configuration is invalid
        """
        if not self.model_path:
            raise TerraPulseModelError(
                "Terra Pulse model path is required",
                self.service_name
            )
        
        if not os.path.exists(self.model_path):
            raise TerraPulseModelError(
                f"Terra Pulse model file not found at: {self.model_path}",
                self.service_name
            )
        
        return True
    
    def _load_model(self) -> None:
        """
        Load ONNX model with error handling.
        
        Raises:
            TerraPulseModelError: If model loading fails
        """
        try:
            self.logger.info(f"Loading Terra Pulse model from: {self.model_path}")
            
            # Validate model file exists
            if not os.path.exists(self.model_path):
                raise TerraPulseModelError(
                    f"Model file not found at {self.model_path}",
                    self.service_name
                )
            
            # Load ONNX model
            self._session = ort.InferenceSession(self.model_path)
            self._model_loaded = True
            
            # Log model information
            input_info = self._session.get_inputs()[0]
            output_info = self._session.get_outputs()[0]
            
            self.logger.info(
                f"Model loaded successfully. Input: {input_info.name} {input_info.shape}, "
                f"Output: {output_info.name} {output_info.shape}"
            )
            
        except Exception as e:
            self._model_loaded = False
            error_msg = f"Failed to load Terra Pulse model: {str(e)}"
            self.logger.error(error_msg)
            raise TerraPulseModelError(error_msg, self.service_name, e)
    
    def _validate_input(self, input_data: PredictionInput) -> None:
        """
        Validate prediction input data.
        
        Args:
            input_data: Input data to validate
            
        Raises:
            TerraPulseModelError: If input validation fails
        """
        # Validate NDVI values are in reasonable range
        ndvi_fields = [
            input_data.ndvi_mean_early,
            input_data.ndvi_median_early,
            input_data.ndvi_std_early,
            input_data.ndvi_mean_late,
            input_data.ndvi_median_late,
            input_data.ndvi_std_late,
            input_data.ndvi_delta_mean
        ]
        
        for i, value in enumerate(ndvi_fields):
            if not isinstance(value, (int, float)):
                raise TerraPulseModelError(
                    f"NDVI value at index {i} must be numeric, got {type(value)}",
                    self.service_name
                )
            
            # NDVI values typically range from -1 to 1, but we'll be more lenient
            if not -2.0 <= value <= 2.0:
                self.logger.warning(
                    f"NDVI value at index {i} ({value}) is outside typical range [-1, 1]"
                )
        
        # Validate standard deviation values are non-negative
        if input_data.ndvi_std_early < 0 or input_data.ndvi_std_late < 0:
            raise TerraPulseModelError(
                "NDVI standard deviation values must be non-negative",
                self.service_name
            )
    
    def _prepare_model_input(self, input_data: PredictionInput) -> np.ndarray:
        """
        Prepare input data for ONNX model.
        
        Args:
            input_data: Validated input data
            
        Returns:
            np.ndarray: Model input array
        """
        features = np.array([[
            input_data.ndvi_mean_early,
            input_data.ndvi_median_early,
            input_data.ndvi_std_early,
            input_data.ndvi_mean_late,
            input_data.ndvi_median_late,
            input_data.ndvi_std_late,
            input_data.ndvi_delta_mean
        ]], dtype=np.float32)
        
        return features
    
    def _interpret_prediction(self, raw_prediction: float, input_data: PredictionInput) -> PredictionOutput:
        """
        Interpret raw model prediction and generate structured output.
        
        Args:
            raw_prediction: Raw prediction value from model
            input_data: Original input data
            
        Returns:
            PredictionOutput: Structured prediction result
        """
        # Convert model output to percentage and confidence
        degradation_risk = int(min(100, max(0, raw_prediction * 100)))
        confidence = round(min(1.0, abs(raw_prediction)), 2)
        
        # Determine risk factors and recommended actions based on degradation risk
        if degradation_risk > 70:
            risk_factors = ["bare_soil_increase", "low_ndvi"]
            recommended_action_key = "mulch_crop_residue"
        elif degradation_risk > 40:
            risk_factors = ["moderate_ndvi_drop"]
            recommended_action_key = "increase_soil_cover"
        else:
            risk_factors = ["healthy_ndvi"]
            recommended_action_key = "maintain_current_practices"
        
        # Add additional risk factors based on NDVI analysis
        if input_data.ndvi_delta_mean < -0.1:
            risk_factors.append("significant_vegetation_decline")
        
        if input_data.ndvi_std_early > 0.2 or input_data.ndvi_std_late > 0.2:
            risk_factors.append("high_vegetation_variability")
        
        return PredictionOutput(
            location=input_data.location,
            degradation_risk=degradation_risk,
            risk_factors=risk_factors,
            recommended_action_key=recommended_action_key,
            confidence=confidence,
            user_context=input_data.user_context,
            raw_prediction=raw_prediction,
            processing_time_ms=0  # Will be set by caller
        )
    
    @retry_with_backoff(exceptions=(TerraPulseModelError,))
    def predict(self, input_data: PredictionInput) -> PredictionOutput:
        """
        Perform land degradation prediction.
        
        Args:
            input_data: Prediction input data
            
        Returns:
            PredictionOutput: Prediction result
            
        Raises:
            TerraPulseModelError: If prediction fails
        """
        start_time = time.time()
        
        try:
            # Validate model is loaded
            if not self._model_loaded or self._session is None:
                raise TerraPulseModelError(
                    "Terra Pulse model is not loaded",
                    self.service_name
                )
            
            # Validate input data
            self._validate_input(input_data)
            
            # Prepare model input
            features = self._prepare_model_input(input_data)
            
            # Run prediction
            inputs = {self._session.get_inputs()[0].name: features}
            outputs = self._session.run(None, inputs)
            raw_prediction = float(outputs[0][0])
            
            # Interpret prediction
            result = self._interpret_prediction(raw_prediction, input_data)
            
            # Set processing time
            processing_time = (time.time() - start_time) * 1000
            result.processing_time_ms = processing_time
            
            # Log successful prediction
            self.log_operation(
                operation="predict",
                duration_ms=processing_time,
                success=True,
                degradation_risk=result.degradation_risk,
                confidence=result.confidence,
                location=result.location
            )
            
            return result
            
        except TerraPulseModelError:
            # Re-raise Terra Pulse specific errors
            raise
        except Exception as e:
            # Handle unexpected errors
            processing_time = (time.time() - start_time) * 1000
            error_msg = f"Prediction failed: {str(e)}"
            
            self.log_operation(
                operation="predict",
                duration_ms=processing_time,
                success=False,
                error=str(e)
            )
            
            raise TerraPulseModelError(error_msg, self.service_name, e)
    
    def _perform_health_check(self) -> ServiceHealthCheck:
        """
        Perform Terra Pulse service health check.
        Clean, focused health check following single responsibility.
        
        Returns:
            ServiceHealthCheck: Health check result
        """
        if not self._is_model_ready():
            return ServiceHealthCheck(
                status=ServiceStatus.UNHEALTHY,
                message="Terra Pulse model is not loaded"
            )
        
        return self._test_model_prediction()
    
    def _is_model_ready(self) -> bool:
        """Check if model is ready for predictions."""
        return self._model_loaded and self._session is not None
    
    def _test_model_prediction(self) -> ServiceHealthCheck:
        """Test model with dummy prediction."""
        try:
            test_input = self._create_test_input()
            start_time = time.time()
            result = self.predict(test_input)
            response_time = (time.time() - start_time) * 1000
            
            return self._validate_test_result(result, response_time)
            
        except Exception as e:
            return ServiceHealthCheck(
                status=ServiceStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                error=str(e)
            )
    
    def _create_test_input(self) -> PredictionInput:
        """Create test input for health check."""
        return PredictionInput(
            ndvi_mean_early=0.5,
            ndvi_median_early=0.48,
            ndvi_std_early=0.1,
            ndvi_mean_late=0.45,
            ndvi_median_late=0.43,
            ndvi_std_late=0.12,
            ndvi_delta_mean=-0.05,
            location="Health Check",
            user_context="system"
        )
    
    def _validate_test_result(self, result: PredictionOutput, response_time: float) -> ServiceHealthCheck:
        """Validate test prediction result."""
        if result.degradation_risk < 0 or result.degradation_risk > 100:
            return ServiceHealthCheck(
                status=ServiceStatus.DEGRADED,
                message="Model prediction out of expected range",
                response_time_ms=response_time
            )
        
        return ServiceHealthCheck(
            status=ServiceStatus.HEALTHY,
            message="Terra Pulse model is functioning correctly",
            response_time_ms=response_time
        )
    
    def reload_model(self) -> None:
        """
        Reload the ONNX model.
        
        Raises:
            TerraPulseModelError: If model reloading fails
        """
        self.logger.info("Reloading Terra Pulse model...")
        self._model_loaded = False
        self._session = None
        self._load_model()
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the loaded model.
        
        Returns:
            Dict[str, Any]: Model information
        """
        if not self._model_loaded or self._session is None:
            return {"status": "not_loaded"}
        
        try:
            input_info = self._session.get_inputs()[0]
            output_info = self._session.get_outputs()[0]
            
            return {
                "status": "loaded",
                "model_path": self.model_path,
                "input_name": input_info.name,
                "input_shape": input_info.shape,
                "input_type": str(input_info.type),
                "output_name": output_info.name,
                "output_shape": output_info.shape,
                "output_type": str(output_info.type)
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def shutdown(self) -> None:
        """
        Shutdown the Terra Pulse service and clean up resources.
        """
        self.logger.info("Shutting down Terra Pulse service...")
        self._model_loaded = False
        self._session = None