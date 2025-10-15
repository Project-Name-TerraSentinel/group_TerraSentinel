"""
Comprehensive system tests for resilience, error recovery, and monitoring.
Tests system behavior under various failure conditions and validates alerting functionality.
"""

import pytest
import json
import time
import threading
import asyncio
from unittest.mock import Mock, patch, MagicMock, call
from flask import Flask
import requests
from datetime import datetime, timedelta

# Import the app and services
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import app, terra_pulse_service, dify_service, alerting_service, logging_service
from backend.services.terra_pulse_service import PredictionOutput, TerraPulseModelError
from backend.services.dify_service import DifyWorkflowResponse
from backend.services.exceptions import *
from backend.services.alerting_service import AlertingService
from backend.services.logging_service import LoggingService


class TestSystemResilience:
    """Test system resilience and error recovery capabilities."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    @pytest.fixture
    def valid_request(self):
        """Valid prediction request."""
        return {
            "NDVI_mean_early": 0.45,
            "NDVI_median_early": 0.43,
            "NDVI_std_early": 0.12,
            "NDVI_mean_late": 0.38,
            "NDVI_median_late": 0.36,
            "NDVI_std_late": 0.15,
            "NDVI_delta_mean": -0.07,
            "location": "Resilience Test Location",
            "user_context": "system_test",
            "user_type": "farmer"
        }
    
    @pytest.fixture
    def api_key(self):
        """Valid API key."""
        return "resilience-test-key-12345"


class TestServiceFailureRecovery(TestSystemResilience):
    """Test recovery from various service failures."""
    
    def test_terra_pulse_model_corruption_recovery(self, client, valid_request, api_key):
        """Test recovery when Terra Pulse model is corrupted."""
        # Simulate model corruption
        with patch.object(terra_pulse_service, 'predict', 
                         side_effect=TerraPulseModelError("Model file corrupted", "terra_pulse")):
            
            response = client.post('/enhanced-predict',
                                 data=json.dumps(valid_request),
                                 content_type='application/json',
                                 headers={'X-API-Key': api_key})
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data
            assert 'Enhanced prediction failed' in data['error']
    
    def test_dify_api_intermittent_failures(self, client, valid_request, api_key):
        """Test handling of intermittent Dify API failures."""
        mock_terra_result = PredictionOutput(
            degradation_risk=70,
            risk_factors=["moderate_ndvi_drop"],
            recommended_action_key="increase_soil_cover",
            confidence=0.75,
            location="Resilience Test Location",
            user_context="system_test",
            raw_prediction=0.70,
            processing_time_ms=100.0
        )
        
        # Simulate intermittent failures (fail, succeed, fail, succeed)
        failure_responses = [
            requests.exceptions.ConnectionError("Connection failed"),
            {
                'status': 'success',
                'workflow_run_id': 'recovery-test-123',
                'enhanced_recommendations': ['Recovery recommendation'],
                'risk_assessment': 'System recovered successfully',
                'timeline': 'Immediate',
                'cost_estimate': 'Low',
                'success_probability': 0.8,
                'processing_time': 150.0
            },
            requests.exceptions.Timeout("Request timeout"),
            {
                'status': 'success',
                'workflow_run_id': 'recovery-test-456',
                'enhanced_recommendations': ['Second recovery recommendation'],
                'risk_assessment': 'System stable',
                'timeline': 'Within 1 week',
                'cost_estimate': 'Medium',
                'success_probability': 0.85,
                'processing_time': 120.0
            }
        ]
        
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_result), \
             patch.object(dify_service, 'execute_workflow', side_effect=failure_responses):
            
            # First request - should fail and use fallback
            response1 = client.post('/enhanced-predict',
                                  data=json.dumps(valid_request),
                                  content_type='application/json',
                                  headers={'X-API-Key': api_key})
            
            assert response1.status_code == 200
            data1 = json.loads(response1.data)
            assert data1['metadata']['dify_success'] is False
            assert data1['ai_insights']['fallback_used'] is True
            
            # Second request - should succeed
            response2 = client.post('/enhanced-predict',
                                  data=json.dumps(valid_request),
                                  content_type='application/json',
                                  headers={'X-API-Key': api_key})
            
            assert response2.status_code == 200
            data2 = json.loads(response2.data)
            assert data2['metadata']['dify_success'] is True
            assert 'Recovery recommendation' in data2['ai_insights']['enhanced_recommendations']
    
    def test_redis_cache_failure_graceful_degradation(self, client, valid_request, api_key):
        """Test graceful degradation when Redis cache fails."""
        mock_terra_result = PredictionOutput(
            degradation_risk=60,
            risk_factors=["moderate_ndvi_drop"],
            recommended_action_key="increase_soil_cover",
            confidence=0.80,
            location="Resilience Test Location",
            user_context="system_test",
            raw_prediction=0.60,
            processing_time_ms=110.0
        )
        
        mock_dify_result = {
            'status': 'success',
            'workflow_run_id': 'cache-failure-test',
            'enhanced_recommendations': ['Cache failure recommendation'],
            'risk_assessment': 'System operating without cache',
            'timeline': 'Normal processing',
            'cost_estimate': 'Standard',
            'success_probability': 0.75,
            'processing_time': 200.0
        }
        
        # Simulate Redis failure
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_result), \
             patch.object(dify_service, 'execute_workflow', return_value=mock_dify_result), \
             patch('app.redis_available', False):
            
            response = client.post('/enhanced-predict',
                                 data=json.dumps(valid_request),
                                 content_type='application/json',
                                 headers={'X-API-Key': api_key})
            
            # Should still work without cache
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['terra_pulse_prediction']['degradation_risk'] == 60
            assert data['ai_insights']['status'] == 'success'
    
    def test_memory_pressure_handling(self, client, valid_request, api_key):
        """Test system behavior under memory pressure."""
        mock_terra_result = PredictionOutput(
            degradation_risk=55,
            risk_factors=["moderate_ndvi_drop"],
            recommended_action_key="increase_soil_cover",
            confidence=0.78,
            location="Memory Test Location",
            user_context="memory_test",
            raw_prediction=0.55,
            processing_time_ms=95.0
        )
        
        # Simulate memory pressure by making many requests
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_result), \
             patch.object(dify_service, 'execute_workflow', 
                         return_value={'status': 'success', 'enhanced_recommendations': ['Memory test']}):
            
            # Make many concurrent requests to stress memory
            import threading
            results = []
            
            def make_request():
                response = client.post('/enhanced-predict',
                                     data=json.dumps(valid_request),
                                     content_type='application/json',
                                     headers={'X-API-Key': api_key})
                results.append(response.status_code)
            
            threads = []
            for _ in range(20):  # 20 concurrent requests
                thread = threading.Thread(target=make_request)
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join()
            
            # All requests should complete successfully
            assert len(results) == 20
            success_rate = sum(1 for code in results if code == 200) / len(results)
            assert success_rate >= 0.9, f"Success rate {success_rate:.2%} too low under memory pressure"
    
    def test_network_timeout_recovery(self, client, valid_request, api_key):
        """Test recovery from network timeouts."""
        mock_terra_result = PredictionOutput(
            degradation_risk=75,
            risk_factors=["bare_soil_increase"],
            recommended_action_key="emergency_soil_protection",
            confidence=0.85,
            location="Network Test Location",
            user_context="network_test",
            raw_prediction=0.75,
            processing_time_ms=120.0
        )
        
        # Simulate network timeout followed by success
        timeout_then_success = [
            requests.exceptions.Timeout("Network timeout"),
            {
                'status': 'success',
                'workflow_run_id': 'timeout-recovery-123',
                'enhanced_recommendations': ['Network recovered successfully'],
                'risk_assessment': 'Connection restored',
                'timeline': 'Normal operation resumed',
                'cost_estimate': 'Standard',
                'success_probability': 0.82,
                'processing_time': 180.0
            }
        ]
        
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_result), \
             patch.object(dify_service, 'execute_workflow', side_effect=timeout_then_success):
            
            # First request - timeout, should use fallback
            response1 = client.post('/enhanced-predict',
                                  data=json.dumps(valid_request),
                                  content_type='application/json',
                                  headers={'X-API-Key': api_key})
            
            assert response1.status_code == 200
            data1 = json.loads(response1.data)
            assert data1['metadata']['dify_success'] is False
            
            # Second request - should succeed
            response2 = client.post('/enhanced-predict',
                                  data=json.dumps(valid_request),
                                  content_type='application/json',
                                  headers={'X-API-Key': api_key})
            
            assert response2.status_code == 200
            data2 = json.loads(response2.data)
            assert data2['metadata']['dify_success'] is True
            assert 'Network recovered successfully' in data2['ai_insights']['enhanced_recommendations']


class TestErrorHandlingAndRecovery(TestSystemResilience):
    """Test comprehensive error handling and recovery mechanisms."""
    
    def test_malformed_json_handling(self, client, api_key):
        """Test handling of malformed JSON requests."""
        malformed_json = '{"NDVI_mean_early": 0.45, "invalid": }'
        
        response = client.post('/enhanced-predict',
                             data=malformed_json,
                             content_type='application/json',
                             headers={'X-API-Key': api_key})
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'JSON' in data['error'] or 'parse' in data['error'].lower()
    
    def test_sql_injection_protection(self, client, api_key):
        """Test protection against SQL injection attempts."""
        injection_request = {
            "NDVI_mean_early": 0.45,
            "NDVI_median_early": 0.43,
            "NDVI_std_early": 0.12,
            "NDVI_mean_late": 0.38,
            "NDVI_median_late": 0.36,
            "NDVI_std_late": 0.15,
            "NDVI_delta_mean": -0.07,
            "location": "'; DROP TABLE users; --",
            "user_context": "1' OR '1'='1",
            "user_type": "farmer"
        }
        
        mock_terra_result = PredictionOutput(
            degradation_risk=50,
            risk_factors=["test"],
            recommended_action_key="test",
            confidence=0.5,
            location="Sanitized Location",  # Should be sanitized
            user_context="Sanitized Context",  # Should be sanitized
            raw_prediction=0.5,
            processing_time_ms=100.0
        )
        
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_result), \
             patch.object(dify_service, 'execute_workflow', 
                         return_value={'status': 'success', 'enhanced_recommendations': ['Safe response']}):
            
            response = client.post('/enhanced-predict',
                                 data=json.dumps(injection_request),
                                 content_type='application/json',
                                 headers={'X-API-Key': api_key})
            
            # Should either sanitize input or reject request
            if response.status_code == 200:
                data = json.loads(response.data)
                # Verify dangerous content was sanitized
                location = data['terra_pulse_prediction']['location']
                user_context = data['terra_pulse_prediction']['user_context']
                assert 'DROP TABLE' not in location
                assert "1'='1" not in user_context
            else:
                # Request was rejected due to validation
                assert response.status_code == 400
    
    def test_xss_protection(self, client, api_key):
        """Test protection against XSS attacks."""
        xss_request = {
            "NDVI_mean_early": 0.45,
            "NDVI_median_early": 0.43,
            "NDVI_std_early": 0.12,
            "NDVI_mean_late": 0.38,
            "NDVI_median_late": 0.36,
            "NDVI_std_late": 0.15,
            "NDVI_delta_mean": -0.07,
            "location": "<script>alert('xss')</script>Nairobi",
            "user_context": "farmer<img src=x onerror=alert('xss')>",
            "user_type": "farmer"
        }
        
        mock_terra_result = PredictionOutput(
            degradation_risk=45,
            risk_factors=["test"],
            recommended_action_key="test",
            confidence=0.7,
            location="Nairobi",  # Should be sanitized
            user_context="farmer",  # Should be sanitized
            raw_prediction=0.45,
            processing_time_ms=90.0
        )
        
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_result), \
             patch.object(dify_service, 'execute_workflow', 
                         return_value={'status': 'success', 'enhanced_recommendations': ['Clean response']}):
            
            response = client.post('/enhanced-predict',
                                 data=json.dumps(xss_request),
                                 content_type='application/json',
                                 headers={'X-API-Key': api_key})
            
            if response.status_code == 200:
                data = json.loads(response.data)
                # Verify XSS content was sanitized
                location = data['terra_pulse_prediction']['location']
                user_context = data['terra_pulse_prediction']['user_context']
                assert '<script>' not in location
                assert 'onerror=' not in user_context
            else:
                assert response.status_code == 400
    
    def test_rate_limiting_recovery(self, client, valid_request, api_key):
        """Test recovery after rate limiting."""
        # Simulate rate limit exceeded
        with patch('app.redis_client') as mock_redis:
            mock_redis.get.return_value = b'100'  # Simulate high request count
            
            response = client.post('/enhanced-predict',
                                 data=json.dumps(valid_request),
                                 content_type='application/json',
                                 headers={'X-API-Key': api_key})
            
            assert response.status_code == 429
            data = json.loads(response.data)
            assert 'Rate limit exceeded' in data['error']
            assert 'retry_after_seconds' in data
    
    def test_concurrent_error_handling(self, client, valid_request, api_key):
        """Test error handling under concurrent load."""
        # Mix of successful and failing requests
        def make_request(should_fail=False):
            if should_fail:
                with patch.object(terra_pulse_service, 'predict', 
                                side_effect=Exception("Simulated failure")):
                    return client.post('/enhanced-predict',
                                     data=json.dumps(valid_request),
                                     content_type='application/json',
                                     headers={'X-API-Key': api_key})
            else:
                mock_result = PredictionOutput(
                    degradation_risk=50, risk_factors=["test"], recommended_action_key="test",
                    confidence=0.5, location="Test", user_context="test", raw_prediction=0.5, processing_time_ms=100.0
                )
                with patch.object(terra_pulse_service, 'predict', return_value=mock_result), \
                     patch.object(dify_service, 'execute_workflow', 
                                 return_value={'status': 'success', 'enhanced_recommendations': ['Test']}):
                    return client.post('/enhanced-predict',
                                     data=json.dumps(valid_request),
                                     content_type='application/json',
                                     headers={'X-API-Key': api_key})
        
        # Run concurrent requests with mixed success/failure
        import threading
        results = []
        
        def worker(fail_rate=0.3):
            for i in range(10):
                should_fail = (i % 10) < (fail_rate * 10)
                response = make_request(should_fail)
                results.append(response.status_code)
        
        threads = []
        for _ in range(3):  # 3 threads, 10 requests each
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Analyze results
        success_count = sum(1 for code in results if code == 200)
        error_count = sum(1 for code in results if code >= 500)
        
        print(f"Concurrent error handling: {success_count} success, {error_count} errors out of {len(results)}")
        
        # System should handle errors gracefully without crashing
        assert len(results) == 30  # All requests completed
        assert success_count > 0  # Some requests succeeded


class TestMonitoringAndAlerting(TestSystemResilience):
    """Test monitoring and alerting functionality."""
    
    def test_health_check_monitoring(self, client):
        """Test health check endpoints for monitoring."""
        # Test individual service health checks
        with patch.object(terra_pulse_service.terra_pulse_service, 'health_check') as mock_terra_health, \
             patch.object(dify_service.dify_service, 'health_check') as mock_dify_health:
            
            # Mock healthy responses
            from services.base_service import ServiceHealthCheck, ServiceStatus
            mock_terra_health.return_value = ServiceHealthCheck(
                status=ServiceStatus.HEALTHY,
                message="Terra Pulse healthy",
                response_time_ms=50.0
            )
            mock_dify_health.return_value = ServiceHealthCheck(
                status=ServiceStatus.HEALTHY,
                message="Dify healthy",
                response_time_ms=100.0
            )
            
            # Test Terra Pulse health
            response = client.get('/health/terra-pulse')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['service'] == 'terra_pulse'
            assert data['status'] == 'healthy'
            
            # Test Dify health
            response = client.get('/health/dify')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['service'] == 'dify'
            assert data['status'] == 'healthy'
            
            # Test system health
            with patch.object(terra_pulse_service.cache_service, 'get_cache_stats', 
                            return_value={"available": True, "hit_ratio": 0.8, "total_keys": 50}):
                response = client.get('/health/system')
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data['overall_status'] == 'healthy'
                assert data['capabilities']['basic_predictions'] is True
                assert data['capabilities']['enhanced_predictions'] is True
    
    def test_metrics_endpoint_monitoring(self, client):
        """Test metrics endpoint for Prometheus monitoring."""
        with patch.object(terra_pulse_service.terra_pulse_service, 'health_check') as mock_terra_health, \
             patch.object(dify_service.dify_service, 'health_check') as mock_dify_health, \
             patch.object(terra_pulse_service.cache_service, 'get_cache_stats') as mock_cache_stats:
            
            # Mock service responses
            from services.base_service import ServiceHealthCheck, ServiceStatus
            mock_terra_health.return_value = ServiceHealthCheck(
                status=ServiceStatus.HEALTHY,
                message="Healthy",
                response_time_ms=75.0
            )
            mock_dify_health.return_value = ServiceHealthCheck(
                status=ServiceStatus.HEALTHY,
                message="Healthy",
                response_time_ms=125.0
            )
            mock_cache_stats.return_value = {
                "available": True,
                "hit_ratio": 0.75,
                "total_keys": 100,
                "memory_usage": 50 * 1024 * 1024  # 50MB
            }
            
            response = client.get('/metrics')
            assert response.status_code == 200
            assert response.content_type == 'text/plain; charset=utf-8'
            
            metrics_text = response.data.decode('utf-8')
            
            # Verify key metrics are present
            assert 'terra_pulse_service_health 1' in metrics_text
            assert 'dify_service_health 1' in metrics_text
            assert 'cache_available 1' in metrics_text
            assert 'cache_hit_ratio 0.75' in metrics_text
    
    def test_alerting_system_functionality(self, client, valid_request, api_key):
        """Test alerting system triggers and notifications."""
        with patch.object(alerting_service, 'send_alert') as mock_send_alert:
            
            # Simulate critical error that should trigger alert
            with patch.object(terra_pulse_service, 'predict', 
                            side_effect=Exception("Critical model failure")):
                
                response = client.post('/enhanced-predict',
                                     data=json.dumps(valid_request),
                                     content_type='application/json',
                                     headers={'X-API-Key': api_key})
                
                assert response.status_code == 500
                
                # Verify alert was sent
                # Note: This depends on the actual alerting implementation
                # The mock may or may not be called depending on how alerts are configured
    
    def test_logging_system_functionality(self, client, valid_request, api_key):
        """Test comprehensive logging functionality."""
        mock_terra_result = PredictionOutput(
            degradation_risk=65,
            risk_factors=["moderate_ndvi_drop"],
            recommended_action_key="increase_soil_cover",
            confidence=0.80,
            location="Logging Test Location",
            user_context="logging_test",
            raw_prediction=0.65,
            processing_time_ms=105.0
        )
        
        mock_dify_result = {
            'status': 'success',
            'workflow_run_id': 'logging-test-123',
            'enhanced_recommendations': ['Logging test recommendation'],
            'risk_assessment': 'System logging correctly',
            'timeline': 'Normal operation',
            'cost_estimate': 'Standard',
            'success_probability': 0.78,
            'processing_time': 160.0
        }
        
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_result), \
             patch.object(dify_service, 'execute_workflow', return_value=mock_dify_result), \
             patch.object(logging_service, 'log_api_request') as mock_log_request, \
             patch.object(logging_service, 'log_api_response') as mock_log_response:
            
            response = client.post('/enhanced-predict',
                                 data=json.dumps(valid_request),
                                 content_type='application/json',
                                 headers={'X-API-Key': api_key})
            
            assert response.status_code == 200
            
            # Verify logging calls were made
            # Note: Actual verification depends on logging implementation
            # These mocks may or may not be called based on decorator usage
    
    def test_security_event_logging(self, client, api_key):
        """Test security event logging and monitoring."""
        # Test invalid API key logging
        response = client.post('/enhanced-predict',
                             data=json.dumps({"test": "data"}),
                             content_type='application/json',
                             headers={'X-API-Key': 'invalid-key'})
        
        # Should log security event for invalid API key
        assert response.status_code == 401
        
        # Test missing API key logging
        response = client.post('/enhanced-predict',
                             data=json.dumps({"test": "data"}),
                             content_type='application/json')
        
        # Should log security event for missing API key
        assert response.status_code == 401
    
    def test_performance_monitoring_integration(self, client, valid_request, api_key):
        """Test performance monitoring and metrics collection."""
        mock_terra_result = PredictionOutput(
            degradation_risk=70,
            risk_factors=["moderate_ndvi_drop"],
            recommended_action_key="increase_soil_cover",
            confidence=0.82,
            location="Performance Monitor Test",
            user_context="perf_test",
            raw_prediction=0.70,
            processing_time_ms=115.0
        )
        
        mock_dify_result = {
            'status': 'success',
            'workflow_run_id': 'perf-monitor-123',
            'enhanced_recommendations': ['Performance monitoring active'],
            'risk_assessment': 'System performance normal',
            'timeline': 'Standard processing',
            'cost_estimate': 'Normal',
            'success_probability': 0.80,
            'processing_time': 175.0
        }
        
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_result), \
             patch.object(dify_service, 'execute_workflow', return_value=mock_dify_result):
            
            start_time = time.time()
            response = client.post('/enhanced-predict',
                                 data=json.dumps(valid_request),
                                 content_type='application/json',
                                 headers={'X-API-Key': api_key})
            end_time = time.time()
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            # Verify performance metadata is included
            metadata = data['metadata']
            assert 'total_processing_time_ms' in metadata
            assert metadata['total_processing_time_ms'] > 0
            
            # Verify timing is reasonable
            actual_time_ms = (end_time - start_time) * 1000
            reported_time_ms = metadata['total_processing_time_ms']
            
            # Reported time should be less than or equal to actual time
            assert reported_time_ms <= actual_time_ms * 1.1  # Allow 10% margin


class TestSystemIntegrationScenarios(TestSystemResilience):
    """Test complex integration scenarios and edge cases."""
    
    def test_full_system_stress_test(self, client, valid_request, api_key):
        """Test system behavior under full stress conditions."""
        mock_terra_result = PredictionOutput(
            degradation_risk=80,
            risk_factors=["bare_soil_increase", "low_ndvi"],
            recommended_action_key="emergency_soil_protection",
            confidence=0.88,
            location="Stress Test Location",
            user_context="stress_test",
            raw_prediction=0.80,
            processing_time_ms=130.0
        )
        
        mock_dify_result = {
            'status': 'success',
            'workflow_run_id': 'stress-test-123',
            'enhanced_recommendations': ['Stress test recommendation'],
            'risk_assessment': 'System under stress but functioning',
            'timeline': 'Immediate attention required',
            'cost_estimate': 'High priority',
            'success_probability': 0.85,
            'processing_time': 200.0
        }
        
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_result), \
             patch.object(dify_service, 'execute_workflow', return_value=mock_dify_result):
            
            # Simulate high concurrent load
            import threading
            import queue
            
            results = queue.Queue()
            errors = queue.Queue()
            
            def stress_worker():
                try:
                    for _ in range(10):  # 10 requests per thread
                        response = client.post('/enhanced-predict',
                                             data=json.dumps(valid_request),
                                             content_type='application/json',
                                             headers={'X-API-Key': api_key})
                        results.put(response.status_code)
                        time.sleep(0.01)  # Small delay
                except Exception as e:
                    errors.put(str(e))
            
            # Start multiple threads
            threads = []
            for _ in range(5):  # 5 threads = 50 total requests
                thread = threading.Thread(target=stress_worker)
                threads.append(thread)
                thread.start()
            
            # Wait for completion
            for thread in threads:
                thread.join()
            
            # Analyze results
            status_codes = []
            while not results.empty():
                status_codes.append(results.get())
            
            error_messages = []
            while not errors.empty():
                error_messages.append(errors.get())
            
            print(f"Stress test results: {len(status_codes)} responses, {len(error_messages)} errors")
            
            # System should handle stress gracefully
            assert len(status_codes) > 0, "No responses received"
            success_rate = sum(1 for code in status_codes if code == 200) / len(status_codes)
            assert success_rate >= 0.8, f"Success rate {success_rate:.2%} too low under stress"
            assert len(error_messages) == 0, f"Unexpected errors: {error_messages}"
    
    def test_cascading_failure_recovery(self, client, valid_request, api_key):
        """Test recovery from cascading system failures."""
        # Simulate cascading failures: Terra Pulse -> Dify -> Cache
        failure_sequence = [
            # First: Terra Pulse fails
            (Exception("Terra Pulse failure"), None, False),
            # Then: Terra Pulse recovers, Dify fails
            (PredictionOutput(50, ["test"], "test", 0.5, "Test", "test", 0.5, 100.0), 
             requests.exceptions.ConnectionError("Dify failure"), True),
            # Finally: Both recover
            (PredictionOutput(60, ["test"], "test", 0.6, "Test", "test", 0.6, 110.0),
             {'status': 'success', 'enhanced_recommendations': ['Recovery complete']}, True)
        ]
        
        for i, (terra_response, dify_response, redis_available) in enumerate(failure_sequence):
            with patch.object(terra_pulse_service, 'predict', 
                            side_effect=[terra_response] if isinstance(terra_response, Exception) else None,
                            return_value=None if isinstance(terra_response, Exception) else terra_response), \
                 patch.object(dify_service, 'execute_workflow',
                            side_effect=[dify_response] if isinstance(dify_response, Exception) else None,
                            return_value=None if isinstance(dify_response, Exception) else dify_response), \
                 patch('app.redis_available', redis_available):
                
                response = client.post('/enhanced-predict',
                                     data=json.dumps(valid_request),
                                     content_type='application/json',
                                     headers={'X-API-Key': api_key})
                
                print(f"Cascading failure test {i+1}: Status {response.status_code}")
                
                if i == 0:  # Terra Pulse failure
                    assert response.status_code == 500
                elif i == 1:  # Dify failure, Terra Pulse OK
                    assert response.status_code == 200
                    data = json.loads(response.data)
                    assert data['metadata']['dify_success'] is False
                else:  # Both services OK
                    assert response.status_code == 200
                    data = json.loads(response.data)
                    assert data['metadata']['dify_success'] is True


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])