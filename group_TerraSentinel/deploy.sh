#!/bin/bash

# Terra Pulse-Dify Integration Deployment Script
# This script helps deploy the application in different environments

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check environment variables
check_env_vars() {
    local missing_vars=()
    
    # Required variables
    required_vars=(
        "DIFY_API_KEY"
        "DIFY_WORKFLOW_ID"
    )
    
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            missing_vars+=("$var")
        fi
    done
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        print_error "Missing required environment variables:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        echo ""
        echo "Please set these variables in your .env file or environment."
        echo "See .env.example for reference."
        return 1
    fi
    
    return 0
}

# Function to validate model file
check_model_file() {
    if [[ ! -f "backend/terra_pulse_model.onnx" ]]; then
        print_error "backend/terra_pulse_model.onnx not found!"
        echo "Please ensure the ONNX model file is in the backend directory."
        return 1
    fi
    
    # Check file size (should be reasonable for a model)
    local file_size=$(stat -f%z "backend/terra_pulse_model.onnx" 2>/dev/null || stat -c%s "backend/terra_pulse_model.onnx" 2>/dev/null)
    if [[ $file_size -lt 1000 ]]; then
        print_warning "Model file seems very small ($file_size bytes). Please verify it's correct."
    fi
    
    return 0
}

# Function to setup local environment
setup_local() {
    print_status "Setting up local development environment..."
    
    # Check Python
    if ! command_exists python3; then
        print_error "Python 3 is required but not installed."
        return 1
    fi
    
    # Check Python version
    python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if [[ $(echo "$python_version < 3.9" | bc -l) -eq 1 ]]; then
        print_error "Python 3.9+ is required. Found: $python_version"
        return 1
    fi
    
    # Create virtual environment if it doesn't exist
    if [[ ! -d "venv" ]]; then
        print_status "Creating virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Install dependencies
    print_status "Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    
    # Setup environment file
    if [[ ! -f ".env" ]]; then
        print_status "Creating .env file from template..."
        cp .env.example .env
        print_warning "Please edit .env file with your actual configuration values."
    fi
    
    print_success "Local environment setup complete!"
    echo ""
    echo "Next steps:"
    echo "1. Edit .env file with your Dify API credentials"
    echo "2. Run: source venv/bin/activate"
    echo "3. Run: python -m backend.app"
}

# Function to deploy with Docker
deploy_docker() {
    print_status "Deploying with Docker..."
    
    # Check Docker
    if ! command_exists docker; then
        print_error "Docker is required but not installed."
        return 1
    fi
    
    if ! command_exists docker-compose; then
        print_error "Docker Compose is required but not installed."
        return 1
    fi
    
    # Check if .env exists
    if [[ ! -f ".env" ]]; then
        print_status "Creating .env file from template..."
        cp .env.example .env
        print_warning "Please edit .env file with your configuration before continuing."
        read -p "Press Enter after editing .env file..."
    fi
    
    # Load environment variables
    set -a
    source .env
    set +a
    
    # Validate environment
    if ! check_env_vars; then
        return 1
    fi
    
    # Validate model file
    if ! check_model_file; then
        return 1
    fi
    
    # Build and start services
    print_status "Building Docker images..."
    docker-compose build
    
    print_status "Starting services..."
    docker-compose up -d
    
    # Wait for services to be ready
    print_status "Waiting for services to start..."
    sleep 10
    
    # Health check
    print_status "Checking service health..."
    if curl -f http://localhost:5000/health/system >/dev/null 2>&1; then
        print_success "Services are healthy!"
        echo ""
        echo "🚀 Deployment successful!"
        echo ""
        echo "API Endpoints:"
        echo "  - Health: http://localhost:5000/health/system"
        echo "  - Docs: http://localhost:5000/"
        echo "  - Predict: http://localhost:5000/predict"
        echo "  - Enhanced: http://localhost:5000/enhanced-predict"
        echo ""
        echo "Useful commands:"
        echo "  - View logs: docker-compose logs -f"
        echo "  - Stop services: docker-compose down"
    else
        print_error "Health check failed. Check logs with: docker-compose logs"
        return 1
    fi
}

# Function to run tests
run_tests() {
    print_status "Running deployment tests..."
    
    # Check if virtual environment exists
    if [[ -d "venv" ]]; then
        source venv/bin/activate
    fi
    
    # Run tests
    python -m pytest tests/ -v --tb=short
    
    if [[ $? -eq 0 ]]; then
        print_success "All tests passed!"
    else
        print_error "Some tests failed. Please check the output above."
        return 1
    fi
}

# Function to show usage
show_usage() {
    echo "Terra Pulse-Dify Integration Deployment Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  local     Setup local development environment"
    echo "  docker    Deploy using Docker Compose"
    echo "  test      Run deployment and integration tests"
    echo "  check     Check environment and dependencies"
    echo "  help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 local     # Setup local development"
    echo "  $0 docker    # Deploy with Docker"
    echo "  $0 test      # Run tests"
}

# Function to check environment
check_environment() {
    print_status "Checking environment and dependencies..."
    
    # Check Python
    if command_exists python3; then
        python_version=$(python3 --version)
        print_success "Python: $python_version"
    else
        print_error "Python 3 not found"
    fi
    
    # Check Docker
    if command_exists docker; then
        docker_version=$(docker --version)
        print_success "Docker: $docker_version"
    else
        print_warning "Docker not found (optional for local development)"
    fi
    
    # Check Docker Compose
    if command_exists docker-compose; then
        compose_version=$(docker-compose --version)
        print_success "Docker Compose: $compose_version"
    else
        print_warning "Docker Compose not found (optional for local development)"
    fi
    
    # Check model file
    if check_model_file; then
        print_success "Model file: backend/terra_pulse_model.onnx found"
    fi
    
    # Check environment file
    if [[ -f ".env" ]]; then
        print_success "Environment file: .env found"
        
        # Load and check variables
        set -a
        source .env
        set +a
        
        if check_env_vars; then
            print_success "Required environment variables are set"
        fi
    else
        print_warning "Environment file: .env not found (will be created)"
    fi
}

# Main script logic
case "${1:-help}" in
    "local")
        setup_local
        ;;
    "docker")
        deploy_docker
        ;;
    "test")
        run_tests
        ;;
    "check")
        check_environment
        ;;
    "help"|*)
        show_usage
        ;;
esac