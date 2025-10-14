"""
Tests for security validation and input sanitization.
"""

import pytest
from unittest.mock import patch, MagicMock
from backend.services.security_validator import (
    SecurityValidator, InputSanitizer, SecureEnhancedPredictionRequest,
    SecurityValidationException
)
from backend.services.exceptions import ValidationException


class TestInputSanitizer:
    """Test cases for InputSanitizer class."""
    
    def test_sanitize_string_normal_input(self):
        """Test sanitizing normal string input."""
        result = InputSanitizer.sanitize_string("Baringo County, Kenya")
        assert result == "Baringo County, Kenya"
    
    def test_sanitize_string_with_html(self):
        """Test sanitizing string with HTML content."""
        result = InputSanitizer.sanitize_string("Test <script>alert('xss')</script> Location")
        assert "<script>" not in result
        assert "alert" not in result
        assert "Test" in result
        assert "Location" in result
    
    def test_sanitize_string_sql_injection_detection(self):
        """Test detection of SQL injection patterns."""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'/**/OR/**/1=1",
            "UNION SELECT * FROM users",
        ]
        
        for malicious_input in malicious_inputs:
            with pytest.raises(SecurityValidationException) as exc_info:
                InputSanitizer.sanitize_string(malicious_input)
            assert exc_info.value.details['security_issue'] == 'sql_injection'
    
    def test_sanitize_string_xss_detection(self):
        """Test detection of XSS patterns."""
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img onerror='alert(1)' src='x'>",
            "<iframe src='javascript:alert(1)'></iframe>",
        ]
        
        for malicious_input in malicious_inputs:
            with pytest.raises(SecurityValidationException) as exc_info:
                InputSanitizer.sanitize_string(malicious_input)
            assert exc_info.value.details['security_issue'] == 'xss_attack'
    
    def test_sanitize_string_length_limit(self):
        """Test string length limiting."""
        long_string = "A" * 300
        result = InputSanitizer.sanitize_string(long_string, max_length=100)
        assert len(result) <= 100
    
    def test_sanitize_string_character_filtering(self):
        """Test character filtering with allowed patterns."""
        import re
        pattern = re.compile(r'^[a-zA-Z0-9\s\-\.,\(\)]+$')
        result = InputSanitizer.sanitize_string("Test@#$%Location", allowed_chars=pattern)
        assert "@#$%" not in result
        assert "Test" in result
        assert "Location" in result
    
    def test_sanitize_numeric_valid_input(self):
        """Test sanitizing valid numeric input."""
        assert InputSanitizer.sanitize_numeric("0.5") == 0.5
        assert InputSanitizer.sanitize_numeric(0.75) == 0.75
        assert InputSanitizer.sanitize_numeric(-0.25) == -0.25
    
    def test_sanitize_numeric_invalid_input(self):
        """Test sanitizing invalid numeric input."""
        with pytest.raises(ValidationException):
            InputSanitizer.sanitize_numeric("not_a_number")
        
        with pytest.raises(ValidationException):
            InputSanitizer.sanitize_numeric("NaN")
    
    def test_sanitize_numeric_range_clamping(self):
        """Test numeric range clamping."""
        result = InputSanitizer.sanitize_numeric(5.0, min_val=-1.0, max_val=1.0)
        assert result == 1.0
        
        result = InputSanitizer.sanitize_numeric(-5.0, min_val=-1.0, max_val=1.0)
        assert result == -1.0
    
    def test_sanitize_numeric_infinity_detection(self):
        """Test detection of infinity values."""
        with pytest.raises(ValidationException):
            InputSanitizer.sanitize_numeric(float('inf'))
        
        with pytest.raises(ValidationException):
            InputSanitizer.sanitize_numeric(float('-inf'))


class TestSecureEnhancedPredictionRequest:
    """Test cases for SecureEnhancedPredictionRequest model."""
    
    def test_valid_request(self):
        """Test validation of valid request data."""
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
    
    def test_ndvi_value_validation(self):
        """Test NDVI value validation and sanitization."""
        # Test out of range values
        data = {
            'ndvi_mean_early': 5.0,  # Too high
            'ndvi_median_early': 0.5,
            'ndvi_std_early': 0.1,
            'ndvi_mean_late': -5.0,  # Too low
            'ndvi_median_late': 0.3,
            'ndvi_std_late': 0.1,
            'ndvi_delta_mean': 0.0,
            'location': 'Test Location'
        }
        
        request = SecureEnhancedPredictionRequest(**data)
        # Values should be clamped to valid ranges
        assert -2.0 <= request.ndvi_mean_early <= 2.0
        assert -2.0 <= request.ndvi_mean_late <= 2.0
    
    def test_location_validation(self):
        """Test location validation and sanitization."""
        # Test empty location
        with pytest.raises(ValidationException):
            SecureEnhancedPredictionRequest(
                ndvi_mean_early=0.5, ndvi_median_early=0.5, ndvi_std_early=0.1,
                ndvi_mean_late=0.3, ndvi_median_late=0.3, ndvi_std_late=0.1,
                ndvi_delta_mean=-0.2, location=""
            )
        
        # Test location with special characters
        request = SecureEnhancedPredictionRequest(
            ndvi_mean_early=0.5, ndvi_median_early=0.5, ndvi_std_early=0.1,
            ndvi_mean_late=0.3, ndvi_median_late=0.3, ndvi_std_late=0.1,
            ndvi_delta_mean=-0.2, location="Test@#$Location"
        )
        # Special characters should be removed
        assert "@#$" not in request.location
    
    def test_user_type_validation(self):
        """Test user type validation."""
        # Test invalid user type
        request = SecureEnhancedPredictionRequest(
            ndvi_mean_early=0.5, ndvi_median_early=0.5, ndvi_std_early=0.1,
            ndvi_mean_late=0.3, ndvi_median_late=0.3, ndvi_std_late=0.1,
            ndvi_delta_mean=-0.2, location="Test Location", user_type="invalid"
        )
        # Should default to 'farmer'
        assert request.user_type == 'farmer'
    
    def test_ndvi_consistency_validation(self):
        """Test NDVI consistency validation."""
        # This should not raise an exception but may log warnings
        request = SecureEnhancedPredictionRequest(
            ndvi_mean_early=0.5, ndvi_median_early=0.5, ndvi_std_early=0.1,
            ndvi_mean_late=0.3, ndvi_median_late=0.3, ndvi_std_late=0.1,
            ndvi_delta_mean=-0.1,  # Inconsistent with calculated delta
            location="Test Location"
        )
        assert request is not None


class TestSecurityValidator:
    """Test cases for SecurityValidator class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = SecurityValidator()
    
    def test_validate_normal_request(self):
        """Test validation of normal request."""
        request_data = {
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
        
        result = self.validator.validate_and_sanitize_request(request_data)
        assert isinstance(result, SecureEnhancedPredictionRequest)
        assert result.location == 'Baringo County, Kenya'
    
    def test_oversized_request_detection(self):
        """Test detection of oversized requests."""
        # Create a very large request
        large_data = {
            'ndvi_mean_early': 0.5,
            'ndvi_median_early': 0.5,
            'ndvi_std_early': 0.1,
            'ndvi_mean_late': 0.3,
            'ndvi_median_late': 0.3,
            'ndvi_std_late': 0.1,
            'ndvi_delta_mean': -0.2,
            'location': 'A' * 10000,  # Very long location
        }
        
        with pytest.raises(SecurityValidationException) as exc_info:
            self.validator.validate_and_sanitize_request(large_data)
        assert exc_info.value.details['security_issue'] == 'oversized_request'
    
    def test_excessive_fields_detection(self):
        """Test detection of requests with too many fields."""
        # Create request with many fields
        excessive_data = {f'field_{i}': f'value_{i}' for i in range(60)}
        excessive_data.update({
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
            self.validator.validate_and_sanitize_request(excessive_data)
        assert exc_info.value.details['security_issue'] == 'excessive_fields'
    
    def test_deep_nesting_detection(self):
        """Test detection of deeply nested request structures."""
        # Create deeply nested structure
        nested_data = {'level1': {'level2': {'level3': {'level4': {'level5': {
            'level6': {'level7': {'level8': {'level9': {'level10': {'level11': 'deep'}}}}}}}}}}}
        nested_data.update({
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
            self.validator.validate_and_sanitize_request(nested_data)
        assert exc_info.value.details['security_issue'] == 'deep_nesting'
    
    def test_suspicious_data_patterns(self):
        """Test detection of suspicious data patterns."""
        # Test all identical NDVI values (potential fake data)
        suspicious_data = {
            'ndvi_mean_early': 0.5,
            'ndvi_median_early': 0.5,
            'ndvi_std_early': 0.1,
            'ndvi_mean_late': 0.5,
            'ndvi_median_late': 0.5,
            'ndvi_std_late': 0.1,
            'ndvi_delta_mean': 0.0,
            'location': 'Test Location'
        }
        
        # This should not raise an exception but may log warnings
        result = self.validator.validate_and_sanitize_request(suspicious_data)
        assert result is not None
    
    def test_test_location_detection(self):
        """Test detection of test/dummy locations."""
        test_data = {
            'ndvi_mean_early': 0.5,
            'ndvi_median_early': 0.5,
            'ndvi_std_early': 0.1,
            'ndvi_mean_late': 0.3,
            'ndvi_median_late': 0.3,
            'ndvi_std_late': 0.1,
            'ndvi_delta_mean': -0.2,
            'location': 'Test Location'
        }
        
        # This should not raise an exception but may log warnings
        result = self.validator.validate_and_sanitize_request(test_data)
        assert result is not None
    
    @patch('services.security_validator.logger')
    def test_logging_during_validation(self, mock_logger):
        """Test that appropriate logging occurs during validation."""
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
        
        self.validator.validate_and_sanitize_request(request_data)
        
        # Check that info logging occurred
        mock_logger.info.assert_called()


class TestSecurityValidatorIntegration:
    """Integration tests for security validator."""
    
    def test_malicious_request_handling(self):
        """Test handling of various malicious request patterns."""
        validator = SecurityValidator()
        
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
                validator.validate_and_sanitize_request(malicious_request)
    
    def test_edge_case_numeric_values(self):
        """Test handling of edge case numeric values."""
        validator = SecurityValidator()
        
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
            }
        ]
        
        for edge_case in edge_cases:
            # Should not raise exceptions, values should be clamped
            result = validator.validate_and_sanitize_request(edge_case)
            assert result is not None
            assert -2.0 <= result.ndvi_mean_early <= 2.0
    
    def test_unicode_and_special_characters(self):
        """Test handling of unicode and special characters."""
        validator = SecurityValidator()
        
        unicode_data = {
            'ndvi_mean_early': 0.5, 'ndvi_median_early': 0.5, 'ndvi_std_early': 0.1,
            'ndvi_mean_late': 0.3, 'ndvi_median_late': 0.3, 'ndvi_std_late': 0.1,
            'ndvi_delta_mean': -0.2, 'location': 'Nairobi, Kenya 🇰🇪'
        }
        
        result = validator.validate_and_sanitize_request(unicode_data)
        assert result is not None
        # Unicode characters should be handled appropriately
        assert result.location is not None