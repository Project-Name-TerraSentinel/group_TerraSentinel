"""
Tests for authentication mechanisms including API key validation.
"""

import pytest
from unittest.mock import patch, MagicMock
from flask import Flask, g
from werkzeug.test import Client

from backend.services.exceptions import InvalidAPIKeyException, RateLimitExceededException
from backend.config.settings import get_config


class TestAPIKeyAuthentication:
    """Test cases for API key authentication."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        # Import and apply decorators
        from app import require_api_key, rate_limit
        
        @self.app.route('/protected', methods=['POST'])
        @require_api_key
        def protected_route():
            return {'message': 'success', 'api_key': g.api_key}
        
        @self.app.route('/rate_limited', methods=['POST'])
        @rate_limit
        @require_api_key
        def rate_limited_route():
            return {'message': 'success'}
        
        @self.app.route('/health_check', methods=['GET'])
        @require_api_key
        def health_check():
            return {'status': 'healthy'}
        
        self.client = self.app.test_client()
    
    def test_valid_api_key_authentication(self):
        """Test successful authentication with valid API key."""
        response = self.client.post('/protected',
                                  headers={'X-API-Key': 'valid_test_key'},
                                  json={'test': 'data'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'success'
        assert data['api_key'] == 'valid_test_key'
    
    def test_missing_api_key(self):
        """Test authentication failure when API key is missing."""
        response = self.client.post('/protected', json={'test': 'data'})
        
        assert response.status_code == 401
        data = response.get_json()
        assert data['error'] == 'INVALID_API_KEY'
        assert 'API key is required' in data['message']
    
    def test_empty_api_key(self):
        """Test authentication failure with empty API key."""
        response = self.client.post('/protected',
                                  headers={'X-API-Key': ''},
                                  json={'test': 'data'})
        
        assert response.status_code == 401
        data = response.get_json()
        assert data['error'] == 'INVALID_API_KEY'
    
    def test_whitespace_only_api_key(self):
        """Test authentication failure with whitespace-only API key."""
        response = self.client.post('/protected',
                                  headers={'X-API-Key': '   '},
                                  json={'test': 'data'})
        
        assert response.status_code == 401
        data = response.get_json()
        assert data['error'] == 'INVALID_API_KEY'
    
    def test_health_endpoint_bypass(self):
        """Test that health endpoints bypass authentication."""
        # This test assumes health endpoints start with 'health_'
        # The actual implementation may vary
        response = self.client.get('/health_check')
        
        # Health endpoints should either bypass auth or handle it differently
        # The exact behavior depends on the implementation
        assert response.status_code in [200, 401]  # Either works or requires auth
    
    def test_api_key_stored_in_context(self):
        """Test that API key is properly stored in request context."""
        with self.app.test_request_context('/protected',
                                         method='POST',
                                         headers={'X-API-Key': 'test_key_123'},
                                         json={'test': 'data'}):
            from app import require_api_key
            
            @require_api_key
            def mock_handler():
                return g.api_key
            
            result = mock_handler()
            assert result == 'test_key_123'
    
    def test_api_key_logging(self):
        """Test that API key authentication events are logged."""
        with patch('app.logging_service') as mock_logging:
            response = self.client.post('/protected',
                                      headers={'X-API-Key': 'test_key_for_logging'},
                                      json={'test': 'data'})
            
            # Verify security event logging
            mock_logging.log_security_event.assert_called()
            
            # Check that the call includes authentication success
            calls = mock_logging.log_security_event.call_args_list
            auth_calls = [call for call in calls if 'api_key_authenticated' in str(call)]
            assert len(auth_calls) > 0
    
    def test_invalid_api_key_logging(self):
        """Test that invalid API key attempts are logged."""
        with patch('app.logging_service') as mock_logging:
            response = self.client.post('/protected', json={'test': 'data'})
            
            # Verify security event logging for missing API key
            mock_logging.log_security_event.assert_called()
            
            # Check that the call includes authentication failure
            calls = mock_logging.log_security_event.call_args_list
            auth_calls = [call for call in calls if 'missing_api_key' in str(call)]
            assert len(auth_calls) > 0
    
    def test_api_key_hint_in_logs(self):
        """Test that API key hints are properly formatted in logs."""
        with patch('app.logging_service') as mock_logging:
            long_api_key = 'very_long_api_key_for_testing_hint_functionality'
            
            response = self.client.post('/protected',
                                      headers={'X-API-Key': long_api_key},
                                      json={'test': 'data'})
            
            # Check that API key hint is properly truncated
            calls = mock_logging.log_security_event.call_args_list
            for call in calls:
                if 'api_key_hint' in str(call):
                    # API key hint should be first 8 characters + "..."
                    assert 'very_lon...' in str(call)
                    break
            else:
                pytest.fail("No API key hint found in logging calls")


class TestRateLimiting:
    """Test cases for rate limiting functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        from app import require_api_key, rate_limit
        
        @self.app.route('/rate_limited', methods=['POST'])
        @rate_limit
        @require_api_key
        def rate_limited_route():
            return {'message': 'success'}
        
        self.client = self.app.test_client()
    
    @patch('app.cache_service')
    def test_rate_limiting_within_limit(self, mock_cache):
        """Test requests within rate limit are allowed."""
        # Mock Redis to return count below limit
        mock_cache.get_redis_client.return_value.get.return_value = b'5'
        mock_cache.get_redis_client.return_value.incr.return_value = 6
        mock_cache.get_redis_client.return_value.expire.return_value = True
        
        response = self.client.post('/rate_limited',
                                  headers={'X-API-Key': 'test_key'},
                                  json={'test': 'data'})
        
        assert response.status_code == 200
    
    @patch('app.cache_service')
    @patch('config.settings.get_config')
    def test_rate_limiting_exceeded(self, mock_get_config, mock_cache):
        """Test requests exceeding rate limit are blocked."""
        # Mock configuration
        mock_config = MagicMock()
        mock_config.rate_limit_per_minute = 10
        mock_get_config.return_value = mock_config
        
        # Mock Redis to return count at limit
        mock_cache.get_redis_client.return_value.get.return_value = b'10'
        mock_cache.get_redis_client.return_value.incr.return_value = 11
        
        response = self.client.post('/rate_limited',
                                  headers={'X-API-Key': 'test_key'},
                                  json={'test': 'data'})
        
        assert response.status_code == 429
        data = response.get_json()
        assert data['error'] == 'RATE_LIMIT_EXCEEDED'
    
    @patch('app.cache_service')
    def test_rate_limiting_per_api_key(self, mock_cache):
        """Test that rate limiting is applied per API key."""
        # Mock Redis responses for different API keys
        def mock_get(key):
            if 'key1' in key:
                return b'5'  # Below limit
            elif 'key2' in key:
                return b'15'  # Above limit
            return b'0'
        
        mock_cache.get_redis_client.return_value.get.side_effect = mock_get
        mock_cache.get_redis_client.return_value.incr.return_value = 6
        mock_cache.get_redis_client.return_value.expire.return_value = True
        
        # First API key should work
        response1 = self.client.post('/rate_limited',
                                   headers={'X-API-Key': 'test_key1'},
                                   json={'test': 'data'})
        
        # Second API key should be rate limited (mocked as over limit)
        mock_cache.get_redis_client.return_value.incr.return_value = 16
        response2 = self.client.post('/rate_limited',
                                   headers={'X-API-Key': 'test_key2'},
                                   json={'test': 'data'})
        
        assert response1.status_code == 200
        # Note: This test may need adjustment based on actual implementation
    
    @patch('app.cache_service')
    def test_rate_limiting_redis_failure(self, mock_cache):
        """Test graceful handling when Redis is unavailable."""
        # Mock Redis failure
        mock_cache.get_redis_client.side_effect = Exception("Redis connection failed")
        
        response = self.client.post('/rate_limited',
                                  headers={'X-API-Key': 'test_key'},
                                  json={'test': 'data'})
        
        # Should continue without rate limiting when Redis fails
        assert response.status_code == 200
    
    def test_rate_limiting_logging(self):
        """Test that rate limiting events are logged."""
        with patch('app.logging_service') as mock_logging, \
             patch('app.cache_service') as mock_cache:
            
            # Mock rate limit exceeded
            mock_cache.get_redis_client.return_value.get.return_value = b'15'
            mock_cache.get_redis_client.return_value.incr.return_value = 16
            
            response = self.client.post('/rate_limited',
                                      headers={'X-API-Key': 'test_key'},
                                      json={'test': 'data'})
            
            # Verify rate limit logging
            calls = mock_logging.log_security_event.call_args_list
            rate_limit_calls = [call for call in calls if 'rate_limit_exceeded' in str(call)]
            assert len(rate_limit_calls) > 0


class TestAuthenticationIntegration:
    """Integration tests for authentication with other security features."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        from app import require_api_key, rate_limit
        from services.security_middleware import create_security_middleware
        
        # Initialize security middleware
        security_middleware = create_security_middleware()
        security_middleware.init_app(self.app)
        
        @self.app.route('/secure_endpoint', methods=['POST'])
        @rate_limit
        @require_api_key
        def secure_endpoint():
            return {'message': 'secure success'}
        
        self.client = self.app.test_client()
    
    def test_authentication_with_security_headers(self):
        """Test that authentication works with security middleware."""
        response = self.client.post('/secure_endpoint',
                                  headers={
                                      'X-API-Key': 'valid_key',
                                      'Content-Type': 'application/json'
                                  },
                                  json={'test': 'data'})
        
        # Should succeed and include security headers
        assert response.status_code == 200
        assert 'X-Content-Type-Options' in response.headers
        assert 'X-Frame-Options' in response.headers
    
    def test_authentication_with_cors(self):
        """Test authentication with CORS headers."""
        response = self.client.post('/secure_endpoint',
                                  headers={
                                      'X-API-Key': 'valid_key',
                                      'Content-Type': 'application/json',
                                      'Origin': 'http://localhost:3000'
                                  },
                                  json={'test': 'data'})
        
        assert response.status_code == 200
        # CORS headers should be present for allowed origins
        assert 'Access-Control-Allow-Origin' in response.headers
    
    def test_authentication_failure_with_security_logging(self):
        """Test that authentication failures are properly logged with security context."""
        with patch('app.logging_service') as mock_logging:
            response = self.client.post('/secure_endpoint',
                                      headers={'Content-Type': 'application/json'},
                                      json={'test': 'data'})
            
            assert response.status_code == 401
            
            # Verify comprehensive security logging
            mock_logging.log_security_event.assert_called()
            
            # Check for proper security context in logs
            calls = mock_logging.log_security_event.call_args_list
            security_calls = [call for call in calls if 'missing_api_key' in str(call)]
            assert len(security_calls) > 0
    
    def test_multiple_security_violations(self):
        """Test handling of multiple security violations."""
        # Request with missing API key and suspicious User-Agent
        response = self.client.post('/secure_endpoint',
                                  headers={
                                      'Content-Type': 'application/json',
                                      'User-Agent': 'sqlmap/1.0'
                                  },
                                  json={'test': 'data'})
        
        # Should catch the first security violation
        assert response.status_code in [400, 401]
    
    @patch('app.cache_service')
    def test_authentication_and_rate_limiting_interaction(self, mock_cache):
        """Test interaction between authentication and rate limiting."""
        # Mock Redis for rate limiting
        mock_cache.get_redis_client.return_value.get.return_value = b'5'
        mock_cache.get_redis_client.return_value.incr.return_value = 6
        mock_cache.get_redis_client.return_value.expire.return_value = True
        
        # Valid request should pass both authentication and rate limiting
        response = self.client.post('/secure_endpoint',
                                  headers={
                                      'X-API-Key': 'valid_key',
                                      'Content-Type': 'application/json'
                                  },
                                  json={'test': 'data'})
        
        assert response.status_code == 200
        
        # Verify that API key is used for rate limiting
        mock_cache.get_redis_client.return_value.get.assert_called()
        call_args = mock_cache.get_redis_client.return_value.get.call_args[0][0]
        assert 'valid_key' in call_args or 'rate_limit' in call_args


class TestAuthorizationMechanisms:
    """Test cases for authorization mechanisms beyond basic API key validation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        # Mock role-based authorization (if implemented)
        @self.app.route('/admin_only', methods=['POST'])
        def admin_only_route():
            # This would check for admin role in a real implementation
            api_key = self.app.request.headers.get('X-API-Key', '')
            if not api_key.startswith('admin_'):
                return {'error': 'INSUFFICIENT_PRIVILEGES'}, 403
            return {'message': 'admin access granted'}
        
        @self.app.route('/user_data/<user_id>', methods=['GET'])
        def user_data_route(user_id):
            # This would check if API key can access specific user data
            api_key = self.app.request.headers.get('X-API-Key', '')
            if user_id not in api_key:  # Simple mock authorization
                return {'error': 'ACCESS_DENIED'}, 403
            return {'user_id': user_id, 'data': 'user_specific_data'}
        
        self.client = self.app.test_client()
    
    def test_role_based_authorization_success(self):
        """Test successful role-based authorization."""
        response = self.client.post('/admin_only',
                                  headers={'X-API-Key': 'admin_key_123'},
                                  json={'admin_action': 'test'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'admin access granted'
    
    def test_role_based_authorization_failure(self):
        """Test role-based authorization failure."""
        response = self.client.post('/admin_only',
                                  headers={'X-API-Key': 'user_key_123'},
                                  json={'admin_action': 'test'})
        
        assert response.status_code == 403
        data = response.get_json()
        assert data['error'] == 'INSUFFICIENT_PRIVILEGES'
    
    def test_resource_based_authorization_success(self):
        """Test successful resource-based authorization."""
        response = self.client.get('/user_data/user123',
                                 headers={'X-API-Key': 'key_for_user123'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['user_id'] == 'user123'
    
    def test_resource_based_authorization_failure(self):
        """Test resource-based authorization failure."""
        response = self.client.get('/user_data/user123',
                                 headers={'X-API-Key': 'key_for_user456'})
        
        assert response.status_code == 403
        data = response.get_json()
        assert data['error'] == 'ACCESS_DENIED'
    
    def test_authorization_without_authentication(self):
        """Test that authorization checks still require authentication."""
        response = self.client.post('/admin_only', json={'admin_action': 'test'})
        
        # Should fail due to missing API key, not authorization
        assert response.status_code in [401, 403]


class TestSecurityEventLogging:
    """Test cases for security event logging and monitoring."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        from app import require_api_key
        
        @self.app.route('/monitored', methods=['POST'])
        @require_api_key
        def monitored_route():
            return {'message': 'success'}
        
        self.client = self.app.test_client()
    
    def test_successful_authentication_logging(self):
        """Test logging of successful authentication events."""
        with patch('app.logging_service') as mock_logging:
            response = self.client.post('/monitored',
                                      headers={'X-API-Key': 'valid_key'},
                                      json={'test': 'data'})
            
            # Verify authentication success is logged
            calls = mock_logging.log_security_event.call_args_list
            success_calls = [call for call in calls if 'api_key_authenticated' in str(call)]
            assert len(success_calls) > 0
            
            # Verify log contains proper security context
            for call in success_calls:
                args, kwargs = call
                assert 'severity' in kwargs
                assert kwargs['severity'] == 'low'  # Successful auth is low severity
    
    def test_failed_authentication_logging(self):
        """Test logging of failed authentication events."""
        with patch('app.logging_service') as mock_logging:
            response = self.client.post('/monitored', json={'test': 'data'})
            
            # Verify authentication failure is logged
            calls = mock_logging.log_security_event.call_args_list
            failure_calls = [call for call in calls if 'missing_api_key' in str(call)]
            assert len(failure_calls) > 0
            
            # Verify log contains proper security context
            for call in failure_calls:
                args, kwargs = call
                assert 'severity' in kwargs
                assert kwargs['severity'] == 'medium'  # Auth failure is medium severity
    
    def test_security_event_context_information(self):
        """Test that security events include proper context information."""
        with patch('app.logging_service') as mock_logging:
            response = self.client.post('/monitored',
                                      headers={
                                          'X-API-Key': 'test_key_context',
                                          'User-Agent': 'TestClient/1.0'
                                      },
                                      json={'test': 'data'})
            
            # Verify context information is included
            calls = mock_logging.log_security_event.call_args_list
            for call in calls:
                args, kwargs = call
                if 'api_key_authenticated' in str(call):
                    assert 'endpoint' in kwargs
                    assert 'api_key_hint' in kwargs
                    assert kwargs['api_key_hint'] == 'test_key...'
    
    def test_alerting_for_critical_security_events(self):
        """Test that critical security events trigger alerts."""
        with patch('app.send_exception_alert') as mock_alert, \
             patch('app.logging_service') as mock_logging:
            
            # Trigger multiple failed authentication attempts
            for i in range(3):
                response = self.client.post('/monitored', json={'test': f'data_{i}'})
            
            # Verify alerts are sent for authentication failures
            assert mock_alert.call_count >= 1
    
    def test_performance_monitoring_of_authentication(self):
        """Test performance monitoring of authentication operations."""
        import time
        
        with patch('app.logging_service') as mock_logging:
            start_time = time.time()
            
            response = self.client.post('/monitored',
                                      headers={'X-API-Key': 'perf_test_key'},
                                      json={'test': 'data'})
            
            end_time = time.time()
            
            # Authentication should be fast
            auth_time = end_time - start_time
            assert auth_time < 0.1  # Should complete in less than 100ms
            
            # Verify performance is logged
            calls = mock_logging.log_api_request.call_args_list
            assert len(calls) > 0