# Terra Pulse-Dify Integration API

## Overview

This is a clean, maintainable Flask application following Uncle Bob's Clean Architecture principles for soil degradation prediction using Terra Pulse ML models enhanced with Dify AI workflows.

## Architecture

The application follows Clean Architecture with clear separation of concerns:

```
backend/
├── api/           # Interface adapters (controllers, middleware)
├── services/      # Business logic and external service integrations  
├── config/        # Configuration management
└── tests/         # Comprehensive test suite
```

## Key Features

- **Terra Pulse ML Integration**: ONNX model for soil degradation prediction
- **Dify AI Enhancement**: AI-powered insights and recommendations
- **Clean Architecture**: Following Uncle Bob's principles
- **Comprehensive Testing**: Unit, integration, and security tests
- **Production Ready**: Docker, monitoring, and deployment scripts

## Quick Start

### Local Development

```bash
# Setup environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Dify API credentials

# Run the application
python -m backend.app
```

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up --build
```

## API Endpoints

- `POST /predict` - Basic Terra Pulse prediction
- `POST /enhanced-predict` - AI-enhanced prediction with Dify
- `GET /health/system` - System health check
- `GET /metrics` - Prometheus metrics
- `GET /` - API documentation

## Configuration

Key environment variables:

- `DIFY_API_KEY` - Your Dify API key
- `DIFY_WORKFLOW_ID` - Dify workflow ID
- `TERRA_PULSE_MODEL_PATH` - Path to ONNX model
- `REDIS_URL` - Redis connection for caching

See `.env.example` for full configuration options.

## Testing

```bash
# Run all tests
python -m pytest backend/tests/

# Run specific test categories
python -m pytest backend/tests/test_security_*.py
python -m pytest backend/tests/test_api_*.py
```

## Deployment

Use the provided deployment scripts:

```bash
# Local deployment
./deploy.sh local

# Docker deployment  
./deploy.sh docker

# Check environment
./deploy.sh check
```

## Architecture Principles

This codebase follows Uncle Bob's Clean Architecture:

1. **Independence**: Business rules don't depend on frameworks
2. **Testability**: Business rules can be tested without external elements
3. **Independence of UI**: UI can change without changing business rules
4. **Independence of Database**: Business rules not bound to database
5. **Independence of External Agency**: Business rules don't know about outside world

## Contributing

1. Follow the existing architecture patterns
2. Write tests for new features
3. Update documentation
4. Follow Python PEP 8 style guidelines