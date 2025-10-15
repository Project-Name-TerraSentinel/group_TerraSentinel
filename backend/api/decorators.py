"""
API decorators for authentication, rate limiting, and request handling.
Clean, reusable decorators following single responsibility principle.
"""

import time
from functools import wraps
from flask import request, jsonify, g
import redis

from backend.config.settings import get_config
from backend.services.logging_service import get_logger, setup_request_logging
from backend.services.exceptions import *
from backend.services.alerting_service import send_exception_alert

config = get_config()
logger = get_logger("decorators")

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
        
        if not api_key or len(api_key.strip()) == 0:
            exc = InvalidAPIKeyException()
            logger.warning(f"Missing or invalid API key from {request.remote_addr}")
            send_exception_alert(exc, {'endpoint': request.endpoint, 'remote_addr': request.remote_addr})
            return jsonify(exc.to_dict()), exc.status_code
        
        # Store API key in request context
        g.api_key = api_key.strip()
        
        logger.debug(f"API key authenticated for {request.endpoint}")
        return f(*args, **kwargs)
    
    return decorated_function


def rate_limit(f):
    """Decorator to implement rate limiting per API key."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip rate limiting if Redis is not available or for health endpoints
        if not redis_available or (request.endpoint and request.endpoint.startswith('health_')):
            return f(*args, **kwargs)
        
        # Get API key from context
        api_key = getattr(g, 'api_key', 'anonymous')
        rate_limit_key = f"rate_limit:{api_key}:{int(time.time() // 60)}"
        
        try:
            current_count = redis_client.get(rate_limit_key)
            current_count = int(current_count) if current_count else 0
            
            if current_count >= config.rate_limit_per_minute:
                exc = RateLimitExceededException(
                    limit=config.rate_limit_per_minute,
                    window="minute",
                    retry_after=60
                )
                logger.warning(f"Rate limit exceeded for API key: {api_key[:8]}...")
                return jsonify(exc.to_dict()), exc.status_code
            
            # Increment counter
            pipe = redis_client.pipeline()
            pipe.incr(rate_limit_key)
            pipe.expire(rate_limit_key, 60)
            pipe.execute()
            
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
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
        
        logger.info(
            f"API request: {request.method} {request.endpoint}",
            extra={
                'extra_fields': {
                    'event_type': 'api_request',
                    'method': request.method,
                    'endpoint': request.endpoint,
                    'remote_addr': request.remote_addr,
                    'api_key_hint': api_key_hint,
                    'user_agent': request.headers.get('User-Agent', ''),
                    'content_length': request.content_length
                }
            }
        )
        
        # Execute the request
        try:
            response = f(*args, **kwargs)
            
            # Log successful response
            processing_time = (time.time() - start_time) * 1000
            status_code = response[1] if isinstance(response, tuple) else 200
            
            logger.info(
                f"API response: {status_code} in {processing_time:.2f}ms",
                extra={
                    'extra_fields': {
                        'event_type': 'api_response',
                        'status_code': status_code,
                        'processing_time_ms': processing_time,
                        'endpoint': request.endpoint,
                        'api_key_hint': api_key_hint
                    }
                }
            )
            
            return response
            
        except Exception as e:
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


def require_https(f):
    """Decorator to enforce HTTPS in production."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if config.enforce_https and not request.is_secure:
            exc = ValidationException("HTTPS required for this endpoint")
            return jsonify(exc.to_dict()), exc.status_code
        return f(*args, **kwargs)
    
    return decorated_function