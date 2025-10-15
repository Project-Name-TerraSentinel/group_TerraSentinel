# 🌱 TerraPulse - AI-Powered Soil Degradation Analysis

A complete full-stack application for intelligent soil degradation prediction and land restoration planning.

## 🚀 Complete Application

**Backend**: Enterprise-grade Python/Flask API with Terra Pulse ML + Dify AI  
**Frontend**: Modern responsive web application for farmers and planners  
**Integration**: Seamless connection with live predictions and AI recommendations

## Architecture

```
backend/
├── api/           # Interface adapters (controllers, middleware)
├── services/      # Business logic and external service integrations  
├── config/        # Configuration management
└── tests/         # Comprehensive test suite
```

## 🚀 Quick Start

### **Option 1: One-Click Launch**

**Windows:**
```bash
start_app.bat
```

**Linux/Mac:**
```bash
./start_app.sh
```

### **Option 2: Manual Setup**

**Backend:**
```bash
export PYTHONPATH=.
python backend/app.py
```

**Frontend:**
```bash
cd frontend
python -m http.server 8080
```

**Then open**: `http://localhost:8080`

### **Option 3: Docker**
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

## 🎯 Features

### **👨‍🌾 For Farmers**
- 📍 **GPS Location Detection**: Automatic field location detection
- 🤖 **AI Predictions**: Real-time soil degradation analysis  
- 💡 **Smart Recommendations**: Dify AI-powered actionable advice
- 📱 **Mobile Friendly**: Works on phones and tablets
- 🔊 **Accessibility**: Text-to-speech for recommendations

### **🗺️ For Land Planners**
- 🌍 **Regional Analysis**: Multi-parcel degradation mapping
- 📊 **Priority Scoring**: Weighted degradation/area/vulnerability analysis
- 📋 **Restoration Planning**: Select and export restoration plans
- 🎨 **Visual Analytics**: Color-coded risk and priority indicators
- 📈 **Data Export**: CSV export for planning workflows

## 📁 Project Structure

```
TerraPulse/
├── 🔧 BACKEND
│   ├── backend/              # Enterprise Python/Flask API
│   │   ├── api/              # Routes & handlers
│   │   ├── services/         # Business logic & AI integration
│   │   ├── config/           # Configuration management
│   │   ├── tests/            # Comprehensive test suite
│   │   └── terra_pulse_model.onnx  # ML model
│   └── .env                  # Environment configuration
│
├── 🎨 FRONTEND  
│   └── frontend/             # Modern responsive web app
│       ├── js/               # JavaScript modules
│       ├── index.html        # Main application
│       └── styles.css        # CSS styles
│
├── 🚀 LAUNCHERS
│   ├── start_app.bat         # Windows one-click start
│   └── start_app.sh          # Linux/Mac one-click start
│
└── 📚 DOCS
    ├── docs/                 # API documentation
    └── FULL_STACK_INTEGRATION.md  # Complete guide
```

## License

MIT License