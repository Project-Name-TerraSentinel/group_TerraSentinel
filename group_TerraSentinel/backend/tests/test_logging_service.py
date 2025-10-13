"""
Tests for the structured logging service.
"""

import json
import logging
import pytest
import time
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from io import StringIO
import sys

from backend.services.logging_service import (
    StructuredFormatter, PerformanceLogger, LoggingService,
    get_logging_service, get_logger, setup_request_logging
)
from backend.services.exceptions import BaseAPIException, ErrorSeverity, ErrorCategory


class TestStructuredFormatter:
    """Test the structured JSON formatter."""
    
    def test_basic_log_formatting(self):
        """Test basic log record formatting."""
        formatter = StructuredFormatter()
        
        # Create a log record
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.module = "test_module"
        record.funcName = "test_function"
        
        # Format the record
        formatted = formatter.format(record)
        
        # Parse the JSON
        log_data = json.loads(formatted)
        
        # Verify structure
        assert log_data['level'] == 'INFO'
        assert log_data['logger'] == 'test_logger'
        assert log_data['message'] == 'Test message'
        assert log_data['module'] == 'test_module'
        assert log_data['function'] == 'test_function'
        assert log_data['line'] == 42
        assert 'timestamp' in log_data
        
        # Verify timestamp format
        datetime.fromisoformat(log_data['timestamp'].replace('Z', '+00:00'))
    
    def test_log_with_extra_fields(self):
        """Test log formatting with extra fields."""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.module = "test_module"
        record.funcName = "test_function"
        record.extra_fields = {
            'user_id': 'test_user',
            'operation': 'test_operation',
            'custom_data': {'key': 'value'}
        }
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert log_data['user_id'] == 'test_user'
        assert log_data['operation'] == 'test_operation'
        assert log_data['custom_data'] == {'key': 'value'}
    
    def test_log_with_performance_data(self):
        """Test log formatting with performance metrics."""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.module = "test_module"
        record.funcName = "test_function"
        record.performance = {
            'duration_ms': 123.45,
            'operation': 'api_call'
        }
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert 'performance' in log_data
        assert log_data['performance']['duration_ms'] == 123.45
        assert log_data['performance']['operation'] == 'api_call'
    
    def test_log_with_exception(self):
        """Test log formatting with exception information."""
        formatter = StructuredFormatter()
        
        try:
            raise ValueError("Test exception")
        except ValueError:
            exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=42,
            msg="Test error message",
            args=(),
            exc_info=exc_info
        )
        record.module = "test_module"
        record.funcName = "test_function"
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert 'exception' in log_data
        assert log_data['exception']['type'] == 'ValueError'
        assert log_data['exception']['message'] == 'Test exception'
        assert isinstance(log_data['exception']['traceback'], list)


class TestPerformanceLogger:
    """Test the performance logging context manager."""
    
    def test_performance_logger_success(self):
        """Test performance logger for successful operations."""
        mock_logger = Mock()
        
        with PerformanceLogger(mock_logger, "test_operation", user_id="test_user"):
            time.sleep(0.01)  # Small delay to measure
        
        # Verify start and end log calls
        assert mock_logger.info.call_count == 1
        assert mock_logger.log.call_count == 1
        
        # Check start log
        start_call = mock_logger.info.call_args
        assert "Starting test_operation" in start_call[0][0]
        
        # Check end log
        end_call = mock_logger.log.call_args
        assert "test_operation completed" in end_call[0][1]
        assert end_call[0][0] == logging.INFO  # Log level
    
    def test_performance_logger_with_exception(self):
        """Test performance logger when operation fails."""
        mock_logger = Mock()
        
        with pytest.raises(ValueError):
            with PerformanceLogger(mock_logger, "test_operation"):
                raise ValueError("Test error")
        
        # Verify error logging
        end_call = mock_logger.log.call_args
        assert "test_operation failed" in end_call[0][1]
        assert end_call[0][0] == logging.ERROR  # Log level


class TestLoggingService:
    """Test the main logging service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Capture log output
        self.log_capture = StringIO()
        self.handler = logging.StreamHandler(self.log_capture)
        
    def test_logging_service_initialization(self):
        """Test logging service initialization."""
        service = LoggingService("test_app", "DEBUG")
        
        assert service.app_name == "test_app"
        assert service.log_level == logging.DEBUG
        
        # Test logger creation
        logger = service.get_logger("test_module")
        assert logger.name == "test_app.test_module"
    
    def test_log_api_request(self):
        """Test API request logging."""
        service = LoggingService("test_app", "INFO")
        logger = service.get_logger("test")
        logger.addHandler(self.handler)
        
        service.log_api_request(
            logger,
            method="POST",
            endpoint="/test",
            user_id="test_user"
        )
        
        # Verify log output
        log_output = self.log_capture.getvalue()
        assert "API request received" in log_output
        
        # Parse JSON log
        log_data = json.loads(log_output.strip())
        assert log_data['event_type'] == 'api_request'
        assert log_data['method'] == 'POST'
        assert log_data['endpoint'] == '/test'
        assert log_data['user_id'] == 'test_user'
    
    def test_log_api_response(self):
        """Test API response logging."""
        service = LoggingService("test_app", "INFO")
        logger = service.get_logger("test")
        logger.addHandler(self.handler)
        
        service.log_api_response(
            logger,
            status_code=200,
            processing_time_ms=123.45,
            endpoint="/test"
        )
        
        # Verify log output
        log_output = self.log_capture.getvalue()
        assert "API response sent with status 200" in log_output
        
        # Parse JSON log
        log_data = json.loads(log_output.strip())
        assert log_data['event_type'] == 'api_response'
        assert log_data['status_code'] == 200
        assert log_data['processing_time_ms'] == 123.45
    
    def test_log_external_api_call(self):
        """Test external API call logging."""
        service = LoggingService("test_app", "INFO")
        logger = service.get_logger("test")
        logger.addHandler(self.handler)
        
        service.log_external_api_call(
            logger,
            service="dify",
            endpoint="/workflow",
            method="POST",
            response_time_ms=456.78
        )
        
        # Verify log output
        log_output = self.log_capture.getvalue()
        assert "External API call to dify" in log_output
        
        # Parse JSON log
        log_data = json.loads(log_output.strip())
        assert log_data['event_type'] == 'external_api_call'
        assert log_data['service'] == 'dify'
        assert log_data['endpoint'] == '/workflow'
        assert log_data['method'] == 'POST'
    
    def test_log_cache_operation(self):
        """Test cache operation logging."""
        service = LoggingService("test_app", "DEBUG")
        logger = service.get_logger("test")
        logger.addHandler(self.handler)
        
        service.log_cache_operation(
            logger,
            operation="get",
            key="test_key",
            hit=True
        )
        
        # Verify log output
        log_output = self.log_capture.getvalue()
        assert "Cache get: test_key" in log_output
        
        # Parse JSON log
        log_data = json.loads(log_output.strip())
        assert log_data['event_type'] == 'cache_operation'
        assert log_data['operation'] == 'get'
        assert log_data['cache_key'] == 'test_key'
        assert log_data['cache_hit'] is True
    
    def test_log_security_event(self):
        """Test security event logging."""
        service = LoggingService("test_app", "INFO")
        logger = service.get_logger("test")
        logger.addHandler(self.handler)
        
        service.log_security_event(
            logger,
            event_type="invalid_api_key",
            severity="high",
            api_key_hint="abc123...",
            remote_addr="192.168.1.1"
        )
        
        # Verify log output
        log_output = self.log_capture.getvalue()
        assert "Security event: invalid_api_key" in log_output
        
        # Parse JSON log
        log_data = json.loads(log_output.strip())
        assert log_data['event_type'] == 'security_event'
        assert log_data['security_event_type'] == 'invalid_api_key'
        assert log_data['severity'] == 'high'
        assert log_data['api_key_hint'] == 'abc123...'
    
    def test_performance_timer(self):
        """Test performance timer context manager."""
        service = LoggingService("test_app", "INFO")
        logger = service.get_logger("test")
        logger.addHandler(self.handler)
        
        with service.performance_timer(logger, "test_operation", user_id="test_user"):
            time.sleep(0.01)
        
        # Verify log output contains both start and end messages
        log_output = self.log_capture.getvalue()
        assert "Starting test_operation" in log_output
        assert "test_operation completed" in log_output


class TestLoggingIntegration:
    """Test logging integration with Flask and other components."""
    
    @patch('services.logging_service.has_request_context')
    @patch('services.logging_service.request')
    @patch('services.logging_service.g')
    def test_request_context_logging(self, mock_g, mock_request, mock_has_context):
        """Test logging with Flask request context."""
        # Mock Flask request context
        mock_has_context.return_value = True
        mock_request.endpoint = '/test'
        mock_request.method = 'POST'
        mock_request.path = '/test'
        mock_request.remote_addr = '192.168.1.1'
        mock_request.headers = {'User-Agent': 'test-agent'}
        mock_g.request_id = 'test-request-id'
        mock_g.api_key_hash = 'abc123'
        
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.module = "test_module"
        record.funcName = "test_function"
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        # Verify request context is included
        assert log_data['request_id'] == 'test-request-id'
        assert log_data['endpoint'] == '/test'
        assert log_data['method'] == 'POST'
        assert log_data['path'] == '/test'
        assert log_data['remote_addr'] == '192.168.1.1'
        assert log_data['user_agent'] == 'test-agent'
        assert log_data['api_key_hash'] == 'abc123'
    
    def test_get_logging_service_singleton(self):
        """Test that get_logging_service returns singleton."""
        service1 = get_logging_service("test_app", "INFO")
        service2 = get_logging_service("test_app", "DEBUG")  # Different params
        
        # Should return the same instance
        assert service1 is service2
    
    def test_get_logger_convenience_function(self):
        """Test the convenience get_logger function."""
        logger = get_logger("test_module")
        
        assert logger.name == "terra_pulse_dify.test_module"
        assert isinstance(logger, logging.Logger)


class TestLogValidation:
    """Test log output validation and format compliance."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.log_capture = StringIO()
        self.handler = logging.StreamHandler(self.log_capture)
        
        # Create logging service
        self.service = LoggingService("test_app", "DEBUG")
        self.logger = self.service.get_logger("test")
        self.logger.addHandler(self.handler)
    
    def test_log_json_format_compliance(self):
        """Test that all logs are valid JSON."""
        # Generate various types of logs
        self.service.log_api_request(self.logger, method="GET", endpoint="/test")
        self.service.log_api_response(self.logger, status_code=200, processing_time_ms=100)
        self.service.log_external_api_call(self.logger, service="test", endpoint="/api", method="POST")
        self.service.log_cache_operation(self.logger, operation="set", key="test_key")
        self.service.log_security_event(self.logger, event_type="test_event")
        
        # Verify all logs are valid JSON
        log_output = self.log_capture.getvalue()
        log_lines = [line.strip() for line in log_output.split('\n') if line.strip()]
        
        for line in log_lines:
            try:
                log_data = json.loads(line)
                # Verify required fields
                assert 'timestamp' in log_data
                assert 'level' in log_data
                assert 'logger' in log_data
                assert 'message' in log_data
            except json.JSONDecodeError:
                pytest.fail(f"Invalid JSON log line: {line}")
    
    def test_log_field_consistency(self):
        """Test that log fields are consistent across different log types."""
        # Generate logs with extra fields
        self.service.log_api_request(
            self.logger,
            method="POST",
            endpoint="/test",
            user_id="test_user",
            custom_field="custom_value"
        )
        
        log_output = self.log_capture.getvalue()
        log_data = json.loads(log_output.strip())
        
        # Verify standard fields
        required_fields = ['timestamp', 'level', 'logger', 'message', 'module', 'function', 'line']
        for field in required_fields:
            assert field in log_data, f"Missing required field: {field}"
        
        # Verify extra fields
        assert log_data['method'] == 'POST'
        assert log_data['endpoint'] == '/test'
        assert log_data['user_id'] == 'test_user'
        assert log_data['custom_field'] == 'custom_value'
    
    def test_log_timestamp_format(self):
        """Test that timestamps are in correct ISO format."""
        self.logger.info("Test message")
        
        log_output = self.log_capture.getvalue()
        log_data = json.loads(log_output.strip())
        
        timestamp = log_data['timestamp']
        
        # Should be ISO format with Z suffix
        assert timestamp.endswith('Z')
        
        # Should be parseable as datetime
        parsed_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        assert isinstance(parsed_time, datetime)
    
    def test_log_level_consistency(self):
        """Test that log levels are correctly formatted."""
        test_levels = [
            (logging.DEBUG, 'DEBUG'),
            (logging.INFO, 'INFO'),
            (logging.WARNING, 'WARNING'),
            (logging.ERROR, 'ERROR'),
            (logging.CRITICAL, 'CRITICAL')
        ]
        
        for level_num, level_name in test_levels:
            # Clear previous output
            self.log_capture.truncate(0)
            self.log_capture.seek(0)
            
            self.logger.log(level_num, f"Test {level_name} message")
            
            log_output = self.log_capture.getvalue()
            if log_output.strip():  # Only check if log was actually output
                log_data = json.loads(log_output.strip())
                assert log_data['level'] == level_name


if __name__ == '__main__':
    pytest.main([__file__])