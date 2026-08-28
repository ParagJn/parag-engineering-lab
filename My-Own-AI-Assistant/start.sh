#!/bin/bash

# Start script for AI Assistant
# This script starts both the backend and frontend servers

set -e

echo "🚀 Starting AI Assistant..."
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if virtual environment exists
if [ ! -d "/Users/paragjain/dev-works/myenv" ]; then
    echo "❌ Virtual environment not found at /Users/paragjain/dev-works/myenv"
    echo "Please create it first or update the path in this script."
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found"
    echo "Please create a .env file with your IBM ICA credentials"
    exit 1
fi

# Start backend in background
echo "${BLUE}Starting backend server...${NC}"
cd backend
source /Users/paragjain/dev-works/myenv/bin/activate
python -m uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
echo "${GREEN}✓ Backend started (PID: $BACKEND_PID)${NC}"
cd ..

# Wait a bit for backend to start
sleep 3

# Start frontend in background
echo "${BLUE}Starting frontend server...${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!
echo "${GREEN}✓ Frontend started (PID: $FRONTEND_PID)${NC}"
cd ..

echo ""
echo "${GREEN}========================================${NC}"
echo "${GREEN}  AI Assistant is running!${NC}"
echo "${GREEN}========================================${NC}"
echo ""
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop all servers"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down servers..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    echo "✓ Servers stopped"
    exit 0
}

# Register cleanup function
trap cleanup SIGINT SIGTERM

# Wait for processes
wait
