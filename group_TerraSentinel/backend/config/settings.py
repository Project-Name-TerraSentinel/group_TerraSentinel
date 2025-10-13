"""
Configuration management for Terra Pulse-Dify integration.
Handles environment variables with validation and provides configuration defaults.
"""

import os
import sys
from typing import Optional
from pydantic import BaseModel, validator, Field
from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    """Application configuration with environment variable validation."""
    
    # Terra Pulse Configuration
    terra_pulse_model_path: str = Field(
        default="terra_pulse_model.onnx",
        description="Path to the Terra Pulse ONNX model file"
    )
    
    # Dify API Configuration
    dify_api_key: str = Field(
        ...,
        description="API key for Dify service authentication"
    )
    dify_api_endpoint: str = Field(
        default="https://api.dify.ai/v1",
        description="Base URL for Dify API endpoints"
    )
    dify_workflow_id: str = Field(
        ...,
        description="Dify workflow ID for processing Terra Pulse predictions"
    )
    
    # Redis Configuration
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for caching"
    )
    cache_ttl: int = Field(
        default=3600,
        description="Cache TTL in seconds (default: 1 hour)"
    )
    
    # API Configuration
    max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for external API calls"
    )
    timeout_seconds: int = Field(
        default=30,
        description="Timeout for external API calls in seconds"
    )
    
    # Security Configuration
    api_key_header: str = Field(
        default="X-API-Key",
        description="Header name for API key authentication"
    )
    rate_limit_per_minute: int = Field(
        default=60,
        description="Rate limit per minute per API key"
    )
    cors_allowed_origins: str = Field(
        default="http://localhost:3000,http://localhost:8080",
        description="Comma-separated list of allowed CORS origins"
    )
    enforce_https: bool = Field(
        default=False,
        description="Whether to enforce HTTPS for all requests"
    )
    
    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARN, ERROR, CRITICAL)"
    )
    log_format: str = Field(
        default="json",
        description="Log format (json or text)"
    )
    log_request_details: bool = Field(
        default=True,
        description="Whether to log detailed request information"
    )
    
    # Alerting Configuration
    alerting_enabled: bool = Field(
        default=True,
        description="Whether alerting is enabled"
    )
    alert_email_enabled: bool = Field(
        default=False,
        description="Whether email alerting is enabled"
    )
    alert_webhook_enabled: bool = Field(
        default=False,
        description="Whether webhook alerting is enabled"
    )
    alert_smtp_host: str = Field(
        default="",
        description="SMTP host for email alerts"
    )
    alert_smtp_port: int = Field(
        default=587,
        description="SMTP port for email alerts"
    )
    alert_email_username: str = Field(
        default="",
        description="Email username for alerts"
    )
    alert_email_password: str = Field(
        default="",
        description="Email password for alerts"
    )
    alert_from_email: str = Field(
        default="",
        description="From email address for alerts"
    )
    alert_to_emails: str = Field(
        default="",
        description="Comma-separated list of email addresses for alerts"
    )
    alert_webhook_url: str = Field(
        default="",
        description="Webhook URL for alerts"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
    @validator("terra_pulse_model_path")
    def validate_model_path(cls, v):
        """Validate that the Terra Pulse model file exists."""
        if not os.path.exists(v):
            raise ValueError(f"Terra Pulse model file not found at: {v}")
        return v
    
    @validator("dify_api_key")
    def validate_dify_api_key(cls, v):
        """Validate that Dify API key is provided."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Dify API key is required")
        return v.strip()
    
    @validator("dify_workflow_id")
    def validate_dify_workflow_id(cls, v):
        """Validate that Dify workflow ID is provided."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Dify workflow ID is required")
        return v.strip()
    
    @validator("cache_ttl")
    def validate_cache_ttl(cls, v):
        """Validate cache TTL is positive."""
        if v <= 0:
            raise ValueError("Cache TTL must be positive")
        return v
    
    @validator("max_retries")
    def validate_max_retries(cls, v):
        """Validate max retries is non-negative."""
        if v < 0:
            raise ValueError("Max retries must be non-negative")
        return v
    
    @validator("timeout_seconds")
    def validate_timeout(cls, v):
        """Validate timeout is positive."""
        if v <= 0:
            raise ValueError("Timeout must be positive")
        return v
    
    @validator("rate_limit_per_minute")
    def validate_rate_limit(cls, v):
        """Validate rate limit is positive."""
        if v <= 0:
            raise ValueError("Rate limit must be positive")
        return v
    
    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level is valid."""
        valid_levels = ["DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()
    
    @validator("log_format")
    def validate_log_format(cls, v):
        """Validate log format is valid."""
        valid_formats = ["json", "text"]
        if v.lower() not in valid_formats:
            raise ValueError(f"Log format must be one of: {valid_formats}")
        return v.lower()
    
    @validator("alert_to_emails")
    def validate_alert_emails(cls, v):
        """Validate alert email addresses."""
        if v and v.strip():
            emails = [email.strip() for email in v.split(',')]
            for email in emails:
                if email and '@' not in email:
                    raise ValueError(f"Invalid email address: {email}")
        return v


def load_config() -> AppConfig:
    """
    Load and validate application configuration.
    
    Returns:
        AppConfig: Validated configuration object
        
    Raises:
        SystemExit: If configuration validation fails
    """
    try:
        config = AppConfig()
        return config
    except Exception as e:
        print(f"ERROR: Configuration validation failed: {e}", file=sys.stderr)
        sys.exit(1)


def get_config() -> AppConfig:
    """
    Get application configuration singleton.
    
    Returns:
        AppConfig: Application configuration instance
    """
    if not hasattr(get_config, "_config"):
        get_config._config = load_config()
    return get_config._config


# Global configuration instance
config = get_config()