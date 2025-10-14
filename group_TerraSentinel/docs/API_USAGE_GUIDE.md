# Terra Pulse Enhanced API - Usage Guide

## Overview

The Terra Pulse Enhanced API provides AI-powered soil degradation predictions by combining machine learning models with intelligent workflow processing. This guide covers authentication, endpoints, request/response formats, and integration examples.

## Base URL

- **Production**: `https://terra-pulse-api.onrender.com`
- **Local Development**: `http://localhost:5000`

## Authentication

All prediction endpoints require API key authentication via the `X-API-Key` header.

```bash
curl -H "X-API-Key: your-api-key-here" \
     -H "Content-Type: application/json" \
     https://terra-pulse-api.onrender.com/predict
```

### Getting an API Key

For testing purposes, any non-empty string can be used as an API key. In production, contact your system administrator for a valid API key.

## Rate Limiting

- **Default Limit**: 60 requests per minute per API key
- **Rate Limit Headers**: Check `X-RateLimit-*` headers in responses
- **429 Response**: When rate limit is exceeded, wait for the time specified in `Retry-After` header

## Endpoints

### 1. Basic Prediction (`/predict`)

Performs soil degradation risk assessment using the Terra Pulse ONNX model.

#### Request

```http
POST /predict
Content-Type: application/json
X-API-Key: your-api-key

{
  "NDVI_mean_early": 0.45,
  "NDVI_median_early": 0.43,
  "NDVI_std_early": 0.12,
  "NDVI_mean_late": 0.38,
  "NDVI_median_late": 0.36,
  "NDVI_std_late": 0.15,
  "NDVI_delta_mean": -0.07,
  "location": "Baringo County, Kenya",
  "user_context": "smallholder_farmer"
}
```

#### Response

```json
{
  "ml_output": {
    "location": "Baringo County, Kenya",
    "degradation_risk": 75,
    "risk_factors": ["bare_soil_increase", "low_ndvi"],
    "recommended_action_key": "mulch_crop_residue",
    "confidence": 0.85,
    "user_context": "smallholder_farmer"
  }
}
```

### 2. Enhanced Prediction (`/enhanced-predict`)

Provides AI-enhanced predictions with user-specific formatting and comprehensive recommendations.

#### Request

```http
POST /enhanced-predict
Content-Type: application/json
X-API-Key: your-api-key

{
  "NDVI_mean_early": 0.45,
  "NDVI_median_early": 0.43,
  "NDVI_std_early": 0.12,
  "NDVI_mean_late": 0.38,
  "NDVI_median_late": 0.36,
  "NDVI_std_late": 0.15,
  "NDVI_delta_mean": -0.07,
  "location": "Baringo County, Kenya",
  "user_context": "smallholder_farmer",
  "user_type": "farmer"
}
```

#### Response

```json
{
  "terra_pulse_prediction": {
    "location": "Baringo County, Kenya",
    "degradation_risk": 75,
    "risk_factors": ["bare_soil_increase", "low_ndvi"],
    "recommended_action_key": "mulch_crop_residue",
    "confidence": 0.85,
    "user_context": "smallholder_farmer"
  },
  "ai_insights": {
    "enhanced_recommendations": [
      "Apply crop residue mulch within 2 weeks",
      "Consider drought-resistant maize varieties",
      "Implement contour farming on slopes"
    ],
    "risk_assessment": "High degradation risk due to recent drought conditions",
    "timeline": "Immediate action required within 14 days",
    "cost_estimate": "Low cost - use existing crop residue",
    "success_probability": 0.78
  },
  "formatted_response": {
    "farmer_message": "Your field shows high erosion risk. Apply crop residue mulch this week to protect soil.",
    "technical_details": "NDVI decline of 15% indicates significant vegetation stress requiring immediate intervention."
  },
  "metadata": {
    "processing_time_ms": 1200,
    "dify_workflow_id": "workflow_123",
    "cache_hit": false,
    "timestamp": "2024-10-13T10:30:00Z",
    "dify_success": true,
    "total_processing_time_ms": 1500
  }
}
```

### 3. Health Endpoints

#### System Health (`/health/system`)

```http
GET /health/system
```

Returns overall system health including all services.

#### Service-Specific Health

```http
GET /health/terra-pulse    # Terra Pulse model health
GET /health/dify          # Dify AI service health
```

### 4. Metrics (`/metrics`)

```http
GET /metrics
```

Returns Prometheus-compatible metrics for monitoring.

## Request Parameters

### NDVI Parameters

All NDVI values should be between -1.0 and 1.0 (except delta values):

- `NDVI_mean_early`: Mean NDVI for early season
- `NDVI_median_early`: Median NDVI for early season  
- `NDVI_std_early`: Standard deviation for early season
- `NDVI_mean_late`: Mean NDVI for late season
- `NDVI_median_late`: Median NDVI for late season
- `NDVI_std_late`: Standard deviation for late season
- `NDVI_delta_mean`: Change in mean NDVI between seasons

### User Parameters

- `location`: Geographic location (string)
- `user_context`: Context about the user (string)
- `user_type`: "farmer" or "official" (enhanced endpoint only)

## User Types and Response Formatting

### Farmer Responses
- Simple, actionable language
- Focus on practical recommendations
- Cost-effective solutions
- Timeline for immediate action

### Official Responses  
- Technical details and analysis
- Policy recommendations
- Statistical confidence measures
- Broader regional context

## Error Handling

### Error Response Format

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": {
    "additional": "error details"
  },
  "timestamp": "2024-10-13T10:30:00Z"
}
```

### Common Error Codes

| Code | Status | Description |
|------|--------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid request data |
| `MISSING_REQUIRED_FIELD` | 400 | Required field missing |
| `INVALID_NDVI_DATA` | 400 | NDVI values out of range |
| `INVALID_API_KEY` | 401 | Missing or invalid API key |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `TERRA_PULSE_SERVICE_ERROR` | 502 | Terra Pulse model error |
| `DIFY_SERVICE_ERROR` | 502 | Dify AI service error |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

## Integration Examples

### Python

```python
import requests
import json

# Configuration
API_BASE_URL = "https://terra-pulse-api.onrender.com"
API_KEY = "your-api-key-here"

def predict_enhanced(ndvi_data, location, user_type="farmer"):
    """Make enhanced prediction request."""
    
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY
    }
    
    payload = {
        **ndvi_data,
        "location": location,
        "user_context": "api_client",
        "user_type": user_type
    }
    
    response = requests.post(
        f"{API_BASE_URL}/enhanced-predict",
        headers=headers,
        json=payload,
        timeout=30
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error {response.status_code}: {response.text}")
        return None

# Example usage
ndvi_data = {
    "NDVI_mean_early": 0.45,
    "NDVI_median_early": 0.43,
    "NDVI_std_early": 0.12,
    "NDVI_mean_late": 0.38,
    "NDVI_median_late": 0.36,
    "NDVI_std_late": 0.15,
    "NDVI_delta_mean": -0.07
}

result = predict_enhanced(ndvi_data, "Baringo County, Kenya", "farmer")
if result:
    print(f"Risk: {result['terra_pulse_prediction']['degradation_risk']}%")
    print(f"Message: {result['formatted_response']['farmer_message']}")
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

const API_BASE_URL = 'https://terra-pulse-api.onrender.com';
const API_KEY = 'your-api-key-here';

async function predictEnhanced(ndviData, location, userType = 'farmer') {
    try {
        const response = await axios.post(
            `${API_BASE_URL}/enhanced-predict`,
            {
                ...ndviData,
                location: location,
                user_context: 'api_client',
                user_type: userType
            },
            {
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': API_KEY
                },
                timeout: 30000
            }
        );
        
        return response.data;
    } catch (error) {
        if (error.response) {
            console.error(`Error ${error.response.status}:`, error.response.data);
        } else {
            console.error('Request failed:', error.message);
        }
        return null;
    }
}

// Example usage
const ndviData = {
    NDVI_mean_early: 0.45,
    NDVI_median_early: 0.43,
    NDVI_std_early: 0.12,
    NDVI_mean_late: 0.38,
    NDVI_median_late: 0.36,
    NDVI_std_late: 0.15,
    NDVI_delta_mean: -0.07
};

predictEnhanced(ndviData, 'Baringo County, Kenya', 'farmer')
    .then(result => {
        if (result) {
            console.log(`Risk: ${result.terra_pulse_prediction.degradation_risk}%`);
            console.log(`Message: ${result.formatted_response.farmer_message}`);
        }
    });
```

### cURL

```bash
#!/bin/bash

# Basic prediction
curl -X POST https://terra-pulse-api.onrender.com/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "NDVI_mean_early": 0.45,
    "NDVI_median_early": 0.43,
    "NDVI_std_early": 0.12,
    "NDVI_mean_late": 0.38,
    "NDVI_median_late": 0.36,
    "NDVI_std_late": 0.15,
    "NDVI_delta_mean": -0.07,
    "location": "Baringo County, Kenya",
    "user_context": "smallholder_farmer"
  }'

# Enhanced prediction
curl -X POST https://terra-pulse-api.onrender.com/enhanced-predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "NDVI_mean_early": 0.45,
    "NDVI_median_early": 0.43,
    "NDVI_std_early": 0.12,
    "NDVI_mean_late": 0.38,
    "NDVI_median_late": 0.36,
    "NDVI_std_late": 0.15,
    "NDVI_delta_mean": -0.07,
    "location": "Baringo County, Kenya",
    "user_context": "smallholder_farmer",
    "user_type": "farmer"
  }'

# Health check
curl https://terra-pulse-api.onrender.com/health/system
```

## Best Practices

### 1. Error Handling
- Always check response status codes
- Implement retry logic for 5xx errors
- Handle rate limiting with exponential backoff
- Log errors for debugging

### 2. Performance
- Cache results when appropriate
- Use connection pooling for multiple requests
- Set reasonable timeouts (30-60 seconds)
- Monitor response times

### 3. Security
- Keep API keys secure and rotate regularly
- Use HTTPS in production
- Validate and sanitize input data
- Implement request logging for audit trails

### 4. Monitoring
- Monitor API health endpoints
- Track response times and error rates
- Set up alerts for service degradation
- Use metrics endpoint for monitoring integration

## Troubleshooting

### Common Issues

1. **401 Unauthorized**
   - Check API key is included in `X-API-Key` header
   - Verify API key is not empty

2. **400 Validation Error**
   - Ensure all required NDVI fields are present
   - Check NDVI values are in valid range (-1.0 to 1.0)
   - Verify JSON format is correct

3. **429 Rate Limited**
   - Implement exponential backoff
   - Check `Retry-After` header for wait time
   - Consider requesting higher rate limits

4. **502/503 Service Errors**
   - Check service health endpoints
   - Retry with exponential backoff
   - Fall back to basic prediction if enhanced fails

### Getting Help

- Check API health: `GET /health/system`
- Review error response details
- Monitor service metrics: `GET /metrics`
- Contact system administrator for persistent issues

## Changelog

### Version 2.0.0
- Added enhanced prediction endpoint with AI insights
- Implemented user-specific response formatting
- Added comprehensive health monitoring
- Enhanced error handling and validation
- Added rate limiting and caching

### Version 1.0.0
- Initial Terra Pulse prediction API
- Basic ONNX model integration
- Simple health checks