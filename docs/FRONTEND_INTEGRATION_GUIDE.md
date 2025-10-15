# Frontend Integration Guide

## Overview

This guide helps frontend developers integrate with the Terra Pulse-Dify Integration API. The backend provides AI-enhanced soil degradation predictions with a clean, RESTful API.

## Quick Start for Frontend Developers

### 1. API Base URL

```javascript
// Development
const API_BASE_URL = "http://localhost:5000";

// Production (replace with your actual domain)
const API_BASE_URL = "https://your-api-domain.com";
```

### 2. Authentication

All prediction endpoints require an API key in the header:

```javascript
const headers = {
  "Content-Type": "application/json",
  "X-API-Key": "your-api-key-here",
};
```

### 3. Basic Integration Example

```javascript
// Basic prediction request
async function getPrediction(ndviData) {
  try {
    const response = await fetch(`${API_BASE_URL}/predict`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": "your-api-key",
      },
      body: JSON.stringify({
        NDVI_mean_early: ndviData.meanEarly,
        NDVI_median_early: ndviData.medianEarly,
        NDVI_std_early: ndviData.stdEarly,
        NDVI_mean_late: ndviData.meanLate,
        NDVI_median_late: ndviData.medianLate,
        NDVI_std_late: ndviData.stdLate,
        NDVI_delta_mean: ndviData.deltaMean,
        location: ndviData.location,
        user_context: ndviData.context,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    return result;
  } catch (error) {
    console.error("Prediction failed:", error);
    throw error;
  }
}
```

## API Endpoints

### 1. Basic Prediction

**Endpoint:** `POST /predict`

**Purpose:** Get basic soil degradation prediction from Terra Pulse ML model

**Request:**

```javascript
{
  "NDVI_mean_early": 0.65,
  "NDVI_median_early": 0.67,
  "NDVI_std_early": 0.12,
  "NDVI_mean_late": 0.45,
  "NDVI_median_late": 0.47,
  "NDVI_std_late": 0.15,
  "NDVI_delta_mean": -0.20,
  "location": "Farm Field A",
  "user_context": "Spring assessment"
}
```

**Response:**

```javascript
{
  "ml_output": {
    "location": "Farm Field A",
    "degradation_risk": 75,
    "risk_factors": ["bare_soil_increase", "low_ndvi"],
    "recommended_action_key": "mulch_crop_residue",
    "confidence": 0.85,
    "user_context": "Spring assessment"
  }
}
```

### 2. Enhanced Prediction (Recommended)

**Endpoint:** `POST /enhanced-predict`

**Purpose:** Get AI-enhanced prediction with Dify insights and user-specific formatting

**Request:**

```javascript
{
  "ndvi_mean_early": 0.65,
  "ndvi_median_early": 0.67,
  "ndvi_std_early": 0.12,
  "ndvi_mean_late": 0.45,
  "ndvi_median_late": 0.47,
  "ndvi_std_late": 0.15,
  "ndvi_delta_mean": -0.20,
  "location": "Farm Field A",
  "user_context": "Spring assessment",
  "user_type": "farmer"  // "farmer", "researcher", "consultant"
}
```

**Response:**

```javascript
{
  "terra_pulse_prediction": {
    "degradation_risk": 75,
    "confidence": 0.85,
    "risk_factors": ["bare_soil_increase", "low_ndvi"]
  },
  "ai_insights": {
    "risk_assessment": "High degradation risk detected...",
    "recommendations": [
      {
        "action": "Apply organic mulch",
        "priority": "high",
        "timeline": "within 2 weeks",
        "cost_estimate": "$50-100 per acre"
      }
    ],
    "success_probability": 0.78
  },
  "user_formatted_response": {
    "summary": "Your field shows signs of soil degradation...",
    "action_plan": "Immediate steps to take...",
    "timeline": "2-week action plan"
  },
  "metadata": {
    "processing_time_ms": 1250,
    "dify_success": true,
    "api_version": "1.0"
  }
}
```

### 3. Health Checks

**System Health:** `GET /health/system`

```javascript
async function checkSystemHealth() {
  const response = await fetch(`${API_BASE_URL}/health/system`);
  return await response.json();
}
```

**Individual Services:**

- `GET /health/terra-pulse` - ML model health
- `GET /health/dify` - AI service health

### 4. API Documentation

**Endpoint:** `GET /`

Returns comprehensive API documentation and available endpoints.

## Frontend Implementation Examples

### React Hook Example

```javascript
import { useState, useCallback } from "react";

export const useTerraAPI = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const predict = useCallback(async (data, enhanced = true) => {
    setLoading(true);
    setError(null);

    try {
      const endpoint = enhanced ? "/enhanced-predict" : "/predict";
      const response = await fetch(
        `${process.env.REACT_APP_API_URL}${endpoint}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-API-Key": process.env.REACT_APP_API_KEY,
          },
          body: JSON.stringify(data),
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || "Prediction failed");
      }

      return await response.json();
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const checkHealth = useCallback(async () => {
    try {
      const response = await fetch(
        `${process.env.REACT_APP_API_URL}/health/system`
      );
      return await response.json();
    } catch (err) {
      console.error("Health check failed:", err);
      return { status: "unhealthy" };
    }
  }, []);

  return { predict, checkHealth, loading, error };
};
```

### Vue.js Composable Example

```javascript
import { ref, computed } from "vue";

export function useTerraAPI() {
  const loading = ref(false);
  const error = ref(null);
  const data = ref(null);

  const predict = async (inputData, enhanced = true) => {
    loading.value = true;
    error.value = null;

    try {
      const endpoint = enhanced ? "/enhanced-predict" : "/predict";
      const response = await fetch(
        `${import.meta.env.VITE_API_URL}${endpoint}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-API-Key": import.meta.env.VITE_API_KEY,
          },
          body: JSON.stringify(inputData),
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || "Prediction failed");
      }

      data.value = await response.json();
      return data.value;
    } catch (err) {
      error.value = err.message;
      throw err;
    } finally {
      loading.value = false;
    }
  };

  return {
    predict,
    loading: computed(() => loading.value),
    error: computed(() => error.value),
    data: computed(() => data.value),
  };
}
```

### Vanilla JavaScript Class

```javascript
class TerraAPI {
  constructor(baseUrl, apiKey) {
    this.baseUrl = baseUrl;
    this.apiKey = apiKey;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const config = {
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": this.apiKey,
        ...options.headers,
      },
      ...options,
    };

    const response = await fetch(url, config);

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message || `HTTP ${response.status}`);
    }

    return await response.json();
  }

  async predict(data) {
    return this.request("/predict", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async enhancedPredict(data) {
    return this.request("/enhanced-predict", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async getHealth() {
    return this.request("/health/system");
  }
}

// Usage
const api = new TerraAPI("https://your-api.com", "your-api-key");
```

## Error Handling

### Common Error Responses

```javascript
// Validation Error (400)
{
  "error": "VALIDATION_ERROR",
  "message": "Invalid input data",
  "details": {
    "missing_fields": ["NDVI_mean_early"],
    "invalid_fields": ["NDVI_std_early"]
  }
}

// Authentication Error (401)
{
  "error": "INVALID_API_KEY",
  "message": "Invalid or missing API key"
}

// Rate Limit Error (429)
{
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "Rate limit exceeded",
  "retry_after": 60
}

// Server Error (500)
{
  "error": "INTERNAL_ERROR",
  "message": "An unexpected error occurred",
  "details": {
    "error_type": "ModelPredictionException"
  }
}
```

### Error Handling Best Practices

```javascript
async function handleAPICall(apiFunction) {
  try {
    return await apiFunction();
  } catch (error) {
    // Parse error response
    if (error.message.includes("401")) {
      // Handle authentication error
      console.error("Authentication failed - check API key");
      // Redirect to login or show auth error
    } else if (error.message.includes("429")) {
      // Handle rate limiting
      console.error("Rate limit exceeded - please wait");
      // Show rate limit message to user
    } else if (error.message.includes("400")) {
      // Handle validation errors
      console.error("Invalid input data");
      // Show validation errors to user
    } else {
      // Handle other errors
      console.error("API call failed:", error.message);
      // Show generic error message
    }
    throw error;
  }
}
```

## Environment Configuration

### Development Setup

```bash
# .env.development
REACT_APP_API_URL=http://localhost:5000
REACT_APP_API_KEY=dev-api-key-123
```

### Production Setup

```bash
# .env.production
REACT_APP_API_URL=https://api.yourcompany.com
REACT_APP_API_KEY=prod-api-key-xyz
```

## Testing the Integration

### 1. Health Check First

```javascript
// Always check if the API is healthy before making requests
const health = await fetch("http://localhost:5000/health/system");
const healthData = await health.json();
console.log("API Health:", healthData.overall_status);
```

### 2. Test Data

```javascript
const testData = {
  ndvi_mean_early: 0.65,
  ndvi_median_early: 0.67,
  ndvi_std_early: 0.12,
  ndvi_mean_late: 0.45,
  ndvi_median_late: 0.47,
  ndvi_std_late: 0.15,
  ndvi_delta_mean: -0.2,
  location: "Test Field",
  user_context: "Testing",
  user_type: "farmer",
};
```

### 3. Integration Test

```javascript
async function testIntegration() {
  try {
    // Test health
    const health = await checkHealth();
    console.log("Health:", health);

    // Test basic prediction
    const basicResult = await predict(testData, false);
    console.log("Basic prediction:", basicResult);

    // Test enhanced prediction
    const enhancedResult = await predict(testData, true);
    console.log("Enhanced prediction:", enhancedResult);

    console.log("✅ All tests passed!");
  } catch (error) {
    console.error("❌ Test failed:", error);
  }
}
```

## Performance Considerations

### 1. Caching

```javascript
// Cache predictions for identical inputs
const predictionCache = new Map();

async function cachedPredict(data) {
  const key = JSON.stringify(data);

  if (predictionCache.has(key)) {
    return predictionCache.get(key);
  }

  const result = await predict(data);
  predictionCache.set(key, result);

  return result;
}
```

### 2. Request Debouncing

```javascript
// Debounce rapid requests
import { debounce } from "lodash";

const debouncedPredict = debounce(async (data) => {
  return await predict(data);
}, 500);
```

### 3. Loading States

```javascript
function PredictionComponent() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const handlePredict = async (data) => {
    setLoading(true);
    try {
      const prediction = await predict(data);
      setResult(prediction);
    } catch (error) {
      // Handle error
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      {loading && <div>Analyzing soil data...</div>}
      {result && <PredictionResults data={result} />}
    </div>
  );
}
```

## Security Best Practices

### 1. API Key Management

```javascript
// ❌ Never expose API keys in client-side code
const API_KEY = "your-secret-key"; // DON'T DO THIS

// ✅ Use environment variables
const API_KEY = process.env.REACT_APP_API_KEY;

// ✅ Or proxy through your backend
async function proxyPredict(data) {
  return fetch("/api/terra-predict", {
    method: "POST",
    body: JSON.stringify(data),
  });
}
```

### 2. Input Validation

```javascript
function validateNDVIData(data) {
  const required = [
    "ndvi_mean_early",
    "ndvi_median_early",
    "ndvi_std_early",
    "ndvi_mean_late",
    "ndvi_median_late",
    "ndvi_std_late",
    "ndvi_delta_mean",
  ];

  for (const field of required) {
    if (typeof data[field] !== "number") {
      throw new Error(`${field} must be a number`);
    }

    if (field.includes("ndvi_") && !field.includes("delta")) {
      if (data[field] < -1 || data[field] > 1) {
        throw new Error(`${field} must be between -1 and 1`);
      }
    }
  }
}
```

## Deployment Checklist

### Frontend Developer Checklist

- [ ] API base URL configured for environment
- [ ] API key properly secured (not in client code)
- [ ] Error handling implemented for all API calls
- [ ] Loading states implemented
- [ ] Input validation added
- [ ] Health checks integrated
- [ ] Rate limiting handled gracefully
- [ ] CORS configured if needed
- [ ] SSL/HTTPS enforced in production
- [ ] API integration tested end-to-end

### Backend Deployment (Your Responsibility)

- [ ] Deploy backend using `./deploy.sh docker`
- [ ] Configure environment variables
- [ ] Set up SSL certificate
- [ ] Configure CORS for frontend domain
- [ ] Set up monitoring and alerting
- [ ] Provide API key to frontend team
- [ ] Share API documentation

## Support and Troubleshooting

### Common Issues

1. **CORS Errors**: Configure CORS in backend for frontend domain
2. **401 Errors**: Check API key configuration
3. **429 Errors**: Implement rate limiting handling
4. **Slow Responses**: Use loading states and consider caching

### Getting Help

1. Check API health endpoints first
2. Review error response details
3. Test with provided examples
4. Check network connectivity
5. Verify API key validity

### Contact Information

- **API Documentation**: Available at `GET /` endpoint
- **Health Status**: Check `GET /health/system`
- **Error Codes**: See `docs/ERROR_CODES.md`
- **Examples**: See `docs/API_EXAMPLES.md`
