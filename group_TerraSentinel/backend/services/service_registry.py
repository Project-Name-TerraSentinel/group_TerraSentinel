"""
Service registry for Terra Pulse-Dify integration.
Clean service registration following Uncle Bob's dependency injection principles.
"""

from backend.config.settings import AppConfig
from backend.services.service_factory import ServiceFactory, ServiceScope
from backend.services.terra_pulse_service import TerraPulseService
from backend.services.dify_service import DifyService
from backend.services.cache_service import CacheService
from backend.services.logging_service import get_logger

logger = get_logger("service_registry")


def register_all_services(config: AppConfig) -> ServiceFactory:
    """
    Register all services with the service factory.
    Clean, centralized service registration.
    
    Args:
        config: Application configuration
        
    Returns:
        ServiceFactory: Configured service factory
    """
    factory = ServiceFactory(config)
    
    # Register core services
    _register_core_services(factory)
    
    # Register cached services
    _register_cached_services(factory)
    
    # Register utility services
    _register_utility_services(factory)
    
    logger.info("All services registered successfully")
    return factory


def _register_core_services(factory: ServiceFactory) -> None:
    """Register core business services."""
    
    # Terra Pulse service
    factory.register(
        service_name="terra_pulse",
        service_class=TerraPulseService,
        scope=ServiceScope.SINGLETON,
        config_section="terra_pulse"
    )
    
    # Dify service
    factory.register(
        service_name="dify",
        service_class=DifyService,
        scope=ServiceScope.SINGLETON,
        config_section="dify"
    )
    
    logger.debug("Core services registered")


def _register_cached_services(factory: ServiceFactory) -> None:
    """Register cached service wrappers."""
    
    # Cache service
    factory.register(
        service_name="cache",
        service_class=CacheService,
        scope=ServiceScope.SINGLETON
    )
    
    # Cached Terra Pulse service would be registered here
    # when CachedTerraPulseService is implemented
    
    logger.debug("Cached services registered")


def _register_utility_services(factory: ServiceFactory) -> None:
    """Register utility services."""
    
    # Data processor, response formatter, etc. would be registered here
    # when these services are implemented
    
    logger.debug("Utility services registered")