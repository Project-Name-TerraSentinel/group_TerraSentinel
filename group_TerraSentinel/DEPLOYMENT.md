# 🚀 Terra Pulse Enhanced API - Production Deployment Guide

## Overview
This guide will help you deploy the enhanced Terra Pulse API to replace your existing Render deployment at `https://terra-pulse-api.onrender.com`.

## 🎯 What You're Deploying

### New Enhanced API Features:
- ✅ **Backward Compatible**: Existing `/predict` endpoint still works
- ✅ **Enhanced Predictions**: New `/enhanced-predict` with AI insights
- ✅ **Authentication**: API key protection for all endpoints
- ✅ **Rate Limiting**: Redis-based rate limiting per API key
- ✅ **Health Monitoring**: Comprehensive health checks
- ✅ **Metrics**: Prometheus-compatible monitoring
- ✅ **User-Specific Formatting**: Farmer vs Official responses

### API Endpoints:
```
🏠 /                    - API documentation
🔮 /predict            - Original Terra Pulse predictions (with auth)
✨ /enhanced-predict   - AI-enhanced predictions with Dify
🏥 /health/system      - System health status
📊 /metrics           - Prometheus metrics
```

## 📋 Pre-Deployment Checklist

### 1. Environment Variables (Required)
Set these in your deployment platform:

#### Core Configuration (Required)
```bash
# Terra Pulse Model
TERRA_PULSE_MODEL_PATH=terra_pulse_model.onnx

# Dify API Configuration (REQUIRED - Get from Dify dashboard)
DIFY_API_KEY=your_dify_api_key_here
DIFY_API_ENDPOINT=https://api.dify.ai/v1
DIFY_WORKFLOW_ID=your_workflow_id_here

# Redis Configuration (REQUIRED for production)
REDIS_URL=redis://your-redis-url:6379/0
```

#### Performance & Reliability
```bash
# Caching
CACHE_TTL=3600                    # Cache time-to-live in seconds

# API Resilience
MAX_RETRIES=3                     # Max retries for external API calls
TIMEOUT_SECONDS=30                # Request timeout in seconds
```

#### Security Configuration
```bash
# Authentication
API_KEY_HEADER=X-API-Key          # Header name for API key authentication

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60          # Requests per minute per API key

# CORS (for web frontend integration)
CORS_ALLOWED_ORIGINS=http://localhost:3000,https://your-frontend.com

# HTTPS Enforcement (set to true in production)
ENFORCE_HTTPS=false
```

#### Monitoring & Logging
```bash
# Logging Level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO
```

### 2. Environment Variable Details

#### DIFY_API_KEY
- **Required**: Yes
- **Description**: Your Dify application API key
- **How to get**: 
  1. Login to Dify dashboard
  2. Go to your application settings
  3. Copy the API key from the "API Access" section
- **Example**: `app-LpBDV8ynBr5J5YgnkfBoR6pg`

#### DIFY_WORKFLOW_ID
- **Required**: Yes
- **Description**: The ID of your Dify workflow for land degradation insights
- **How to get**:
  1. In Dify, go to your workflow
  2. Copy the workflow ID from the URL or workflow settings
- **Example**: `YLObOSRKAB5YFRI6`

#### REDIS_URL
- **Required**: Yes (for production)
- **Description**: Redis connection URL for caching and rate limiting
- **Formats**:
  - Local: `redis://localhost:6379/0`
  - With auth: `redis://username:password@host:port/db`
  - SSL: `rediss://host:port/db`
- **Fallback**: System works without Redis but with reduced performance

### 2. Required Files ✅
- `app.py` - Main Flask application
- `Procfile` - Gunicorn configuration
- `requirements.txt` - Python dependencies
- `runtime.txt` - Python version
- `terra_pulse_model.onnx` - Your trained model
- All `services/` and `config/` directories

## 🔧 Deployment Options

### Option A: Docker Deployment (Recommended for Local Development)

#### Prerequisites
- Docker and Docker Compose installed
- Copy `.env.example` to `.env` and configure your values

#### Quick Start
```bash
# Clone and setup
git clone <your-repo>
cd terra-pulse-dify-integration

# Configure environment
cp .env.example .env
# Edit .env with your Dify API credentials

# Start services
docker-compose up -d

# Check health
curl http://localhost:5000/health/system
```

#### Docker Services
- **terra-pulse-api**: Main Flask application (port 5000)
- **redis**: Redis cache and rate limiting (port 6379)

#### Docker Commands
```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f terra-pulse-api

# Stop services
docker-compose down

# Rebuild after code changes
docker-compose up --build -d

# Scale API instances
docker-compose up --scale terra-pulse-api=3 -d
```

### Option B: Render Deployment (Production)

#### Step 1: Update Your Render Service
1. Go to your Render dashboard
2. Select your existing `terra-pulse-api` service
3. Connect to this updated repository
4. Set environment variables (see checklist above)

### Step 2: Add Redis (Recommended)
```bash
# Option A: Render Redis Add-on (Recommended)
1. In Render dashboard, add Redis add-on
2. Copy the REDIS_URL to environment variables

# Option B: External Redis (Alternative)
Use Redis Cloud, AWS ElastiCache, or similar
```

### Step 3: Deploy
1. Push your code to the connected repository
2. Render will automatically deploy
3. Monitor deployment logs for any issues

### Step 4: Test Deployment
```bash
# Test basic health
curl https://terra-pulse-api.onrender.com/health/system

# Test enhanced prediction (with API key)
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

## 🔑 API Key Management

### For Testing:
- Any non-empty string works as API key
- Example: `test-api-key-12345`

### For Production:
- Generate secure API keys for your clients
- Consider implementing proper API key validation
- Store API keys securely

## 📊 Monitoring

### Health Checks:
- `/health/system` - Overall system status
- `/health/terra-pulse` - Model service health
- `/health/dify` - AI service health

### Metrics:
- `/metrics` - Prometheus-compatible metrics
- Monitor service health, response times, cache hit ratios

## 🔄 Migration Strategy

### Phase 1: Deploy (Immediate)
- Deploy enhanced API to existing URL
- Existing `/predict` clients continue working
- New `/enhanced-predict` available immediately

### Phase 2: Client Migration (Gradual)
- Update client applications to use `/enhanced-predict`
- Provide API keys to clients
- Monitor usage patterns

### Phase 3: Optimization (Ongoing)
- Monitor performance and adjust rate limits
- Optimize caching strategies
- Add more sophisticated API key management

## 🚨 Troubleshooting

### Common Issues:

1. **Dify Connection Failed**
   ```bash
   # Check environment variables
   echo $DIFY_API_KEY
   echo $DIFY_WORKFLOW_ID
   
   # Test Dify health
   curl https://terra-pulse-api.onrender.com/health/dify
   ```

2. **Redis Connection Failed**
   ```bash
   # Check Redis URL
   echo $REDIS_URL
   
   # System will work without Redis (rate limiting disabled)
   ```

3. **Model Loading Failed**
   ```bash
   # Ensure terra_pulse_model.onnx is in repository root
   # Check file size limits on Render
   ```

### Fallback Behavior:
- ✅ If Dify fails: Enhanced predictions fall back to basic recommendations
- ✅ If Redis fails: Rate limiting is disabled, authentication still works
- ✅ If cache fails: Direct predictions without caching

## 📈 Performance Expectations

### Response Times:
- `/predict`: ~150-300ms (model inference)
- `/enhanced-predict`: ~500-1000ms (model + AI workflow)
- `/health/*`: ~50-100ms
- `/metrics`: ~100-200ms

### Throughput:
- Default: 60 requests/minute per API key
- Configurable via `RATE_LIMIT_PER_MINUTE`
- Scales with Render service tier

## 🎉 Success Criteria

After deployment, you should have:
- ✅ Existing `/predict` endpoint working with authentication
- ✅ New `/enhanced-predict` providing AI-enhanced insights
- ✅ Health monitoring showing all services healthy
- ✅ Metrics available for monitoring
- ✅ Backward compatibility maintained
- ✅ Enhanced features available immediately

## 📞 Support

If you encounter issues:
1. Check deployment logs in Render dashboard
2. Test individual health endpoints
3. Verify environment variables are set correctly
4. Monitor `/metrics` for service health

Your enhanced Terra Pulse API will be production-ready with AI capabilities! 🚀