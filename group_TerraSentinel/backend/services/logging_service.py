"""
Structured logging service for Terra Pulse-Dify integration.
Provides JSON-based logging with request tracing and performance metrics.
"""

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Union
from contextvars import ContextVar
from functools import wraps
import traceback
import sys
# Optional Flask imports for request context
try:
    from flask import request, g, has_request_context
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    # Mock Flask objects for testing
    class MockRequest:
        endpoint = None
        method = None
        path = None
        remote_addr = None
        headers = {}
    
    class MockG:
        pass
    
    request = MockRequest()
    g = MockG()
    
    def has_request_context():
        return False


# Context variables for request tracing
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured JSON logs with consistent fields.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        
        # Base log structure
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add request context if available
        if has_request_context():
            try:
                log_entry.update({
                    'request_id': getattr(g, 'request_id', None),
                    'endpoint': request.endpoint,
                    'method': request.method,
                    'path': request.path,
                    'remote_addr': request.remote_addr,
                    'user_agent': request.headers.get('User-Agent', ''),
                    'api_key_hash': getattr(g, 'api_key_hash', None)
                })
            except RuntimeError:
                # Outside request context
                pass
        
        # Add context variables
        request_id = request_id_var.get()
        user_id = user_id_var.get()
        
        if request_id:
            log_entry['request_id'] = request_id
        if user_id:
            log_entry['user_id'] = user_id
        
        # Add extra fields from record
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        # Add performance metrics if available
        if hasattr(record, 'performance'):
            log_entry['performance'] = record.performance
        
        # Add error details for exceptions
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Add stack trace for errors
        if record.levelno >= logging.ERROR and not record.exc_info:
            log_entry['stack_trace'] = traceback.format_stack()
        
        return json.dumps(log_entry, default=str, ensure_ascii=False)


class PerformanceLogger:
    """
    Context manager for logging performance metrics.
    """
    
    def __init__(self, logger: logging.Logger, operation: str, **kwargs):
        self.logger = logger
        self.operation = operation
        self.extra_fields = kwargs
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        self.logger.info(
            f"Starting {self.operation}",
            extra={
                'extra_fields': {
                    'operation': self.operation,
                    'operation_status': 'started',
                    **self.extra_fields
                }
            }
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration_ms = (self.end_time - self.start_time) * 1000
        
        status = 'failed' if exc_type else 'completed'
        level = logging.ERROR if exc_type else logging.INFO
        
        performance_data = {
            'operation': self.operation,
            'operation_status': status,
            'duration_ms': round(duration_ms, 2),
            'start_time': self.start_time,
            'end_time': self.end_time,
            **self.extra_fields
        }
        
        if exc_type:
            performance_data['error_type'] = exc_type.__name__
            performance_data['error_message'] = str(exc_val)
        
        self.logger.log(
            level,
            f"{self.operation} {status} in {duration_ms:.2f}ms",
            extra={
                'extra_fields': performance_data,
                'performance': performance_data
            }
        )


class LoggingService:
    """
    Centralized logging service with structured logging and request tracing.
    """
    
    def __init__(self, app_name: str = "terra_pulse_dify", log_level: str = "INFO"):
        self.app_name = app_name
        self.log_level = getattr(logging, log_level.upper())
        self._setup_logging()
    
    def _setup_logging(self):
        """Configure structured logging for the application."""
        
        # Remove existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Create structured formatter
        formatter = StructuredFormatter()
        
        # Console handler with structured output
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(self.log_level)
        
        # Configure root logger
        root_logger.setLevel(self.log_level)
        root_logger.addHandler(console_handler)
        
        # Configure specific loggers
        self._configure_logger('terra_pulse_dify', self.log_level)
        self._configure_logger('services', self.log_level)
        self._configure_logger('werkzeug', logging.WARNING)  # Reduce Flask noise
        self._configure_logger('urllib3', logging.WARNING)   # Reduce HTTP noise
    
    def _configure_logger(self, name: str, level: int):
        """Configure a specific logger."""
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.propagate = True
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger instance with the given name."""
        return logging.getLogger(f"{self.app_name}.{name}")
    
    def log_api_request(self, logger: logging.Logger, **kwargs):
        """Log API request with structured data."""
        logger.info(
            "API request received",
            extra={
                'extra_fields': {
                    'event_type': 'api_request',
                    **kwargs
                }
            }
        )
    
    def log_api_response(self, logger: logging.Logger, status_code: int, 
                        processing_time_ms: float, **kwargs):
        """Log API response with performance metrics."""
        level = logging.INFO if status_code < 400 else logging.ERROR
        
        logger.log(
            level,
            f"API response sent with status {status_code}",
            extra={
                'extra_fields': {
                    'event_type': 'api_response',
                    'status_code': status_code,
                    'processing_time_ms': processing_time_ms,
                    **kwargs
                },
                'performance': {
                    'processing_time_ms': processing_time_ms,
                    'status_code': status_code
                }
            }
        )
    
    def log_external_api_call(self, logger: logging.Logger, service: str, 
                             endpoint: str, method: str, **kwargs):
        """Log external API call."""
        logger.info(
            f"External API call to {service}",
            extra={
                'extra_fields': {
                    'event_type': 'external_api_call',
                    'service': service,
                    'endpoint': endpoint,
                    'method': method,
                    **kwargs
                }
            }
        )
    
    def log_cache_operation(self, logger: logging.Logger, operation: str, 
                           key: str, hit: bool = None, **kwargs):
        """Log cache operation."""
        logger.debug(
            f"Cache {operation}: {key}",
            extra={
                'extra_fields': {
                    'event_type': 'cache_operation',
                    'operation': operation,
                    'cache_key': key,
                    'cache_hit': hit,
                    **kwargs
                }
            }
        )
    
    def log_security_event(self, logger: logging.Logger, event_type: str, 
                          severity: str = "medium", **kwargs):
        """Log security-related events."""
        level = {
            'low': logging.INFO,
            'medium': logging.WARNING,
            'high': logging.ERROR,
            'critical': logging.CRITICAL
        }.get(severity, logging.WARNING)
        
        logger.log(
            level,
            f"Security event: {event_type}",
            extra={
                'extra_fields': {
                    'event_type': 'security_event',
                    'security_event_type': event_type,
                    'severity': severity,
                    **kwargs
                }
            }
        )
    
    def performance_timer(self, logger: logging.Logger, operation: str, **kwargs):
        """Create a performance timer context manager."""
        return PerformanceLogger(logger, operation, **kwargs)


def setup_request_logging():
    """
    Decorator to set up request-specific logging context.
    Should be applied to Flask routes.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Generate unique request ID
            request_id = str(uuid.uuid4())
            g.request_id = request_id
            request_id_var.set(request_id)
            
            # Hash API key for logging (if present)
            api_key = getattr(g, 'api_key', None)
            if api_key:
                import hashlib
                g.api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:8]
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


# Global logging service instance
_logging_service = None


def get_logging_service(app_name: str = "terra_pulse_dify", 
                       log_level: str = "INFO") -> LoggingService:
    """Get or create the global logging service instance."""
    global _logging_service
    if _logging_service is None:
        _logging_service = LoggingService(app_name, log_level)
    return _logging_service


def get_logger(name: str) -> logging.Logger:
    """Convenience function to get a logger."""
    service = get_logging_service()
    return service.get_logger(name)