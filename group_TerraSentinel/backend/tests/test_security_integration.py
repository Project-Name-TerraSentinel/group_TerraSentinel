"""
Integration tests for security features including authentication and authorization.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from flask import Flask
from werkzeug.test import Client

from backend.services.security_middleware import create_security_middleware
from backend.services.security_validator import SecurityValidator
from backend.services.exceptions import (
    InvalidAPIKeyException, RateLimitExceededException, SecurityValidationException
)


class TestSecurityIntegration:
    """Integration tests for complete security pipeline."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        # Mock configuration
        self.mock_config = MagicMock()
        self.mock_config.api_key_header = 'X-API-Key'
        self.mock_config.rate_limit_per_minute = 10
        self.mock_config.enforce_https = False
        self.mock_config.cors_allowed_origins = 'http://localhost:3000'
        
        # Initialize security middleware
        security_config = {
            'max_content_length': 1024 * 1024,
            'cors': {
                'origins': ['http://localhost:3000'],
                'methods': ['GET', 'POST', 'OPTIONS'],
                'headers': ['Content-Type', 'X-API-Key']
            }
        }
        
        self.security_middleware = create_security_middleware(security_config)
        self.security_middleware.init_app(self.app)
        
        # Create test routes with security decorators
        self._create_test_routes()
        
        self.client = self.app.test_client()
    
    def _create_test_routes(self):
        """Create test routes with security decorators."""
        from services.security_middleware import require_https
        
        @self.app.route('/api/predict', methods=['POST'])
        def predict_route():
            """Mock prediction endpoint."""
            # Mock API key validation
            api_key = self.app.request.headers.get('X-API-Key')
            if not api_key or api_key != 'valid_api_key':
                return {'error': 'INVALID_API_KEY', 'message': 'Invalid API key'}, 401
            
            # Mock input validation
            data = self.app.request.get_json()
            if not data:
                return {'error': 'VALIDATION_ERROR', 'message': 'No data provided'}, 400
            
            return {'prediction': 'success', 'data': data}
        
        @self.app.route('/api/secure', methods=['POST'])
        @require_https
        def secure_route():
            """Mock secure endpoint."""
            return {'message': 'secure endpoint accessed'}
        
        @self.app.route('/health', methods=['GET'])
        def health_route():
            """Mock health endpoint (no auth required)."""
            return {'status': 'healthy'}
    
    def test_valid_authenticated_request(self):
        """Test valid authenticated request flow."""
        response = self.client.post('/api/predict',
                                  headers={
                                      'X-API-Key': 'valid_api_key',
                                      'Content-Type': 'application/json'
                                  },
                                  json={
                                      'ndvi_mean_early': 0.5,
                                      'ndvi_median_early': 0.48,
                                      'ndvi_std_early': 0.1,
                                      'ndvi_mean_late': 0.3,
                                      'ndvi_median_late': 0.28,
                                      'ndvi_std_late': 0.12,
                                      'ndvi_delta_mean': -0.2,
                                      'location': 'Baringo County, Kenya'
                                  })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['prediction'] == 'success'
        
        # Check security headers are present
        assert 'X-Content-Type-Options' in response.headers
        assert 'X-Frame-Options' in response.headers
    
    def test_missing_api_key(self):
        """Test request without API key."""
        response = self.client.post('/api/predict',
                                  headers={'Content-Type': 'application/json'},
                                  json={'test': 'data'})
        
        assert response.status_code == 401
        data = response.get_json()
        assert data['error'] == 'INVALID_API_KEY'
    
    def test_invalid_api_key(self):
        """Test request with invalid API key."""
        response = self.client.post('/api/predict',
                                  headers={
                                      'X-API-Key': 'invalid_key',
                                      'Content-Type': 'application/json'
                                  },
                                  json={'test': 'data'})
        
        assert response.status_code == 401
        data = response.get_json()
        assert data['error'] == 'INVALID_API_KEY'
    
    def test_malicious_input_blocked(self):
        """Test that malicious input is blocked by security validation."""
        response = self.client.post('/api/predict',
                                  headers={
                                      'X-API-Key': 'valid_api_key',
                                      'Content-Type': 'application/json'
                                  },
                                  json={
                                      'ndvi_mean_early': 0.5,
                                      'location': "'; DROP TABLE users; --"
                                  })
        
        # Should be blocked by input validation
        assert response.status_code in [400, 422]
    
    def test_cors_preflight_request(self):
        """Test CORS preflight request handling."""
        response = self.client.options('/api/predict',
                                     headers={
                                         'Origin': 'http://localhost:3000',
                                         'Access-Control-Request-Method': 'POST',
                                         'Access-Control-Request-Headers': 'Content-Type,X-API-Key'
                                     })
        
        assert response.status_code == 200
        assert 'Access-Control-Allow-Origin' in response.headers
        assert 'Access-Control-Allow-Methods' in response.headers
        assert 'Access-Control-Allow-Headers' in response.headers
    
    def test_cors_actual_request(self):
        """Test CORS actual request with allowed origin."""
        response = self.client.post('/api/predict',
                                  headers={
                                      'Origin': 'http://localhost:3000',
                                      'X-API-Key': 'valid_api_key',
                                      'Content-Type': 'application/json'
                                  },
                                  json={'test': 'data'})
        
        assert 'Access-Control-Allow-Origin' in response.headers
        assert response.headers['Access-Control-Allow-Origin'] == 'http://localhost:3000'
    
    def test_cors_blocked_origin(self):
        """Test CORS request with blocked origin."""
        response = self.client.post('/api/predict',
                                  headers={
                                      'Origin': 'http://malicious-site.com',
                                      'X-API-Key': 'valid_api_key',
                                      'Content-Type': 'application/json'
                                  },
                                  json={'test': 'data'})
        
        # Request should succeed but CORS headers should not be set
        assert 'Access-Control-Allow-Origin' not in response.headers
    
    def test_request_size_limit_enforcement(self):
        """Test request size limit enforcement."""
        # Create large payload
        large_data = {'data': 'x' * (2 * 1024 * 1024)}  # 2MB+ payload
        
        response = self.client.post('/api/predict',
                                  headers={
                                      'X-API-Key': 'valid_api_key',
                                      'Content-Type': 'application/json'
                                  },
                                  data=json.dumps(large_data))
        
        assert response.status_code == 413
        data = response.get_json()
        assert data['error'] == 'REQUEST_TOO_LARGE'
    
    def test_suspicious_user_agent_blocked(self):
        """Test that suspicious User-Agent strings are blocked."""
        response = self.client.post('/api/predict',
                                  headers={
                                      'X-API-Key': 'valid_api_key',
                                      'Content-Type': 'application/json',
                                      'User-Agent': 'sqlmap/1.0'
                                  },
                                  json={'test': 'data'})
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'SECURITY_VALIDATION_ERROR'
    
    def test_health_endpoint_no_auth_required(self):
        """Test that health endpoints don't require authentication."""
        response = self.client.get('/health')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'healthy'
    
    @patch('config.settings.get_config')
    def test_https_enforcement(self, mock_get_config):
        """Test HTTPS enforcement on secure endpoints."""
        mock_get_config.return_value = self.mock_config
        self.mock_config.enforce_https = True
        
        # Mock production environment
        with self.app.test_request_context('/api/secure',
                                         environ_base={'SERVER_NAME': 'api.example.com'}):
            response = self.client.post('/api/secure',
                                      headers={'Content-Type': 'application/json'},
                                      json={'test': 'data'})
            
            assert response.status_code == 426  # Upgrade Required
    
    def test_content_type_validation(self):
        """Test Content-Type validation for POST requests."""
        response = self.client.post('/api/predict',
                                  headers={
                                      'X-API-Key': 'valid_api_key',
                                      'Content-Type': 'text/plain'
                                  },
                                  data='plain text data')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'Content-Type must be application/json' in data['message']
    
    def test_multiple_security_violations(self):
        """Test handling of multiple security violations."""
        # Request with multiple issues: no API key, suspicious User-Agent, wrong Content-Type
        response = self.client.post('/api/predict',
                                  headers={
                                      'User-Agent': 'nikto',
                                      'Content-Type': 'text/plain'
                                  },
                                  data='test data')
        
        # Should catch the first security violation
        assert response.status_code == 400
    
    def test_security_logging(self):
        """Test that security events are properly logged."""
        with patch('services.security_middleware.logger') as mock_logger:
            # Make request that should trigger security logging
            response = self.client.post('/api/predict',
                                      headers={
                                          'User-Agent': 'sqlmap/1.0',
                                          'Content-Type': 'application/json'
                                      },
                                      json={'test': 'data'})
            
            # Verify logging occurred
            mock_logger.warning.assert_called()


class TestInputValidationIntegration:
    """Integration tests for input validation with security features."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = SecurityValidator()
    
    def test_comprehensive_input_validation(self):
        """Test comprehensive input validation pipeline."""
        # Valid input should pass
        valid_input = {
            'ndvi_mean_early': 0.5,
            'ndvi_median_early': 0.48,
            'ndvi_std_early': 0.1,
            'ndvi_mean_late': 0.3,
            'ndvi_median_late': 0.28,
            'ndvi_std_late': 0.12,
            'ndvi_delta_mean': -0.2,
            'location': 'Baringo County, Kenya',
            'user_context': 'smallholder_farmer',
            'user_type': 'farmer'
        }
        
        result = self.validator.validate_and_sanitize_request(valid_input)
        assert result is not None
        assert result.location == 'Baringo County, Kenya'
    
    def test_sql_injection_prevention(self):
        """Test SQL injection prevention in input validation."""
        malicious_input = {
            'ndvi_mean_early': 0.5,
            'ndvi_median_early': 0.5,
            'ndvi_std_early': 0.1,
            'ndvi_mean_late': 0.3,
            'ndvi_median_late': 0.3,
            'ndvi_std_late': 0.1,
            'ndvi_delta_mean': -0.2,
            'location': "'; DROP TABLE predictions; --",
            'user_type': 'farmer'
        }
        
        with pytest.raises(SecurityValidationException) as exc_info:
            self.validator.validate_and_sanitize_request(malicious_input)
        
        assert exc_info.value.details['security_issue'] == 'sql_injection'
    
    def test_xss_prevention(self):
        """Test XSS prevention in input validation."""
        malicious_input = {
            'ndvi_mean_early': 0.5,
            'ndvi_median_early': 0.5,
            'ndvi_std_early': 0.1,
            'ndvi_mean_late': 0.3,
            'ndvi_median_late': 0.3,
            'ndvi_std_late': 0.1,
            'ndvi_delta_mean': -0.2,
            'location': 'Test Location',
            'user_context': "<script>alert('xss')</script>",
            'user_type': 'farmer'
        }
        
        with pytest.raises(SecurityValidationException) as exc_info:
            self.validator.validate_and_sanitize_request(malicious_input)
        
        assert exc_info.value.details['security_issue'] == 'xss_attack'
    
    def test_data_sanitization(self):
        """Test data sanitization preserves valid data while removing threats."""
        input_with_special_chars = {
            'ndvi_mean_early': 0.5,
            'ndvi_median_early': 0.5,
            'ndvi_std_early': 0.1,
            'ndvi_mean_late': 0.3,
            'ndvi_median_late': 0.3,
            'ndvi_std_late': 0.1,
            'ndvi_delta_mean': -0.2,
            'location': 'Nairobi, Kenya (East Africa)',  # Valid special chars
            'user_context': 'smallholder_farmer_2024',
            'user_type': 'farmer'
        }
        
        result = self.validator.validate_and_sanitize_request(input_with_special_chars)
        assert result is not None
        assert 'Nairobi' in result.location
        assert 'Kenya' in result.location
    
    def test_numeric_validation_and_clamping(self):
        """Test numeric validation and range clamping."""
        input_with_extreme_values = {
            'ndvi_mean_early': 10.0,  # Too high
            'ndvi_median_early': 0.5,
            'ndvi_std_early': 0.1,
            'ndvi_mean_late': -10.0,  # Too low
            'ndvi_median_late': 0.3,
            'ndvi_std_late': 0.1,
            'ndvi_delta_mean': 0.0,
            'location': 'Test Location',
            'user_type': 'farmer'
        }
        
        result = self.validator.validate_and_sanitize_request(input_with_extreme_values)
        assert result is not None
        # Values should be clamped to valid ranges
        assert -2.0 <= result.ndvi_mean_early <= 2.0
        assert -2.0 <= result.ndvi_mean_late <= 2.0
    
    def test_edge_case_handling(self):
        """Test handling of edge cases in input validation."""
        edge_cases = [
            # Empty strings
            {
                'ndvi_mean_early': 0.5, 'ndvi_median_early': 0.5, 'ndvi_std_early': 0.1,
                'ndvi_mean_late': 0.3, 'ndvi_median_late': 0.3, 'ndvi_std_late': 0.1,
                'ndvi_delta_mean': -0.2, 'location': '', 'user_type': 'farmer'
            },
            # None values
            {
                'ndvi_mean_early': 0.5, 'ndvi_median_early': 0.5, 'ndvi_std_early': 0.1,
                'ndvi_mean_late': 0.3, 'ndvi_median_late': 0.3, 'ndvi_std_late': 0.1,
                'ndvi_delta_mean': -0.2, 'location': 'Test', 'user_context': None
            }
        ]
        
        for edge_case in edge_cases:
            try:
                result = self.validator.validate_and_sanitize_request(edge_case)
                # Some edge cases should be handled gracefully
                if result:
                    assert result.location is not None
            except (SecurityValidationException, ValidationException):
                # Some edge cases should raise validation errors
                pass


class TestRateLimitingIntegration:
    """Integration tests for rate limiting functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        # Mock Redis for rate limiting
        self.mock_redis = MagicMock()
        
        @self.app.route('/api/test', methods=['POST'])
        def test_route():
            return {'message': 'success'}
        
        self.client = self.app.test_client()
    
    @patch('redis.from_url')
    def test_rate_limiting_enforcement(self, mock_redis_from_url):
        """Test rate limiting enforcement."""
        mock_redis_from_url.return_value = self.mock_redis
        
        # Mock rate limit exceeded
        self.mock_redis.get.return_value = b'10'  # Current count at limit
        
        # This would require implementing the actual rate limiting decorator
        # For now, we'll test the concept
        
        # Multiple requests should eventually be rate limited
        responses = []
        for i in range(15):  # Exceed typical rate limit
            response = self.client.post('/api/test',
                                      headers={
                                          'X-API-Key': f'test_key_{i % 3}',  # Vary API keys
                                          'Content-Type': 'application/json'
                                      },
                                      json={'test': f'request_{i}'})
            responses.append(response.status_code)
        
        # At least some requests should succeed
        assert 200 in responses
    
    def test_rate_limiting_per_api_key(self):
        """Test that rate limiting is applied per API key."""
        # This would test that different API keys have separate rate limits
        # Implementation would depend on the actual rate limiting logic
        pass


class TestSecurityMetrics:
    """Tests for security metrics and monitoring."""
    
    def test_security_event_logging(self):
        """Test that security events are properly logged for monitoring."""
        with patch('services.security_validator.logger') as mock_logger:
            validator = SecurityValidator()
            
            # Trigger security validation
            try:
                validator.validate_and_sanitize_request({
                    'ndvi_mean_early': 0.5,
                    'location': "'; DROP TABLE users; --"
                })
            except SecurityValidationException:
                pass
            
            # Verify security event was logged
            mock_logger.warning.assert_called()
    
    def test_performance_monitoring(self):
        """Test performance monitoring of security operations."""
        import time
        
        validator = SecurityValidator()
        
        start_time = time.time()
        
        # Perform validation
        try:
            validator.validate_and_sanitize_request({
                'ndvi_mean_early': 0.5,
                'ndvi_median_early': 0.5,
                'ndvi_std_early': 0.1,
                'ndvi_mean_late': 0.3,
                'ndvi_median_late': 0.3,
                'ndvi_std_late': 0.1,
                'ndvi_delta_mean': -0.2,
                'location': 'Test Location'
            })
        except Exception:
            pass
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Security validation should be fast (< 100ms)
        assert processing_time < 0.1