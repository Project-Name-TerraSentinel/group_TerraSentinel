"""
Terra Pulse-Dify Integration API
Clean, maintainable Flask application following Uncle Bob's principles.

This refactored version follows:
- Single Responsibility Principle: Each module has one reason to change
- Open/Closed Principle: Easy to extend without modifying existing code
- Dependency Inversion: High-level modules don't depend on low-level modules
- Clean Architecture: Clear separation between API, business logic, and infrastructure
"""

import os
import sys
import time
import atexit
import numpy as np
import onnxruntime as ort
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, g, has_request_context
import redis

from backend.config.settings import get_config
from backend.services.logging_service import get_logging_service, get_logger, setup_request_logging
from backend.services.service_registry import register_all_services
from backend.services.security_middleware import create_security_middleware
from backend.services.alerting_service import get_alerting_service
from backend.services.cached_terra_pulse_service import CachedTerraPulseService
from backend.services.cached_dify_service import CachedDifyService
from backend.services.data_processor import DataProcessor, EnhancedPredictionRequest
from backend.services.terra_pulse_service import PredictionInput
from backend.services.response_formatter import ResponseFormatter
from backend.services.exceptions import *
from backend.services.alerting_service import send_exception_alert
from backend.api.routes import create_routes
from backend.api.middleware import setup_middleware
from backend.api.error_handlers import setup_error_handlers
from backend.api.decorators import require_api_key, rate_limit, log_request, require_https


def create_app() -> Flask:
    """
    Application factory pattern for creating Flask app.
    
    Benefits of this approach:
    - Testability: Easy to create app instances for testing
    - Flexibility: Can create different app configurations
    - Dependency Injection: Services are injected, not hard-coded
    - Clean Architecture: Clear separation of concerns
    
    Returns:
        Flask: Configured Flask application
    """
    # Initialize configuration and logging
    config = get_config()
    logging_service = get_logging_service("terra_pulse_dify", config.log_level)
    logger = get_logger("app")
    
    # Create Flask app
    app = Flask(__name__)
    
    # Register all services (dependency injection)
    service_factory = register_all_services(config)
    
    # Setup application layers
    setup_middleware(app, config)
    setup_error_handlers(app)
    create_routes(app, config)
    
    # Store service factory in app context for cleanup
    app.service_factory = service_factory
    
    logger.info("Terra Pulse-Dify Integration API initialized successfully")
    return app


def shutdown_app(app: Flask) -> None:
    """
    Clean shutdown of application resources.
    
    Args:
        app: Flask application to shutdown
    """
    if hasattr(app, 'service_factory'):
        app.service_factory.shutdown()


# Create application instance
app = create_app()

# Register shutdown handler
import atexit
atexit.register(lambda: shutdown_app(app))

# Get config for additional setup
config = get_config()
logger = get_logger("app")

# Initialize security middleware
security_config = {
    'max_content_length': 2 * 1024 * 1024,  # 2MB for prediction requests
    'max_request_time_seconds': 60,  # Allow longer for AI processing
    'cors': {
        'origins': config.cors_allowed_origins.split(',') if hasattr(config, 'cors_allowed_origins') else ['http://localhost:3000'],
        'methods': ['GET', 'POST', 'OPTIONS'],
        'headers': ['Content-Type', 'Authorization', 'X-API-Key'],
        'max_age': 86400,
        'allow_credentials': False
    }
}

security_middleware = create_security_middleware(security_config)
security_middleware.init_app(app)

# CORS preflight requests are handled by middleware

# Initialize alerting service
alerting_config = {
    'email': {
        'enabled': config.alert_email_enabled,
        'smtp_host': config.alert_smtp_host,
        'smtp_port': config.alert_smtp_port,
        'username': config.alert_email_username,
        'password': config.alert_email_password,
        'from_email': config.alert_from_email,
        'to_emails': [email.strip() for email in config.alert_to_emails.split(',') if email.strip()]
    },
    'webhook': {
        'enabled': config.alert_webhook_enabled,
        'url': config.alert_webhook_url
    }
}

alerting_service = get_alerting_service(alerting_config)

# Initialize services
terra_pulse_service = CachedTerraPulseService(config)
dify_service = CachedDifyService(config)
data_processor = DataProcessor()
response_formatter = ResponseFormatter()

# Initialize Redis for rate limiting
try:
    redis_client = redis.from_url(config.redis_url)
    redis_available = True
    logger.info("Redis connection established for rate limiting")
except Exception as e:
    logger.warning(f"Redis not available for rate limiting: {e}")
    redis_client = None
    redis_available = False


def require_api_key(f):
    """Decorator to require API key authentication."""
    @wraps(f)
    @setup_request_logging()
    def decorated_function(*args, **kwargs):
        # Skip authentication for health endpoints
        if request.endpoint and request.endpoint.startswith('health_'):
            return f(*args, **kwargs)
        
        # Get API key from header
        api_key = request.headers.get(config.api_key_header)
        
        if not api_key:
            exc = InvalidAPIKeyException()
            logging_service.log_security_event(
                logger, "missing_api_key",
                severity="medium",
                endpoint=request.endpoint,
                remote_addr=request.remote_addr
            )
            send_exception_alert(exc, {'endpoint': request.endpoint, 'remote_addr': request.remote_addr})
            return jsonify(exc.to_dict()), exc.status_code
        
        # Validate API key (in production, this would check against a database)
        # For now, we'll accept any non-empty key
        if len(api_key.strip()) == 0:
            exc = InvalidAPIKeyException(api_key[:8] + "...")
            logging_service.log_security_event(
                logger, "invalid_api_key",
                severity="medium",
                endpoint=request.endpoint,
                remote_addr=request.remote_addr,
                api_key_hint=api_key[:8] + "..."
            )
            send_exception_alert(exc, {'endpoint': request.endpoint, 'remote_addr': request.remote_addr})
            return jsonify(exc.to_dict()), exc.status_code
        
        # Store API key in request context for rate limiting
        g.api_key = api_key.strip()
        
        logging_service.log_security_event(
            logger, "api_key_authenticated",
            severity="low",
            endpoint=request.endpoint,
            api_key_hint=api_key[:8] + "..."
        )
        return f(*args, **kwargs)
    
    return decorated_function


def rate_limit(f):
    """Decorator to implement rate limiting per API key."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip rate limiting if Redis is not available
        if not redis_available:
            logging_service.log_cache_operation(logger, "rate_limit_skip", "redis_unavailable")
            return f(*args, **kwargs)
        
        # Skip rate limiting for health endpoints
        if request.endpoint and request.endpoint.startswith('health_'):
            return f(*args, **kwargs)
        
        # Get API key from context (set by require_api_key decorator)
        api_key = getattr(g, 'api_key', 'anonymous')
        
        # Create rate limit key
        rate_limit_key = f"rate_limit:{api_key}:{int(time.time() // 60)}"  # Per minute window
        
        try:
            # Get current request count
            current_count = redis_client.get(rate_limit_key)
            current_count = int(current_count) if current_count else 0
            
            # Check if rate limit exceeded
            if current_count >= config.rate_limit_per_minute:
                exc = RateLimitExceededException(
                    limit=config.rate_limit_per_minute,
                    window="minute",
                    retry_after=60
                )
                
                logging_service.log_security_event(
                    logger, "rate_limit_exceeded",
                    severity="medium",
                    api_key_hint=api_key[:8] + "...",
                    current_count=current_count,
                    limit=config.rate_limit_per_minute
                )
                
                return jsonify(exc.to_dict()), exc.status_code
            
            # Increment counter
            pipe = redis_client.pipeline()
            pipe.incr(rate_limit_key)
            pipe.expire(rate_limit_key, 60)  # Expire after 1 minute
            pipe.execute()
            
            logging_service.log_cache_operation(
                logger, "rate_limit_check", rate_limit_key,
                current_count=current_count + 1,
                limit=config.rate_limit_per_minute
            )
            
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            send_exception_alert(e, {'operation': 'rate_limiting', 'api_key_hint': api_key[:8] + "..."})
            # Continue without rate limiting if Redis fails
        
        return f(*args, **kwargs)
    
    return decorated_function


def log_request(f):
    """Decorator to log API requests for audit trail."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        
        # Log request details
        api_key = getattr(g, 'api_key', 'anonymous')
        api_key_hint = api_key[:8] + "..." if api_key != 'anonymous' else 'none'
        
        logging_service.log_api_request(
            logger,
            method=request.method,
            endpoint=request.endpoint,
            remote_addr=request.remote_addr,
            api_key_hint=api_key_hint,
            user_agent=request.headers.get('User-Agent', ''),
            content_length=request.content_length
        )
        
        # Execute the request
        try:
            with logging_service.performance_timer(logger, f"api_request_{request.endpoint}"):
                response = f(*args, **kwargs)
            
            # Log successful response
            processing_time = (time.time() - start_time) * 1000
            status_code = response[1] if isinstance(response, tuple) else 200
            
            logging_service.log_api_response(
                logger,
                status_code=status_code,
                processing_time_ms=processing_time,
                endpoint=request.endpoint,
                api_key_hint=api_key_hint
            )
            
            return response
            
        except Exception as e:
            # Log error response
            processing_time = (time.time() - start_time) * 1000
            
            logger.error(
                f"API request failed: {request.method} {request.endpoint}",
                extra={
                    'extra_fields': {
                        'event_type': 'api_error',
                        'endpoint': request.endpoint,
                        'method': request.method,
                        'processing_time_ms': processing_time,
                        'api_key_hint': api_key_hint,
                        'error_message': str(e)
                    }
                },
                exc_info=True
            )
            
            # Send alert for unhandled exceptions
            if not isinstance(e, BaseAPIException):
                send_exception_alert(e, {
                    'endpoint': request.endpoint,
                    'method': request.method,
                    'processing_time_ms': processing_time,
                    'api_key_hint': api_key_hint
                })
            
            raise
    
    return decorated_function

# Model loading is now handled by the TerraPulseService

# All routes are now handled by the routes module


if __name__ == "__main__":
    # Production-ready configuration
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"
    
    app.run(debug=debug, host="0.0.0.0", port=port)
