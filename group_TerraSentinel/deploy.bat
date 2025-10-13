@echo off
REM Terra Pulse-Dify Integration Deployment Script for Windows
setlocal enabledelayedexpansion

REM Colors (limited in Windows CMD)
set "INFO=[INFO]"
set "SUCCESS=[SUCCESS]"
set "WARNING=[WARNING]"
set "ERROR=[ERROR]"

REM Function to check if command exists
where docker >nul 2>&1
if %errorlevel% equ 0 (
    set "DOCKER_AVAILABLE=1"
) else (
    set "DOCKER_AVAILABLE=0"
)

where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_AVAILABLE=1"
) else (
    set "PYTHON_AVAILABLE=0"
)

REM Main script logic
if "%1"=="local" goto setup_local
if "%1"=="docker" goto deploy_docker
if "%1"=="test" goto run_tests
if "%1"=="check" goto check_environment
goto show_usage

:setup_local
echo %INFO% Setting up local development environment...

if %PYTHON_AVAILABLE% equ 0 (
    echo %ERROR% Python is required but not installed.
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo %INFO% Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
echo %INFO% Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt

REM Setup environment file
if not exist ".env" (
    echo %INFO% Creating .env file from template...
    copy .env.example .env
    echo %WARNING% Please edit .env file with your actual configuration values.
)

echo %SUCCESS% Local environment setup complete!
echo.
echo Next steps:
echo 1. Edit .env file with your Dify API credentials
echo 2. Run: venv\Scripts\activate.bat
echo 3. Run: python -m backend.app
goto end

:deploy_docker
echo %INFO% Deploying with Docker...

if %DOCKER_AVAILABLE% equ 0 (
    echo %ERROR% Docker is required but not installed.
    exit /b 1
)

REM Check if .env exists
if not exist ".env" (
    echo %INFO% Creating .env file from template...
    copy .env.example .env
    echo %WARNING% Please edit .env file with your configuration before continuing.
    pause
)

REM Check model file
if not exist "backend\terra_pulse_model.onnx" (
    echo %ERROR% backend\terra_pulse_model.onnx not found!
    echo Please ensure the ONNX model file is in the backend directory.
    exit /b 1
)

REM Build and start services
echo %INFO% Building Docker images...
docker-compose build

echo %INFO% Starting services...
docker-compose up -d

REM Wait for services to be ready
echo %INFO% Waiting for services to start...
timeout /t 10 /nobreak >nul

REM Health check
echo %INFO% Checking service health...
curl -f http://localhost:5000/health/system >nul 2>&1
if %errorlevel% equ 0 (
    echo %SUCCESS% Services are healthy!
    echo.
    echo 🚀 Deployment successful!
    echo.
    echo API Endpoints:
    echo   - Health: http://localhost:5000/health/system
    echo   - Docs: http://localhost:5000/
    echo   - Predict: http://localhost:5000/predict
    echo   - Enhanced: http://localhost:5000/enhanced-predict
    echo.
    echo Useful commands:
    echo   - View logs: docker-compose logs -f
    echo   - Stop services: docker-compose down
) else (
    echo %ERROR% Health check failed. Check logs with: docker-compose logs
    exit /b 1
)
goto end

:run_tests
echo %INFO% Running deployment tests...

REM Check if virtual environment exists
if exist "venv" (
    call venv\Scripts\activate.bat
)

REM Run tests
python -m pytest tests/ -v --tb=short

if %errorlevel% equ 0 (
    echo %SUCCESS% All tests passed!
) else (
    echo %ERROR% Some tests failed. Please check the output above.
    exit /b 1
)
goto end

:check_environment
echo %INFO% Checking environment and dependencies...

if %PYTHON_AVAILABLE% equ 1 (
    for /f "tokens=*" %%i in ('python --version') do echo %SUCCESS% Python: %%i
) else (
    echo %ERROR% Python not found
)

if %DOCKER_AVAILABLE% equ 1 (
    for /f "tokens=*" %%i in ('docker --version') do echo %SUCCESS% Docker: %%i
) else (
    echo %WARNING% Docker not found (optional for local development)
)

where docker-compose >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('docker-compose --version') do echo %SUCCESS% Docker Compose: %%i
) else (
    echo %WARNING% Docker Compose not found (optional for local development)
)

if exist "backend\terra_pulse_model.onnx" (
    echo %SUCCESS% Model file: backend\terra_pulse_model.onnx found
) else (
    echo %ERROR% Model file: backend\terra_pulse_model.onnx not found
)

if exist ".env" (
    echo %SUCCESS% Environment file: .env found
) else (
    echo %WARNING% Environment file: .env not found (will be created)
)
goto end

:show_usage
echo Terra Pulse-Dify Integration Deployment Script
echo.
echo Usage: %0 [COMMAND]
echo.
echo Commands:
echo   local     Setup local development environment
echo   docker    Deploy using Docker Compose
echo   test      Run deployment and integration tests
echo   check     Check environment and dependencies
echo   help      Show this help message
echo.
echo Examples:
echo   %0 local     # Setup local development
echo   %0 docker    # Deploy with Docker
echo   %0 test      # Run tests

:end
endlocal