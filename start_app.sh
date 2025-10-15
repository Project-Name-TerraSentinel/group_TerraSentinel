#!/bin/bash

echo "Starting TerraPulse Full Stack Application..."
echo

# Function to check if a port is in use
check_port() {
    if command -v lsof > /dev/null; then
        lsof -i :$1 > /dev/null 2>&1
    elif command -v netstat > /dev/null; then
        netstat -tuln | grep :$1 > /dev/null 2>&1
    else
        return 1
    fi
}

# Start backend
echo "1. Starting Backend API..."
export PYTHONPATH=.

# Check if backend is already running
if check_port 5000; then
    echo "Backend already running on port 5000"
else
    echo "Starting new backend instance..."
    python backend/app.py &
    BACKEND_PID=$!
    echo "Backend started with PID: $BACKEND_PID"
fi

# Wait for backend to start
echo "2. Waiting for backend to initialize..."
sleep 5

# Start frontend
echo "3. Starting Frontend Server..."
cd frontend

# Check if frontend is already running
if check_port 8080; then
    echo "Frontend already running on port 8080"
else
    echo "Starting new frontend server..."
    if command -v python3 > /dev/null; then
        python3 -m http.server 8080 &
    elif command -v python > /dev/null; then
        python -m http.server 8080 &
    else
        echo "Python not found. Please install Python to run the frontend server."
        exit 1
    fi
    FRONTEND_PID=$!
    echo "Frontend started with PID: $FRONTEND_PID"
fi

cd ..

echo
echo "========================================"
echo "TerraPulse Application Started!"
echo "========================================"
echo
echo "Backend API: http://localhost:5000"
echo "Frontend App: http://localhost:8080"
echo
echo "Opening application in browser..."

# Open browser (cross-platform)
if command -v xdg-open > /dev/null; then
    xdg-open http://localhost:8080
elif command -v open > /dev/null; then
    open http://localhost:8080
elif command -v start > /dev/null; then
    start http://localhost:8080
else
    echo "Please open http://localhost:8080 in your browser"
fi

echo
echo "Application is now running!"
echo "Press Ctrl+C to stop the application"
echo

# Wait for interrupt
trap 'echo "Stopping application..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit' INT
wait