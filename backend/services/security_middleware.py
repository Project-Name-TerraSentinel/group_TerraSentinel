"""
Security middleware for Flask application.
Provides CORS configuration, request size limits, timeout controls, and security headers.
"""

import time
import logging
from functools import wraps
from typing import Dict, Any, Optional, List
from flask import Flask, request, jsonify, g, make_response
from werkzeug.exceptions import RequestEntityTooLarge

from backend.services.exceptions import (
    BaseAPIException, ValidationException,
    ErrorCategory, ErrorSeverity
)
from backend.services.security_validator import SecurityValidationException


logger = logging.getLogger(__name__)


class SecurityMiddleware:
    """
    Security middleware for Flask application providing comprehensive security features.
    """
    
    def __init__(self, app: Flask = None, config: Dict[str, Any] = None):
        """
        Initialize security middleware.
        
        Args:
            app: Flask application instance
            config: Security configuration dictionary
        """
        self.app = app
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app: Flask) -> None:
        """
        Initialize security middleware with Flask app.
        
        Args:
            app: Flask application instance
        """
        self.app = app
        
        # Configure request size limits
        max_content_length = self.config.get('max_content_length', 1024 * 1024)  # 1MB default
        app.config['MAX_CONTENT_LENGTH'] = max_content_length
        
        # Register error handlers
        self._register_error_handlers(app)
        
        # Register before/after request handlers
        self._register_request_handlers(app)
    
    def _register_error_handlers(self, app: Flask) -> None:
        """Register custom error handlers."""
        
        @app.errorhandler(RequestEntityTooLarge)
        def handle_request_too_large(e):
            """Handle request entity too large errors."""
            self.logger.warning(
                f"Request too large from {request.remote_addr}",
                extra={'extra_fields': {'content_length': request.content_length}}
            )
            
            error_response = {
                'error': 'REQUEST_TOO_LARGE',
                'message': 'Request size exceeds maximum allowed limit',
                'max_size_bytes': app.config.get('MAX_CONTENT_LENGTH', 1024 * 1024),
                'category': 'validation',
                'severity': 'medium'
            }
            return jsonify(error_response), 413
        
        @app.errorhandler(413)
        def handle_payload_too_large(e):
            """Handle payload too large errors."""
            return handle_request_too_large(e)
    
    def _register_request_handlers(self, app: Flask) -> None:
        """Register before and after request handlers."""
        
        @app.before_request
        def before_request():
            """Execute before each request."""
            # Set request start time for timeout tracking
            g.request_start_time = time.time()
            
            # Apply security headers and CORS
            self._apply_security_measures()
        
        @app.after_request
        def after_request(response):
            """Execute after each request."""
            # Add security headers to response
            response = self._add_security_headers(response)
            
            # Add CORS headers
            response = self._add_cors_headers(response)
            
            return response
    
    def _apply_security_measures(self) -> None:
        """Apply security measures to incoming requests."""
        # Check request timeout
        self._check_request_timeout()
        
        # Validate request headers
        self._validate_request_headers()
        
        # Check for suspicious request patterns
        self._check_suspicious_patterns()
    
    def _check_request_timeout(self) -> None:
        """Check if request processing should timeout."""
        max_request_time = self.config.get('max_request_time_seconds', 30)
        
        if hasattr(g, 'request_start_time'):
            elapsed = time.time() - g.request_start_time
            if elapsed > max_request_time:
                self.logger.warning(
                    f"Request timeout exceeded: {elapsed:.2f}s > {max_request_time}s",
                    extra={'extra_fields': {'elapsed_time': elapsed, 'max_time': max_request_time}}
                )
                raise SecurityValidationException(
                    f"Request processing timeout exceeded ({elapsed:.2f}s)",
                    security_issue="request_timeout"
                )
    
    def _validate_request_headers(self) -> None:
        """Validate request headers for security issues."""
        # Check Content-Type for POST requests
        if request.method == 'POST' and request.endpoint not in ['health_terra_pulse', 'health_dify', 'health_system', 'metrics']:
            content_type = request.headers.get('Content-Type', '')
            if not content_type.startswith('application/json'):
                self.logger.warning(
                    f"Invalid Content-Type: {content_type}",
                    extra={'extra_fields': {'content_type': content_type, 'endpoint': request.endpoint}}
                )
                raise ValidationException("Content-Type must be application/json for POST requests")
        
        # Check for suspicious User-Agent strings
        user_agent = request.headers.get('User-Agent', '')
        suspicious_agents = ['sqlmap', 'nikto', 'nmap', 'masscan', 'nessus']
        if any(agent in user_agent.lower() for agent in suspicious_agents):
            self.logger.warning(
                f"Suspicious User-Agent detected: {user_agent}",
                extra={'extra_fields': {'user_agent': user_agent, 'remote_addr': request.remote_addr}}
            )
            raise SecurityValidationException(
                "Suspicious User-Agent detected",
                security_issue="suspicious_user_agent"
            )
        
        # Check for excessively long headers
        for header_name, header_value in request.headers:
            if len(header_value) > 8192:  # 8KB limit per header
                self.logger.warning(
                    f"Excessively long header: {header_name}",
                    extra={'extra_fields': {'header_name': header_name, 'header_length': len(header_value)}}
                )
                raise SecurityValidationException(
                    f"Header '{header_name}' exceeds maximum length",
                    security_issue="oversized_header"
                )
    
    def _check_suspicious_patterns(self) -> None:
        """Check for suspicious request patterns."""
        # Check for too many headers (potential DoS)
        if len(request.headers) > 50:
            self.logger.warning(
                f"Excessive headers count: {len(request.headers)}",
                extra={'extra_fields': {'headers_count': len(request.headers)}}
            )
            raise SecurityValidationException(
                "Too many request headers",
                security_issue="excessive_headers"
            )
        
        # Check request path for suspicious patterns
        path = request.path
        suspicious_patterns = [
            '../', '..\\', '/etc/', '/proc/', '/sys/', 'cmd.exe', 'powershell',
            '<script', 'javascript:', 'vbscript:', 'onload=', 'onerror='
        ]
        
        for pattern in suspicious_patterns:
            if pattern in path.lower():
                self.logger.warning(
                    f"Suspicious path pattern detected: {pattern} in {path}",
                    extra={'extra_fields': {'path': path, 'pattern': pattern}}
                )
                raise SecurityValidationException(
                    "Suspicious request path detected",
                    security_issue="suspicious_path"
                )
    
    def _add_security_headers(self, response) -> Any:
        """Add security headers to response."""
        security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Content-Security-Policy': "default-src 'self'; script-src 'none'; object-src 'none';",
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
        
        # Add custom security headers from config
        custom_headers = self.config.get('security_headers', {})
        security_headers.update(custom_headers)
        
        for header, value in security_headers.items():
            response.headers[header] = value
        
        return response
    
    def _add_cors_headers(self, response) -> Any:
        """Add CORS headers to response."""
        cors_config = self.config.get('cors', {})
        
        # Default CORS configuration
        default_cors = {
            'origins': ['http://localhost:3000', 'http://localhost:8080'],
            'methods': ['GET', 'POST', 'OPTIONS'],
            'headers': ['Content-Type', 'Authorization', 'X-API-Key'],
            'max_age': 86400  # 24 hours
        }
        
        # Merge with custom configuration
        cors_settings = {**default_cors, **cors_config}
        
        # Get origin from request
        origin = request.headers.get('Origin')
        
        # Check if origin is allowed
        allowed_origins = cors_settings.get('origins', [])
        if origin and (origin in allowed_origins or '*' in allowed_origins):
            response.headers['Access-Control-Allow-Origin'] = origin
        elif not origin and cors_settings.get('allow_no_origin', False):
            response.headers['Access-Control-Allow-Origin'] = '*'
        
        # Add other CORS headers
        response.headers['Access-Control-Allow-Methods'] = ', '.join(cors_settings.get('methods', []))
        response.headers['Access-Control-Allow-Headers'] = ', '.join(cors_settings.get('headers', []))
        response.headers['Access-Control-Max-Age'] = str(cors_settings.get('max_age', 86400))
        
        # Allow credentials if configured
        if cors_settings.get('allow_credentials', False):
            response.headers['Access-Control-Allow-Credentials'] = 'true'
        
        return response


def create_security_middleware(config: Dict[str, Any] = None) -> SecurityMiddleware:
    """
    Factory function to create SecurityMiddleware instance.
    
    Args:
        config: Security configuration dictionary
        
    Returns:
        SecurityMiddleware: Configured security middleware
    """
    default_config = {
        'max_content_length': 1024 * 1024,  # 1MB
        'max_request_time_seconds': 30,
        'cors': {
            'origins': ['http://localhost:3000', 'http://localhost:8080'],
            'methods': ['GET', 'POST', 'OPTIONS'],
            'headers': ['Content-Type', 'Authorization', 'X-API-Key'],
            'max_age': 86400,
            'allow_credentials': False
        },
        'security_headers': {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Content-Security-Policy': "default-src 'self'; script-src 'none'; object-src 'none';",
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains'
        }
    }
    
    # Merge with provided config
    if config:
        merged_config = {**default_config}
        for key, value in config.items():
            if isinstance(value, dict) and key in merged_config:
                merged_config[key].update(value)
            else:
                merged_config[key] = value
        config = merged_config
    else:
        config = default_config
    
    return SecurityMiddleware(config=config)


def require_https(f):
    """
    Decorator to enforce HTTPS for sensitive endpoints.
    
    Args:
        f: Function to decorate
        
    Returns:
        Decorated function that enforces HTTPS
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from config.settings import get_config
        config = get_config()
        
        # Skip HTTPS check if not enforced in config
        if not config.enforce_https:
            return f(*args, **kwargs)
        
        # Skip HTTPS check in development
        if request.environ.get('SERVER_NAME') in ['localhost', '127.0.0.1']:
            return f(*args, **kwargs)
        
        # Check if request is HTTPS
        if not request.is_secure:
            logger.warning(
                f"Non-HTTPS request to secure endpoint: {request.endpoint}",
                extra={'extra_fields': {'endpoint': request.endpoint, 'remote_addr': request.remote_addr}}
            )
            
            error_response = {
                'error': 'HTTPS_REQUIRED',
                'message': 'HTTPS is required for this endpoint',
                'category': 'security',
                'severity': 'high'
            }
            return jsonify(error_response), 426  # Upgrade Required
        
        return f(*args, **kwargs)
    
    return decorated_function


def handle_options_request():
    """
    Handle preflight OPTIONS requests for CORS.
    
    Returns:
        Empty response with CORS headers
    """
    response = make_response()
    response.status_code = 200
    return response