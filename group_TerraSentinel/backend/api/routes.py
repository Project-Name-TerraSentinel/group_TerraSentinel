"""
API routes for Terra Pulse-Dify integration.
Clean, focused route handlers following single responsibility principle.
"""

from flask import Flask, request, jsonify
from typing import Dict, Any

from backend.config.settings import AppConfig
from backend.services.service_factory import get_service_factory
from backend.services.logging_service import get_logger
from backend.api.decorators import require_api_key, rate_limit, log_request, require_https
from backend.api.handlers import PredictionHandler, HealthHandler

logger = get_logger("routes")


def create_routes(app: Flask, config: AppConfig) -> None:
    """
    Create and register all API routes.
    
    Args:
        app: Flask application instance
        config: Application configuration
    """
    # Get service factory from app context
    service_factory = getattr(app, 'service_factory', None)
    if not service_factory:
        from backend.services.service_registry import register_all_services
        service_factory = register_all_services(config)
        app.service_factory = service_factory
    
    # Initialize handlers
    prediction_handler = PredictionHandler(service_factory)
    health_handler = HealthHandler(service_factory)
    
    # Prediction endpoints
    @app.route("/predict", methods=["POST"])
    @log_request
    @rate_limit
    @require_api_key
    @require_https
    def predict():
        """Basic Terra Pulse prediction endpoint."""
        return prediction_handler.handle_basic_prediction(request)
    
    @app.route("/enhanced-predict", methods=["POST"])
    @log_request
    @rate_limit
    @require_api_key
    @require_https
    def enhanced_predict():
        """Enhanced prediction with Dify AI insights."""
        return prediction_handler.handle_enhanced_prediction(request)

    @app.route('/ai', methods=['POST'])
    @log_request
    @rate_limit
    @require_api_key
    def ai_proxy():
        """Simple AI proxy endpoint that forwards structured prompts to the Dify service via server-side credentials."""
        try:
            data = request.get_json()
            if not data:
                raise ValueError('No JSON payload provided')

            # Handler will call DifyService through the service factory
            return prediction_handler.handle_ai_proxy(request)
        except Exception as e:
            logger.exception('AI proxy error')
            return jsonify({'error': 'AI_PROXY_ERROR', 'message': str(e)}), 500
    
    # Health check endpoints
    @app.route("/health/terra-pulse", methods=["GET"])
    @log_request
    def health_terra_pulse():
        """Terra Pulse service health check."""
        return health_handler.handle_terra_pulse_health()
    
    @app.route("/health/dify", methods=["GET"])
    @log_request
    def health_dify():
        """Dify service health check."""
        return health_handler.handle_dify_health()
    
    @app.route("/health/system", methods=["GET"])
    @log_request
    def health_system():
        """System-wide health check."""
        return health_handler.handle_system_health()
    
    @app.route("/metrics", methods=["GET"])
    @log_request
    def metrics():
        """Prometheus-compatible metrics."""
        return health_handler.handle_metrics()
    
    logger.info("API routes registered successfully")