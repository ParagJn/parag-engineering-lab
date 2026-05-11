#!/bin/bash

# Energy Dashboard Monitor - Startup Script
# This script starts both the backend API and frontend development server

echo "=========================================="
echo "  Energy Dashboard Monitor - VoltStream"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Python virtual environment path
PYTHON_VENV="/Users/paragjain/dev-works/myenv/bin/python"

# Check if data exists
if [ ! -f "data/raw/customers.json" ]; then
    echo -e "${YELLOW}⚠️  Mock data not found. Generating...${NC}"
    cd backend
    $PYTHON_VENV generate_mock_data.py
    cd ..
    echo ""
fi

# Start backend
echo -e "${BLUE}🚀 Starting Backend API (Port 8000)...${NC}"
cd backend
$PYTHON_VENV -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

# Wait for backend to start
echo "   Waiting for backend to initialize..."
sleep 3

# Check if backend is running
if curl -s http://localhost:8000/api/system-status > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Backend API is running${NC}"
else
    echo -e "${YELLOW}⚠️  Backend may still be starting...${NC}"
fi

echo ""

# Start frontend
echo -e "${BLUE}🚀 Starting Frontend Dev Server (Port 5173)...${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "=========================================="
echo -e "${GREEN}✓ Application Started Successfully!${NC}"
echo "=========================================="
echo ""
echo "📊 Access Points:"
echo "   Frontend:  http://localhost:5173"
echo "   Backend:   http://localhost:8000"
echo "   API Docs:  http://localhost:8000/docs"
echo ""
echo "🛑 To stop the application:"
echo "   Press Ctrl+C or run: kill $BACKEND_PID $FRONTEND_PID"
echo ""
echo "📝 Logs:"
echo "   Backend PID:  $BACKEND_PID"
echo "   Frontend PID: $FRONTEND_PID"
echo ""

# Keep script running and handle Ctrl+C
trap "echo ''; echo 'Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT

# Wait for both processes
wait

# Made with Bob
