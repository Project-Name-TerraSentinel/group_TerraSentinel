# Production Deployment Guide

## Overview

This guide walks you through deploying the Terra Pulse-Dify Integration API to production and providing frontend developers with everything they need for integration.

## Pre-Deployment Checklist

### 1. Environment Setup

```bash
# 1. Clone and setup
git clone <your-repo>
cd terra-pulse-dify-integration

# 2. Create production environment file
cp .env.example .env.production

# 3. Configure production variables
nano .env.production
```

**Required Production Variables:**
```bash
# Dify Configuration (REQUIRED)
DIFY_API_KEY=your-production-dify-api-key
DIFY_WORKFLOW_ID=your-production-workflow-id
DIFY_API_ENDPOINT=https://api.dify.ai/v1

# Model Configuration
TERRA_PULSE_MODEL_PATH=backend/terra_pulse_model.onnx

# Security Configuration
API_KEY_HEADER=X-API-Key
RATE_LIMIT_PER_MINUTE=100
ENFORCE_HTTPS=true

# CORS Configuration (ADD YOUR FRONTEND DOMAINS)
CORS_ALLOWED_ORIGINS=https://yourfrontend.com,https://www.yourfrontend.com

# Redis Configuration (RECOMMENDED)
REDIS_URL=redis://your-redis-host:6379/0
CACHE_TTL=3600

# Monitoring Configuration
LOG_LEVEL=INFO
ALERT_EMAIL_ENABLED=true
ALERT_EMAIL_USERNAME=alerts@yourcompany.com
ALERT_EMAIL_PASSWORD=your-email-password
ALERT_TO_EMAILS=admin@yourcompany.com,devops@yourcompany.com

# Performance Configuration
MAX_RETRIES=3
TIMEOUT_SECONDS=30
```

### 2. Infrastructure Requirements

**Minimum Requirements:**
- **CPU**: 2 cores
- **RAM**: 4GB
- **Storage**: 10GB
- **Network**: HTTPS/SSL certificate

**Recommended for Production:**
- **CPU**: 4+ cores
- **RAM**: 8GB+
- **Storage**: 20GB+ SSD
- **Redis**: Separate Redis instance
- **Load Balancer**: For high availability
- **Monitoring**: Prometheus + Grafana

## Deployment Options

### Option 1: Docker Compose (Recommended)

```bash
# 1. Prepare environment
cp .env.production .env

# 2. Deploy with Docker Compose
./deploy.sh docker

# 3. Verify deployment
curl https://your-domain.com/health/system
```

**docker-compose.production.yml:**
```yaml
version: '3.8'

services:
  terra-pulse-api:
    build: .
    ports:
      - "5000:5000"
    environment:
      - DIFY_API_KEY=${DIFY_API_KEY}
      - DIFY_WORKFLOW_ID=${DIFY_WORKFLOW_ID}
      - REDIS_URL=redis://redis:6379/0
      - ENFORCE_HTTPS=true
      - CORS_ALLOWED_ORIGINS=${CORS_ALLOWED_ORIGINS}
    depends_on:
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health/system"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - terra-pulse-api
    restart: unless-stopped

volumes:
  redis_data:
```

### Option 2: Cloud Deployment (AWS/GCP/Azure)

**AWS ECS Example:**
```bash
# 1. Build and push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com
docker build -t terra-pulse-api .
docker tag terra-pulse-api:latest <account>.dkr.ecr.us-east-1.amazonaws.com/terra-pulse-api:latest
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/terra-pulse-api:latest

# 2. Deploy to ECS using task definition
aws ecs update-service --cluster production --service terra-pulse-api --force-new-deployment
```

### Option 3: Kubernetes

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: terra-pulse-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: terra-pulse-api
  template:
    metadata:
      labels:
        app: terra-pulse-api
    spec:
      containers:
      - name: api
        image: terra-pulse-api:latest
        ports:
        - containerPort: 5000
        env:
        - name: DIFY_API_KEY
          valueFrom:
            secretKeyRef:
              name: terra-pulse-secrets
              key: dify-api-key
        livenessProbe:
          httpGet:
            path: /health/system
            port: 5000
          initialDelaySeconds: 30
          periodSeconds: 10
```

## SSL/HTTPS Configuration

### Nginx Configuration

```nginx
# nginx.conf
events {
    worker_connections 1024;
}

http {
    upstream api {
        server terra-pulse-api:5000;
    }

    server {
        listen 80;
        server_name your-domain.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com;

        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;

        location / {
            proxy_pass http://api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # CORS headers for frontend
        add_header Access-Control-Allow-Origin "https://yourfrontend.com" always;
        add_header Access-Control-Allow-Methods "GET, POST, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Content-Type, Authorization, X-API-Key" always;
    }
}
```

## API Key Management

### 1. Generate API Keys

```python
# generate_api_keys.py
import secrets
import hashlib
from datetime import datetime

def generate_api_key(client_name):
    """Generate a secure API key for a client."""
    key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    
    print(f"Client: {client_name}")
    print(f"API Key: {key}")
    print(f"Key Hash: {key_hash}")
    print(f"Generated: {datetime.now()}")
    print("-" * 50)
    
    return key, key_hash

# Generate keys for different clients
frontend_key, frontend_hash = generate_api_key("Frontend App")
mobile_key, mobile_hash = generate_api_key("Mobile App")
partner_key, partner_hash = generate_api_key("Partner Integration")
```

### 2. API Key Validation (Optional Enhancement)

```python
# backend/services/api_key_service.py
import hashlib
from typing import Optional

class APIKeyService:
    def __init__(self):
        # In production, store these in a database
        self.valid_keys = {
            "frontend": "hash_of_frontend_key",
            "mobile": "hash_of_mobile_key",
            "partner": "hash_of_partner_key"
        }
    
    def validate_key(self, api_key: str) -> Optional[str]:
        """Validate API key and return client identifier."""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        for client, stored_hash in self.valid_keys.items():
            if key_hash == stored_hash:
                return client
        
        return None
```

## Monitoring Setup

### 1. Health Check Monitoring

```bash
# health-check.sh
#!/bin/bash

API_URL="https://your-domain.com"
SLACK_WEBHOOK="your-slack-webhook-url"

check_health() {
    response=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/health/system")
    
    if [ "$response" != "200" ]; then
        message="🚨 Terra Pulse API Health Check Failed! Status: $response"
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"$message\"}" \
            "$SLACK_WEBHOOK"
    fi
}

check_health
```

### 2. Prometheus Metrics

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'terra-pulse-api'
    static_configs:
      - targets: ['your-domain.com:5000']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

### 3. Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Terra Pulse API Monitoring",
    "panels": [
      {
        "title": "API Health Status",
        "type": "stat",
        "targets": [
          {
            "expr": "terra_pulse_service_health"
          }
        ]
      },
      {
        "title": "Response Times",
        "type": "graph",
        "targets": [
          {
            "expr": "terra_pulse_response_time_ms"
          }
        ]
      }
    ]
  }
}
```

## Frontend Integration Handoff

### 1. Provide Frontend Team With:

**API Information:**
```json
{
  "api_base_url": "https://your-domain.com",
  "api_key": "frontend-api-key-here",
  "documentation_url": "https://your-domain.com/",
  "health_check_url": "https://your-domain.com/health/system"
}
```

**Integration Guide:**
- Share `docs/FRONTEND_INTEGRATION_GUIDE.md`
- Provide test API key for development
- Share example requests and responses

### 2. CORS Configuration

Update your backend to allow frontend domains:

```python
# backend/config/settings.py
cors_allowed_origins: str = Field(
    default="https://yourfrontend.com,https://www.yourfrontend.com",
    description="Comma-separated list of allowed CORS origins"
)
```

### 3. Rate Limiting Guidelines

```python
# Recommended rate limits by client type
RATE_LIMITS = {
    "frontend": 1000,  # requests per minute
    "mobile": 500,
    "partner": 2000,
    "development": 100
}
```

## Testing Production Deployment

### 1. Automated Tests

```bash
# test-production.sh
#!/bin/bash

API_URL="https://your-domain.com"
API_KEY="your-test-api-key"

echo "Testing production deployment..."

# Test health endpoint
echo "1. Testing health endpoint..."
curl -f "$API_URL/health/system" || exit 1

# Test basic prediction
echo "2. Testing basic prediction..."
curl -X POST "$API_URL/predict" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "NDVI_mean_early": 0.65,
    "NDVI_median_early": 0.67,
    "NDVI_std_early": 0.12,
    "NDVI_mean_late": 0.45,
    "NDVI_median_late": 0.47,
    "NDVI_std_late": 0.15,
    "NDVI_delta_mean": -0.20,
    "location": "Test Field",
    "user_context": "Production Test"
  }' || exit 1

# Test enhanced prediction
echo "3. Testing enhanced prediction..."
curl -X POST "$API_URL/enhanced-predict" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "ndvi_mean_early": 0.65,
    "ndvi_median_early": 0.67,
    "ndvi_std_early": 0.12,
    "ndvi_mean_late": 0.45,
    "ndvi_median_late": 0.47,
    "ndvi_std_late": 0.15,
    "ndvi_delta_mean": -0.20,
    "location": "Test Field",
    "user_context": "Production Test",
    "user_type": "farmer"
  }' || exit 1

echo "✅ All production tests passed!"
```

### 2. Load Testing

```bash
# Install Apache Bench
sudo apt-get install apache2-utils

# Run load test
ab -n 1000 -c 10 -H "X-API-Key: your-api-key" \
   -p test-data.json -T application/json \
   https://your-domain.com/predict
```

## Maintenance and Updates

### 1. Zero-Downtime Deployment

```bash
# blue-green-deploy.sh
#!/bin/bash

# Build new version
docker build -t terra-pulse-api:new .

# Start new container
docker run -d --name terra-pulse-new \
  --env-file .env.production \
  -p 5001:5000 \
  terra-pulse-api:new

# Health check new version
sleep 30
curl -f http://localhost:5001/health/system

# Switch traffic (update load balancer)
# Stop old container
docker stop terra-pulse-old
docker rm terra-pulse-old

# Rename new container
docker rename terra-pulse-new terra-pulse-api
```

### 2. Database Migrations (if added later)

```python
# migrations/001_add_api_keys_table.py
def upgrade():
    """Add API keys table."""
    pass

def downgrade():
    """Remove API keys table."""
    pass
```

### 3. Backup Strategy

```bash
# backup.sh
#!/bin/bash

DATE=$(date +%Y%m%d_%H%M%S)

# Backup Redis data
docker exec redis redis-cli BGSAVE
docker cp redis:/data/dump.rdb ./backups/redis_$DATE.rdb

# Backup configuration
cp .env.production ./backups/env_$DATE.backup

# Backup logs
docker logs terra-pulse-api > ./backups/logs_$DATE.log
```

## Troubleshooting

### Common Production Issues

1. **High Memory Usage**
   ```bash
   # Monitor memory
   docker stats terra-pulse-api
   
   # Restart if needed
   docker restart terra-pulse-api
   ```

2. **Slow Response Times**
   ```bash
   # Check Redis connection
   docker exec redis redis-cli ping
   
   # Check API health
   curl https://your-domain.com/health/system
   ```

3. **SSL Certificate Issues**
   ```bash
   # Check certificate expiry
   openssl x509 -in cert.pem -text -noout | grep "Not After"
   
   # Renew Let's Encrypt certificate
   certbot renew
   ```

### Monitoring Commands

```bash
# Check API logs
docker logs -f terra-pulse-api

# Check system resources
docker stats

# Check Redis status
docker exec redis redis-cli info

# Test API endpoints
curl -H "X-API-Key: your-key" https://your-domain.com/health/system
```

## Security Checklist

- [ ] HTTPS/SSL enabled and enforced
- [ ] API keys properly secured
- [ ] CORS configured for specific domains
- [ ] Rate limiting enabled
- [ ] Input validation active
- [ ] Security headers configured
- [ ] Monitoring and alerting setup
- [ ] Regular security updates scheduled
- [ ] Backup strategy implemented
- [ ] Access logs enabled

## Frontend Developer Handoff Checklist

- [ ] API deployed and accessible
- [ ] SSL certificate configured
- [ ] CORS configured for frontend domain
- [ ] API key generated and shared securely
- [ ] Documentation shared (`docs/FRONTEND_INTEGRATION_GUIDE.md`)
- [ ] Test endpoints verified
- [ ] Rate limits communicated
- [ ] Error handling examples provided
- [ ] Health check endpoints documented
- [ ] Support contact information shared

## Post-Deployment

1. **Monitor for 24 hours** after initial deployment
2. **Set up alerts** for health check failures
3. **Schedule regular backups**
4. **Plan for scaling** based on usage patterns
5. **Document any custom configurations**
6. **Set up log rotation** to prevent disk space issues

Your API is now production-ready and frontend developers have everything they need to integrate successfully! 🚀