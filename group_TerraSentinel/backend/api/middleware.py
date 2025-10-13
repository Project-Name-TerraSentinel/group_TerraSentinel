"""
Middleware setup for Terra Pulse-Dify integration.
Clean middleware configuration following separation of concerns.
"""

from flask import Flask
from backend.config.settings import AppConfig
from backend.services.logging_service import get_logger

logger = get_logger("middleware")


def setup_middleware(app: Flask, config: AppConfig) -> None:
    """
    Setup all middleware for the Flask application.
    
    Args:
        app: Flask application instance
        config: Application configuration
    """
    # Setup security middleware
    _setup_security_middleware(app, config)
    
    # Setup CORS
    _setup_cors(app, config)
    
    # Setup request/response middleware
    _setup_request_middleware(app)
    
    logger.info("Middleware setup completed")


def _setup_security_middleware(app: Flask, config: AppConfig) -> None:
    """Setup security-related middleware."""
    try:
        from services.security_middleware import create_security_middleware
        
        security_config = {
            'max_content_length': 2 * 1024 * 1024,  # 2MB
            'max_request_time_seconds': 60,
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
        
        logger.info("Security middleware configured")
        
    except ImportError:
        logger.warning("Security middleware not available")


def _setup_cors(app: Flask, config: AppConfig) -> None:
    """Setup CORS handling."""
    @app.route('/<path:path>', methods=['OPTIONS'])
    def handle_cors_preflight(path):
        """Handle CORS preflight requests."""
        try:
            from services.security_middleware import handle_options_request
            return handle_options_request()
        except ImportError:
            # Fallback CORS handling
            from flask import make_response
            response = make_response()
            response.headers.add("Access-Control-Allow-Origin", "*")
            response.headers.add('Access-Control-Allow-Headers', "*")
            response.headers.add('Access-Control-Allow-Methods', "*")
            return response


def _setup_request_middleware(app: Flask) -> None:
    """Setup request/response middleware."""
    
    @app.before_request
    def before_request():
        """Execute before each request."""
        # Request preprocessing can be added here
        pass
    
    @app.after_request
    def after_request(response):
        """Execute after each request."""
        # Add security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        return response