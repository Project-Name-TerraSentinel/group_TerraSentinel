@echo off
echo Starting TerraPulse Full Stack Application...
echo.

echo 1. Starting Backend API...
cd /d "%~dp0"
start "TerraPulse Backend" cmd /k "set PYTHONPATH=. && python backend/app.py"

echo 2. Waiting for backend to start...
timeout /t 5 /nobreak > nul

echo 3. Starting Frontend Server...
cd frontend
start "TerraPulse Frontend" cmd /k "python -m http.server 8080"

echo.
echo ========================================
echo TerraPulse Application Started!
echo ========================================
echo.
echo Backend API: http://localhost:5000
echo Frontend App: http://localhost:8080
echo.
echo Press any key to open the application...
pause > nul

start http://localhost:8080

echo.
echo Application is now running!
echo Close both command windows to stop the application.
echo.
pause