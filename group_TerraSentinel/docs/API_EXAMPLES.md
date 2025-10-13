# 🔧 Terra Pulse Enhanced API - Usage Examples

## Base URL
```
https://terra-pulse-api.onrender.com
```

## Authentication
All prediction endpoints require an API key in the header:
```bash
X-API-Key: your-api-key-here
```

## 📖 API Endpoints

### 1. Root Documentation
```bash
curl https://terra-pulse-api.onrender.com/
```

**Response:**
```json
{
  "service": "Terra Pulse Enhanced API",
  "version": "2.0.0",
  "endpoints": {
    "predictions": {
      "/predict": "Basic Terra Pulse prediction",
      "/enhanced-predict": "AI-enhanced prediction with insights"
    }
  }
}
```

### 2. Basic Prediction (Original)
```bash
curl -X POST https://terra-pulse-api.onrender.com/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
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
```

**Response:**
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

### 3. Enhanced Prediction (NEW - AI-Powered)
```bash
curl -X POST https://terra-pulse-api.onrender.com/enhanced-predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
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
```

**Response (Farmer Format):**
```json
{
  "terra_pulse_prediction": {
    "degradation_risk": 75,
    "risk_factors": ["bare_soil_increase", "low_ndvi"],
    "recommended_action_key": "mulch_crop_residue",
    "confidence": 0.85,
    "location": "Baringo County, Kenya"
  },
  "ai_insights": {
    "enhanced_recommendations": [
      "Apply crop residue mulch within 2 weeks",
      "Consider drought-resistant maize varieties",
      "Implement water harvesting techniques"
    ],
    "risk_assessment": "High degradation risk due to recent drought conditions and bare soil exposure",
    "timeline": "Immediate action required within 14 days",
    "cost_estimate": "Low cost - use existing crop residue",
    "success_probability": 0.78
  },
  "formatted_response": {
    "user_type": "farmer",
    "region": "east_africa",
    "risk_level": "high",
    "urgency": "urgent",
    "title": "⚠️ Warning: Soil degradation detected in Baringo County, Kenya",
    "summary": "Your land has 75% degradation risk. Take action soon to prevent soil loss and maintain crop yields.",
    "recommendations": [
      "Cover bare soil with crop residue or grass to prevent erosion",
      "Plant across slopes (contour farming) to slow water runoff",
      "Consider drought-resistant maize varieties"
    ],
    "farmer_message": "Your land has 75% degradation risk. Take action soon to prevent soil loss and maintain crop yields. Key action: Cover bare soil with crop residue or grass to prevent erosion"
  },
  "metadata": {
    "total_processing_time_ms": 850.5,
    "dify_success": true,
    "endpoint": "enhanced-predict",
    "api_version": "1.0"
  }
}
```

### 4. Enhanced Prediction for Officials
```bash
curl -X POST https://terra-pulse-api.onrender.com/enhanced-predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "NDVI_mean_early": 0.45,
    "NDVI_median_early": 0.43,
    "NDVI_std_early": 0.12,
    "NDVI_mean_late": 0.38,
    "NDVI_median_late": 0.36,
    "NDVI_std_late": 0.15,
    "NDVI_delta_mean": -0.07,
    "location": "Baringo County, Kenya",
    "user_context": "agricultural_extension",
    "user_type": "official"
  }'
```

**Response (Official Format):**
```json
{
  "formatted_response": {
    "user_type": "official",
    "region": "east_africa",
    "risk_level": "high",
    "urgency": "urgent",
    "title": "Land Degradation Assessment: Baringo County, Kenya - HIGH Risk (75%)",
    "summary": "Satellite-based analysis indicates 75% degradation risk in Baringo County, Kenya with 85.0% confidence. Primary risk factors: bare_soil_increase, low_ndvi. Assessment based on NDVI analysis under semi-arid conditions with irregular rainfall.",
    "technical_details": "Model confidence: 85.0% | Processing time: 850.5ms | Risk factors: 2 identified | AI enhancement: Available",
    "policy_recommendations": [
      "Implement targeted conservation programs in Baringo County, Kenya",
      "Provide technical assistance for sustainable land management",
      "Monitor degradation trends with follow-up assessments",
      "Support farmer training on agroforestry"
    ],
    "official_summary": "Risk Level: HIGH (75%) | Confidence: 85.0% | Action Required: urgent"
  }
}
```

## 🏥 Health Check Endpoints

### System Health
```bash
curl https://terra-pulse-api.onrender.com/health/system
```

**Response:**
```json
{
  "system": "terra_pulse_dify_integration",
  "overall_status": "healthy",
  "services": {
    "terra_pulse": {
      "status": "healthy",
      "message": "Model loaded and ready",
      "response_time_ms": 45.2
    },
    "dify": {
      "status": "healthy", 
      "message": "API accessible and workflow ready",
      "response_time_ms": 120.8
    },
    "cache": {
      "available": true,
      "hit_ratio": 0.85,
      "total_keys": 150
    }
  },
  "capabilities": {
    "basic_predictions": true,
    "enhanced_predictions": true,
    "caching": true
  }
}
```

### Individual Service Health
```bash
# Terra Pulse health
curl https://terra-pulse-api.onrender.com/health/terra-pulse

# Dify health  
curl https://terra-pulse-api.onrender.com/health/dify
```

## 📊 Metrics Endpoint
```bash
curl https://terra-pulse-api.onrender.com/metrics
```

**Response (Prometheus format):**
```
# HELP terra_pulse_service_health Terra Pulse service health status
# TYPE terra_pulse_service_health gauge
terra_pulse_service_health 1

# HELP dify_service_health Dify service health status
# TYPE dify_service_health gauge
dify_service_health 1

# HELP cache_hit_ratio Cache hit ratio
# TYPE cache_hit_ratio gauge
cache_hit_ratio 0.85
```

## 🚨 Error Responses

### Authentication Error
```json
{
  "error": "Authentication required",
  "message": "API key required in X-API-Key header"
}
```

### Rate Limit Exceeded
```json
{
  "error": "Rate limit exceeded",
  "message": "Maximum 60 requests per minute allowed",
  "retry_after_seconds": 45
}
```

### Validation Error
```json
{
  "error": "Validation failed",
  "details": [
    "NDVI_mean_early must be between -2.0 and 2.0"
  ]
}
```

### Service Degraded (Dify Unavailable)
```json
{
  "terra_pulse_prediction": { /* normal prediction */ },
  "ai_insights": {
    "enhanced_recommendations": [],
    "risk_assessment": "AI processing unavailable - manual assessment recommended",
    "fallback_used": true
  },
  "metadata": {
    "dify_success": false
  }
}
```

## 🔧 Integration Examples

### Python Client
```python
import requests

API_BASE = "https://terra-pulse-api.onrender.com"
API_KEY = "your-api-key"

def get_enhanced_prediction(ndvi_data, location, user_type="farmer"):
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY
    }
    
    payload = {
        **ndvi_data,
        "location": location,
        "user_type": user_type
    }
    
    response = requests.post(f"{API_BASE}/enhanced-predict", 
                           json=payload, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"API Error: {response.status_code} - {response.text}")

# Usage
ndvi_data = {
    "NDVI_mean_early": 0.45,
    "NDVI_median_early": 0.43,
    "NDVI_std_early": 0.12,
    "NDVI_mean_late": 0.38,
    "NDVI_median_late": 0.36,
    "NDVI_std_late": 0.15,
    "NDVI_delta_mean": -0.07,
    "user_context": "smallholder_farmer"
}

result = get_enhanced_prediction(ndvi_data, "Baringo County, Kenya", "farmer")
print(f"Risk Level: {result['formatted_response']['risk_level']}")
print(f"Recommendations: {result['formatted_response']['recommendations']}")
```

### JavaScript Client
```javascript
const API_BASE = "https://terra-pulse-api.onrender.com";
const API_KEY = "your-api-key";

async function getEnhancedPrediction(ndviData, location, userType = "farmer") {
    const response = await fetch(`${API_BASE}/enhanced-predict`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-API-Key': API_KEY
        },
        body: JSON.stringify({
            ...ndviData,
            location: location,
            user_type: userType
        })
    });
    
    if (!response.ok) {
        throw new Error(`API Error: ${response.status}`);
    }
    
    return await response.json();
}

// Usage
const ndviData = {
    NDVI_mean_early: 0.45,
    NDVI_median_early: 0.43,
    NDVI_std_early: 0.12,
    NDVI_mean_late: 0.38,
    NDVI_median_late: 0.36,
    NDVI_std_late: 0.15,
    NDVI_delta_mean: -0.07,
    user_context: "smallholder_farmer"
};

getEnhancedPrediction(ndviData, "Baringo County, Kenya", "farmer")
    .then(result => {
        console.log("Risk Level:", result.formatted_response.risk_level);
        console.log("Recommendations:", result.formatted_response.recommendations);
    })
    .catch(error => console.error("Error:", error));
```

## 🎯 Migration from Original API

### Before (Original API):
```bash
curl -X POST https://terra-pulse-api.onrender.com/predict \
  -H "Content-Type: application/json" \
  -d '{ /* NDVI data */ }'
```

### After (Enhanced API):
```bash
# Option 1: Keep using original endpoint (now with auth)
curl -X POST https://terra-pulse-api.onrender.com/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{ /* NDVI data */ }'

# Option 2: Upgrade to enhanced endpoint
curl -X POST https://terra-pulse-api.onrender.com/enhanced-predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{ /* NDVI data + user_type */ }'
```

The enhanced API provides backward compatibility while offering powerful new AI-driven insights! 🚀