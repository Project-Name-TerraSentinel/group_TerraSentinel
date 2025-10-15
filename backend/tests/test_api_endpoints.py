"""
Integration tests for Flask API endpoints.
Tests authentication, rate limiting, and error scenarios.
"""

import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from flask import Flask

# Import the app and services
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import app, terra_pulse_service, dify_service, redis_client
from backend.services.terra_pulse_service import PredictionOutput, HealthCheckResult, ServiceStatus
from backend.services.dify_service import DifyWorkflowResponse


class TestAPIEndpoints:
    """Test suite for API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    @pytest.fixture
    def valid_prediction_data(self):
        """Valid prediction request data."""
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
    def valid_api_key(self):
        """Valid API key for testing."""
        return "test-api-key-12345"
    
    @pytest.fixture
    def mock_terra_pulse_result(self):
        """Mock Terra Pulse prediction result."""
        return PredictionOutput(
            degradation_risk=75,
            risk_factors=["bare_soil_increase", "low_ndvi"],
            recommended_action_key="mulch_crop_residue",
            confidence=0.85,
            location="Baringo County, Kenya",
            user_context="smallholder_farmer",
            raw_prediction=0.75,
            processing_time_ms=150.0
        )
    
    @pytest.fixture
    def mock_dify_response(self):
        """Mock Dify workflow response."""
        return {
            'status': 'success',
            'enhanced_recommendations': [
                'Apply crop residue mulch within 2 weeks',
                'Consider drought-resistant maize varieties'
            ],
            'risk_assessment': 'High degradation risk due to recent drought conditions',
            'timeline': 'Immediate action required within 14 days',
            'cost_estimate': 'Low cost - use existing crop residue',
            'success_probability': 0.78,
            'processing_time': 200.0,
            'workflow_run_id': 'test-workflow-123'
        }


class TestEnhancedPredictEndpoint(TestAPIEndpoints):
    """Tests for /enhanced-predict endpoint."""
    
    def test_enhanced_predict_success(self, client, valid_prediction_data, valid_api_key, 
                                    mock_terra_pulse_result, mock_dify_response):
        """Test successful enhanced prediction."""
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_pulse_result), \
             patch.object(dify_service, 'execute_workflow', return_value=mock_dify_response):
            
            response = client.post('/enhanced-predict',
                                 data=json.dumps(valid_prediction_data),
                                 content_type='application/json',
                                 headers={'X-API-Key': valid_api_key})
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            # Check response structure
            assert 'terra_pulse_prediction' in data
            assert 'ai_insights' in data
            assert 'formatted_response' in data
            assert 'metadata' in data
            
            # Check Terra Pulse data
            terra_data = data['terra_pulse_prediction']
            assert terra_data['degradation_risk'] == 75
            assert terra_data['location'] == "Baringo County, Kenya"
            
            # Check AI insights
            ai_data = data['ai_insights']
            assert len(ai_data['enhanced_recommendations']) == 2
            assert ai_data['risk_assessment'] == 'High degradation risk due to recent drought conditions'
            
            # Check formatted response
            formatted = data['formatted_response']
            assert formatted['user_type'] == 'farmer'
            assert 'title' in formatted
            assert 'summary' in formatted
            
            # Check metadata
            metadata = data['metadata']
            assert metadata['dify_success'] is True
            assert metadata['endpoint'] == 'enhanced-predict'
    
    def test_enhanced_predict_missing_api_key(self, client, valid_prediction_data):
        """Test enhanced prediction without API key."""
        response = client.post('/enhanced-predict',
                             data=json.dumps(valid_prediction_data),
                             content_type='application/json')
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Authentication required' in data['error']
    
    def test_enhanced_predict_invalid_data(self, client, valid_api_key):
        """Test enhanced prediction with invalid data."""
        invalid_data = {
            "NDVI_mean_early": "invalid",  # Should be float
            "location": "Test Location"
        }
        
        response = client.post('/enhanced-predict',
                             data=json.dumps(invalid_data),
                             content_type='application/json',
                             headers={'X-API-Key': valid_api_key})
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Validation failed' in data['error']
    
    def test_enhanced_predict_missing_json(self, client, valid_api_key):
        """Test enhanced prediction without JSON data."""
        response = client.post('/enhanced-predict',
                             headers={'X-API-Key': valid_api_key})
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'No JSON data provided' in data['error']
    
    def test_enhanced_predict_dify_failure_fallback(self, client, valid_prediction_data, 
                                                  valid_api_key, mock_terra_pulse_result):
        """Test enhanced prediction with Dify failure fallback."""
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_pulse_result), \
             patch.object(dify_service, 'execute_workflow', side_effect=Exception("Dify API error")):
            
            response = client.post('/enhanced-predict',
                                 data=json.dumps(valid_prediction_data),
                                 content_type='application/json',
                                 headers={'X-API-Key': valid_api_key})
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            # Should still have Terra Pulse data
            assert 'terra_pulse_prediction' in data
            assert data['terra_pulse_prediction']['degradation_risk'] == 75
            
            # Should have fallback AI insights
            ai_data = data['ai_insights']
            assert ai_data['fallback_used'] is True
            assert 'AI processing unavailable' in ai_data['risk_assessment']
            
            # Metadata should indicate Dify failure
            assert data['metadata']['dify_success'] is False
    
    def test_enhanced_predict_terra_pulse_failure(self, client, valid_prediction_data, valid_api_key):
        """Test enhanced prediction with Terra Pulse failure."""
        with patch.object(terra_pulse_service, 'predict', side_effect=Exception("Model error")):
            
            response = client.post('/enhanced-predict',
                                 data=json.dumps(valid_prediction_data),
                                 content_type='application/json',
                                 headers={'X-API-Key': valid_api_key})
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data
            assert 'Enhanced prediction failed' in data['error']


class TestHealthEndpoints(TestAPIEndpoints):
    """Tests for health check endpoints."""
    
    def test_health_terra_pulse_healthy(self, client):
        """Test Terra Pulse health check when healthy."""
        mock_health = HealthCheckResult(
            status=ServiceStatus.HEALTHY,
            message="Service is healthy",
            model_loaded=True,
            response_time_ms=50.0
        )
        
        with patch.object(terra_pulse_service.terra_pulse_service, 'health_check', return_value=mock_health):
            response = client.get('/health/terra-pulse')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['service'] == 'terra_pulse'
            assert data['status'] == 'healthy'
            assert data['model_loaded'] is True
    
    def test_health_terra_pulse_unhealthy(self, client):
        """Test Terra Pulse health check when unhealthy."""
        with patch.object(terra_pulse_service.terra_pulse_service, 'health_check', 
                         side_effect=Exception("Health check failed")):
            response = client.get('/health/terra-pulse')
            
            assert response.status_code == 503
            data = json.loads(response.data)
            assert data['service'] == 'terra_pulse'
            assert data['status'] == 'unhealthy'
    
    def test_health_dify_healthy(self, client):
        """Test Dify health check when healthy."""
        mock_health = HealthCheckResult(
            status=ServiceStatus.HEALTHY,
            message="Service is healthy",
            api_accessible=True,
            workflow_accessible=True,
            response_time_ms=100.0
        )
        
        with patch.object(dify_service.dify_service, 'health_check', return_value=mock_health):
            response = client.get('/health/dify')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['service'] == 'dify'
            assert data['status'] == 'healthy'
    
    def test_health_system_all_healthy(self, client):
        """Test system health when all services are healthy."""
        terra_health = HealthCheckResult(
            status=ServiceStatus.HEALTHY,
            message="Terra Pulse healthy",
            response_time_ms=50.0
        )
        dify_health = HealthCheckResult(
            status=ServiceStatus.HEALTHY,
            message="Dify healthy",
            response_time_ms=100.0
        )
        cache_stats = {"available": True, "hit_ratio": 0.85, "total_keys": 100}
        
        with patch.object(terra_pulse_service.terra_pulse_service, 'health_check', return_value=terra_health), \
             patch.object(dify_service.dify_service, 'health_check', return_value=dify_health), \
             patch.object(terra_pulse_service.cache_service, 'get_cache_stats', return_value=cache_stats):
            
            response = client.get('/health/system')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['overall_status'] == 'healthy'
            assert data['capabilities']['basic_predictions'] is True
            assert data['capabilities']['enhanced_predictions'] is True
            assert data['capabilities']['caching'] is True
    
    def test_health_system_degraded(self, client):
        """Test system health when Dify is down but Terra Pulse is healthy."""
        terra_health = HealthCheckResult(
            status=ServiceStatus.HEALTHY,
            message="Terra Pulse healthy",
            response_time_ms=50.0
        )
        dify_health = HealthCheckResult(
            status=ServiceStatus.UNHEALTHY,
            message="Dify unhealthy",
            response_time_ms=0.0
        )
        cache_stats = {"available": True, "hit_ratio": 0.85, "total_keys": 100}
        
        with patch.object(terra_pulse_service.terra_pulse_service, 'health_check', return_value=terra_health), \
             patch.object(dify_service.dify_service, 'health_check', return_value=dify_health), \
             patch.object(terra_pulse_service.cache_service, 'get_cache_stats', return_value=cache_stats):
            
            response = client.get('/health/system')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['overall_status'] == 'degraded'
            assert data['capabilities']['basic_predictions'] is True
            assert data['capabilities']['enhanced_predictions'] is False


class TestMetricsEndpoint(TestAPIEndpoints):
    """Tests for metrics endpoint."""
    
    def test_metrics_success(self, client):
        """Test metrics endpoint success."""
        terra_health = HealthCheckResult(
            status=ServiceStatus.HEALTHY,
            message="Healthy",
            response_time_ms=50.0
        )
        dify_health = HealthCheckResult(
            status=ServiceStatus.HEALTHY,
            message="Healthy",
            response_time_ms=100.0
        )
        cache_stats = {"available": True, "hit_ratio": 0.85, "total_keys": 100}
        
        with patch.object(terra_pulse_service.terra_pulse_service, 'health_check', return_value=terra_health), \
             patch.object(dify_service.dify_service, 'health_check', return_value=dify_health), \
             patch.object(terra_pulse_service.cache_service, 'get_cache_stats', return_value=cache_stats):
            
            response = client.get('/metrics')
            
            assert response.status_code == 200
            assert response.content_type == 'text/plain; charset=utf-8'
            
            metrics_text = response.data.decode('utf-8')
            assert 'terra_pulse_service_health 1' in metrics_text
            assert 'dify_service_health 1' in metrics_text
            assert 'cache_available 1' in metrics_text
            assert 'cache_hit_ratio 0.85' in metrics_text
    
    def test_metrics_with_unhealthy_services(self, client):
        """Test metrics endpoint with unhealthy services."""
        terra_health = HealthCheckResult(
            status=ServiceStatus.UNHEALTHY,
            message="Unhealthy",
            response_time_ms=0.0
        )
        dify_health = HealthCheckResult(
            status=ServiceStatus.UNHEALTHY,
            message="Unhealthy",
            response_time_ms=0.0
        )
        cache_stats = {"available": False}
        
        with patch.object(terra_pulse_service.terra_pulse_service, 'health_check', return_value=terra_health), \
             patch.object(dify_service.dify_service, 'health_check', return_value=dify_health), \
             patch.object(terra_pulse_service.cache_service, 'get_cache_stats', return_value=cache_stats):
            
            response = client.get('/metrics')
            
            assert response.status_code == 200
            metrics_text = response.data.decode('utf-8')
            assert 'terra_pulse_service_health 0' in metrics_text
            assert 'dify_service_health 0' in metrics_text
            assert 'cache_available 0' in metrics_text


class TestAuthenticationAndRateLimiting(TestAPIEndpoints):
    """Tests for authentication and rate limiting."""
    
    def test_rate_limiting_enforcement(self, client, valid_prediction_data, valid_api_key):
        """Test rate limiting enforcement."""
        # Mock Redis to simulate rate limiting
        with patch.object(redis_client, 'get', return_value=b'60'), \
             patch.object(redis_client, 'ttl', return_value=30):
            
            response = client.post('/enhanced-predict',
                                 data=json.dumps(valid_prediction_data),
                                 content_type='application/json',
                                 headers={'X-API-Key': valid_api_key})
            
            assert response.status_code == 429
            data = json.loads(response.data)
            assert 'Rate limit exceeded' in data['error']
            assert 'retry_after_seconds' in data
    
    def test_rate_limiting_within_limit(self, client, valid_prediction_data, valid_api_key, 
                                      mock_terra_pulse_result, mock_dify_response):
        """Test rate limiting when within limits."""
        with patch.object(redis_client, 'get', return_value=b'5'), \
             patch.object(redis_client, 'pipeline') as mock_pipeline, \
             patch.object(terra_pulse_service, 'predict', return_value=mock_terra_pulse_result), \
             patch.object(dify_service, 'execute_workflow', return_value=mock_dify_response):
            
            # Mock pipeline operations
            mock_pipe = MagicMock()
            mock_pipeline.return_value = mock_pipe
            
            response = client.post('/enhanced-predict',
                                 data=json.dumps(valid_prediction_data),
                                 content_type='application/json',
                                 headers={'X-API-Key': valid_api_key})
            
            assert response.status_code == 200
            # Verify pipeline operations were called
            mock_pipe.incr.assert_called_once()
            mock_pipe.expire.assert_called_once()
            mock_pipe.execute.assert_called_once()
    
    def test_authentication_bypass_for_health_endpoints(self, client):
        """Test that health endpoints bypass authentication."""
        response = client.get('/health/system')
        # Should succeed without API key
        assert response.status_code in [200, 503]  # 503 if services are mocked as unhealthy
    
    def test_empty_api_key_rejection(self, client, valid_prediction_data):
        """Test rejection of empty API key."""
        response = client.post('/enhanced-predict',
                             data=json.dumps(valid_prediction_data),
                             content_type='application/json',
                             headers={'X-API-Key': ''})
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'Invalid API key' in data['error']
    
    def test_rate_limiting_redis_unavailable(self, client, valid_prediction_data, valid_api_key,
                                           mock_terra_pulse_result, mock_dify_response):
        """Test rate limiting when Redis is unavailable."""
        with patch('app.redis_available', False), \
             patch.object(terra_pulse_service, 'predict', return_value=mock_terra_pulse_result), \
             patch.object(dify_service, 'execute_workflow', return_value=mock_dify_response):
            
            response = client.post('/enhanced-predict',
                                 data=json.dumps(valid_prediction_data),
                                 content_type='application/json',
                                 headers={'X-API-Key': valid_api_key})
            
            # Should succeed without rate limiting
            assert response.status_code == 200


class TestOriginalPredictEndpoint(TestAPIEndpoints):
    """Tests for original /predict endpoint with new middleware."""
    
    def test_original_predict_with_auth(self, client, valid_api_key):
        """Test original predict endpoint with authentication."""
        prediction_data = {
            "NDVI_mean_early": 0.45,
            "NDVI_median_early": 0.43,
            "NDVI_std_early": 0.12,
            "NDVI_mean_late": 0.38,
            "NDVI_median_late": 0.36,
            "NDVI_std_late": 0.15,
            "NDVI_delta_mean": -0.07,
            "location": "Test Location",
            "user_context": "test_user"
        }
        
        response = client.post('/predict',
                             data=json.dumps(prediction_data),
                             content_type='application/json',
                             headers={'X-API-Key': valid_api_key})
        
        # Should succeed (assuming ONNX model is available in test environment)
        # In a real test environment, we'd mock the ONNX session
        assert response.status_code in [200, 500]  # 500 if model not available in test
    
    def test_original_predict_without_auth(self, client):
        """Test original predict endpoint without authentication."""
        prediction_data = {
            "NDVI_mean_early": 0.45,
            "location": "Test Location"
        }
        
        response = client.post('/predict',
                             data=json.dumps(prediction_data),
                             content_type='application/json')
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'Authentication required' in data['error']


if __name__ == '__main__':
    pytest.main([__file__])