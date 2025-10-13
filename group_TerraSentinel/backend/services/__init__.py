"""
Services package for Terra Pulse-Dify integration.
Provides service layer architecture with dependency injection and error handling.
"""

from .base_service import (
    BaseService,
    ExternalAPIService,
    ServiceError,
    ServiceUnavailableError,
    ServiceTimeoutError,
    ServiceAuthenticationError,
    ServiceValidationError,
    ServiceStatus,
    ServiceHealthCheck,
    RetryConfig,
    retry_with_backoff
)

from .service_factory import (
    ServiceFactory,
    ServiceScope,
    ServiceRegistration,
    get_service_factory,
    register_default_services
)

__all__ = [
    # Base service classes
    'BaseService',
    'ExternalAPIService',
    
    # Service exceptions
    'ServiceError',
    'ServiceUnavailableError', 
    'ServiceTimeoutError',
    'ServiceAuthenticationError',
    'ServiceValidationError',
    
    # Service health and status
    'ServiceStatus',
    'ServiceHealthCheck',
    
    # Retry functionality
    'RetryConfig',
    'retry_with_backoff',
    
    # Service factory
    'ServiceFactory',
    'ServiceScope',
    'ServiceRegistration',
    'get_service_factory',
    'register_default_services'
]