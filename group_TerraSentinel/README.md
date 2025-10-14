# Terra Pulse-Dify Integration API

A clean, maintainable Flask application following Uncle Bob's Clean Architecture principles for AI-enhanced soil degradation prediction.

## Overview

This API integrates Terra Pulse ML models with Dify AI workflows to provide intelligent soil degradation predictions and recommendations for agricultural decision-making.

## Architecture

```
backend/
├── api/           # Interface adapters (controllers, middleware)
├── services/      # Business logic and external service integrations  
├── config/        # Configuration management
└── tests/         # Comprehensive test suite
```

## Quick Start

### Local Development

```bash
# Setup environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your Dify API credentials

# Run
python -m backend.app
```

### Docker Deployment

```bash
docker-compose up --build
```

## Key Features

- **Clean Architecture**: Following Uncle Bob's SOLID principles
- **Terra Pulse ML**: ONNX model for soil degradation prediction
- **Dify AI Enhancement**: AI-powered insights and recommendations
- **Production Ready**: Comprehensive testing, monitoring, security
- **User-Specific**: Tailored responses for different user types

## API Endpoints

- `POST /predict` - Basic Terra Pulse prediction
- `POST /enhanced-predict` - AI-enhanced prediction with Dify
- `GET /health/system` - System health check
- `GET /metrics` - Prometheus metrics

## Configuration

Key environment variables:
- `DIFY_API_KEY` - Your Dify API key (required)
- `DIFY_WORKFLOW_ID` - Dify workflow ID (required)
- `TERRA_PULSE_MODEL_PATH` - Path to ONNX model
- `REDIS_URL` - Redis for caching (optional)

See `.env.example` for full configuration.

## Documentation

Comprehensive documentation available in the `docs/` folder:
- [API Examples](docs/API_EXAMPLES.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Security Guide](docs/SECURITY_TESTS_SUMMARY.md)
- [Production Checklist](docs/PRODUCTION_CHECKLIST.md)

## Testing

```bash
# Run all tests
python -m pytest backend/tests/

# Run specific categories
python -m pytest backend/tests/test_security_*.py
python -m pytest backend/tests/test_api_*.py
```

## Deployment

```bash
# Check environment
./deploy.sh check

# Local deployment
./deploy.sh local

# Docker deployment
./deploy.sh docker
```

## Clean Architecture Principles

This codebase follows Uncle Bob's Clean Architecture:

1. **Independence of Frameworks**: Business rules don't depend on frameworks
2. **Testable**: Business rules can be tested without external elements  
3. **Independent of UI**: UI can change without changing business rules
4. **Independent of Database**: Business rules not bound to database
5. **Independent of External Agency**: Business rules don't know about outside world

## For Frontend Developers

🎯 **Ready to integrate?** See [FRONTEND_HANDOFF.md](FRONTEND_HANDOFF.md) for quick start guide.

📚 **Complete integration guide**: [docs/FRONTEND_INTEGRATION_GUIDE.md](docs/FRONTEND_INTEGRATION_GUIDE.md)

### Quick Integration Example

```javascript
// Enhanced prediction with AI insights
const response = await fetch('https://your-api.com/enhanced-predict', {
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
    user_type: "farmer"
  })
});

const prediction = await response.json();
// Use prediction.ai_insights for recommendations
// Use prediction.user_formatted_response for display
```

## License

MIT License