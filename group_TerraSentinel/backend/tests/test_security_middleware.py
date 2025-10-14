"""
Tests for security middleware functionality.
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from flask import Flask, request, jsonify
from werkzeug.test import Client
from werkzeug.wrappers import Response

from backend.services.security_middleware import (
    SecurityMiddleware, create_security_middleware, require_https, handle_options_request
)
from backend.services.exceptions import SecurityValidationException, ValidationException


class TestSecurityMiddleware:
    """Test cases for SecurityMiddleware class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        # Create test routes
        @self.app.route('/test', methods=['POST'])
        def test_route():
            return jsonify({'message': 'success'})
        
        @self.app.route('/test-get', methods=['GET'])
        def test_get_route():
            return jsonify({'message': 'success'})
        
        self.client = self.app.test_client()
    
    def test_middleware_initialization(self):
        """Test middleware initialization."""
        config = {
            'max_content_length': 2048,
            'max_request_time_seconds': 10
        }
        
        middleware = SecurityMiddleware(config=config)
        assert middleware.config == config
        
        # Test with app initialization
        middleware.init_app(self.app)
        assert self.app.config['MAX_CONTENT_LENGTH'] == 2048
    
    def test_request_size_limit(self):
        """Test request size limiting."""
        config = {'max_content_length': 100}  # Very small limit
        middleware = create_security_middleware(config)
        middleware.init_app(self.app)
        
        # Send request larger than limit
        large_data = 'x' * 200
        response = self.client.post('/test', 
                                  data=large_data,
                                  content_type='application/json')
        
        assert response.status_code == 413
        data = response.get_json()
        assert data['error'] == 'REQUEST_TOO_LARGE'
    
    def test_security_headers_added(self):
        """Test that security headers are added to responses."""
        middleware = create_security_middleware()
        middleware.init_app(self.app)
        
        response = self.client.get('/test-get')
        
        # Check for security headers
        assert 'X-Content-Type-Options' in response.headers
        assert response.headers['X-Content-Type-Options'] == 'nosniff'
        assert 'X-Frame-Options' in response.headers
        assert response.headers['X-Frame-Options'] == 'DENY'
        assert 'X-XSS-Protection' in response.headers
        assert 'Content-Security-Policy' in response.headers
    
    def test_cors_headers_added(self):
        """Test that CORS headers are added to responses."""
        config = {
            'cors': {
                'origins': ['http://localhost:3000'],
                'methods': ['GET', 'POST'],
                'headers': ['Content-Type', 'Authorization']
            }
        }
        
        middleware = create_security_middleware(config)
        middleware.init_app(self.app)
        
        # Test with allowed origin
        response = self.client.get('/test-get', 
                                 headers={'Origin': 'http://localhost:3000'})
        
        assert 'Access-Control-Allow-Origin' in response.headers
        assert response.headers['Access-Control-Allow-Origin'] == 'http://localhost:3000'
        assert 'Access-Control-Allow-Methods' in response.headers
        assert 'Access-Control-Allow-Headers' in response.headers
    
    def test_cors_origin_validation(self):
        """Test CORS origin validation."""
        config = {
            'cors': {
                'origins': ['http://localhost:3000']
            }
        }
        
        middleware = create_security_middleware(config)
        middleware.init_app(self.app)
        
        # Test with disallowed origin
        response = self.client.get('/test-get', 
                                 headers={'Origin': 'http://malicious-site.com'})
        
        # Should not include CORS headers for disallowed origin
        assert 'Access-Control-Allow-Origin' not in response.headers
    
    def test_suspicious_user_agent_detection(self):
        """Test detection of suspicious User-Agent strings."""
        middleware = create_security_middleware()
        middleware.init_app(self.app)
        
        suspicious_agents = ['sqlmap/1.0', 'nikto', 'nmap', 'masscan']
        
        for agent in suspicious_agents:
            response = self.client.post('/test',
                                      headers={'User-Agent': agent},
                                      json={'test': 'data'})
            
            assert response.status_code == 400
            data = response.get_json()
            assert data['error'] == 'SECURITY_VALIDATION_ERROR'
    
    def test_content_type_validation(self):
        """Test Content-Type validation for POST requests."""
        middleware = create_security_middleware()
        middleware.init_app(self.app)
        
        # Test with invalid Content-Type
        response = self.client.post('/test',
                                  data='test data',
                                  content_type='text/plain')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'Content-Type must be application/json' in data['message']
    
    def test_excessive_headers_detection(self):
        """Test detection of excessive headers."""
        middleware = create_security_middleware()
        middleware.init_app(self.app)
        
        # Create request with many headers
        headers = {f'X-Custom-Header-{i}': f'value{i}' for i in range(60)}
        headers['Content-Type'] = 'application/json'
        
        response = self.client.post('/test',
                                  headers=headers,
                                  json={'test': 'data'})
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'SECURITY_VALIDATION_ERROR'
    
    def test_oversized_header_detection(self):
        """Test detection of oversized headers."""
        middleware = create_security_middleware()
        middleware.init_app(self.app)
        
        # Create request with very large header
        large_header_value = 'x' * 10000
        response = self.client.post('/test',
                                  headers={
                                      'Content-Type': 'application/json',
                                      'X-Large-Header': large_header_value
                                  },
                                  json={'test': 'data'})
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'SECURITY_VALIDATION_ERROR'
    
    def test_suspicious_path_detection(self):
        """Test detection of suspicious request paths."""
        middleware = create_security_middleware()
        middleware.init_app(self.app)
        
        # Add route with path parameter for testing
        @self.app.route('/file/<path:filename>')
        def file_route(filename):
            return jsonify({'filename': filename})
        
        suspicious_paths = [
            '/file/../etc/passwd',
            '/file/..\\windows\\system32',
            '/file/<script>alert(1)</script>',
            '/file/javascript:alert(1)'
        ]
        
        for path in suspicious_paths:
            response = self.client.get(path)
            assert response.status_code == 400
    
    @patch('time.time')
    def test_request_timeout_detection(self, mock_time):
        """Test request timeout detection."""
        config = {'max_request_time_seconds': 1}
        middleware = create_security_middleware(config)
        middleware.init_app(self.app)
        
        # Mock time to simulate timeout
        mock_time.side_effect = [0, 2]  # Start at 0, check at 2 seconds
        
        response = self.client.post('/test', json={'test': 'data'})
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'SECURITY_VALIDATION_ERROR'


class TestRequireHTTPS:
    """Test cases for HTTPS enforcement decorator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        @self.app.route('/secure', methods=['POST'])
        @require_https
        def secure_route():
            return jsonify({'message': 'secure'})
        
        self.client = self.app.test_client()
    
    @patch('config.settings.get_config')
    def test_https_not_enforced_in_config(self, mock_get_config):
        """Test HTTPS not enforced when disabled in config."""
        mock_config = MagicMock()
        mock_config.enforce_https = False
        mock_get_config.return_value = mock_config
        
        response = self.client.post('/secure', json={'test': 'data'})
        assert response.status_code == 200
    
    @patch('config.settings.get_config')
    def test_https_enforced_in_production(self, mock_get_config):
        """Test HTTPS enforcement in production."""
        mock_config = MagicMock()
        mock_config.enforce_https = True
        mock_get_config.return_value = mock_config
        
        # Mock production environment
        with self.app.test_request_context('/secure', 
                                         environ_base={'SERVER_NAME': 'api.example.com'}):
            from flask import request
            # Mock non-secure request
            request.is_secure = False
            
            response = self.client.post('/secure', json={'test': 'data'})
            assert response.status_code == 426  # Upgrade Required
    
    @patch('config.settings.get_config')
    def test_https_allowed_in_development(self, mock_get_config):
        """Test HTTPS not enforced in development."""
        mock_config = MagicMock()
        mock_config.enforce_https = True
        mock_get_config.return_value = mock_config
        
        # Test with localhost (development)
        with self.app.test_request_context('/secure',
                                         environ_base={'SERVER_NAME': 'localhost'}):
            response = self.client.post('/secure', json={'test': 'data'})
            assert response.status_code == 200


class TestCORSHandling:
    """Test cases for CORS handling."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        @self.app.route('/api/test', methods=['GET', 'POST', 'OPTIONS'])
        def test_api():
            if request.method == 'OPTIONS':
                return handle_options_request()
            return jsonify({'message': 'success'})
        
        self.client = self.app.test_client()
    
    def test_options_request_handling(self):
        """Test handling of OPTIONS preflight requests."""
        config = {
            'cors': {
                'origins': ['http://localhost:3000'],
                'methods': ['GET', 'POST'],
                'headers': ['Content-Type']
            }
        }
        
        middleware = create_security_middleware(config)
        middleware.init_app(self.app)
        
        response = self.client.options('/api/test',
                                     headers={'Origin': 'http://localhost:3000'})
        
        assert response.status_code == 200
        assert 'Access-Control-Allow-Origin' in response.headers
    
    def test_cors_credentials_handling(self):
        """Test CORS credentials handling."""
        config = {
            'cors': {
                'origins': ['http://localhost:3000'],
                'allow_credentials': True
            }
        }
        
        middleware = create_security_middleware(config)
        middleware.init_app(self.app)
        
        response = self.client.get('/api/test',
                                 headers={'Origin': 'http://localhost:3000'})
        
        assert 'Access-Control-Allow-Credentials' in response.headers
        assert response.headers['Access-Control-Allow-Credentials'] == 'true'


class TestSecurityMiddlewareIntegration:
    """Integration tests for security middleware."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        # Create comprehensive test route
        @self.app.route('/api/predict', methods=['POST', 'OPTIONS'])
        @require_https
        def predict_route():
            if request.method == 'OPTIONS':
                return handle_options_request()
            return jsonify({'prediction': 'success'})
        
        self.client = self.app.test_client()
    
    @patch('config.settings.get_config')
    def test_full_security_pipeline(self, mock_get_config):
        """Test complete security pipeline."""
        mock_config = MagicMock()
        mock_config.enforce_https = False  # Disable for testing
        mock_get_config.return_value = mock_config
        
        config = {
            'max_content_length': 1024 * 1024,
            'cors': {
                'origins': ['http://localhost:3000'],
                'methods': ['POST', 'OPTIONS'],
                'headers': ['Content-Type', 'Authorization']
            }
        }
        
        middleware = create_security_middleware(config)
        middleware.init_app(self.app)
        
        # Test valid request
        response = self.client.post('/api/predict',
                                  headers={
                                      'Origin': 'http://localhost:3000',
                                      'Content-Type': 'application/json'
                                  },
                                  json={'ndvi_mean_early': 0.5})
        
        assert response.status_code == 200
        
        # Check security headers
        assert 'X-Content-Type-Options' in response.headers
        assert 'X-Frame-Options' in response.headers
        
        # Check CORS headers
        assert 'Access-Control-Allow-Origin' in response.headers
    
    def test_malicious_request_blocking(self):
        """Test blocking of malicious requests."""
        middleware = create_security_middleware()
        middleware.init_app(self.app)
        
        # Test with malicious User-Agent
        response = self.client.post('/api/predict',
                                  headers={
                                      'User-Agent': 'sqlmap/1.0',
                                      'Content-Type': 'application/json'
                                  },
                                  json={'test': 'data'})
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'SECURITY_VALIDATION_ERROR'
    
    def test_performance_under_load(self):
        """Test middleware performance under simulated load."""
        middleware = create_security_middleware()
        middleware.init_app(self.app)
        
        # Simulate multiple requests
        start_time = time.time()
        
        for i in range(10):
            response = self.client.get('/api/predict')
            # Requests should be processed quickly
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should process 10 requests in reasonable time (< 1 second)
        assert processing_time < 1.0


class TestSecurityConfiguration:
    """Test cases for security configuration."""
    
    def test_default_configuration(self):
        """Test default security configuration."""
        middleware = create_security_middleware()
        
        assert middleware.config['max_content_length'] == 1024 * 1024
        assert middleware.config['max_request_time_seconds'] == 30
        assert 'cors' in middleware.config
        assert 'security_headers' in middleware.config
    
    def test_custom_configuration_merge(self):
        """Test merging of custom configuration."""
        custom_config = {
            'max_content_length': 2048,
            'cors': {
                'origins': ['https://myapp.com']
            },
            'security_headers': {
                'X-Custom-Header': 'custom-value'
            }
        }
        
        middleware = create_security_middleware(custom_config)
        
        assert middleware.config['max_content_length'] == 2048
        assert 'https://myapp.com' in middleware.config['cors']['origins']
        assert middleware.config['security_headers']['X-Custom-Header'] == 'custom-value'
        # Default headers should still be present
        assert 'X-Content-Type-Options' in middleware.config['security_headers']
    
    def test_invalid_configuration_handling(self):
        """Test handling of invalid configuration."""
        # This should not raise an exception, invalid values should be ignored or use defaults
        invalid_config = {
            'max_content_length': 'invalid',
            'cors': 'not_a_dict'
        }
        
        middleware = create_security_middleware(invalid_config)
        # Should fall back to reasonable defaults
        assert isinstance(middleware.config['max_content_length'], int)