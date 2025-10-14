"""
Alerting service for Terra Pulse-Dify integration.
Clean alerting implementation following single responsibility principle.
"""

import logging
from typing import Dict, Any, Optional
from backend.services.logging_service import get_logger

logger = get_logger("alerting")


class AlertingService:
    """
    Simple alerting service for critical errors.
    Follows Uncle Bob's principle of doing one thing well.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get('enabled', True)
    
    def send_alert(self, exception: Exception, context: Dict[str, Any] = None) -> bool:
        """
        Send alert for exception.
        
        Args:
            exception: Exception to alert on
            context: Additional context information
            
        Returns:
            bool: True if alert sent successfully
        """
        if not self.enabled:
            return False
        
        try:
            # For now, just log the alert
            # In production, this would send emails, webhooks, etc.
            logger.error(
                f"ALERT: {exception.__class__.__name__}: {str(exception)}",
                extra={
                    'extra_fields': {
                        'alert_type': 'exception',
                        'exception_type': exception.__class__.__name__,
                        'context': context or {}
                    }
                }
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False


# Global alerting service instance
_alerting_service: Optional[AlertingService] = None


def get_alerting_service(config: Dict[str, Any] = None) -> AlertingService:
    """Get or create alerting service instance."""
    global _alerting_service
    if _alerting_service is None:
        _alerting_service = AlertingService(config or {'enabled': True})
    return _alerting_service


def send_exception_alert(exception: Exception, context: Dict[str, Any] = None) -> bool:
    """Convenience function to send exception alert."""
    alerting_service = get_alerting_service()
    return alerting_service.send_alert(exception, context)