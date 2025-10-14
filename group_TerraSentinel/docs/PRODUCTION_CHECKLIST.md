# ✅ Production Deployment Checklist

## Pre-Deployment Requirements

### 🔧 Environment Configuration
- [ ] `.env` file created with production values
- [ ] `DIFY_API_KEY=app-LpBDV8ynBr5J5YgnkfBoR6pg` set
- [ ] `DIFY_WORKFLOW_ID=YLObOSRKAB5YFRI6` set
- [ ] `DIFY_API_ENDPOINT=https://api.dify.ai/v1` set
- [ ] Redis URL configured (or disabled for initial deployment)

### 📁 Required Files
- [ ] `app.py` - Enhanced Flask application
- [ ] `Procfile` - Gunicorn configuration
- [ ] `requirements.txt` - Python dependencies
- [ ] `runtime.txt` - Python version specification
- [ ] `terra_pulse_model.onnx` - Your trained model file
- [ ] All `services/` directory files
- [ ] All `config/` directory files

### 🧪 Pre-Deployment Testing
- [ ] Run `python test_production_config.py` locally
- [ ] Verify Dify connection works
- [ ] Verify Terra Pulse model loads
- [ ] Test basic prediction functionality

## Deployment Steps

### 1. Render Dashboard Setup
- [ ] Go to your Render dashboard
- [ ] Select existing `terra-pulse-api` service
- [ ] Update repository connection to this enhanced version
- [ ] Set environment variables in Render dashboard

### 2. Environment Variables in Render
```bash
DIFY_API_KEY=app-LpBDV8ynBr5J5YgnkfBoR6pg
DIFY_API_ENDPOINT=https://api.dify.ai/v1
DIFY_WORKFLOW_ID=YLObOSRKAB5YFRI6
API_KEY_HEADER=X-API-Key
RATE_LIMIT_PER_MINUTE=60
LOG_LEVEL=INFO
CACHE_TTL=3600
MAX_RETRIES=3
TIMEOUT_SECONDS=30
```

### 3. Optional: Redis Setup
- [ ] Add Redis add-on in Render (recommended)
- [ ] Or configure external Redis service
- [ ] Set `REDIS_URL` environment variable
- [ ] Note: System works without Redis (rate limiting disabled)

### 4. Deploy
- [ ] Push code to connected repository
- [ ] Monitor deployment logs in Render dashboard
- [ ] Wait for successful deployment

## Post-Deployment Verification

### 🏥 Health Checks
Test these endpoints after deployment:

```bash
# System health
curl https://terra-pulse-api.onrender.com/health/system

# Individual services
curl https://terra-pulse-api.onrender.com/health/terra-pulse
curl https://terra-pulse-api.onrender.com/health/dify

# API documentation
curl https://terra-pulse-api.onrender.com/
```

Expected responses:
- [ ] System health shows "healthy" or "degraded" (not "unhealthy")
- [ ] Terra Pulse service shows "healthy"
- [ ] Dify service shows "healthy"
- [ ] Root endpoint returns API documentation

### 🔮 Prediction Testing
Test both prediction endpoints:

```bash
# Basic prediction (backward compatibility)
curl -X POST https://terra-pulse-api.onrender.com/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-key-12345" \
  -d '{
    "NDVI_mean_early": 0.45,
    "NDVI_median_early": 0.43,
    "NDVI_std_early": 0.12,
    "NDVI_mean_late": 0.38,
    "NDVI_median_late": 0.36,
    "NDVI_std_late": 0.15,
    "NDVI_delta_mean": -0.07,
    "location": "Test Location",
    "user_context": "test"
  }'

# Enhanced prediction (new feature)
curl -X POST https://terra-pulse-api.onrender.com/enhanced-predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-key-12345" \
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

Expected results:
- [ ] Basic prediction returns `ml_output` with degradation risk
- [ ] Enhanced prediction returns full response with AI insights
- [ ] Both endpoints require API key (401 without key)
- [ ] Response times under 2 seconds

### 🔐 Security Testing
- [ ] Requests without API key return 401
- [ ] Invalid API keys return 401
- [ ] Rate limiting works (if Redis configured)
- [ ] Health endpoints accessible without auth

### 📊 Monitoring Setup
- [ ] Metrics endpoint accessible: `/metrics`
- [ ] Consider setting up monitoring dashboard
- [ ] Set up alerts for service health
- [ ] Monitor response times and error rates

## Success Criteria

Your deployment is successful when:

### ✅ Backward Compatibility
- [ ] Existing `/predict` endpoint works with API key
- [ ] Same response format as before
- [ ] No breaking changes for existing clients

### ✅ Enhanced Features
- [ ] `/enhanced-predict` endpoint provides AI insights
- [ ] User-specific formatting (farmer vs official)
- [ ] Fallback behavior when Dify unavailable

### ✅ Production Readiness
- [ ] Authentication and rate limiting active
- [ ] Health monitoring functional
- [ ] Error handling graceful
- [ ] Logging and metrics available

### ✅ Performance
- [ ] Basic predictions: < 500ms
- [ ] Enhanced predictions: < 2000ms
- [ ] Health checks: < 200ms
- [ ] System handles expected load

## Rollback Plan

If issues occur:

### Quick Rollback
1. In Render dashboard, revert to previous deployment
2. Or temporarily disable enhanced features by setting:
   ```bash
   DIFY_API_KEY=""  # Disables Dify integration
   ```

### Gradual Migration
1. Keep both old and new APIs running
2. Gradually migrate clients to new endpoints
3. Monitor performance and fix issues

## Client Migration

### Phase 1: Immediate (Backward Compatible)
- Existing clients continue using `/predict`
- Add API key requirement
- No other changes needed

### Phase 2: Enhanced Features
- Update clients to use `/enhanced-predict`
- Provide API keys to clients
- Train users on new response format

### Phase 3: Optimization
- Monitor usage patterns
- Optimize performance
- Add advanced features

## Support and Monitoring

### Key Metrics to Monitor
- Response times for each endpoint
- Error rates and types
- API key usage patterns
- Dify service availability
- Cache hit ratios (if Redis enabled)

### Common Issues and Solutions
1. **Dify Connection Failed**: Check API key and workflow ID
2. **High Response Times**: Monitor Dify service performance
3. **Rate Limiting Issues**: Adjust limits or check Redis
4. **Model Loading Failed**: Verify ONNX file in deployment

## 🎉 Deployment Complete!

Once all checklist items are complete, your enhanced Terra Pulse API is production-ready with:

- ✅ AI-enhanced predictions via Dify integration
- ✅ Backward compatibility maintained
- ✅ Production-grade security and monitoring
- ✅ User-specific response formatting
- ✅ Comprehensive health checks and metrics

Your API is now serving at: `https://terra-pulse-api.onrender.com` 🚀