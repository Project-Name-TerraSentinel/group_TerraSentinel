"""
Error handlers for Terra Pulse-Dify integration.
Centralized error handling following clean architecture principles.
"""

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from backend.services.exceptions import BaseAPIException
from backend.services.logging_service import get_logger
from backend.services.alerting_service import send_exception_alert

logger = get_logger("error_handlers")


def setup_error_handlers(app: Flask) -> None:
    """
    Setup centralized error handlers for the Flask application.
    
    Args:
        app: Flask application instance
    """
    
    @app.errorhandler(BaseAPIException)
    def handle_api_exception(error: BaseAPIException):
        """Handle custom API exceptions."""
        logger.error(
            f"API Exception: {error.error_code}",
            extra={
                'extra_fields': {
                    'error_code': error.error_code,
                    'category': error.category.value,
                    'severity': error.severity.value,
                    'user_message': error.user_message
                }
            }
        )
        
        # Send alert if required
        if error.alerting_required:
            send_exception_alert(error, {'handled_by': 'error_handler'})
        
        return jsonify(error.to_dict()), error.status_code
    
    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        """Handle standard HTTP exceptions."""
        logger.warning(f"HTTP Exception: {error.code} - {error.description}")
        
        return jsonify({
            'error': f'HTTP_{error.code}',
            'message': error.description,
            'status_code': error.code
        }), error.code
    
    @app.errorhandler(Exception)
    def handle_generic_exception(error: Exception):
        """Handle unexpected exceptions."""
        logger.error(
            f"Unhandled exception: {str(error)}",
            extra={'extra_fields': {'error_type': error.__class__.__name__}},
            exc_info=True
        )
        
        # Send alert for unhandled exceptions
        send_exception_alert(error, {'handled_by': 'generic_error_handler'})
        
        return jsonify({
            'error': 'INTERNAL_ERROR',
            'message': 'An unexpected error occurred',
            'details': {'error_type': error.__class__.__name__}
        }), 500
    
    logger.info("Error handlers configured")