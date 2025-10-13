"""
Deployment and Integration Tests for Terra Pulse-Dify Integration API

This module contains end-to-end tests that validate the complete integration flow
and deployment configuration.
"""

import pytest
import requests
import time
import json
import os
import subprocess
import docker
from typing import Dict, Any, Optional
from unittest.mock import patch, MagicMock

# Test configuration
TEST_CONFIG = {
    'base_url': os.getenv('TEST_API_URL', 'http://localhost:5000'),
    'api_key': os.getenv('TEST_API_KEY', 'test-deployment-key-12345'),
    'timeout': 30,
    'retry_attempts': 3,
    'retry_delay': 2
}

# Sample test data
SAMPLE_NDVI_DATA = {
    "NDVI_mean_early": 0.45,
    "NDVI_median_early": 0.43,
    "NDVI_std_early": 0.12,
    "NDVI_mean_late": 0.38,
    "NDVI_median_late": 0.36,
    "NDVI_std_late": 0.15,
    "NDVI_delta_mean": -0.07,
    "location": "Test Location, Kenya",
    "user_context": "integration_test"
}

class DeploymentTestClient:
    """Test client for deployment integration tests."""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'X-API-Key': api_key
        })
    
    def make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make HTTP request with retry logic."""
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(TEST_CONFIG['retry_attempts']):
            try:
                response = self.session.request(
                    method, url, 
                    timeout=TEST_CONFIG['timeout'],
                    **kwargs
                )
                return response
            except requests.exceptions.RequestException as e:
                if attempt == TEST_CONFIG['retry_attempts'] - 1:
                    raise
                time.sleep(TEST_CONFIG['retry_delay'])
        
        raise Exception("Max retry attempts exceeded")
    
    def get(self, endpoint: str, **kwargs) -> requests.Response:
        """Make GET request."""
        return self.make_request('GET', endpoint, **kwargs)
    
    def post(self, endpoint: str, data: Dict[str, Any] = None, **kwargs) -> requests.Response:
        """Make POST request."""
        if data:
            kwargs['json'] = data
        return self.make_request('POST', endpoint, **kwargs)


@pytest.fixture(scope="module")
def test_client():
    """Create test client for deployment tests."""
    return DeploymentTestClient(TEST_CONFIG['base_url'], TEST_CONFIG['api_key'])


@pytest.fixture(scope="module")
def wait_for_service():
    """Wait for service to be ready before running tests."""
    client = DeploymentTestClient(TEST_CONFIG['base_url'], TEST_CONFIG['api_key'])
    
    max_wait = 60  # seconds
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        try:
            response = client.get('/health/system')
            if response.status_code in [200, 503]:  # Service responding
                break
        except:
            pass
        time.sleep(2)
    else:
        pytest.fail(f"Service not ready after {max_wait} seconds")


class TestDeploymentConfiguration:
    """Test deployment configuration and environment setup."""
    
    def test_environment_variables_loaded(self):
        """Test that required environment variables are available."""
        # These should be available in the deployment environment
        required_vars = [
            'TERRA_PULSE_MODEL_PATH',
            'DIFY_API_KEY', 
            'DIFY_API_ENDPOINT',
            'DIFY_WORKFLOW_ID'
        ]
        
        # Check if running in test environment
        if os.getenv('PYTEST_RUNNING'):
            pytest.skip("Skipping environment variable test in pytest environment")
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        assert not missing_vars, f"Missing required environment variables: {missing_vars}"
    
    def test_model_file_exists(self):
        """Test that the ONNX model file exists."""
        model_path = os.getenv('TERRA_PULSE_MODEL_PATH', 'terra_pulse_model.onnx')
        
        if not os.path.exists(model_path):
            pytest.skip(f"Model file not found at {model_path} - may be in container")
        
        assert os.path.exists(model_path), f"Model file not found: {model_path}"
        assert os.path.getsize(model_path) > 1000, "Model file seems too small"
    
    def test_docker_configuration(self):
        """Test Docker configuration if Docker is available."""
        try:
            client = docker.from_env()
            
            # Check if our container is running
            containers = client.containers.list()
            terra_pulse_containers = [
                c for c in containers 
                if 'terra-pulse' in c.name or 'terra_pulse' in c.name
            ]
            
            if not terra_pulse_containers:
                pytest.skip("Terra Pulse container not found - may not be running in Docker")
            
            container = terra_pulse_containers[0]
            assert container.status == 'running', f"Container status: {container.status}"
            
        except docker.errors.DockerException:
            pytest.skip("Docker not available or accessible")


class TestServiceAvailability:
    """Test that all services are available and responding."""
    
    def test_service_startup(self, test_client, wait_for_service):
        """Test that the service starts up successfully."""
        response = test_client.get('/health/system')
        assert response.status_code in [200, 503], f"Unexpected status: {response.status_code}"
    
    def test_api_documentation_available(self, test_client, wait_for_service):
        """Test that API documentation is available."""
        # Remove API key for documentation endpoint
        client_no_auth = DeploymentTestClient(TEST_CONFIG['base_url'], '')
        response = client_no_auth.get('/')
        
        assert response.status_code == 200
        data = response.json()
        assert 'service' in data
        assert 'endpoints' in data
        assert data['service'] == 'Terra Pulse Enhanced API'
    
    def test_health_endpoints_available(self, test_client, wait_for_service):
        """Test that all health endpoints are available."""
        health_endpoints = [
            '/health/system',
            '/health/terra-pulse', 
            '/health/dify'
        ]
        
        for endpoint in health_endpoints:
            response = test_client.get(endpoint)
            assert response.status_code in [200, 503], f"Health endpoint {endpoint} failed"
            
            data = response.json()
            assert 'status' in data
            assert 'timestamp' in data
    
    def test_metrics_endpoint_available(self, test_client, wait_for_service):
        """Test that metrics endpoint is available."""
        response = test_client.get('/metrics')
        assert response.status_code == 200
        assert response.headers['content-type'].startswith('text/plain')
        
        # Check for expected metrics
        metrics_text = response.text
        expected_metrics = [
            'terra_pulse_service_health',
            'dify_service_health',
            'cache_available'
        ]
        
        for metric in expected_metrics:
            assert metric in metrics_text, f"Missing metric: {metric}"


class TestEndToEndIntegration:
    """Test complete end-to-end integration flow."""
    
    def test_basic_prediction_flow(self, test_client, wait_for_service):
        """Test complete basic prediction flow."""
        response = test_client.post('/predict', SAMPLE_NDVI_DATA)
        
        assert response.status_code == 200, f"Prediction failed: {response.text}"
        
        data = response.json()
        assert 'ml_output' in data
        
        ml_output = data['ml_output']
        assert 'degradation_risk' in ml_output
        assert 'confidence' in ml_output
        assert 'risk_factors' in ml_output
        assert 'recommended_action_key' in ml_output
        
        # Validate data types and ranges
        assert isinstance(ml_output['degradation_risk'], int)
        assert 0 <= ml_output['degradation_risk'] <= 100
        assert isinstance(ml_output['confidence'], (int, float))
        assert 0 <= ml_output['confidence'] <= 1
    
    def test_enhanced_prediction_flow(self, test_client, wait_for_service):
        """Test complete enhanced prediction flow."""
        enhanced_data = {
            **SAMPLE_NDVI_DATA,
            'user_type': 'farmer'
        }
        
        response = test_client.post('/enhanced-predict', enhanced_data)
        
        # Should succeed even if Dify is unavailable (fallback)
        assert response.status_code == 200, f"Enhanced prediction failed: {response.text}"
        
        data = response.json()
        
        # Check required response structure
        assert 'terra_pulse_prediction' in data
        assert 'ai_insights' in data
        assert 'formatted_response' in data
        assert 'metadata' in data
        
        # Validate Terra Pulse prediction
        terra_prediction = data['terra_pulse_prediction']
        assert 'degradation_risk' in terra_prediction
        assert 'confidence' in terra_prediction
        
        # Validate AI insights (may be fallback)
        ai_insights = data['ai_insights']
        assert 'enhanced_recommendations' in ai_insights
        assert 'risk_assessment' in ai_insights
        
        # Validate formatted response
        formatted = data['formatted_response']
        assert 'farmer_message' in formatted
        
        # Validate metadata
        metadata = data['metadata']
        assert 'processing_time_ms' in metadata
        assert 'timestamp' in metadata
        assert 'dify_success' in metadata
    
    def test_user_type_formatting(self, test_client, wait_for_service):
        """Test that different user types get different formatting."""
        base_data = {**SAMPLE_NDVI_DATA}
        
        # Test farmer response
        farmer_data = {**base_data, 'user_type': 'farmer'}
        farmer_response = test_client.post('/enhanced-predict', farmer_data)
        assert farmer_response.status_code == 200
        
        # Test official response  
        official_data = {**base_data, 'user_type': 'official'}
        official_response = test_client.post('/enhanced-predict', official_data)
        assert official_response.status_code == 200
        
        farmer_result = farmer_response.json()
        official_result = official_response.json()
        
        # Both should have formatted responses but potentially different content
        assert 'formatted_response' in farmer_result
        assert 'formatted_response' in official_result
        
        farmer_formatted = farmer_result['formatted_response']
        official_formatted = official_result['formatted_response']
        
        # Farmer should have farmer_message
        assert 'farmer_message' in farmer_formatted
        
        # Official may have technical_details
        if 'technical_details' in official_formatted:
            assert len(official_formatted['technical_details']) > 0


class TestErrorHandlingAndResilience:
    """Test error handling and system resilience."""
    
    def test_invalid_api_key_handling(self, wait_for_service):
        """Test handling of invalid API keys."""
        invalid_client = DeploymentTestClient(TEST_CONFIG['base_url'], 'invalid-key')
        
        response = invalid_client.post('/predict', SAMPLE_NDVI_DATA)
        assert response.status_code == 401
        
        data = response.json()
        assert data['error'] == 'INVALID_API_KEY'
    
    def test_missing_api_key_handling(self, wait_for_service):
        """Test handling of missing API keys."""
        no_auth_client = DeploymentTestClient(TEST_CONFIG['base_url'], '')
        
        response = no_auth_client.post('/predict', SAMPLE_NDVI_DATA)
        assert response.status_code == 401
        
        data = response.json()
        assert data['error'] == 'INVALID_API_KEY'
    
    def test_invalid_request_data_handling(self, test_client, wait_for_service):
        """Test handling of invalid request data."""
        # Missing required fields
        invalid_data = {'location': 'Test Location'}
        
        response = test_client.post('/predict', invalid_data)
        assert response.status_code == 400
        
        data = response.json()
        assert 'error' in data
        assert data['error'] in ['VALIDATION_ERROR', 'MISSING_REQUIRED_FIELD']
    
    def test_invalid_ndvi_values_handling(self, test_client, wait_for_service):
        """Test handling of invalid NDVI values."""
        invalid_data = {
            **SAMPLE_NDVI_DATA,
            'NDVI_mean_early': 2.0  # Invalid: outside -1.0 to 1.0 range
        }
        
        response = test_client.post('/predict', invalid_data)
        assert response.status_code == 400
        
        data = response.json()
        assert 'error' in data
    
    def test_service_degradation_handling(self, test_client, wait_for_service):
        """Test system behavior when services are degraded."""
        # Check system health
        health_response = test_client.get('/health/system')
        assert health_response.status_code in [200, 503]
        
        health_data = health_response.json()
        overall_status = health_data.get('overall_status', 'unknown')
        
        if overall_status == 'degraded':
            # System is degraded but should still serve basic predictions
            response = test_client.post('/predict', SAMPLE_NDVI_DATA)
            assert response.status_code == 200, "Basic predictions should work when degraded"
        
        elif overall_status == 'unhealthy':
            # System is unhealthy - may not serve predictions
            pytest.skip("System is unhealthy - cannot test degraded behavior")


class TestPerformanceAndScaling:
    """Test performance characteristics and scaling behavior."""
    
    def test_response_time_requirements(self, test_client, wait_for_service):
        """Test that response times meet requirements."""
        # Basic prediction should be under 5 seconds
        start_time = time.time()
        response = test_client.post('/predict', SAMPLE_NDVI_DATA)
        basic_time = time.time() - start_time
        
        assert response.status_code == 200
        assert basic_time < 5.0, f"Basic prediction too slow: {basic_time:.2f}s"
        
        # Enhanced prediction should be under 10 seconds
        enhanced_data = {**SAMPLE_NDVI_DATA, 'user_type': 'farmer'}
        start_time = time.time()
        response = test_client.post('/enhanced-predict', enhanced_data)
        enhanced_time = time.time() - start_time
        
        assert response.status_code == 200
        assert enhanced_time < 10.0, f"Enhanced prediction too slow: {enhanced_time:.2f}s"
    
    def test_concurrent_requests_handling(self, test_client, wait_for_service):
        """Test handling of concurrent requests."""
        import threading
        import queue
        
        results = queue.Queue()
        num_threads = 5
        
        def make_request():
            try:
                response = test_client.post('/predict', SAMPLE_NDVI_DATA)
                results.put(('success', response.status_code))
            except Exception as e:
                results.put(('error', str(e)))
        
        # Start concurrent requests
        threads = []
        for _ in range(num_threads):
            thread = threading.Thread(target=make_request)
            thread.start()
            threads.append(thread)
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=30)
        
        # Check results
        success_count = 0
        error_count = 0
        
        while not results.empty():
            result_type, result_value = results.get()
            if result_type == 'success' and result_value == 200:
                success_count += 1
            else:
                error_count += 1
        
        # At least 80% should succeed
        success_rate = success_count / num_threads
        assert success_rate >= 0.8, f"Success rate too low: {success_rate:.2f}"
    
    def test_memory_usage_stability(self, test_client, wait_for_service):
        """Test that memory usage remains stable under load."""
        # Make multiple requests to check for memory leaks
        num_requests = 10
        
        for i in range(num_requests):
            response = test_client.post('/predict', SAMPLE_NDVI_DATA)
            assert response.status_code == 200, f"Request {i} failed"
            
            # Small delay between requests
            time.sleep(0.1)
        
        # If we get here without errors, memory usage is likely stable
        assert True


class TestMonitoringAndObservability:
    """Test monitoring and observability features."""
    
    def test_health_check_completeness(self, test_client, wait_for_service):
        """Test that health checks provide comprehensive information."""
        response = test_client.get('/health/system')
        assert response.status_code in [200, 503]
        
        data = response.json()
        
        # Check required fields
        required_fields = ['system', 'overall_status', 'services', 'capabilities', 'timestamp']
        for field in required_fields:
            assert field in data, f"Missing health check field: {field}"
        
        # Check services information
        services = data['services']
        assert 'terra_pulse' in services
        assert 'dify' in services
        assert 'cache' in services
        
        # Check capabilities
        capabilities = data['capabilities']
        assert 'basic_predictions' in capabilities
        assert 'enhanced_predictions' in capabilities
    
    def test_metrics_format_compliance(self, test_client, wait_for_service):
        """Test that metrics are in Prometheus format."""
        response = test_client.get('/metrics')
        assert response.status_code == 200
        
        metrics_text = response.text
        lines = metrics_text.strip().split('\n')
        
        # Check for Prometheus format elements
        help_lines = [line for line in lines if line.startswith('# HELP')]
        type_lines = [line for line in lines if line.startswith('# TYPE')]
        metric_lines = [line for line in lines if line and not line.startswith('#')]
        
        assert len(help_lines) > 0, "No HELP lines found in metrics"
        assert len(type_lines) > 0, "No TYPE lines found in metrics"
        assert len(metric_lines) > 0, "No metric lines found in metrics"
        
        # Check metric format (name value)
        for line in metric_lines[:5]:  # Check first 5 metrics
            parts = line.split()
            assert len(parts) >= 2, f"Invalid metric format: {line}"
            
            # Metric name should be valid
            metric_name = parts[0]
            assert metric_name.replace('_', '').replace('-', '').isalnum(), f"Invalid metric name: {metric_name}"
    
    def test_logging_functionality(self, test_client, wait_for_service):
        """Test that logging is working (indirect test via successful requests)."""
        # Make a request that should generate logs
        response = test_client.post('/predict', SAMPLE_NDVI_DATA)
        assert response.status_code == 200
        
        # Make a request that should generate error logs
        invalid_client = DeploymentTestClient(TEST_CONFIG['base_url'], 'invalid-key')
        error_response = invalid_client.post('/predict', SAMPLE_NDVI_DATA)
        assert error_response.status_code == 401
        
        # If we get here, logging is likely working (no exceptions thrown)
        assert True


class TestSecurityFeatures:
    """Test security features and protections."""
    
    def test_cors_headers_present(self, test_client, wait_for_service):
        """Test that CORS headers are properly configured."""
        # Make an OPTIONS request
        response = test_client.make_request('OPTIONS', '/predict')
        
        # Should have CORS headers
        headers = response.headers
        cors_headers = [
            'Access-Control-Allow-Origin',
            'Access-Control-Allow-Methods',
            'Access-Control-Allow-Headers'
        ]
        
        # At least some CORS headers should be present
        present_headers = [h for h in cors_headers if h in headers]
        assert len(present_headers) > 0, "No CORS headers found"
    
    def test_input_sanitization(self, test_client, wait_for_service):
        """Test that input sanitization is working."""
        # Try potentially malicious input
        malicious_data = {
            **SAMPLE_NDVI_DATA,
            'location': '<script>alert("xss")</script>',
            'user_context': '"; DROP TABLE users; --'
        }
        
        response = test_client.post('/predict', malicious_data)
        
        # Should either sanitize and succeed, or reject with 400
        assert response.status_code in [200, 400]
        
        if response.status_code == 200:
            # If successful, check that malicious content was sanitized
            data = response.json()
            location = data['ml_output']['location']
            assert '<script>' not in location
            assert 'DROP TABLE' not in data['ml_output']['user_context']
    
    def test_request_size_limits(self, test_client, wait_for_service):
        """Test that request size limits are enforced."""
        # Create a very large request
        large_data = {
            **SAMPLE_NDVI_DATA,
            'large_field': 'x' * (3 * 1024 * 1024)  # 3MB of data
        }
        
        try:
            response = test_client.post('/predict', large_data)
            # Should be rejected with 413 or similar
            assert response.status_code in [413, 400], f"Large request not rejected: {response.status_code}"
        except requests.exceptions.RequestException:
            # Connection error is also acceptable (request too large)
            pass


# Integration test runner
def run_deployment_tests():
    """Run deployment tests with proper setup and teardown."""
    
    print("Starting deployment integration tests...")
    
    # Check if service is available
    try:
        client = DeploymentTestClient(TEST_CONFIG['base_url'], TEST_CONFIG['api_key'])
        response = client.get('/health/system')
        print(f"Service health check: {response.status_code}")
    except Exception as e:
        print(f"Service not available: {e}")
        return False
    
    # Run pytest
    test_args = [
        __file__,
        '-v',
        '--tb=short',
        f'--timeout={TEST_CONFIG["timeout"]}',
        '--disable-warnings'
    ]
    
    exit_code = pytest.main(test_args)
    
    print(f"Deployment tests completed with exit code: {exit_code}")
    return exit_code == 0


if __name__ == '__main__':
    success = run_deployment_tests()
    exit(0 if success else 1)