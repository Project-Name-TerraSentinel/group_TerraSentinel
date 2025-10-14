"""
Security validation and input sanitization for Terra Pulse-Dify integration.
Provides comprehensive input validation, sanitization, and security measures.
"""

import re
import html
import logging
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field, validator, model_validator
from datetime import datetime
import bleach
from urllib.parse import quote

from backend.services.exceptions import ValidationException, BaseAPIException, ErrorSeverity, ErrorCategory


logger = logging.getLogger(__name__)


class SecurityValidationException(BaseAPIException):
    """Raised when security validation fails."""
    
    def __init__(self, message: str, security_issue: str = None, **kwargs):
        super().__init__(
            message=message,
            user_message="Security validation failed. Please check your input data.",
            status_code=400,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.HIGH,
            error_code="SECURITY_VALIDATION_ERROR",
            alerting_required=True,
            details={'security_issue': security_issue} if security_issue else {},
            **kwargs
        )


class InputSanitizer:
    """
    Input sanitization utilities to prevent injection attacks and ensure data quality.
    """
    
    # Allowed characters for different field types
    LOCATION_ALLOWED_CHARS = re.compile(r'^[a-zA-Z0-9\s\-\.,\(\)]+$')
    USER_CONTEXT_ALLOWED_CHARS = re.compile(r'^[a-zA-Z0-9\s\-_]+$')
    
    # SQL injection patterns to detect
    SQL_INJECTION_PATTERNS = [
        r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)',
        r'(--|#|/\*|\*/)',
        r'(\bOR\b.*=.*\bOR\b)',
        r'(\bAND\b.*=.*\bAND\b)',
        r'(\'.*\'|".*")',
        r'(\bxp_cmdshell\b|\bsp_executesql\b)',
    ]
    
    # XSS patterns to detect
    XSS_PATTERNS = [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'<iframe[^>]*>.*?</iframe>',
        r'<object[^>]*>.*?</object>',
        r'<embed[^>]*>.*?</embed>',
        r'<link[^>]*>',
        r'<meta[^>]*>',
    ]
    
    @classmethod
    def sanitize_string(cls, value: str, max_length: int = 200, 
                       allowed_chars: re.Pattern = None) -> str:
        """
        Sanitize string input to prevent injection attacks.
        
        Args:
            value: String to sanitize
            max_length: Maximum allowed length
            allowed_chars: Regex pattern for allowed characters
            
        Returns:
            Sanitized string
            
        Raises:
            SecurityValidationException: If malicious content is detected
        """
        if not isinstance(value, str):
            value = str(value)
        
        # Check for SQL injection patterns
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"Potential SQL injection detected: {pattern}")
                raise SecurityValidationException(
                    f"Potential SQL injection detected in input",
                    security_issue="sql_injection"
                )
        
        # Check for XSS patterns
        for pattern in cls.XSS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"Potential XSS detected: {pattern}")
                raise SecurityValidationException(
                    f"Potential XSS attack detected in input",
                    security_issue="xss_attack"
                )
        
        # HTML escape the string
        sanitized = html.escape(value)
        
        # Use bleach for additional sanitization
        sanitized = bleach.clean(sanitized, tags=[], attributes={}, strip=True)
        
        # Apply character filtering if pattern provided
        if allowed_chars:
            if not allowed_chars.match(sanitized):
                # Remove disallowed characters
                sanitized = re.sub(r'[^a-zA-Z0-9\s\-\.,\(\)_]', '', sanitized)
        
        # Trim whitespace and limit length
        sanitized = sanitized.strip()[:max_length]
        
        return sanitized
    
    @classmethod
    def sanitize_numeric(cls, value: Union[str, int, float], 
                        min_val: float = None, max_val: float = None) -> float:
        """
        Sanitize and validate numeric input.
        
        Args:
            value: Numeric value to sanitize
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            
        Returns:
            Sanitized numeric value
            
        Raises:
            ValidationException: If value is invalid
        """
        try:
            # Convert to float
            if isinstance(value, str):
                # Remove any non-numeric characters except decimal point and minus
                cleaned = re.sub(r'[^0-9.\-]', '', value)
                numeric_value = float(cleaned)
            else:
                numeric_value = float(value)
            
            # Check for NaN or infinity
            if not (numeric_value == numeric_value):  # NaN check
                raise ValidationException("Invalid numeric value: NaN")
            
            if numeric_value == float('inf') or numeric_value == float('-inf'):
                raise ValidationException("Invalid numeric value: infinity")
            
            # Apply range limits
            if min_val is not None and numeric_value < min_val:
                logger.warning(f"Numeric value {numeric_value} below minimum {min_val}, clamping")
                numeric_value = min_val
            
            if max_val is not None and numeric_value > max_val:
                logger.warning(f"Numeric value {numeric_value} above maximum {max_val}, clamping")
                numeric_value = max_val
            
            return numeric_value
            
        except (ValueError, TypeError) as e:
            raise ValidationException(f"Invalid numeric value: {value}")


class SecureEnhancedPredictionRequest(BaseModel):
    """
    Enhanced prediction request model with comprehensive security validation.
    """
    ndvi_mean_early: float = Field(..., ge=-2.0, le=2.0, description="Early season NDVI mean")
    ndvi_median_early: float = Field(..., ge=-2.0, le=2.0, description="Early season NDVI median")
    ndvi_std_early: float = Field(..., ge=0.0, le=2.0, description="Early season NDVI standard deviation")
    ndvi_mean_late: float = Field(..., ge=-2.0, le=2.0, description="Late season NDVI mean")
    ndvi_median_late: float = Field(..., ge=-2.0, le=2.0, description="Late season NDVI median")
    ndvi_std_late: float = Field(..., ge=0.0, le=2.0, description="Late season NDVI standard deviation")
    ndvi_delta_mean: float = Field(..., ge=-4.0, le=4.0, description="NDVI mean change")
    location: str = Field(..., min_length=1, max_length=200, description="Location information")
    user_context: str = Field(default="general", max_length=100, description="User context")
    user_type: str = Field(default="farmer", description="User type")
    
    @validator('ndvi_mean_early', 'ndvi_median_early', 'ndvi_mean_late', 'ndvi_median_late', pre=True)
    def validate_ndvi_values(cls, v):
        """Validate NDVI values are within reasonable ranges."""
        sanitized = InputSanitizer.sanitize_numeric(v, -2.0, 2.0)
        
        # Additional validation for typical NDVI ranges
        if not -1.0 <= sanitized <= 1.0:
            logger.warning(f"NDVI value {sanitized} outside typical range [-1.0, 1.0]")
        
        return sanitized
    
    @validator('ndvi_std_early', 'ndvi_std_late', pre=True)
    def validate_ndvi_std(cls, v):
        """Validate NDVI standard deviation values."""
        sanitized = InputSanitizer.sanitize_numeric(v, 0.0, 2.0)
        
        # Standard deviation should be reasonable
        if sanitized > 1.0:
            logger.warning(f"High NDVI standard deviation: {sanitized}")
        
        return sanitized
    
    @validator('ndvi_delta_mean', pre=True)
    def validate_ndvi_delta(cls, v):
        """Validate NDVI delta values."""
        sanitized = InputSanitizer.sanitize_numeric(v, -4.0, 4.0)
        
        # Large changes might indicate data quality issues
        if abs(sanitized) > 2.0:
            logger.warning(f"Large NDVI delta detected: {sanitized}")
        
        return sanitized
    
    @validator('location', pre=True)
    def validate_location(cls, v):
        """Validate and sanitize location string."""
        if not v or not str(v).strip():
            raise ValidationException("Location cannot be empty")
        
        sanitized = InputSanitizer.sanitize_string(
            str(v), 
            max_length=200, 
            allowed_chars=InputSanitizer.LOCATION_ALLOWED_CHARS
        )
        
        if len(sanitized) < 2:
            raise ValidationException("Location must be at least 2 characters long")
        
        return sanitized
    
    @validator('user_context', pre=True)
    def validate_user_context(cls, v):
        """Validate and sanitize user context."""
        if v is None:
            return "general"
        
        sanitized = InputSanitizer.sanitize_string(
            str(v),
            max_length=100,
            allowed_chars=InputSanitizer.USER_CONTEXT_ALLOWED_CHARS
        )
        
        return sanitized or "general"
    
    @validator('user_type', pre=True)
    def validate_user_type(cls, v):
        """Validate user type."""
        if v is None:
            return "farmer"
        
        user_type = str(v).lower().strip()
        
        # Sanitize the input
        sanitized = InputSanitizer.sanitize_string(user_type, max_length=20)
        
        if sanitized not in ['farmer', 'official']:
            logger.warning(f"Invalid user_type '{sanitized}', defaulting to 'farmer'")
            return 'farmer'
        
        return sanitized
    
    @model_validator(mode='after')
    def validate_ndvi_consistency(self):
        """Validate NDVI data consistency across fields."""
        try:
            # Check if early and late season values are consistent
            early_mean = self.ndvi_mean_early
            late_mean = self.ndvi_mean_late
            delta_mean = self.ndvi_delta_mean
            
            if all(v is not None for v in [early_mean, late_mean, delta_mean]):
                calculated_delta = late_mean - early_mean
                
                # Allow some tolerance for floating point precision
                if abs(calculated_delta - delta_mean) > 0.1:
                    logger.warning(
                        f"NDVI delta inconsistency: calculated={calculated_delta:.3f}, "
                        f"provided={delta_mean:.3f}"
                    )
            
            # Check for suspicious patterns that might indicate fake data
            early_median = self.ndvi_median_early
            late_median = self.ndvi_median_late
            
            if early_mean is not None and early_median is not None:
                if abs(early_mean - early_median) > 1.0:
                    logger.warning("Large difference between NDVI mean and median (early)")
            
            if late_mean is not None and late_median is not None:
                if abs(late_mean - late_median) > 1.0:
                    logger.warning("Large difference between NDVI mean and median (late)")
            
        except Exception as e:
            logger.error(f"Error in NDVI consistency validation: {e}")
        
        return self


class SecurityValidator:
    """
    Main security validation class for request processing.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def validate_and_sanitize_request(self, request_data: Dict[str, Any]) -> SecureEnhancedPredictionRequest:
        """
        Validate and sanitize incoming request data with security checks.
        
        Args:
            request_data: Raw request data
            
        Returns:
            SecureEnhancedPredictionRequest: Validated and sanitized request
            
        Raises:
            ValidationException: If validation fails
            SecurityValidationException: If security issues are detected
        """
        try:
            # Log the validation attempt
            self.logger.info("Starting security validation for prediction request")
            
            # Check for suspicious request patterns
            self._check_request_patterns(request_data)
            
            # Validate using Pydantic model (which includes sanitization)
            validated_request = SecureEnhancedPredictionRequest(**request_data)
            
            # Additional security checks
            self._perform_additional_security_checks(validated_request)
            
            self.logger.info("Security validation completed successfully")
            return validated_request
            
        except ValidationException:
            # Re-raise validation exceptions as-is
            raise
        except SecurityValidationException:
            # Re-raise security exceptions as-is
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error during security validation: {e}")
            raise ValidationException(f"Request validation failed: {str(e)}")
    
    def _check_request_patterns(self, request_data: Dict[str, Any]) -> None:
        """
        Check for suspicious patterns in the request data.
        
        Args:
            request_data: Request data to check
            
        Raises:
            SecurityValidationException: If suspicious patterns are detected
        """
        # Check for excessively large requests
        if len(str(request_data)) > 10000:  # 10KB limit
            raise SecurityValidationException(
                "Request size too large",
                security_issue="oversized_request"
            )
        
        # Check for too many fields (potential DoS)
        if len(request_data) > 50:
            raise SecurityValidationException(
                "Too many fields in request",
                security_issue="excessive_fields"
            )
        
        # Check for deeply nested structures (potential DoS)
        max_depth = self._get_dict_depth(request_data)
        if max_depth > 10:
            raise SecurityValidationException(
                "Request structure too deeply nested",
                security_issue="deep_nesting"
            )
    
    def _get_dict_depth(self, d: Dict[str, Any], depth: int = 0) -> int:
        """Calculate the maximum depth of a dictionary."""
        if not isinstance(d, dict):
            return depth
        
        if not d:
            return depth + 1
        
        return max(self._get_dict_depth(v, depth + 1) for v in d.values())
    
    def _perform_additional_security_checks(self, validated_request: SecureEnhancedPredictionRequest) -> None:
        """
        Perform additional security checks on validated data.
        
        Args:
            validated_request: Validated request object
            
        Raises:
            SecurityValidationException: If security issues are detected
        """
        # Check for potential data poisoning attempts
        ndvi_values = [
            validated_request.ndvi_mean_early,
            validated_request.ndvi_median_early,
            validated_request.ndvi_mean_late,
            validated_request.ndvi_median_late
        ]
        
        # Check for all identical values (potential fake data)
        if len(set(ndvi_values)) == 1:
            self.logger.warning("All NDVI values are identical - potential fake data")
        
        # Check for values that are exactly 0 or 1 (suspicious for NDVI)
        suspicious_values = [v for v in ndvi_values if v in [0.0, 1.0, -1.0]]
        if len(suspicious_values) > 2:
            self.logger.warning(f"Multiple suspicious NDVI values detected: {suspicious_values}")
        
        # Check location for common test/dummy values
        location_lower = validated_request.location.lower()
        test_locations = ['test', 'dummy', 'fake', 'example', 'sample', 'null', 'undefined']
        if any(test_word in location_lower for test_word in test_locations):
            self.logger.warning(f"Potential test location detected: {validated_request.location}")


def create_security_validator() -> SecurityValidator:
    """
    Factory function to create a SecurityValidator instance.
    
    Returns:
        SecurityValidator: Configured security validator
    """
    return SecurityValidator()