"""
Service factory pattern for dependency injection and service management.
Provides centralized service creation, configuration, and lifecycle management.
"""

import logging
from typing import Dict, Type, TypeVar, Optional, Any, Protocol
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from .base_service import BaseService, ServiceHealthCheck, ServiceStatus
from backend.config.settings import AppConfig


# Type variables for service factory
ServiceType = TypeVar('ServiceType', bound=BaseService)


class ServiceScope(Enum):
    """Service lifecycle scope enumeration."""
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    REQUEST = "request"


@dataclass
class ServiceRegistration:
    """Service registration configuration."""
    service_class: Type[BaseService]
    scope: ServiceScope = ServiceScope.SINGLETON
    factory_method: Optional[callable] = None
    dependencies: Optional[Dict[str, str]] = None
    config_section: Optional[str] = None


class ServiceFactory:
    """
    Factory for creating and managing service instances.
    Implements dependency injection and service lifecycle management.
    """
    
    def __init__(self, config: AppConfig):
        """
        Initialize service factory.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._registrations: Dict[str, ServiceRegistration] = {}
        self._singletons: Dict[str, BaseService] = {}
        self._request_scoped: Dict[str, Dict[str, BaseService]] = {}
    
    def register(
        self,
        service_name: str,
        service_class: Type[ServiceType],
        scope: ServiceScope = ServiceScope.SINGLETON,
        factory_method: Optional[callable] = None,
        dependencies: Optional[Dict[str, str]] = None,
        config_section: Optional[str] = None
    ) -> None:
        """
        Register a service with the factory.
        
        Args:
            service_name: Unique name for the service
            service_class: Service class to instantiate
            scope: Service lifecycle scope
            factory_method: Optional custom factory method
            dependencies: Service dependencies mapping
            config_section: Configuration section name
        """
        registration = ServiceRegistration(
            service_class=service_class,
            scope=scope,
            factory_method=factory_method,
            dependencies=dependencies or {},
            config_section=config_section
        )
        
        self._registrations[service_name] = registration
        self.logger.info(f"Registered service: {service_name} with scope: {scope.value}")
    
    def get_service(self, service_name: str, request_id: str = None) -> BaseService:
        """
        Get service instance by name.
        
        Args:
            service_name: Name of the service to retrieve
            request_id: Request ID for request-scoped services
            
        Returns:
            BaseService: Service instance
            
        Raises:
            ValueError: If service is not registered
            RuntimeError: If service creation fails
        """
        if service_name not in self._registrations:
            raise ValueError(f"Service '{service_name}' is not registered")
        
        registration = self._registrations[service_name]
        
        # Handle singleton scope
        if registration.scope == ServiceScope.SINGLETON:
            if service_name not in self._singletons:
                self._singletons[service_name] = self._create_service(service_name, registration)
            return self._singletons[service_name]
        
        # Handle request scope
        elif registration.scope == ServiceScope.REQUEST:
            if not request_id:
                raise ValueError(f"Request ID required for request-scoped service: {service_name}")
            
            if request_id not in self._request_scoped:
                self._request_scoped[request_id] = {}
            
            if service_name not in self._request_scoped[request_id]:
                self._request_scoped[request_id][service_name] = self._create_service(
                    service_name, registration
                )
            
            return self._request_scoped[request_id][service_name]
        
        # Handle transient scope
        else:
            return self._create_service(service_name, registration)
    
    def _create_service(self, service_name: str, registration: ServiceRegistration) -> BaseService:
        """
        Create service instance using registration configuration.
        
        Args:
            service_name: Name of the service
            registration: Service registration configuration
            
        Returns:
            BaseService: Created service instance
            
        Raises:
            RuntimeError: If service creation fails
        """
        try:
            # Use custom factory method if provided
            if registration.factory_method:
                service = registration.factory_method(self.config, self)
            else:
                # Resolve dependencies
                dependencies = {}
                for dep_name, dep_service_name in registration.dependencies.items():
                    dependencies[dep_name] = self.get_service(dep_service_name)
                
                # Create service instance
                service = self._instantiate_service(
                    registration.service_class,
                    service_name,
                    registration.config_section,
                    dependencies
                )
            
            self.logger.info(f"Created service instance: {service_name}")
            return service
            
        except Exception as e:
            error_msg = f"Failed to create service '{service_name}': {str(e)}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    
    def _instantiate_service(
        self,
        service_class: Type[BaseService],
        service_name: str,
        config_section: Optional[str],
        dependencies: Dict[str, Any]
    ) -> BaseService:
        """
        Instantiate service with configuration and dependencies.
        
        Args:
            service_class: Service class to instantiate
            service_name: Service name
            config_section: Configuration section name
            dependencies: Resolved dependencies
            
        Returns:
            BaseService: Service instance
        """
        # Get service-specific configuration
        service_config = self._get_service_config(config_section) if config_section else {}
        
        # Combine configuration and dependencies
        init_kwargs = {
            'service_name': service_name,
            'config': self.config,
            **service_config,
            **dependencies
        }
        
        return service_class(**init_kwargs)
    
    def _get_service_config(self, config_section: str) -> Dict[str, Any]:
        """
        Extract service-specific configuration from app config.
        
        Args:
            config_section: Configuration section name
            
        Returns:
            Dict[str, Any]: Service configuration
        """
        config_dict = {}
        
        # Extract configuration based on section name
        if hasattr(self.config, config_section):
            section_config = getattr(self.config, config_section)
            if isinstance(section_config, dict):
                config_dict.update(section_config)
        
        return config_dict
    
    async def health_check_all(self) -> Dict[str, ServiceHealthCheck]:
        """
        Perform health checks on all registered singleton services.
        
        Returns:
            Dict[str, ServiceHealthCheck]: Health check results by service name
        """
        health_results = {}
        
        for service_name in self._singletons:
            try:
                service = self._singletons[service_name]
                health_check = await service.health_check()
                health_results[service_name] = health_check
            except Exception as e:
                health_results[service_name] = ServiceHealthCheck(
                    status=ServiceStatus.UNHEALTHY,
                    message=f"Health check failed: {str(e)}",
                    error=str(e)
                )
        
        return health_results
    
    def cleanup_request_scope(self, request_id: str) -> None:
        """
        Clean up request-scoped services for a specific request.
        
        Args:
            request_id: Request ID to clean up
        """
        if request_id in self._request_scoped:
            del self._request_scoped[request_id]
            self.logger.debug(f"Cleaned up request-scoped services for request: {request_id}")
    
    def shutdown(self) -> None:
        """
        Shutdown all services and clean up resources.
        """
        self.logger.info("Shutting down service factory...")
        
        # Clean up singletons
        for service_name, service in self._singletons.items():
            try:
                if hasattr(service, 'shutdown'):
                    service.shutdown()
            except Exception as e:
                self.logger.error(f"Error shutting down service {service_name}: {e}")
        
        # Clear all service instances
        self._singletons.clear()
        self._request_scoped.clear()
        
        self.logger.info("Service factory shutdown complete")
    
    def get_registered_services(self) -> Dict[str, ServiceRegistration]:
        """
        Get all registered services.
        
        Returns:
            Dict[str, ServiceRegistration]: Registered services by name
        """
        return self._registrations.copy()
    
    def is_service_registered(self, service_name: str) -> bool:
        """
        Check if a service is registered.
        
        Args:
            service_name: Service name to check
            
        Returns:
            bool: True if service is registered
        """
        return service_name in self._registrations


# Global service factory instance
_service_factory: Optional[ServiceFactory] = None


def get_service_factory(config: AppConfig = None) -> ServiceFactory:
    """
    Get global service factory instance.
    
    Args:
        config: Application configuration (required for first call)
        
    Returns:
        ServiceFactory: Global service factory instance
        
    Raises:
        RuntimeError: If factory is not initialized and no config provided
    """
    global _service_factory
    
    if _service_factory is None:
        if config is None:
            raise RuntimeError("Service factory not initialized. Provide config parameter.")
        _service_factory = ServiceFactory(config)
    
    return _service_factory


def register_default_services(factory: ServiceFactory) -> None:
    """
    Register default services with the factory.
    
    Args:
        factory: Service factory instance
    """
    # This will be populated as we implement specific services
    # For now, we'll register the services that will be implemented in subsequent tasks
    
    # Terra Pulse service will be registered in task 2.2
    # Dify service will be registered in task 3.1
    # Cache service will be registered in task 5.1
    
    factory.logger.info("Default services registration placeholder - services will be registered as implemented")