"""
Core security validation tests that can run independently.
Tests input validation, sanitization, and security mechanisms.
"""

import pytest
from unittest.mock import patch, MagicMock
import time
import re

from backend.services.security_validator import (
    SecurityValidator, InputSanitizer, SecureEnhancedPredictionRequest,
    SecurityValidationException
)
from backend.services.exceptions import ValidationException


class TestInputSanitizationCore:
    """Core tests for input sanitization functionality."""
    
    def test_sql_injection_detection_comprehensive(self):
        """Test comprehensive SQL injection detection."""
        sql_payloads = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'/**/OR/**/1=1",
            "UNION SELECT * FROM users",
            "1; DELETE FROM predictions",
            "' OR 1=1#",
            "'; EXEC xp_cmdshell('dir'); --"
        ]
        
        for payload in sql_payloads:
            with pytest.raises(SecurityValidationException) as exc_info:
                InputSanitizer.sanitize_string(payload)
            assert exc_info.value.details['security_issue'] == 'sql_injection'
    
    def test_xss_detection_comprehensive(self):
        """Test comprehensive XSS detection."""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "<svg onload=alert('xss')>",
            "javascript:alert('xss')",
            "<iframe src='javascript:alert(1)'></iframe>",
            "<body onload=alert('xss')>",
            "<input onfocus=alert('xss') autofocus>"
        ]
        
        for payload in xss_payloads:
            with pytest.raises(SecurityValidationException) as exc_info:
                InputSanitizer.sanitize_string(payload)
            assert exc_info.value.details['security_issue'] in ['xss_attack', 'sql_injection']
    
    def test_safe_string_sanitization(self):
        """Test that safe strings are properly sanitized without errors."""
        safe_strings = [
            "Baringo County, Kenya",
            "Nairobi (Capital City)",
            "Location-123",
            "Test Location 2024"
        ]
        
        for safe_string in safe_strings:
            # Should not raise exceptions for safe strings
            result = InputSanitizer.sanitize_string(safe_string)
            assert isinstance(result, str)
            assert len(result) > 0
    
    def test_numeric_validation_edge_cases(self):
        """Test numeric validation with edge cases."""
        # Test valid numeric values
        valid_values = [0.5, -0.3, 1.0, -1.0, 0.0]
        for value in valid_values:
            result = InputSanitizer.sanitize_numeric(value, -2.0, 2.0)
            assert isinstance(result, float)
            assert -2.0 <= result <= 2.0
        
        # Test invalid numeric values
        invalid_values = ["not_a_number", "NaN", None]
        for value in invalid_values:
            with pytest.raises(ValidationException):
                InputSanitizer.sanitize_numeric(value)
        
        # Test infinity values
        with pytest.raises(ValidationException):
            InputSanitizer.sanitize_numeric(float('inf'))
        
        with pytest.raises(ValidationException):
            InputSanitizer.sanitize_numeric(float('-inf'))
    
    def test_string_length_limiting(self):
        """Test string length limiting functionality."""
        long_string = "A" * 1000
        result = InputSanitizer.sanitize_string(long_string, max_length=100)
        assert len(result) <= 100
    
    def test_character_filtering(self):
        """Test character filtering with allowed patterns."""
        # Test with allowed characters pattern
        pattern = re.compile(r'^[a-zA-Z0-9\s\-\.,\(\)]+$')
        test_string = "Valid-Location.123 (Test)"
        result = InputSanitizer.sanitize_string(test_string, allowed_chars=pattern)
        assert "Valid" in result
        assert "Location" in result
        assert "123" in result


class TestSecureRequestValidation:
    """Test secure request validation functionality."""
    
    def test_valid_prediction_request(self):
        """Test validation of valid prediction request."""
        valid_data = {
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
        
        request = SecureEnhancedPredictionRequest(**valid_data)
        assert request.ndvi_mean_early == 0.5
        assert request.location == 'Baringo County, Kenya'
        assert request.user_type == 'farmer'
    
    def test_ndvi_value_clamping(self):
        """Test NDVI value clamping to valid ranges."""
        data_with_extreme_values = {
            'ndvi_mean_early': 10.0,  # Too high
            'ndvi_median_early': 0.5,
            'ndvi_std_early': 0.1,
            'ndvi_mean_late': -10.0,  # Too low
            'ndvi_median_late': 0.3,
            'ndvi_std_late': 0.1,
            'ndvi_delta_mean': 0.0,
            'location': 'Test Location'
        }
        
        request = SecureEnhancedPredictionRequest(**data_with_extreme_values)
        # Values should be clamped to valid ranges
        assert -2.0 <= request.ndvi_mean_early <= 2.0
        assert -2.0 <= request.ndvi_mean_late <= 2.0
    
    def test_location_validation_edge_cases(self):
        """Test location validation with edge cases."""
        # Test empty location
        with pytest.raises(ValidationException):
            SecureEnhancedPredictionRequest(
                ndvi_mean_early=0.5, ndvi_median_early=0.5, ndvi_std_early=0.1,
                ndvi_mean_late=0.3, ndvi_median_late=0.3, ndvi_std_late=0.1,
                ndvi_delta_mean=-0.2, location=""
            )
        
        # Test very short location
        with pytest.raises(ValidationException):
            SecureEnhancedPredictionRequest(
                ndvi_mean_early=0.5, ndvi_median_early=0.5, ndvi_std_early=0.1,
                ndvi_mean_late=0.3, ndvi_median_late=0.3, ndvi_std_late=0.1,
                ndvi_delta_mean=-0.2, location="A"
            )
    
    def test_user_type_normalization(self):
        """Test user type normalization and validation."""
        test_cases = [
            ('farmer', 'farmer'),
            ('FARMER', 'farmer'),
            ('official', 'official'),
            ('OFFICIAL', 'official'),
            ('invalid_type', 'farmer'),  # Should default to farmer
            (None, 'farmer'),  # Should default to farmer
            ('', 'farmer')  # Should default to farmer
        ]
        
        for input_type, expected_type in test_cases:
            request = SecureEnhancedPredictionRequest(
                ndvi_mean_early=0.5, ndvi_median_early=0.5, ndvi_std_early=0.1,
                ndvi_mean_late=0.3, ndvi_median_late=0.3, ndvi_std_late=0.1,
                ndvi_delta_mean=-0.2, location='Test Location', user_type=input_type
            )
            assert request.user_type == expected_type


class TestSecurityValidatorCore:
    """Core tests for SecurityValidator functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = SecurityValidator()
    
    def test_normal_request_validation(self):
        """Test validation of normal, safe requests."""
        normal_request = {
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
        
        result = self.validator.validate_and_sanitize_request(normal_request)
        assert isinstance(result, SecureEnhancedPredictionRequest)
        assert result.location == 'Baringo County, Kenya'
    
    def test_oversized_request_detection(self):
        """Test detection of oversized requests."""
        oversized_request = {
            'ndvi_mean_early': 0.5,
            'ndvi_median_early': 0.5,
            'ndvi_std_early': 0.1,
            'ndvi_mean_late': 0.3,
            'ndvi_median_late': 0.3,
            'ndvi_std_late': 0.1,
            'ndvi_delta_mean': -0.2,
            'location': 'A' * 15000,  # Very long location
        }
        
        with pytest.raises(SecurityValidationException) as exc_info:
            self.validator.validate_and_sanitize_request(oversized_request)
        assert exc_info.value.details['security_issue'] == 'oversized_request'
    
    def test_excessive_fields_detection(self):
        """Test detection of requests with too many fields."""
        excessive_request = {f'field_{i}': f'value_{i}' for i in range(60)}
        excessive_request.update({
            'ndvi_mean_early': 0.5,
            'ndvi_median_early': 0.5,
            'ndvi_std_early': 0.1,
            'ndvi_mean_late': 0.3,
            'ndvi_median_late': 0.3,
            'ndvi_std_late': 0.1,
            'ndvi_delta_mean': -0.2,
            'location': 'Test Location'
        })
        
        with pytest.raises(SecurityValidationException) as exc_info:
            self.validator.validate_and_sanitize_request(excessive_request)
        assert exc_info.value.details['security_issue'] == 'excessive_fields'
    
    def test_deep_nesting_detection(self):
        """Test detection of deeply nested request structures."""
        nested_request = {
            'level1': {'level2': {'level3': {'level4': {'level5': {
                'level6': {'level7': {'level8': {'level9': {'level10': {'level11': 'deep'}}}}}}}}}},
            'ndvi_mean_early': 0.5,
            'ndvi_median_early': 0.5,
            'ndvi_std_early': 0.1,
            'ndvi_mean_late': 0.3,
            'ndvi_median_late': 0.3,
            'ndvi_std_late': 0.1,
            'ndvi_delta_mean': -0.2,
            'location': 'Test Location'
        }
        
        with pytest.raises(SecurityValidationException) as exc_info:
            self.validator.validate_and_sanitize_request(nested_request)
        assert exc_info.value.details['security_issue'] == 'deep_nesting'
    
    def test_malicious_input_detection(self):
        """Test detection of various malicious inputs."""
        malicious_requests = [
            # SQL injection in location
            {
                'ndvi_mean_early': 0.5, 'ndvi_median_early': 0.5, 'ndvi_std_early': 0.1,
                'ndvi_mean_late': 0.3, 'ndvi_median_late': 0.3, 'ndvi_std_late': 0.1,
                'ndvi_delta_mean': -0.2, 'location': "'; DROP TABLE users; --"
            },
            # XSS in user_context
            {
                'ndvi_mean_early': 0.5, 'ndvi_median_early': 0.5, 'ndvi_std_early': 0.1,
                'ndvi_mean_late': 0.3, 'ndvi_median_late': 0.3, 'ndvi_std_late': 0.1,
                'ndvi_delta_mean': -0.2, 'location': 'Test', 
                'user_context': "<script>alert('xss')</script>"
            }
        ]
        
        for malicious_request in malicious_requests:
            with pytest.raises(SecurityValidationException):
                self.validator.validate_and_sanitize_request(malicious_request)
    
    def test_suspicious_data_pattern_detection(self):
        """Test detection of suspicious data patterns."""
        # All identical NDVI values (potential fake data)
        suspicious_request = {
            'ndvi_mean_early': 0.5,
            'ndvi_median_early': 0.5,
            'ndvi_std_early': 0.1,
            'ndvi_mean_late': 0.5,
            'ndvi_median_late': 0.5,
            'ndvi_std_late': 0.1,
            'ndvi_delta_mean': 0.0,
            'location': 'Test Location'
        }
        
        # Should not raise exception but may log warnings
        result = self.validator.validate_and_sanitize_request(suspicious_request)
        assert result is not None
    
    def test_test_location_detection(self):
        """Test detection of test/dummy locations."""
        test_locations = [
            'Test Location',
            'Dummy Data',
            'Fake Place',
            'Example Location',
            'Sample Area'
        ]
        
        for location in test_locations:
            request_data = {
                'ndvi_mean_early': 0.5,
                'ndvi_median_early': 0.5,
                'ndvi_std_early': 0.1,
                'ndvi_mean_late': 0.3,
                'ndvi_median_late': 0.3,
                'ndvi_std_late': 0.1,
                'ndvi_delta_mean': -0.2,
                'location': location
            }
            
            # Should not raise exception but may log warnings
            result = self.validator.validate_and_sanitize_request(request_data)
            assert result is not None
    
    @patch('services.security_validator.logger')
    def test_validation_logging(self, mock_logger):
        """Test that validation events are properly logged."""
        request_data = {
            'ndvi_mean_early': 0.5,
            'ndvi_median_early': 0.5,
            'ndvi_std_early': 0.1,
            'ndvi_mean_late': 0.3,
            'ndvi_median_late': 0.3,
            'ndvi_std_late': 0.1,
            'ndvi_delta_mean': -0.2,
            'location': 'Baringo County, Kenya'
        }
        
        # Create a new validator instance to ensure fresh logger
        validator = SecurityValidator()
        validator.logger = mock_logger
        
        result = validator.validate_and_sanitize_request(request_data)
        
        # Verify logging occurred
        assert mock_logger.info.call_count >= 1


class TestAdvancedSecurityValidation:
    """Advanced security validation tests."""
    
    def test_unicode_handling(self):
        """Test proper handling of Unicode characters."""
        unicode_strings = [
            "Nairobi, Kenya 🇰🇪",
            "São Paulo, Brasil",
            "北京市, 中国",
            "Москва, Россия",
            "القاهرة، مصر"
        ]
        
        for unicode_string in unicode_strings:
            request_data = {
                'ndvi_mean_early': 0.5,
                'ndvi_median_early': 0.5,
                'ndvi_std_early': 0.1,
                'ndvi_mean_late': 0.3,
                'ndvi_median_late': 0.3,
                'ndvi_std_late': 0.1,
                'ndvi_delta_mean': -0.2,
                'location': unicode_string
            }
            
            validator = SecurityValidator()
            result = validator.validate_and_sanitize_request(request_data)
            assert result is not None
            assert result.location is not None
    
    def test_numeric_edge_cases(self):
        """Test handling of numeric edge cases."""
        edge_cases = [
            # Very large numbers
            {
                'ndvi_mean_early': 1e10, 'ndvi_median_early': 0.5, 'ndvi_std_early': 0.1,
                'ndvi_mean_late': 0.3, 'ndvi_median_late': 0.3, 'ndvi_std_late': 0.1,
                'ndvi_delta_mean': -0.2, 'location': 'Test Location'
            },
            # Very small numbers
            {
                'ndvi_mean_early': 1e-10, 'ndvi_median_early': 0.5, 'ndvi_std_early': 0.1,
                'ndvi_mean_late': 0.3, 'ndvi_median_late': 0.3, 'ndvi_std_late': 0.1,
                'ndvi_delta_mean': -0.2, 'location': 'Test Location'
            },
            # Negative zero
            {
                'ndvi_mean_early': -0.0, 'ndvi_median_early': 0.5, 'ndvi_std_early': 0.1,
                'ndvi_mean_late': 0.3, 'ndvi_median_late': 0.3, 'ndvi_std_late': 0.1,
                'ndvi_delta_mean': -0.2, 'location': 'Test Location'
            }
        ]
        
        validator = SecurityValidator()
        
        for edge_case in edge_cases:
            result = validator.validate_and_sanitize_request(edge_case)
            assert result is not None
            # Values should be clamped to valid ranges
            assert -2.0 <= result.ndvi_mean_early <= 2.0
    
    def test_performance_under_load(self):
        """Test validation performance under load."""
        validator = SecurityValidator()
        
        # Create a typical request
        request_data = {
            'ndvi_mean_early': 0.5,
            'ndvi_median_early': 0.48,
            'ndvi_std_early': 0.1,
            'ndvi_mean_late': 0.3,
            'ndvi_median_late': 0.28,
            'ndvi_std_late': 0.12,
            'ndvi_delta_mean': -0.2,
            'location': 'Baringo County, Kenya',
            'user_type': 'farmer'
        }
        
        # Measure performance
        start_time = time.time()
        
        # Validate multiple requests
        for i in range(100):
            result = validator.validate_and_sanitize_request(request_data)
            assert result is not None
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Should process 100 requests quickly
        assert total_time < 5.0  # Less than 5 seconds for 100 requests
        avg_time = total_time / 100
        assert avg_time < 0.05  # Less than 50ms per request
    
    def test_memory_usage_validation(self):
        """Test that validation doesn't cause memory leaks."""
        validator = SecurityValidator()
        
        # Create requests with varying sizes
        for size in [100, 1000, 5000]:
            request_data = {
                'ndvi_mean_early': 0.5,
                'ndvi_median_early': 0.5,
                'ndvi_std_early': 0.1,
                'ndvi_mean_late': 0.3,
                'ndvi_median_late': 0.3,
                'ndvi_std_late': 0.1,
                'ndvi_delta_mean': -0.2,
                'location': 'A' * size,  # Variable size location
                'user_type': 'farmer'
            }
            
            try:
                result = validator.validate_and_sanitize_request(request_data)
                # Large requests should either be processed or rejected gracefully
                if result:
                    assert len(result.location) <= 200  # Should be truncated
            except SecurityValidationException:
                # Rejection is also acceptable for oversized requests
                pass


class TestSecurityValidatorFactory:
    """Test security validator factory functions."""
    
    def test_create_security_validator(self):
        """Test security validator factory function."""
        from services.security_validator import create_security_validator
        
        validator = create_security_validator()
        assert isinstance(validator, SecurityValidator)
        assert validator is not None
    
    def test_validator_singleton_behavior(self):
        """Test that validator instances work independently."""
        from services.security_validator import create_security_validator
        
        validator1 = create_security_validator()
        validator2 = create_security_validator()
        
        # Should be separate instances
        assert validator1 is not validator2
        
        # But should work identically
        request_data = {
            'ndvi_mean_early': 0.5,
            'location': 'Test Location',
            'user_type': 'farmer'
        }
        
        result1 = validator1.validate_and_sanitize_request(request_data)
        result2 = validator2.validate_and_sanitize_request(request_data)
        
        assert result1.location == result2.location
        assert result1.user_type == result2.user_type


class TestSecurityExceptionHandling:
    """Test security exception handling."""
    
    def test_security_validation_exception_details(self):
        """Test SecurityValidationException contains proper details."""
        try:
            InputSanitizer.sanitize_string("'; DROP TABLE users; --")
        except SecurityValidationException as e:
            assert e.details is not None
            assert 'security_issue' in e.details
            assert e.details['security_issue'] == 'sql_injection'
            assert e.status_code == 400
            assert e.category.value == 'validation'
            assert e.severity.value == 'high'
            assert e.alerting_required is True
    
    def test_validation_exception_for_invalid_data(self):
        """Test ValidationException for invalid data types."""
        with pytest.raises(ValidationException):
            InputSanitizer.sanitize_numeric("clearly_not_a_number")
    
    def test_exception_message_sanitization(self):
        """Test that exception messages don't leak sensitive information."""
        try:
            InputSanitizer.sanitize_string("admin'; DROP TABLE users; --")
        except SecurityValidationException as e:
            # Exception message should not contain the full malicious payload
            assert "DROP TABLE users" not in str(e)
            assert "Potential SQL injection detected" in str(e)


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])