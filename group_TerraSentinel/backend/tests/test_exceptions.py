"""
Tests for custom exception classes and error handling.
"""

import pytest
from backend.services.exceptions import (
    BaseAPIException, ValidationException, InvalidNDVIDataException,
    MissingRequiredFieldException, AuthenticationException, InvalidAPIKeyException,
    RateLimitExceededException, ExternalServiceException, TerraPulseServiceException,
    DifyServiceException, DifyWorkflowException, NetworkException, TimeoutException,
    DataProcessingException, ModelPredictionException, DataTransformationException,
    ConfigurationException, CacheException, ErrorSeverity, ErrorCategory,
    format_error_response, is_retryable_error, should_alert
)


class TestBaseAPIException:
    """Test the base API exception class."""
    
    def test_basic_exception_creation(self):
        """Test basic exception creation with minimal parameters."""
        exc = BaseAPIException("Test error message")
        
        assert exc.message == "Test error message"
        assert exc.status_code == 500
        assert exc.category == ErrorCategory.INTERNAL
        assert exc.severity == ErrorSeverity.MEDIUM
        assert exc.details == {}
        assert exc.retry_after is None
        assert exc.alerting_required is False
        assert exc.error_code == "BASEAPIEXCEPTION"
    
    def test_exception_with_all_parameters(self):
        """Test exception creation with all parameters."""
        details = {"field": "value", "code": 123}
        
        exc = BaseAPIException(
            message="Detailed error message",
            user_message="User-friendly message",
            error_code="CUSTOM_ERROR",
            status_code=422,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.HIGH,
            details=details,
            retry_after=60,
            alerting_required=True
        )
        
        assert exc.message == "Detailed error message"
        assert exc.user_message == "User-friendly message"
        assert exc.error_code == "CUSTOM_ERROR"
        assert exc.status_code == 422
        assert exc.category == ErrorCategory.VALIDATION
        assert exc.severity == ErrorSeverity.HIGH
        assert exc.details == details
        assert exc.retry_after == 60
        assert exc.alerting_required is True
    
    def test_default_user_message_generation(self):
        """Test default user message generation based on status code."""
        # Test 4xx error
        exc_400 = BaseAPIException("Test error", status_code=400)
        assert "issue with your request" in exc_400.user_message
        
        # Test 5xx error
        exc_500 = BaseAPIException("Test error", status_code=500)
        assert "internal server error" in exc_500.user_message
        
        # Test other error
        exc_200 = BaseAPIException("Test error", status_code=200)
        assert "unexpected error" in exc_200.user_message
    
    def test_to_dict_conversion(self):
        """Test conversion to dictionary for JSON serialization."""
        exc = BaseAPIException(
            message="Test error",
            user_message="User message",
            error_code="TEST_ERROR",
            status_code=422,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.LOW,
            details={"field": "value"},
            retry_after=30
        )
        
        result = exc.to_dict()
        
        expected = {
            'error': 'TEST_ERROR',
            'message': 'User message',
            'details': {'field': 'value'},
            'category': 'validation',
            'severity': 'low',
            'retry_after_seconds': 30
        }
        
        assert result == expected
    
    def test_to_dict_without_retry_after(self):
        """Test to_dict without retry_after field."""
        exc = BaseAPIException("Test error")
        result = exc.to_dict()
        
        assert 'retry_after_seconds' not in result


class TestValidationExceptions:
    """Test validation-related exceptions."""
    
    def test_validation_exception(self):
        """Test basic validation exception."""
        validation_errors = ["Field1 is required", "Field2 is invalid"]
        
        exc = ValidationException(
            message="Validation failed",
            validation_errors=validation_errors
        )
        
        assert exc.message == "Validation failed"
        assert exc.status_code == 400
        assert exc.category == ErrorCategory.VALIDATION
        assert exc.severity == ErrorSeverity.LOW
        assert exc.details['validation_errors'] == validation_errors
    
    def test_invalid_ndvi_data_exception(self):
        """Test NDVI data validation exception."""
        exc = InvalidNDVIDataException(
            field="NDVI_mean_early",
            value=1.5,
            expected_range="-1.0 to 1.0"
        )
        
        assert "NDVI_mean_early" in exc.message
        assert "1.5" in exc.message
        assert exc.error_code == "INVALID_NDVI_DATA"
        assert exc.details['field'] == "NDVI_mean_early"
        assert exc.details['value'] == 1.5
        assert exc.details['expected_range'] == "-1.0 to 1.0"
        assert "Expected range: -1.0 to 1.0" in exc.user_message
    
    def test_missing_required_field_exception(self):
        """Test missing required fields exception."""
        missing_fields = ["field1", "field2", "field3"]
        
        exc = MissingRequiredFieldException(missing_fields)
        
        assert "field1, field2, field3" in exc.message
        assert "field1, field2, field3" in exc.user_message
        assert exc.error_code == "MISSING_REQUIRED_FIELDS"
        assert exc.details['missing_fields'] == missing_fields


class TestAuthenticationExceptions:
    """Test authentication-related exceptions."""
    
    def test_authentication_exception(self):
        """Test basic authentication exception."""
        exc = AuthenticationException()
        
        assert exc.status_code == 401
        assert exc.category == ErrorCategory.AUTHENTICATION
        assert exc.severity == ErrorSeverity.MEDIUM
        assert exc.alerting_required is True
        assert "Authentication required" in exc.user_message
    
    def test_invalid_api_key_exception(self):
        """Test invalid API key exception."""
        exc = InvalidAPIKeyException(api_key_hint="abc123...")
        
        assert "abc123..." in exc.message
        assert exc.error_code == "INVALID_API_KEY"
        assert exc.details['api_key_hint'] == "abc123..."
        assert "Invalid API key" in exc.user_message
    
    def test_rate_limit_exceeded_exception(self):
        """Test rate limit exceeded exception."""
        exc = RateLimitExceededException(
            limit=100,
            window="minute",
            retry_after=60
        )
        
        assert exc.status_code == 429
        assert exc.category == ErrorCategory.RATE_LIMITING
        assert exc.retry_after == 60
        assert exc.error_code == "RATE_LIMIT_EXCEEDED"
        assert exc.details['limit'] == 100
        assert exc.details['window'] == "minute"
        assert "100 per minute" in exc.user_message


class TestExternalServiceExceptions:
    """Test external service-related exceptions."""
    
    def test_external_service_exception(self):
        """Test basic external service exception."""
        exc = ExternalServiceException("TestService", "Connection failed")
        
        assert "TestService error: Connection failed" in exc.message
        assert exc.status_code == 502
        assert exc.category == ErrorCategory.EXTERNAL_SERVICE
        assert exc.severity == ErrorSeverity.HIGH
        assert exc.alerting_required is True
        assert exc.details['service'] == "TestService"
    
    def test_terra_pulse_service_exception(self):
        """Test Terra Pulse service exception."""
        exc = TerraPulseServiceException("Model loading failed")
        
        assert "Terra Pulse error: Model loading failed" in exc.message
        assert exc.error_code == "TERRA_PULSE_ERROR"
        assert "soil prediction service" in exc.user_message.lower()
    
    def test_dify_service_exception(self):
        """Test Dify service exception."""
        exc = DifyServiceException("API timeout")
        
        assert "Dify error: API timeout" in exc.message
        assert exc.error_code == "DIFY_ERROR"
        assert "AI enhancement service" in exc.user_message
    
    def test_dify_workflow_exception(self):
        """Test Dify workflow exception."""
        exc = DifyWorkflowException("workflow_123", "Execution failed")
        
        assert "Workflow workflow_123 failed: Execution failed" in exc.message
        assert exc.error_code == "DIFY_WORKFLOW_ERROR"
        assert exc.details['workflow_id'] == "workflow_123"


class TestNetworkExceptions:
    """Test network-related exceptions."""
    
    def test_network_exception(self):
        """Test basic network exception."""
        exc = NetworkException("Connection refused", service="TestService")
        
        assert exc.message == "Connection refused"
        assert exc.status_code == 503
        assert exc.category == ErrorCategory.NETWORK
        assert exc.severity == ErrorSeverity.HIGH
        assert exc.alerting_required is True
        assert exc.details['service'] == "TestService"
    
    def test_timeout_exception(self):
        """Test timeout exception."""
        exc = TimeoutException("DifyAPI", 30)
        
        assert "DifyAPI request timed out after 30 seconds" in exc.message
        assert exc.error_code == "REQUEST_TIMEOUT"
        assert exc.details['timeout_seconds'] == 30
        assert exc.details['service'] == "DifyAPI"
        assert "taking longer than expected" in exc.user_message


class TestDataProcessingExceptions:
    """Test data processing-related exceptions."""
    
    def test_data_processing_exception(self):
        """Test basic data processing exception."""
        exc = DataProcessingException(
            "Processing failed",
            processing_stage="validation"
        )
        
        assert exc.message == "Processing failed"
        assert exc.status_code == 422
        assert exc.category == ErrorCategory.DATA_PROCESSING
        assert exc.severity == ErrorSeverity.MEDIUM
        assert exc.details['processing_stage'] == "validation"
    
    def test_model_prediction_exception(self):
        """Test model prediction exception."""
        exc = ModelPredictionException("ONNX Model", "Invalid input shape")
        
        assert "ONNX Model prediction failed: Invalid input shape" in exc.message
        assert exc.error_code == "MODEL_PREDICTION_ERROR"
        assert exc.details['model_name'] == "ONNX Model"
        assert "Prediction model encountered an error" in exc.user_message
    
    def test_data_transformation_exception(self):
        """Test data transformation exception."""
        exc = DataTransformationException("json_to_dict", "Invalid JSON format")
        
        assert "Data transformation 'json_to_dict' failed: Invalid JSON format" in exc.message
        assert exc.error_code == "DATA_TRANSFORMATION_ERROR"
        assert exc.details['transformation'] == "json_to_dict"


class TestConfigurationExceptions:
    """Test configuration-related exceptions."""
    
    def test_configuration_exception(self):
        """Test configuration exception."""
        exc = ConfigurationException(
            "Missing API key",
            config_key="dify_api_key"
        )
        
        assert exc.message == "Missing API key"
        assert exc.status_code == 500
        assert exc.category == ErrorCategory.CONFIGURATION
        assert exc.severity == ErrorSeverity.CRITICAL
        assert exc.alerting_required is True
        assert exc.details['config_key'] == "dify_api_key"
        assert "configuration error" in exc.user_message.lower()
    
    def test_cache_exception(self):
        """Test cache exception."""
        exc = CacheException("Redis connection failed", operation="get")
        
        assert exc.message == "Redis connection failed"
        assert exc.status_code == 503
        assert exc.category == ErrorCategory.INTERNAL
        assert exc.severity == ErrorSeverity.MEDIUM
        assert exc.details['operation'] == "get"
        assert "Caching service temporarily unavailable" in exc.user_message


class TestExceptionUtilities:
    """Test exception utility functions."""
    
    def test_format_error_response(self):
        """Test error response formatting."""
        exc = ValidationException(
            "Test validation error",
            validation_errors=["field1 required"]
        )
        
        response_dict, status_code = format_error_response(exc)
        
        assert status_code == 400
        assert response_dict['error'] == 'VALIDATION_EXCEPTION'
        assert response_dict['category'] == 'validation'
        assert response_dict['severity'] == 'low'
    
    def test_is_retryable_error(self):
        """Test retryable error detection."""
        # Non-retryable errors
        validation_exc = ValidationException("Invalid input")
        auth_exc = AuthenticationException()
        rate_limit_exc = RateLimitExceededException(100, "minute")
        
        assert is_retryable_error(validation_exc) is False
        assert is_retryable_error(auth_exc) is False
        assert is_retryable_error(rate_limit_exc) is False
        
        # Retryable errors
        network_exc = NetworkException("Connection failed")
        service_exc = TerraPulseServiceException("Temporary failure")
        
        assert is_retryable_error(network_exc) is True
        assert is_retryable_error(service_exc) is True
        
        # Unknown exceptions (not retryable by default)
        generic_exc = Exception("Unknown error")
        assert is_retryable_error(generic_exc) is False
    
    def test_should_alert(self):
        """Test alerting requirement detection."""
        # Exceptions that should trigger alerts
        critical_exc = ConfigurationException("Critical config error")
        high_severity_exc = TerraPulseServiceException("Service down")
        explicit_alert_exc = BaseAPIException(
            "Test error",
            alerting_required=True,
            severity=ErrorSeverity.LOW
        )
        
        assert should_alert(critical_exc) is True
        assert should_alert(high_severity_exc) is True
        assert should_alert(explicit_alert_exc) is True
        
        # Exceptions that should not trigger alerts
        low_severity_exc = ValidationException("Minor validation error")
        medium_no_alert_exc = BaseAPIException(
            "Test error",
            severity=ErrorSeverity.MEDIUM,
            alerting_required=False
        )
        
        assert should_alert(low_severity_exc) is False
        assert should_alert(medium_no_alert_exc) is False
        
        # Unknown exceptions should trigger alerts
        generic_exc = Exception("Unknown error")
        assert should_alert(generic_exc) is True


class TestExceptionInheritance:
    """Test exception class inheritance and behavior."""
    
    def test_exception_inheritance_chain(self):
        """Test that custom exceptions inherit properly."""
        exc = ValidationException("Test error")
        
        assert isinstance(exc, BaseAPIException)
        assert isinstance(exc, Exception)
        
        # Test string representation
        assert str(exc) == "Test error"
    
    def test_exception_category_consistency(self):
        """Test that exception categories are consistent."""
        test_cases = [
            (ValidationException("test"), ErrorCategory.VALIDATION),
            (AuthenticationException(), ErrorCategory.AUTHENTICATION),
            (NetworkException("test"), ErrorCategory.NETWORK),
            (DataProcessingException("test"), ErrorCategory.DATA_PROCESSING),
            (ConfigurationException("test"), ErrorCategory.CONFIGURATION)
        ]
        
        for exc, expected_category in test_cases:
            assert exc.category == expected_category
    
    def test_exception_severity_consistency(self):
        """Test that exception severities are appropriate."""
        # Low severity exceptions
        low_severity_exceptions = [
            ValidationException("test"),
            RateLimitExceededException(100, "minute")
        ]
        
        for exc in low_severity_exceptions:
            assert exc.severity == ErrorSeverity.LOW
        
        # High severity exceptions
        high_severity_exceptions = [
            TerraPulseServiceException("test"),
            DifyServiceException("test"),
            NetworkException("test")
        ]
        
        for exc in high_severity_exceptions:
            assert exc.severity == ErrorSeverity.HIGH
        
        # Critical severity exceptions
        critical_exceptions = [
            ConfigurationException("test")
        ]
        
        for exc in critical_exceptions:
            assert exc.severity == ErrorSeverity.CRITICAL


if __name__ == '__main__':
    pytest.main([__file__])