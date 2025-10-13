# Frontend Developer Handoff

## 🚀 Terra Pulse API - Ready for Integration

Your backend API is deployed and ready for frontend integration! Here's everything you need to get started.

## Quick Start

### API Endpoint
```
Production: https://your-domain.com
Development: http://localhost:5000
```

### Authentication
```javascript
headers: {
  'Content-Type': 'application/json',
  'X-API-Key': 'your-api-key-here'
}
```

### Basic Usage Example
```javascript
// Enhanced prediction (recommended)
const response = await fetch('https://your-domain.com/enhanced-predict', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'your-api-key'
  },
  body: JSON.stringify({
    ndvi_mean_early: 0.65,
    ndvi_median_early: 0.67,
    ndvi_std_early: 0.12,
    ndvi_mean_late: 0.45,
    ndvi_median_late: 0.47,
    ndvi_std_late: 0.15,
    ndvi_delta_mean: -0.20,
    location: "Farm Field A",
    user_context: "Spring assessment",
    user_type: "farmer"  // "farmer", "researcher", "consultant"
  })
});

const result = await response.json();
console.log(result);
```

## Available Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/enhanced-predict` | POST | AI-enhanced prediction (recommended) |
| `/predict` | POST | Basic prediction |
| `/health/system` | GET | Check API health |
| `/` | GET | API documentation |

## Response Format

```javascript
{
  "terra_pulse_prediction": {
    "degradation_risk": 75,        // 0-100 risk score
    "confidence": 0.85,            // 0-1 confidence
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
  }
}
```

## Error Handling

```javascript
try {
  const response = await fetch(apiUrl, options);
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message);
  }
  
  return await response.json();
} catch (error) {
  console.error('API Error:', error.message);
  // Handle different error types:
  // 401: Invalid API key
  // 429: Rate limit exceeded
  // 400: Invalid input data
  // 500: Server error
}
```

## Documentation

📚 **Complete Integration Guide**: `docs/FRONTEND_INTEGRATION_GUIDE.md`

This includes:
- Detailed API documentation
- React/Vue/Vanilla JS examples
- Error handling best practices
- Performance optimization tips
- Security guidelines

## Health Check

Always verify the API is healthy before making requests:

```javascript
const health = await fetch('https://your-domain.com/health/system');
const status = await health.json();
console.log('API Status:', status.overall_status); // "healthy", "degraded", "unhealthy"
```

## Rate Limits

- **Limit**: 100 requests per minute per API key
- **Headers**: Check `X-RateLimit-Remaining` in response
- **429 Error**: Wait and retry when rate limited

## CORS

The API is configured to accept requests from your frontend domain. If you encounter CORS issues, let me know your domain.

## Support

- **API Documentation**: Visit the root endpoint `/` for full docs
- **Health Status**: Check `/health/system` for real-time status
- **Issues**: Contact backend team for API-related problems

## Next Steps

1. ✅ Review the complete integration guide
2. ✅ Test the health endpoint
3. ✅ Try the example prediction request
4. ✅ Implement error handling
5. ✅ Add loading states for better UX
6. ✅ Test with your actual frontend application

## API Key

**Development**: `dev-key-123` (for localhost testing)
**Production**: `[PROVIDED_SEPARATELY]` (secure delivery)

---

**Backend Developer**: [Your Name]  
**API Version**: 1.0  
**Last Updated**: [Current Date]  

Happy coding! 🎉