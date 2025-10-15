# Terra Pulse Enhanced API - Error Codes Reference

## Overview

This document provides a comprehensive reference for all error codes returned by the Terra Pulse Enhanced API. Each error includes the HTTP status code, error category, description, and recommended actions.

## Error Response Format

All API errors follow a consistent JSON structure:

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": {
    "field": "additional context",
    "suggestion": "recommended action"
  },
  "timestamp": "2024-10-13T10:30:00Z",
  "error_id": "unique-error-identifier"
}
```

## Error Categories

### 1. Validation Errors (400 Bad Request)

#### VALIDATION_ERROR
- **Description**: General request validation failure
- **Common Causes**: 
  - Invalid JSON format
  - Missing required fields
  - Invalid data types
- **Example**:
  ```json
  {
    "error": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": {
      "missing_fields": ["NDVI_mean_early"],
      "invalid_fields": ["user_type"]
    }
  }
  ```
- **Resolution**: Check request format and ensure all required fields are present with correct data types

#### MISSING_REQUIRED_FIELD
- **Description**: One or more required fields are missing
- **Common Causes**: Incomplete request payload
- **Example**:
  ```json
  {
    "error": "MISSING_REQUIRED_FIELD",
    "message": "Required field 'NDVI_mean_early' is missing",
    "details": {
      "missing_fields": ["NDVI_mean_early", "NDVI_median_early"],
      "required_fields": ["NDVI_mean_early", "NDVI_median_early", "NDVI_std_early", "NDVI_mean_late", "NDVI_median_late", "NDVI_std_late", "NDVI_delta_mean"]
    }
  }
  ```
- **Resolution**: Include all required NDVI fields in your request

#### INVALID_NDVI_DATA
- **Description**: NDVI values are outside valid range or invalid format
- **Common Causes**: 
  - NDVI values not between -1.0 and 1.0
  - Non-numeric NDVI values
- **Example**:
  ```json
  {
    "error": "INVALID_NDVI_DATA",
    "message": "NDVI value 1.5 for field 'NDVI_mean_early' is outside valid range",
    "details": {
      "field": "NDVI_mean_early",
      "value": 1.5,
      "valid_range": "-1.0 to 1.0"
    }
  }
  ```
- **Resolution**: Ensure all NDVI values are between -1.0 and 1.0

#### INVALID_USER_TYPE
- **Description**: Invalid user_type specified for enhanced predictions
- **Common Causes**: user_type not "farmer" or "official"
- **Example**:
  ```json
  {
    "error": "INVALID_USER_TYPE",
    "message": "Invalid user_type 'admin'. Must be 'farmer' or 'official'",
    "details": {
      "provided_value": "admin",
      "valid_values": ["farmer", "official"]
    }
  }
  ```
- **Resolution**: Use "farmer" or "official" for user_type field

#### DATA_SANITIZATION_ERROR
- **Description**: Input data failed sanitization checks
- **Common Causes**: 
  - Potentially malicious input
  - Invalid characters in string fields
- **Example**:
  ```json
  {
    "error": "DATA_SANITIZATION_ERROR",
    "message": "Input data contains invalid characters",
    "details": {
      "field": "location",
      "issue": "contains_script_tags"
    }
  }
  ```
- **Resolution**: Remove special characters and ensure clean input data

### 2. Authentication Errors (401 Unauthorized)

#### INVALID_API_KEY
- **Description**: API key is missing, empty, or invalid
- **Common Causes**:
  - Missing X-API-Key header
  - Empty API key value
  - Invalid API key format
- **Example**:
  ```json
  {
    "error": "INVALID_API_KEY",
    "message": "Invalid or missing API key",
    "details": {
      "header_name": "X-API-Key",
      "provided_key_hint": "abc12..."
    }
  }
  ```
- **Resolution**: Include valid API key in X-API-Key header

### 3. Rate Limiting Errors (429 Too Many Requests)

#### RATE_LIMIT_EXCEEDED
- **Description**: API rate limit has been exceeded
- **Common Causes**: Too many requests in the time window
- **Headers**: `Retry-After: 60` (seconds to wait)
- **Example**:
  ```json
  {
    "error": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit of 60 requests per minute exceeded",
    "details": {
      "limit": 60,
      "window": "minute",
      "retry_after": 60,
      "current_usage": 65
    }
  }
  ```
- **Resolution**: Wait for the time specified in Retry-After header before making new requests

### 4. Service Errors (502 Bad Gateway / 503 Service Unavailable)

#### TERRA_PULSE_SERVICE_ERROR
- **Description**: Terra Pulse model service is unavailable or failed
- **Common Causes**:
  - Model loading failure
  - ONNX runtime error
  - Model file corruption
- **Example**:
  ```json
  {
    "error": "TERRA_PULSE_SERVICE_ERROR",
    "message": "Terra Pulse model prediction failed",
    "details": {
      "service": "terra_pulse",
      "error_type": "ModelLoadingException",
      "model_path": "terra_pulse_model.onnx"
    }
  }
  ```
- **Resolution**: Check service health at `/health/terra-pulse`, retry after a delay

#### DIFY_SERVICE_ERROR
- **Description**: Dify AI service is unavailable or failed
- **Common Causes**:
  - Dify API connectivity issues
  - Invalid workflow configuration
  - Dify service timeout
- **Example**:
  ```json
  {
    "error": "DIFY_SERVICE_ERROR",
    "message": "Dify workflow execution failed",
    "details": {
      "service": "dify",
      "workflow_id": "YLObOSRKAB5YFRI6",
      "error_type": "ConnectionTimeout",
      "fallback_available": true
    }
  }
  ```
- **Resolution**: Check service health at `/health/dify`, enhanced predictions will fall back to basic recommendations

#### CACHE_SERVICE_ERROR
- **Description**: Redis cache service is unavailable
- **Common Causes**:
  - Redis connection failure
  - Redis server down
- **Example**:
  ```json
  {
    "error": "CACHE_SERVICE_ERROR",
    "message": "Cache service temporarily unavailable",
    "details": {
      "service": "redis",
      "impact": "Performance may be reduced",
      "fallback": "Direct processing enabled"
    }
  }
  ```
- **Resolution**: Service continues without caching, no action required

### 5. Data Processing Errors (422 Unprocessable Entity)

#### DATA_TRANSFORMATION_ERROR
- **Description**: Error occurred during data transformation between services
- **Common Causes**:
  - Unexpected data format from Terra Pulse
  - Invalid Dify response format
- **Example**:
  ```json
  {
    "error": "DATA_TRANSFORMATION_ERROR",
    "message": "Failed to transform Terra Pulse output for Dify input",
    "details": {
      "transformation_stage": "terra_pulse_to_dify",
      "error_type": "MissingFieldException"
    }
  }
  ```
- **Resolution**: Retry request, contact support if persistent

#### RESPONSE_FORMATTING_ERROR
- **Description**: Error occurred while formatting response for user type
- **Common Causes**:
  - Invalid user type configuration
  - Missing response template
- **Example**:
  ```json
  {
    "error": "RESPONSE_FORMATTING_ERROR",
    "message": "Failed to format response for user type 'farmer'",
    "details": {
      "user_type": "farmer",
      "formatting_stage": "message_generation"
    }
  }
  ```
- **Resolution**: Retry with different user_type or contact support

### 6. Internal Server Errors (500 Internal Server Error)

#### INTERNAL_ERROR
- **Description**: Unexpected server error occurred
- **Common Causes**:
  - Unhandled exceptions
  - System resource issues
  - Configuration problems
- **Example**:
  ```json
  {
    "error": "INTERNAL_ERROR",
    "message": "An unexpected error occurred during prediction",
    "details": {
      "error_type": "UnhandledException",
      "error_id": "err_1697198400_abc123",
      "support_contact": "Contact system administrator"
    }
  }
  ```
- **Resolution**: Retry request, contact support with error_id if persistent

#### MODEL_PREDICTION_ERROR
- **Description**: ONNX model prediction failed
- **Common Causes**:
  - Model runtime error
  - Invalid input tensor shape
  - Memory issues
- **Example**:
  ```json
  {
    "error": "MODEL_PREDICTION_ERROR",
    "message": "ONNX model prediction failed",
    "details": {
      "model": "terra_pulse_model.onnx",
      "error_type": "RuntimeException",
      "input_shape": "[1, 7]"
    }
  }
  ```
- **Resolution**: Check input data format, retry request

### 7. Not Found Errors (404 Not Found)

#### ENDPOINT_NOT_FOUND
- **Description**: Requested endpoint does not exist
- **Common Causes**:
  - Incorrect URL path
  - Typo in endpoint name
- **Example**:
  ```json
  {
    "error": "ENDPOINT_NOT_FOUND",
    "message": "The requested endpoint does not exist",
    "details": {
      "path": "/predicts",
      "method": "POST",
      "available_endpoints": ["/predict", "/enhanced-predict", "/health/system"],
      "suggestion": "Check API documentation for correct endpoints"
    }
  }
  ```
- **Resolution**: Verify endpoint URL against API documentation

## Error Handling Best Practices

### 1. Retry Logic

```python
import time
import random

def make_request_with_retry(request_func, max_retries=3):
    """Make API request with exponential backoff retry logic."""
    
    for attempt in range(max_retries + 1):
        try:
            response = request_func()
            
            # Success
            if response.status_code == 200:
                return response.json()
            
            # Don't retry client errors (4xx)
            if 400 <= response.status_code < 500:
                if response.status_code == 429:  # Rate limit
                    retry_after = int(response.headers.get('Retry-After', 60))
                    time.sleep(retry_after)
                    continue
                else:
                    # Other client errors - don't retry
                    raise Exception(f"Client error: {response.status_code}")
            
            # Retry server errors (5xx)
            if response.status_code >= 500 and attempt < max_retries:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(wait_time)
                continue
            
            # Max retries exceeded
            raise Exception(f"Max retries exceeded: {response.status_code}")
            
        except Exception as e:
            if attempt == max_retries:
                raise
            
            # Exponential backoff
            wait_time = (2 ** attempt) + random.uniform(0, 1)
            time.sleep(wait_time)
```

### 2. Error Response Handling

```python
def handle_api_response(response):
    """Handle API response and extract error information."""
    
    if response.status_code == 200:
        return response.json()
    
    try:
        error_data = response.json()
        error_code = error_data.get('error', 'UNKNOWN_ERROR')
        message = error_data.get('message', 'Unknown error occurred')
        details = error_data.get('details', {})
        
        # Handle specific error types
        if error_code == 'RATE_LIMIT_EXCEEDED':
            retry_after = details.get('retry_after', 60)
            print(f"Rate limited. Retry after {retry_after} seconds.")
            return None
        
        elif error_code == 'INVALID_API_KEY':
            print("Invalid API key. Please check your credentials.")
            return None
        
        elif error_code == 'VALIDATION_ERROR':
            missing_fields = details.get('missing_fields', [])
            print(f"Validation error. Missing fields: {missing_fields}")
            return None
        
        elif error_code in ['TERRA_PULSE_SERVICE_ERROR', 'DIFY_SERVICE_ERROR']:
            print(f"Service error: {message}. Retrying may help.")
            return None
        
        else:
            print(f"API error {error_code}: {message}")
            return None
            
    except ValueError:
        # Non-JSON error response
        print(f"HTTP {response.status_code}: {response.text}")
        return None
```

### 3. Monitoring and Alerting

Set up monitoring for these error patterns:

- **High 4xx rates**: Indicates client integration issues
- **High 5xx rates**: Indicates service problems
- **Rate limit errors**: May need rate limit increases
- **Authentication errors**: Possible security issues
- **Service-specific errors**: Component health problems

### 4. Fallback Strategies

```python
def get_prediction_with_fallback(ndvi_data, location, user_type="farmer"):
    """Get prediction with fallback to basic endpoint."""
    
    try:
        # Try enhanced prediction first
        return make_enhanced_prediction(ndvi_data, location, user_type)
    
    except DifyServiceError:
        # Fall back to basic prediction
        print("Enhanced prediction unavailable, using basic prediction")
        return make_basic_prediction(ndvi_data, location)
    
    except TerraPulseServiceError:
        # No fallback available for Terra Pulse errors
        print("Terra Pulse service unavailable")
        return None
```

## Support and Troubleshooting

### When to Contact Support

- **Persistent 5xx errors**: Service may need attention
- **Unexpected error codes**: New error types not documented
- **Performance issues**: Consistently slow responses
- **Rate limit issues**: Need higher limits for legitimate use

### Information to Include

When reporting errors, include:

1. **Error ID**: From error response (if available)
2. **Timestamp**: When error occurred
3. **Request details**: Endpoint, headers, payload (sanitized)
4. **Response**: Full error response
5. **Frequency**: How often the error occurs
6. **Impact**: How it affects your application

### Health Check Endpoints

Use these endpoints to diagnose issues:

- `GET /health/system` - Overall system status
- `GET /health/terra-pulse` - Terra Pulse model status  
- `GET /health/dify` - Dify AI service status
- `GET /metrics` - Detailed service metrics