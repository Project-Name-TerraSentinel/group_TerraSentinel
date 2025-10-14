"""
Base service classes and interfaces for external service integrations.
Provides common retry logic, error handling patterns, and service abstractions.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type, TypeVar, Generic, Callable
from enum import Enum
from dataclasses import dataclass
from functools import wraps
import random


# Type variables for generic service responses
T = TypeVar('T')
ServiceResponse = TypeVar('ServiceResponse')


class ServiceStatus(Enum):
    """Service health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ServiceHealthCheck:
    """Service health check result."""
    status: ServiceStatus
    message: str
    response_time_ms: Optional[float] = None
    last_check: Optional[float] = None
    error: Optional[str] = None


@dataclass
class RetryConfig:
    """Configuration for retry logic."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


class ServiceError(Exception):
    """Base exception for service-related errors."""
    
    def __init__(self, message: str, service_name: str = None, original_error: Exception = None):
        super().__init__(message)
        self.service_name = service_name
        self.original_error = original_error


class ServiceUnavailableError(ServiceError):
    """Exception raised when a service is unavailable."""
    pass


class ServiceTimeoutError(ServiceError):
    """Exception raised when a service call times out."""
    pass


class ServiceAuthenticationError(ServiceError):
    """Exception raised when service authentication fails."""
    pass


class ServiceValidationError(ServiceError):
    """Exception raised when service input validation fails."""
    pass


def retry_with_backoff(
    retry_config: RetryConfig = None,
    exceptions: tuple = (Exception,),
    logger: logging.Logger = None
):
    """
    Decorator for implementing retry logic with exponential backoff.
    
    Args:
        retry_config: Retry configuration settings
        exceptions: Tuple of exceptions to retry on
        logger: Logger instance for retry attempts
    """
    if retry_config is None:
        retry_config = RetryConfig()
    
    if logger is None:
        logger = logging.getLogger(__name__)
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(retry_config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == retry_config.max_attempts - 1:
                        logger.error(
                            f"Function {func.__name__} failed after {retry_config.max_attempts} attempts: {e}"
                        )
                        raise e
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        retry_config.base_delay * (retry_config.exponential_base ** attempt),
                        retry_config.max_delay
                    )
                    
                    # Add jitter to prevent thundering herd
                    if retry_config.jitter:
                        delay *= (0.5 + random.random() * 0.5)
                    
                    logger.warning(
                        f"Function {func.__name__} failed on attempt {attempt + 1}/{retry_config.max_attempts}: {e}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )
                    
                    time.sleep(delay)
            
            raise last_exception
        
        return wrapper
    return decorator


class BaseService(ABC, Generic[ServiceResponse]):
    """
    Abstract base class for external service integrations.
    Follows Uncle Bob's clean architecture principles with clear responsibilities.
    """
    
    def __init__(self, service_name: str, retry_config: RetryConfig = None):
        """
        Initialize base service with dependency injection.
        
        Args:
            service_name: Name of the service for logging and error reporting
            retry_config: Retry configuration for service calls
        """
        self._service_name = service_name
        self._retry_config = retry_config or RetryConfig()
        self._logger = logging.getLogger(f"{__name__}.{service_name}")
        self._last_health_check: Optional[ServiceHealthCheck] = None
        
        # Validate configuration on initialization
        self._validate_configuration()
    
    @property
    def service_name(self) -> str:
        """Get service name."""
        return self._service_name
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger instance."""
        return self._logger
    
    @abstractmethod
    def _perform_health_check(self) -> ServiceHealthCheck:
        """
        Perform service-specific health check.
        
        Returns:
            ServiceHealthCheck: Health check result
        """
        pass
    
    @abstractmethod
    def _validate_configuration(self) -> bool:
        """
        Validate service configuration.
        
        Returns:
            bool: True if configuration is valid
            
        Raises:
            ServiceValidationError: If configuration is invalid
        """
        pass
    
    def health_check(self, force_check: bool = False) -> ServiceHealthCheck:
        """
        Check service health with caching.
        Simplified to synchronous for better testability.
        
        Args:
            force_check: Force a new health check even if cached result exists
            
        Returns:
            ServiceHealthCheck: Health check result
        """
        if self._should_use_cached_health_check(force_check):
            return self._last_health_check
        
        return self._perform_fresh_health_check()
    
    def _should_use_cached_health_check(self, force_check: bool) -> bool:
        """Determine if cached health check should be used."""
        if force_check or not self._last_health_check:
            return False
        
        if not self._last_health_check.last_check:
            return False
        
        cache_age = time.time() - self._last_health_check.last_check
        return cache_age < 60  # 1 minute cache
    
    def _perform_fresh_health_check(self) -> ServiceHealthCheck:
        """Perform a fresh health check."""
        current_time = time.time()
        
        try:
            start_time = time.time()
            health_check = self._perform_health_check()
            response_time = (time.time() - start_time) * 1000
            
            health_check.response_time_ms = response_time
            health_check.last_check = current_time
            
            self._last_health_check = health_check
            self._log_health_check_result(health_check, response_time)
            
            return health_check
            
        except Exception as e:
            return self._create_failed_health_check(current_time, e)
    
    def _log_health_check_result(self, health_check: ServiceHealthCheck, response_time: float):
        """Log health check result."""
        self._logger.info(
            f"Health check for {self._service_name}: {health_check.status.value} "
            f"({response_time:.2f}ms) - {health_check.message}"
        )
    
    def _create_failed_health_check(self, current_time: float, error: Exception) -> ServiceHealthCheck:
        """Create health check result for failed checks."""
        error_message = f"Health check failed: {str(error)}"
        health_check = ServiceHealthCheck(
            status=ServiceStatus.UNHEALTHY,
            message=error_message,
            last_check=current_time,
            error=str(error)
        )
        
        self._last_health_check = health_check
        self._logger.error(f"Health check for {self._service_name} failed: {error}")
        
        return health_check
    
    def _handle_service_error(self, error: Exception, operation: str) -> ServiceError:
        """
        Convert generic exceptions to service-specific errors.
        
        Args:
            error: Original exception
            operation: Operation that failed
            
        Returns:
            ServiceError: Appropriate service error
        """
        error_message = f"{operation} failed for {self.service_name}: {str(error)}"
        
        if "timeout" in str(error).lower():
            return ServiceTimeoutError(error_message, self.service_name, error)
        elif "auth" in str(error).lower() or "unauthorized" in str(error).lower():
            return ServiceAuthenticationError(error_message, self.service_name, error)
        elif "connection" in str(error).lower() or "network" in str(error).lower():
            return ServiceUnavailableError(error_message, self.service_name, error)
        else:
            return ServiceError(error_message, self.service_name, error)
    
    def log_operation(self, operation: str, duration_ms: float, success: bool, **kwargs):
        """
        Log service operation with structured data.
        
        Args:
            operation: Operation name
            duration_ms: Operation duration in milliseconds
            success: Whether operation succeeded
            **kwargs: Additional context data
        """
        log_data = {
            "service": self.service_name,
            "operation": operation,
            "duration_ms": duration_ms,
            "success": success,
            **kwargs
        }
        
        if success:
            self.logger.info(f"Operation completed", extra=log_data)
        else:
            self.logger.error(f"Operation failed", extra=log_data)


class ExternalAPIService(BaseService[ServiceResponse]):
    """
    Base class for external API service integrations.
    Extends BaseService with HTTP-specific functionality.
    """
    
    def __init__(
        self, 
        service_name: str, 
        base_url: str,
        api_key: str = None,
        timeout: int = 30,
        retry_config: RetryConfig = None
    ):
        """
        Initialize external API service.
        
        Args:
            service_name: Name of the service
            base_url: Base URL for API endpoints
            api_key: API key for authentication
            timeout: Request timeout in seconds
            retry_config: Retry configuration
        """
        super().__init__(service_name, retry_config)
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        
        # Validate configuration on initialization
        self._validate_configuration()
    
    def _validate_configuration(self) -> bool:
        """
        Validate API service configuration.
        
        Returns:
            bool: True if configuration is valid
            
        Raises:
            ServiceValidationError: If configuration is invalid
        """
        if not self.base_url:
            raise ServiceValidationError(
                "Base URL is required for API service",
                self.service_name
            )
        
        if not self.base_url.startswith(('http://', 'https://')):
            raise ServiceValidationError(
                "Base URL must start with http:// or https://",
                self.service_name
            )
        
        return True
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Get default headers for API requests.
        
        Returns:
            Dict[str, str]: Request headers
        """
        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"TerraPluse-Integration/{self.service_name}"
        }
        
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        return headers
    
    async def _perform_health_check(self) -> ServiceHealthCheck:
        """
        Default health check implementation for API services.
        
        Returns:
            ServiceHealthCheck: Health check result
        """
        try:
            # This is a basic implementation - subclasses should override
            # with service-specific health check endpoints
            return ServiceHealthCheck(
                status=ServiceStatus.UNKNOWN,
                message="Health check not implemented for this service"
            )
        except Exception as e:
            return ServiceHealthCheck(
                status=ServiceStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                error=str(e)
            )