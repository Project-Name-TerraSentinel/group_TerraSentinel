"""
Tests for the alerting service and error handling.
"""

import json
import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from io import StringIO
import threading

from backend.services.alerting_service import (
    AlertingService, Alert, AlertLevel, AlertChannel, AlertThrottler,
    EmailAlerter, WebhookAlerter, get_alerting_service, send_alert, send_exception_alert
)
from backend.services.exceptions import (
    BaseAPIException, ValidationException, AuthenticationException,
    TerraPulseServiceException, DifyServiceException, ErrorSeverity, ErrorCategory
)


class TestAlert:
    """Test the Alert data structure."""
    
    def test_alert_creation(self):
        """Test basic alert creation."""
        timestamp = datetime.utcnow()
        
        alert = Alert(
            id="test_alert_1",
            title="Test Alert",
            message="This is a test alert",
            level=AlertLevel.WARNING,
            category="test",
            timestamp=timestamp,
            details={"key": "value"},
            source="test_system"
        )
        
        assert alert.id == "test_alert_1"
        assert alert.title == "Test Alert"
        assert alert.message == "This is a test alert"
        assert alert.level == AlertLevel.WARNING
        assert alert.category == "test"
        assert alert.timestamp == timestamp
        assert alert.details == {"key": "value"}
        assert alert.source == "test_system"
        assert alert.count == 1
        assert alert.first_occurrence == timestamp
        assert alert.last_occurrence == timestamp
    
    def test_alert_post_init(self):
        """Test alert post-initialization logic."""
        timestamp = datetime.utcnow()
        
        alert = Alert(
            id="test_alert_2",
            title="Test Alert",
            message="Test message",
            level=AlertLevel.ERROR,
            category="test",
            timestamp=timestamp,
            details={},
            source="test"
        )
        
        # Should set first and last occurrence to timestamp
        assert alert.first_occurrence == timestamp
        assert alert.last_occurrence == timestamp


class TestAlertThrottler:
    """Test the alert throttling mechanism."""
    
    def test_throttler_allows_initial_alerts(self):
        """Test that throttler allows initial alerts."""
        throttler = AlertThrottler(window_minutes=1, max_alerts_per_window=3)
        
        # First few alerts should be allowed
        assert throttler.should_send_alert("test_key") is True
        assert throttler.should_send_alert("test_key") is True
        assert throttler.should_send_alert("test_key") is True
    
    def test_throttler_blocks_excess_alerts(self):
        """Test that throttler blocks alerts after limit."""
        throttler = AlertThrottler(window_minutes=1, max_alerts_per_window=2)
        
        # First two should be allowed
        assert throttler.should_send_alert("test_key") is True
        assert throttler.should_send_alert("test_key") is True
        
        # Third should be blocked
        assert throttler.should_send_alert("test_key") is False
    
    def test_throttler_different_keys(self):
        """Test that throttler handles different keys independently."""
        throttler = AlertThrottler(window_minutes=1, max_alerts_per_window=1)
        
        # Different keys should be independent
        assert throttler.should_send_alert("key1") is True
        assert throttler.should_send_alert("key2") is True
        
        # Same keys should be throttled
        assert throttler.should_send_alert("key1") is False
        assert throttler.should_send_alert("key2") is False
    
    def test_throttler_get_alert_count(self):
        """Test getting alert count for a key."""
        throttler = AlertThrottler(window_minutes=1, max_alerts_per_window=5)
        
        # Send some alerts
        throttler.should_send_alert("test_key")
        throttler.should_send_alert("test_key")
        throttler.should_send_alert("test_key")
        
        assert throttler.get_alert_count("test_key") == 3
        assert throttler.get_alert_count("other_key") == 0


class TestEmailAlerter:
    """Test the email alerting functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.email_alerter = EmailAlerter(
            smtp_host="smtp.test.com",
            smtp_port=587,
            username="test@example.com",
            password="password",
            from_email="alerts@example.com",
            to_emails=["admin@example.com", "ops@example.com"]
        )
    
    @patch('smtplib.SMTP')
    def test_email_alerter_success(self, mock_smtp):
        """Test successful email alert sending."""
        # Mock SMTP server
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        alert = Alert(
            id="test_alert",
            title="Test Alert",
            message="Test message",
            level=AlertLevel.ERROR,
            category="test",
            timestamp=datetime.utcnow(),
            details={"error_code": "TEST_ERROR"},
            source="test_system"
        )
        
        result = self.email_alerter.send_alert(alert)
        
        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("test@example.com", "password")
        mock_server.send_message.assert_called_once()
    
    @patch('smtplib.SMTP')
    def test_email_alerter_failure(self, mock_smtp):
        """Test email alert sending failure."""
        # Mock SMTP failure
        mock_smtp.side_effect = Exception("SMTP connection failed")
        
        alert = Alert(
            id="test_alert",
            title="Test Alert",
            message="Test message",
            level=AlertLevel.ERROR,
            category="test",
            timestamp=datetime.utcnow(),
            details={},
            source="test_system"
        )
        
        result = self.email_alerter.send_alert(alert)
        
        assert result is False
    
    def test_email_body_formatting(self):
        """Test email body HTML formatting."""
        alert = Alert(
            id="test_alert",
            title="Critical System Error",
            message="Database connection failed",
            level=AlertLevel.CRITICAL,
            category="database",
            timestamp=datetime.utcnow(),
            details={"connection_string": "postgres://...", "retry_count": 3},
            source="api_server",
            count=5
        )
        
        body = self.email_alerter._format_email_body(alert)
        
        # Verify HTML structure
        assert "<html>" in body
        assert "<body>" in body
        assert "Critical System Error" in body
        assert "Database connection failed" in body
        assert "CRITICAL" in body
        assert "database" in body
        assert "api_server" in body
        assert "Count: 5" in body
        assert "postgres://" in body


class TestWebhookAlerter:
    """Test the webhook alerting functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.webhook_alerter = WebhookAlerter(
            webhook_url="https://hooks.example.com/alerts",
            headers={"Authorization": "Bearer token123"}
        )
    
    @patch('requests.post')
    def test_webhook_alerter_success(self, mock_post):
        """Test successful webhook alert sending."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        alert = Alert(
            id="test_alert",
            title="Test Alert",
            message="Test message",
            level=AlertLevel.WARNING,
            category="test",
            timestamp=datetime.utcnow(),
            details={"key": "value"},
            source="test_system"
        )
        
        result = self.webhook_alerter.send_alert(alert)
        
        assert result is True
        mock_post.assert_called_once()
        
        # Verify request parameters
        call_args = mock_post.call_args
        assert call_args[1]['json']['alert_id'] == "test_alert"
        assert call_args[1]['json']['title'] == "Test Alert"
        assert call_args[1]['json']['level'] == "warning"
        assert call_args[1]['headers']['Authorization'] == "Bearer token123"
    
    @patch('requests.post')
    def test_webhook_alerter_failure(self, mock_post):
        """Test webhook alert sending failure."""
        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response
        
        alert = Alert(
            id="test_alert",
            title="Test Alert",
            message="Test message",
            level=AlertLevel.ERROR,
            category="test",
            timestamp=datetime.utcnow(),
            details={},
            source="test_system"
        )
        
        result = self.webhook_alerter.send_alert(alert)
        
        assert result is False
    
    @patch('requests.post')
    def test_webhook_alerter_exception(self, mock_post):
        """Test webhook alerter handling exceptions."""
        # Mock request exception
        mock_post.side_effect = Exception("Network error")
        
        alert = Alert(
            id="test_alert",
            title="Test Alert",
            message="Test message",
            level=AlertLevel.ERROR,
            category="test",
            timestamp=datetime.utcnow(),
            details={},
            source="test_system"
        )
        
        result = self.webhook_alerter.send_alert(alert)
        
        assert result is False


class TestAlertingService:
    """Test the main alerting service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = {
            'email': {'enabled': False},
            'webhook': {'enabled': False},
            'throttle_window_minutes': 1,
            'max_alerts_per_window': 3
        }
        self.alerting_service = AlertingService(self.config)
    
    def test_alerting_service_initialization(self):
        """Test alerting service initialization."""
        assert self.alerting_service.config == self.config
        assert AlertChannel.LOG in self.alerting_service.alerters
        assert AlertChannel.CONSOLE in self.alerting_service.alerters
        assert len(self.alerting_service.alert_rules) > 0
    
    def test_send_alert_basic(self):
        """Test basic alert sending."""
        with patch.object(self.alerting_service, '_send_alert_async') as mock_send:
            alert_id = self.alerting_service.send_alert(
                title="Test Alert",
                message="Test message",
                level=AlertLevel.INFO,
                category="test"
            )
            
            assert alert_id.startswith("terra_pulse_dify_test_")
            mock_send.assert_called_once()
    
    def test_send_alert_with_details(self):
        """Test alert sending with additional details."""
        with patch.object(self.alerting_service, '_send_alert_async') as mock_send:
            alert_id = self.alerting_service.send_alert(
                title="Database Error",
                message="Connection timeout",
                level=AlertLevel.ERROR,
                category="database",
                details={"timeout_seconds": 30, "retry_count": 3},
                source="api_server"
            )
            
            assert alert_id is not None
            mock_send.assert_called_once()
            
            # Verify alert object
            alert = mock_send.call_args[0][0]
            assert alert.title == "Database Error"
            assert alert.message == "Connection timeout"
            assert alert.level == AlertLevel.ERROR
            assert alert.category == "database"
            assert alert.details["timeout_seconds"] == 30
            assert alert.source == "api_server"
    
    def test_send_exception_alert_base_exception(self):
        """Test sending alert for BaseAPIException."""
        exception = ValidationException(
            message="Invalid input data",
            validation_errors=["field1 is required", "field2 is invalid"]
        )
        
        with patch.object(self.alerting_service, '_send_alert_async') as mock_send:
            self.alerting_service.send_exception_alert(
                exception,
                context={"endpoint": "/api/test", "user_id": "test_user"}
            )
            
            mock_send.assert_called_once()
            
            # Verify alert object
            alert = mock_send.call_args[0][0]
            assert "VALIDATION_EXCEPTION" in alert.title
            assert alert.message == "Invalid input data"
            assert alert.level == AlertLevel.INFO  # ValidationException has LOW severity
            assert alert.category == "validation"
            assert "endpoint" in alert.details
            assert "user_id" in alert.details
    
    def test_send_exception_alert_generic_exception(self):
        """Test sending alert for generic exception."""
        exception = RuntimeError("Unexpected error occurred")
        
        with patch.object(self.alerting_service, '_send_alert_async') as mock_send:
            self.alerting_service.send_exception_alert(
                exception,
                context={"operation": "data_processing"}
            )
            
            mock_send.assert_called_once()
            
            # Verify alert object
            alert = mock_send.call_args[0][0]
            assert "Unhandled Exception: RuntimeError" in alert.title
            assert alert.message == "Unexpected error occurred"
            assert alert.level == AlertLevel.ERROR
            assert alert.category == "unhandled_exception"
            assert "operation" in alert.details
    
    def test_alert_throttling(self):
        """Test alert throttling functionality."""
        # Configure tight throttling
        self.alerting_service.throttler = AlertThrottler(
            window_minutes=1, max_alerts_per_window=1
        )
        
        with patch.object(self.alerting_service, '_send_alert_async') as mock_send:
            # First alert should go through
            self.alerting_service.send_alert(
                title="Test Alert",
                message="First message",
                level=AlertLevel.ERROR,
                category="test"
            )
            
            # Second alert should be throttled
            self.alerting_service.send_alert(
                title="Test Alert",
                message="Second message",
                level=AlertLevel.ERROR,
                category="test"
            )
            
            # Only one alert should be sent
            assert mock_send.call_count == 1
    
    def test_alert_aggregation(self):
        """Test alert aggregation functionality."""
        with patch.object(self.alerting_service, '_send_alert_async') as mock_send:
            # Send multiple similar alerts
            for i in range(3):
                self.alerting_service.send_alert(
                    title="Database Connection Error",
                    message=f"Connection failed attempt {i+1}",
                    level=AlertLevel.CRITICAL,  # Critical errors are aggregated
                    category="database"
                )
            
            # Should aggregate into single alert
            assert mock_send.call_count == 1
            
            # Verify aggregated alert
            alert = mock_send.call_args[0][0]
            assert alert.count == 3
    
    def test_log_alerter(self):
        """Test the log-based alerter."""
        alert = Alert(
            id="test_alert",
            title="Test Log Alert",
            message="Test log message",
            level=AlertLevel.WARNING,
            category="test",
            timestamp=datetime.utcnow(),
            details={"key": "value"},
            source="test_system"
        )
        
        with patch('logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            self.alerting_service._log_alerter(alert)
            
            mock_logger.log.assert_called_once()
            call_args = mock_logger.log.call_args
            assert call_args[0][0] == 30  # WARNING level
            assert "ALERT: Test Log Alert - Test log message" in call_args[0][1]
    
    def test_console_alerter(self):
        """Test the console-based alerter."""
        alert = Alert(
            id="test_alert",
            title="Test Console Alert",
            message="Test console message",
            level=AlertLevel.ERROR,
            category="test",
            timestamp=datetime.utcnow(),
            details={},
            source="test_system"
        )
        
        with patch('builtins.print') as mock_print:
            self.alerting_service._console_alerter(alert)
            
            # Verify print was called with alert information
            assert mock_print.call_count >= 4  # Multiple print calls for formatting
            
            # Check that alert title appears in output
            print_calls = [str(call) for call in mock_print.call_args_list]
            alert_output = ' '.join(print_calls)
            assert "Test Console Alert" in alert_output
    
    def test_severity_to_alert_level_mapping(self):
        """Test mapping of error severity to alert levels."""
        mappings = [
            (ErrorSeverity.LOW, AlertLevel.INFO),
            (ErrorSeverity.MEDIUM, AlertLevel.WARNING),
            (ErrorSeverity.HIGH, AlertLevel.ERROR),
            (ErrorSeverity.CRITICAL, AlertLevel.CRITICAL)
        ]
        
        for severity, expected_level in mappings:
            result = self.alerting_service._map_severity_to_alert_level(severity)
            assert result == expected_level
    
    def test_alert_rule_selection(self):
        """Test alert rule selection based on level and category."""
        test_cases = [
            (AlertLevel.CRITICAL, "general", "critical_errors"),
            (AlertLevel.ERROR, "general", "high_errors"),
            (AlertLevel.WARNING, "general", "medium_errors"),
            (AlertLevel.INFO, "security_event", "security_events"),
            (AlertLevel.ERROR, "security_event", "security_events")
        ]
        
        for level, category, expected_rule in test_cases:
            rule_key = self.alerting_service._get_rule_key(level, category)
            assert rule_key == expected_rule


class TestAlertingIntegration:
    """Test alerting service integration with other components."""
    
    def test_get_alerting_service_singleton(self):
        """Test that get_alerting_service returns singleton."""
        config1 = {'test': 'config1'}
        config2 = {'test': 'config2'}
        
        service1 = get_alerting_service(config1)
        service2 = get_alerting_service(config2)  # Different config
        
        # Should return the same instance
        assert service1 is service2
    
    def test_send_alert_convenience_function(self):
        """Test the convenience send_alert function."""
        with patch('services.alerting_service.get_alerting_service') as mock_get_service:
            mock_service = Mock()
            mock_service.send_alert.return_value = "test_alert_id"
            mock_get_service.return_value = mock_service
            
            alert_id = send_alert(
                title="Test Alert",
                message="Test message",
                level=AlertLevel.WARNING,
                category="test"
            )
            
            assert alert_id == "test_alert_id"
            mock_service.send_alert.assert_called_once_with(
                "Test Alert", "Test message", AlertLevel.WARNING, category="test"
            )
    
    def test_send_exception_alert_convenience_function(self):
        """Test the convenience send_exception_alert function."""
        exception = ValueError("Test error")
        context = {"operation": "test"}
        
        with patch('services.alerting_service.get_alerting_service') as mock_get_service:
            mock_service = Mock()
            mock_get_service.return_value = mock_service
            
            send_exception_alert(exception, context)
            
            mock_service.send_exception_alert.assert_called_once_with(exception, context)


class TestAlertingConfiguration:
    """Test alerting service configuration and setup."""
    
    def test_email_alerter_configuration(self):
        """Test email alerter configuration."""
        config = {
            'email': {
                'enabled': True,
                'smtp_host': 'smtp.test.com',
                'smtp_port': 587,
                'username': 'test@example.com',
                'password': 'password',
                'from_email': 'alerts@example.com',
                'to_emails': ['admin@example.com']
            },
            'webhook': {'enabled': False}
        }
        
        service = AlertingService(config)
        
        assert AlertChannel.EMAIL in service.alerters
        assert isinstance(service.alerters[AlertChannel.EMAIL], EmailAlerter)
    
    def test_webhook_alerter_configuration(self):
        """Test webhook alerter configuration."""
        config = {
            'email': {'enabled': False},
            'webhook': {
                'enabled': True,
                'url': 'https://hooks.example.com/alerts',
                'headers': {'Authorization': 'Bearer token'}
            }
        }
        
        service = AlertingService(config)
        
        assert AlertChannel.WEBHOOK in service.alerters
        assert isinstance(service.alerters[AlertChannel.WEBHOOK], WebhookAlerter)
    
    def test_invalid_email_configuration(self):
        """Test handling of invalid email configuration."""
        config = {
            'email': {
                'enabled': True,
                'smtp_host': 'smtp.test.com'
                # Missing required fields
            },
            'webhook': {'enabled': False}
        }
        
        # Should not raise exception, just skip email alerter
        service = AlertingService(config)
        
        assert AlertChannel.EMAIL not in service.alerters
        assert AlertChannel.LOG in service.alerters  # Should still have log alerter


if __name__ == '__main__':
    pytest.main([__file__])