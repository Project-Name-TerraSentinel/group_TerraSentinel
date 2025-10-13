"""
Unit tests for Terra Pulse service.
Tests model loading, prediction logic, error scenarios, and edge cases.
"""

import pytest
import numpy as np
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from typing import Any

from backend.services.terra_pulse_service import (
    TerraPulseService,
    PredictionInput,
    PredictionOutput,
    TerraPulseModelError
)
from backend.services.base_service import ServiceStatus, ServiceHealthCheck
from backend.config.settings import AppConfig


class TestPredictionInput:
    """Test cases for PredictionInput data class."""
    
    def test_prediction_input_creation(self):
        """Test creating PredictionInput with valid data."""
        input_data = PredictionInput(
            ndvi_mean_early=0.5,
            ndvi_median_early=0.48,
            ndvi_std_early=0.1,
            ndvi_mean_late=0.45,
            ndvi_median_late=0.43,
            ndvi_std_late=0.12,
            ndvi_delta_mean=-0.05
        )
        
        assert input_data.ndvi_mean_early == 0.5
        assert input_data.location == "Unknown location"
        assert input_data.user_context == "General user"
    
    def test_prediction_input_with_custom_metadata(self):
        """Test creating PredictionInput with custom location and context."""
        input_data = PredictionInput(
            ndvi_mean_early=0.5,
            ndvi_median_early=0.48,
            ndvi_std_early=0.1,
            ndvi_mean_late=0.45,
            ndvi_median_late=0.43,
            ndvi_std_late=0.12,
            ndvi_delta_mean=-0.05,
            location="Test Location",
            user_context="farmer"
        )
        
        assert input_data.location == "Test Location"
        assert input_data.user_context == "farmer"


class TestTerraPulseService:
    """Test cases for TerraPulseService."""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration for testing."""
        config = Mock(spec=AppConfig)
        config.terra_pulse_model_path = "test_model.onnx"
        return config
    
    @pytest.fixture
    def sample_input(self):
        """Create sample prediction input for testing."""
        return PredictionInput(
            ndvi_mean_early=0.5,
            ndvi_median_early=0.48,
            ndvi_std_early=0.1,
            ndvi_mean_late=0.45,
            ndvi_median_late=0.43,
            ndvi_std_late=0.12,
            ndvi_delta_mean=-0.05,
            location="Test Location",
            user_context="farmer"
        )
    
    @patch('services.terra_pulse_service.ort.InferenceSession')
    @patch('os.path.exists')
    def test_service_initialization_success(self, mock_exists, mock_session, mock_config):
        """Test successful service initialization."""
        mock_exists.return_value = True
        mock_session_instance = Mock()
        mock_session.return_value = mock_session_instance
        
        # Mock input/output info
        mock_input = Mock()
        mock_input.name = "input"
        mock_input.shape = [1, 7]
        mock_output = Mock()
        mock_output.name = "output"
        mock_output.shape = [1, 1]
        
        mock_session_instance.get_inputs.return_value = [mock_input]
        mock_session_instance.get_outputs.return_value = [mock_output]
        
        service = TerraPulseService(mock_config)
        
        assert service._model_loaded is True
        assert service._session is not None
        mock_session.assert_called_once_with("test_model.onnx")
    
    @patch('os.path.exists')
    def test_service_initialization_model_not_found(self, mock_exists, mock_config):
        """Test service initialization when model file is not found."""
        mock_exists.return_value = False
        
        with pytest.raises(TerraPulseModelError) as exc_info:
            TerraPulseService(mock_config)
        
        assert "Model file not found" in str(exc_info.value)
    
    @patch('services.terra_pulse_service.ort.InferenceSession')
    @patch('os.path.exists')
    def test_service_initialization_model_load_error(self, mock_exists, mock_session, mock_config):
        """Test service initialization when model loading fails."""
        mock_exists.return_value = True
        mock_session.side_effect = Exception("ONNX loading error")
        
        with pytest.raises(TerraPulseModelError) as exc_info:
            TerraPulseService(mock_config)
        
        assert "Failed to load Terra Pulse model" in str(exc_info.value)
    
    def test_validate_input_valid_data(self, mock_config, sample_input):
        """Test input validation with valid data."""
        with patch('services.terra_pulse_service.ort.InferenceSession'), \
             patch('os.path.exists', return_value=True):
            
            service = TerraPulseService(mock_config)
            # Should not raise any exception
            service._validate_input(sample_input)
    
    def test_validate_input_invalid_ndvi_type(self, mock_config):
        """Test input validation with invalid NDVI data type."""
        with patch('services.terra_pulse_service.ort.InferenceSession'), \
             patch('os.path.exists', return_value=True):
            
            service = TerraPulseService(mock_config)
            
            invalid_input = PredictionInput(
                ndvi_mean_early="invalid",  # String instead of float
                ndvi_median_early=0.48,
                ndvi_std_early=0.1,
                ndvi_mean_late=0.45,
                ndvi_median_late=0.43,
                ndvi_std_late=0.12,
                ndvi_delta_mean=-0.05
            )
            
            with pytest.raises(TerraPulseModelError) as exc_info:
                service._validate_input(invalid_input)
            
            assert "must be numeric" in str(exc_info.value)
    
    def test_validate_input_negative_std(self, mock_config):
        """Test input validation with negative standard deviation."""
        with patch('services.terra_pulse_service.ort.InferenceSession'), \
             patch('os.path.exists', return_value=True):
            
            service = TerraPulseService(mock_config)
            
            invalid_input = PredictionInput(
                ndvi_mean_early=0.5,
                ndvi_median_early=0.48,
                ndvi_std_early=-0.1,  # Negative std
                ndvi_mean_late=0.45,
                ndvi_median_late=0.43,
                ndvi_std_late=0.12,
                ndvi_delta_mean=-0.05
            )
            
            with pytest.raises(TerraPulseModelError) as exc_info:
                service._validate_input(invalid_input)
            
            assert "must be non-negative" in str(exc_info.value)
    
    def test_prepare_model_input(self, mock_config, sample_input):
        """Test model input preparation."""
        with patch('services.terra_pulse_service.ort.InferenceSession'), \
             patch('os.path.exists', return_value=True):
            
            service = TerraPulseService(mock_config)
            features = service._prepare_model_input(sample_input)
            
            assert isinstance(features, np.ndarray)
            assert features.shape == (1, 7)
            assert features.dtype == np.float32
            
            expected_values = [0.5, 0.48, 0.1, 0.45, 0.43, 0.12, -0.05]
            np.testing.assert_array_almost_equal(features[0], expected_values)
    
    def test_interpret_prediction_high_risk(self, mock_config, sample_input):
        """Test prediction interpretation for high degradation risk."""
        with patch('services.terra_pulse_service.ort.InferenceSession'), \
             patch('os.path.exists', return_value=True):
            
            service = TerraPulseService(mock_config)
            result = service._interpret_prediction(0.8, sample_input)
            
            assert isinstance(result, PredictionOutput)
            assert result.degradation_risk == 80
            assert result.confidence == 0.8
            assert "bare_soil_increase" in result.risk_factors
            assert result.recommended_action_key == "mulch_crop_residue"
            assert result.location == "Test Location"
            assert result.user_context == "farmer"
    
    def test_interpret_prediction_medium_risk(self, mock_config, sample_input):
        """Test prediction interpretation for medium degradation risk."""
        with patch('services.terra_pulse_service.ort.InferenceSession'), \
             patch('os.path.exists', return_value=True):
            
            service = TerraPulseService(mock_config)
            result = service._interpret_prediction(0.5, sample_input)
            
            assert result.degradation_risk == 50
            assert result.confidence == 0.5
            assert "moderate_ndvi_drop" in result.risk_factors
            assert result.recommended_action_key == "increase_soil_cover"
    
    def test_interpret_prediction_low_risk(self, mock_config, sample_input):
        """Test prediction interpretation for low degradation risk."""
        with patch('services.terra_pulse_service.ort.InferenceSession'), \
             patch('os.path.exists', return_value=True):
            
            service = TerraPulseService(mock_config)
            result = service._interpret_prediction(0.2, sample_input)
            
            assert result.degradation_risk == 20
            assert result.confidence == 0.2
            assert "healthy_ndvi" in result.risk_factors
            assert result.recommended_action_key == "maintain_current_practices"
    
    def test_interpret_prediction_with_vegetation_decline(self, mock_config):
        """Test prediction interpretation with significant vegetation decline."""
        with patch('services.terra_pulse_service.ort.InferenceSession'), \
             patch('os.path.exists', return_value=True):
            
            service = TerraPulseService(mock_config)
            
            input_with_decline = PredictionInput(
                ndvi_mean_early=0.5,
                ndvi_median_early=0.48,
                ndvi_std_early=0.1,
                ndvi_mean_late=0.45,
                ndvi_median_late=0.43,
                ndvi_std_late=0.12,
                ndvi_delta_mean=-0.15,  # Significant decline
                location="Test Location"
            )
            
            result = service._interpret_prediction(0.5, input_with_decline)
            assert "significant_vegetation_decline" in result.risk_factors
    
    def test_interpret_prediction_with_high_variability(self, mock_config):
        """Test prediction interpretation with high vegetation variability."""
        with patch('services.terra_pulse_service.ort.InferenceSession'), \
             patch('os.path.exists', return_value=True):
            
            service = TerraPulseService(mock_config)
            
            input_with_variability = PredictionInput(
                ndvi_mean_early=0.5,
                ndvi_median_early=0.48,
                ndvi_std_early=0.25,  # High variability
                ndvi_mean_late=0.45,
                ndvi_median_late=0.43,
                ndvi_std_late=0.12,
                ndvi_delta_mean=-0.05,
                location="Test Location"
            )
            
            result = service._interpret_prediction(0.5, input_with_variability)
            assert "high_vegetation_variability" in result.risk_factors
    
    @patch('services.terra_pulse_service.ort.InferenceSession')
    @patch('os.path.exists')
    def test_predict_success(self, mock_exists, mock_session, mock_config, sample_input):
        """Test successful prediction."""
        mock_exists.return_value = True
        mock_session_instance = Mock()
        mock_session.return_value = mock_session_instance
        
        # Mock model inputs/outputs
        mock_input = Mock()
        mock_input.name = "input"
        mock_session_instance.get_inputs.return_value = [mock_input]
        mock_session_instance.get_outputs.return_value = [Mock()]
        mock_session_instance.run.return_value = [[0.75]]  # Mock prediction result
        
        service = TerraPulseService(mock_config)
        result = service.predict(sample_input)
        
        assert isinstance(result, PredictionOutput)
        assert result.degradation_risk == 75
        assert result.raw_prediction == 0.75
        assert result.processing_time_ms >= 0  # Processing time should be non-negative
        assert result.location == "Test Location"
    
    @patch('services.terra_pulse_service.ort.InferenceSession')
    @patch('os.path.exists')
    def test_predict_model_not_loaded(self, mock_exists, mock_session, mock_config, sample_input):
        """Test prediction when model is not loaded."""
        mock_exists.return_value = True
        mock_session_instance = Mock()
        mock_session.return_value = mock_session_instance
        
        # Mock model setup properly
        mock_input = Mock()
        mock_input.name = "input"
        mock_input.shape = [1, 7]
        mock_output = Mock()
        mock_output.name = "output"
        mock_output.shape = [1, 1]
        
        mock_session_instance.get_inputs.return_value = [mock_input]
        mock_session_instance.get_outputs.return_value = [mock_output]
        
        service = TerraPulseService(mock_config)
        service._model_loaded = False  # Simulate model not loaded
        
        with pytest.raises(TerraPulseModelError) as exc_info:
            service.predict(sample_input)
        
        assert "model is not loaded" in str(exc_info.value)
    
    @patch('services.terra_pulse_service.ort.InferenceSession')
    @patch('os.path.exists')
    def test_predict_model_runtime_error(self, mock_exists, mock_session, mock_config, sample_input):
        """Test prediction when model runtime fails."""
        mock_exists.return_value = True
        mock_session_instance = Mock()
        mock_session.return_value = mock_session_instance
        
        # Mock model setup
        mock_input = Mock()
        mock_input.name = "input"
        mock_session_instance.get_inputs.return_value = [mock_input]
        mock_session_instance.get_outputs.return_value = [Mock()]
        mock_session_instance.run.side_effect = Exception("Runtime error")
        
        service = TerraPulseService(mock_config)
        
        with pytest.raises(TerraPulseModelError) as exc_info:
            service.predict(sample_input)
        
        assert "Prediction failed" in str(exc_info.value)
    
    @patch('services.terra_pulse_service.ort.InferenceSession')
    @patch('os.path.exists')
    @pytest.mark.asyncio
    async def test_health_check_healthy(self, mock_exists, mock_session, mock_config):
        """Test health check when service is healthy."""
        mock_exists.return_value = True
        mock_session_instance = Mock()
        mock_session.return_value = mock_session_instance
        
        # Mock model setup
        mock_input = Mock()
        mock_input.name = "input"
        mock_input.shape = [1, 7]
        mock_output = Mock()
        mock_output.name = "output"
        mock_output.shape = [1, 1]
        
        mock_session_instance.get_inputs.return_value = [mock_input]
        mock_session_instance.get_outputs.return_value = [mock_output]
        mock_session_instance.run.return_value = [[0.5]]  # Valid prediction
        
        service = TerraPulseService(mock_config)
        health_check = await service.health_check()
        
        assert health_check.status == ServiceStatus.HEALTHY
        assert "functioning correctly" in health_check.message
        assert health_check.response_time_ms is not None
    
    @patch('services.terra_pulse_service.ort.InferenceSession')
    @patch('os.path.exists')
    @pytest.mark.asyncio
    async def test_health_check_model_not_loaded(self, mock_exists, mock_session, mock_config):
        """Test health check when model is not loaded."""
        mock_exists.return_value = True
        mock_session_instance = Mock()
        mock_session.return_value = mock_session_instance
        
        # Mock model setup
        mock_input = Mock()
        mock_input.name = "input"
        mock_input.shape = [1, 7]
        mock_output = Mock()
        mock_output.name = "output"
        mock_output.shape = [1, 1]
        
        mock_session_instance.get_inputs.return_value = [mock_input]
        mock_session_instance.get_outputs.return_value = [mock_output]
        
        service = TerraPulseService(mock_config)
        service._model_loaded = False  # Simulate model not loaded
        
        health_check = await service.health_check()
        
        assert health_check.status == ServiceStatus.UNHEALTHY
        assert "model is not loaded" in health_check.message
    
    @patch('services.terra_pulse_service.ort.InferenceSession')
    @patch('os.path.exists')
    @pytest.mark.asyncio
    async def test_health_check_prediction_failure(self, mock_exists, mock_session, mock_config):
        """Test health check when prediction fails."""
        mock_exists.return_value = True
        mock_session_instance = Mock()
        mock_session.return_value = mock_session_instance
        
        # Mock model setup
        mock_input = Mock()
        mock_input.name = "input"
        mock_input.shape = [1, 7]
        mock_output = Mock()
        mock_output.name = "output"
        mock_output.shape = [1, 1]
        
        mock_session_instance.get_inputs.return_value = [mock_input]
        mock_session_instance.get_outputs.return_value = [mock_output]
        mock_session_instance.run.side_effect = Exception("Model prediction failed")
        
        service = TerraPulseService(mock_config)
        health_check = await service.health_check()
        
        assert health_check.status == ServiceStatus.UNHEALTHY
        assert "Health check failed" in health_check.message
    
    @patch('services.terra_pulse_service.ort.InferenceSession')
    @patch('os.path.exists')
    def test_get_model_info_loaded(self, mock_exists, mock_session, mock_config):
        """Test getting model info when model is loaded."""
        mock_exists.return_value = True
        mock_session_instance = Mock()
        mock_session.return_value = mock_session_instance
        
        # Mock input/output info
        mock_input = Mock()
        mock_input.name = "input"
        mock_input.shape = [1, 7]
        mock_input.type = "tensor(float)"
        mock_output = Mock()
        mock_output.name = "output"
        mock_output.shape = [1, 1]
        mock_output.type = "tensor(float)"
        
        mock_session_instance.get_inputs.return_value = [mock_input]
        mock_session_instance.get_outputs.return_value = [mock_output]
        
        service = TerraPulseService(mock_config)
        info = service.get_model_info()
        
        assert info["status"] == "loaded"
        assert info["model_path"] == "test_model.onnx"
        assert info["input_name"] == "input"
        assert info["input_shape"] == [1, 7]
        assert info["output_name"] == "output"
        assert info["output_shape"] == [1, 1]
    
    @patch('services.terra_pulse_service.ort.InferenceSession')
    @patch('os.path.exists')
    def test_get_model_info_not_loaded(self, mock_exists, mock_session, mock_config):
        """Test getting model info when model is not loaded."""
        mock_exists.return_value = True
        mock_session_instance = Mock()
        mock_session.return_value = mock_session_instance
        
        # Mock model setup
        mock_input = Mock()
        mock_input.name = "input"
        mock_input.shape = [1, 7]
        mock_output = Mock()
        mock_output.name = "output"
        mock_output.shape = [1, 1]
        
        mock_session_instance.get_inputs.return_value = [mock_input]
        mock_session_instance.get_outputs.return_value = [mock_output]
        
        service = TerraPulseService(mock_config)
        service._model_loaded = False
        service._session = None
        
        info = service.get_model_info()
        assert info["status"] == "not_loaded"
    
    @patch('services.terra_pulse_service.ort.InferenceSession')
    @patch('os.path.exists')
    def test_reload_model(self, mock_exists, mock_session, mock_config):
        """Test model reloading."""
        mock_exists.return_value = True
        mock_session_instance = Mock()
        mock_session.return_value = mock_session_instance
        
        # Mock input/output info
        mock_input = Mock()
        mock_input.name = "input"
        mock_input.shape = [1, 7]
        mock_output = Mock()
        mock_output.name = "output"
        mock_output.shape = [1, 1]
        
        mock_session_instance.get_inputs.return_value = [mock_input]
        mock_session_instance.get_outputs.return_value = [mock_output]
        
        service = TerraPulseService(mock_config)
        
        # Verify model is initially loaded
        assert service._model_loaded is True
        
        # Reload model
        service.reload_model()
        
        # Verify model is still loaded after reload
        assert service._model_loaded is True
        assert mock_session.call_count == 2  # Initial load + reload
    
    @patch('services.terra_pulse_service.ort.InferenceSession')
    @patch('os.path.exists')
    def test_shutdown(self, mock_exists, mock_session, mock_config):
        """Test service shutdown."""
        mock_exists.return_value = True
        mock_session_instance = Mock()
        mock_session.return_value = mock_session_instance
        
        # Mock model setup
        mock_input = Mock()
        mock_input.name = "input"
        mock_input.shape = [1, 7]
        mock_output = Mock()
        mock_output.name = "output"
        mock_output.shape = [1, 1]
        
        mock_session_instance.get_inputs.return_value = [mock_input]
        mock_session_instance.get_outputs.return_value = [mock_output]
        
        service = TerraPulseService(mock_config)
        
        # Verify service is initially loaded
        assert service._model_loaded is True
        
        # Shutdown service
        service.shutdown()
        
        # Verify service is properly shut down
        assert service._model_loaded is False
        assert service._session is None


if __name__ == "__main__":
    pytest.main([__file__])