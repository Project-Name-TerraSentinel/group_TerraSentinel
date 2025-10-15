"""
Custom exception classes for Terra Pulse-Dify integration.
Provides structured error handling with appropriate HTTP status codes and user-friendly messages.
"""

from typing import Dict, Any, Optional, List
from enum import Enum


class ErrorSeverity(Enum):
    """Error severity levels for alerting and logging."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Categories of errors for better classification and handling."""
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    RATE_LIMITING = "rate_limiting"
    EXTERNAL_SERVICE = "external_service"
    INTERNAL = "internal"
    CONFIGURATION = "configuration"
    NETWORK = "network"
    DATA_PROCESSING = "data_processing"


class BaseAPIException(Exception):
    """
    Base exception class for all API-related errors.
    Provides structured error information for consistent error handling.
    """
    
    def __init__(
        self,
        message: str,
        user_message: str = None,
        error_code: str = None,
        status_code: int = 500,
        category: ErrorCategory = ErrorCategory.INTERNAL,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        details: Dict[str, Any] = None,
        retry_after: Optional[int] = None,
        alerting_required: bool = False
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code  # Set this first
        self.category = category
        self.severity = severity
        self.details = details or {}
        self.retry_after = retry_after
        self.alerting_required = alerting_required
        self.user_message = user_message or self._get_default_user_message()
        self.error_code = error_code or self._get_default_error_code()
    
    def _get_default_user_message(self) -> str:
        """Get default user-friendly message based on status code."""
        if self.status_code >= 500:
            return "An internal server error occurred. Please try again later."
        elif self.status_code >= 400:
            return "There was an issue with your request. Please check your input and try again."
        else:
            return "An unexpected error occurred."
    
    def _get_default_error_code(self) -> str:
        """Get default error code based on exception class name."""
        return self.__class__.__name__.replace('Exception', '').upper()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON serialization."""
        error_dict = {
            'error': self.error_code,
            'message': self.user_message,
            'details': self.details,
            'category': self.category.value,
            'severity': self.severity.value
        }
        
        if self.retry_after:
            error_dict['retry_after_seconds'] = self.retry_after
        
        return error_dict


# Validation Exceptions
class ValidationException(BaseAPIException):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, validation_errors: List[str] = None, **kwargs):
        super().__init__(
            message=message,
            status_code=400,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.LOW,
            **kwargs
        )
        if validation_errors:
            self.details['validation_errors'] = validation_errors


class InvalidNDVIDataException(ValidationException):
    """Raised when NDVI data is invalid or out of range."""
    
    def __init__(self, field: str, value: Any, expected_range: str = None):
        message = f"Invalid NDVI data for field '{field}': {value}"
        user_message = f"Invalid NDVI value for {field}. Please check your satellite data."
        
        details = {'field': field, 'value': value}
        if expected_range:
            details['expected_range'] = expected_range
            user_message += f" Expected range: {expected_range}"
        
        super().__init__(
            message=message,
            error_code="INVALID_NDVI_DATA",
            user_message=user_message
        )
        # Update details after initialization
        self.details.update(details)


class MissingRequiredFieldException(ValidationException):
    """Raised when required fields are missing from request."""
    
    def __init__(self, fields: List[str]):
        field_list = ", ".join(fields)
        message = f"Missing required fields: {field_list}"
        user_message = f"Required fields are missing: {field_list}"
        
        super().__init__(
            message=message,
            user_message=user_message,
            error_code="MISSING_REQUIRED_FIELDS",
            details={'missing_fields': fields}
        )


# Authentication and Authorization Exceptions
class AuthenticationException(BaseAPIException):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(
            message=message,
            user_message="Authentication required. Please provide a valid API key.",
            status_code=401,
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.MEDIUM,
            alerting_required=True,
            **kwargs
        )


class InvalidAPIKeyException(AuthenticationException):
    """Raised when API key is invalid."""
    
    def __init__(self, api_key_hint: str = None):
        message = f"Invalid API key: {api_key_hint}" if api_key_hint else "Invalid API key"
        
        super().__init__(
            message=message,
            user_message="Invalid API key provided. Please check your credentials.",
            error_code="INVALID_API_KEY",
            details={'api_key_hint': api_key_hint} if api_key_hint else {}
        )


class RateLimitExceededException(BaseAPIException):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, limit: int, window: str = "minute", retry_after: int = 60):
        message = f"Rate limit exceeded: {limit} requests per {window}"
        user_message = f"Too many requests. Limit: {limit} per {window}. Please try again later."
        
        super().__init__(
            message=message,
            user_message=user_message,
            status_code=429,
            category=ErrorCategory.RATE_LIMITING,
            severity=ErrorSeverity.LOW,
            error_code="RATE_LIMIT_EXCEEDED",
            retry_after=retry_after,
            details={'limit': limit, 'window': window}
        )


# External Service Exceptions
class ExternalServiceException(BaseAPIException):
    """Base class for external service errors."""
    
    def __init__(self, service_name: str, message: str, **kwargs):
        super().__init__(
            message=f"{service_name} error: {message}",
            user_message="External service temporarily unavailable. Please try again later.",
            status_code=502,
            category=ErrorCategory.EXTERNAL_SERVICE,
            severity=ErrorSeverity.HIGH,
            alerting_required=True,
            details={'service': service_name},
            **kwargs
        )


class TerraPulseServiceException(ExternalServiceException):
    """Raised when Terra Pulse service encounters an error."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            service_name="Terra Pulse",
            message=message,
            error_code="TERRA_PULSE_ERROR",
            **kwargs
        )
        # Override the user message after initialization
        self.user_message = "Soil prediction service is temporarily unavailable. Please try again later."


class DifyServiceException(ExternalServiceException):
    """Raised when Dify service encounters an error."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            service_name="Dify",
            message=message,
            error_code="DIFY_ERROR",
            **kwargs
        )
        # Override the user message after initialization
        self.user_message = "AI enhancement service is temporarily unavailable. Basic predictions are still available."


class DifyWorkflowException(DifyServiceException):
    """Raised when Dify workflow execution fails."""
    
    def __init__(self, workflow_id: str, message: str, **kwargs):
        super().__init__(
            message=f"Workflow {workflow_id} failed: {message}",
            error_code="DIFY_WORKFLOW_ERROR",
            details={'workflow_id': workflow_id},
            **kwargs
        )


# Network and Connectivity Exceptions
class NetworkException(BaseAPIException):
    """Raised when network connectivity issues occur."""
    
    def __init__(self, message: str, service: str = None, **kwargs):
        super().__init__(
            message=message,
            user_message="Network connectivity issue. Please try again later.",
            status_code=503,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.HIGH,
            error_code="NETWORK_ERROR",
            alerting_required=True,
            details={'service': service} if service else {},
            **kwargs
        )


class TimeoutException(NetworkException):
    """Raised when external service calls timeout."""
    
    def __init__(self, service: str, timeout_seconds: int, **kwargs):
        message = f"{service} request timed out after {timeout_seconds} seconds"
        
        super().__init__(
            message=message,
            service=service,
            error_code="REQUEST_TIMEOUT",
            user_message=f"Request timed out. The {service} service is taking longer than expected.",
            details={'timeout_seconds': timeout_seconds, 'service': service},
            **kwargs
        )


# Data Processing Exceptions
class DataProcessingException(BaseAPIException):
    """Raised when data processing fails."""
    
    def __init__(self, message: str, processing_stage: str = None, **kwargs):
        super().__init__(
            message=message,
            user_message="Data processing failed. Please check your input data.",
            status_code=422,
            category=ErrorCategory.DATA_PROCESSING,
            severity=ErrorSeverity.MEDIUM,
            error_code="DATA_PROCESSING_ERROR",
            details={'processing_stage': processing_stage} if processing_stage else {},
            **kwargs
        )


class ModelPredictionException(DataProcessingException):
    """Raised when ML model prediction fails."""
    
    def __init__(self, model_name: str, message: str, **kwargs):
        super().__init__(
            message=f"{model_name} prediction failed: {message}",
            processing_stage="model_prediction",
            error_code="MODEL_PREDICTION_ERROR",
            user_message="Prediction model encountered an error. Please try again with different data.",
            details={'model_name': model_name},
            **kwargs
        )


class DataTransformationException(DataProcessingException):
    """Raised when data transformation fails."""
    
    def __init__(self, transformation: str, message: str, **kwargs):
        super().__init__(
            message=f"Data transformation '{transformation}' failed: {message}",
            processing_stage="data_transformation",
            error_code="DATA_TRANSFORMATION_ERROR",
            details={'transformation': transformation},
            **kwargs
        )


# Configuration and Internal Exceptions
class ConfigurationException(BaseAPIException):
    """Raised when configuration is invalid or missing."""
    
    def __init__(self, message: str, config_key: str = None, **kwargs):
        super().__init__(
            message=message,
            user_message="Service configuration error. Please contact system administrator.",
            status_code=500,
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.CRITICAL,
            error_code="CONFIGURATION_ERROR",
            alerting_required=True,
            details={'config_key': config_key} if config_key else {},
            **kwargs
        )


class CacheException(BaseAPIException):
    """Raised when cache operations fail."""
    
    def __init__(self, message: str, operation: str = None, **kwargs):
        super().__init__(
            message=message,
            user_message="Caching service temporarily unavailable. Performance may be reduced.",
            status_code=503,
            category=ErrorCategory.INTERNAL,
            severity=ErrorSeverity.MEDIUM,
            error_code="CACHE_ERROR",
            details={'operation': operation} if operation else {},
            **kwargs
        )


# Utility functions for exception handling
def format_error_response(exception: BaseAPIException) -> tuple:
    """
    Format exception as Flask response tuple.
    
    Args:
        exception: The exception to format
        
    Returns:
        Tuple of (response_dict, status_code)
    """
    return exception.to_dict(), exception.status_code


def is_retryable_error(exception: Exception) -> bool:
    """
    Determine if an error is retryable.
    
    Args:
        exception: The exception to check
        
    Returns:
        True if the error is retryable, False otherwise
    """
    if isinstance(exception, BaseAPIException):
        # Don't retry validation or authentication errors
        if exception.category in [ErrorCategory.VALIDATION, ErrorCategory.AUTHENTICATION]:
            return False
        
        # Don't retry rate limiting errors
        if exception.category == ErrorCategory.RATE_LIMITING:
            return False
        
        # Retry network and external service errors
        if exception.category in [ErrorCategory.NETWORK, ErrorCategory.EXTERNAL_SERVICE]:
            return True
    
    # Default to not retryable for unknown exceptions
    return False


def should_alert(exception: Exception) -> bool:
    """
    Determine if an exception should trigger alerts.
    
    Args:
        exception: The exception to check
        
    Returns:
        True if alerting is required, False otherwise
    """
    if isinstance(exception, BaseAPIException):
        return exception.alerting_required or exception.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]
    
    # Alert on all unhandled exceptions
    return True