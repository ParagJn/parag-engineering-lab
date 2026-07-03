#!/bin/bash

# Exit on error
set -e

echo "============================================="
echo "   Agentic Procurement Simulator Launcher    "
echo "============================================="

# Get absolute path of workspace
WORKSPACE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$WORKSPACE_DIR"

# Create data directories if they don't exist
mkdir -p "$WORKSPACE_DIR/data/workflows"

# Activate Virtual Environment
echo "[1/5] Activating Python virtual environment..."
source /Users/paragjain/dev-works/myenv/bin/activate

# Install requirements
echo "[2/5] Verifying backend python dependencies..."
pip install -r "$WORKSPACE_DIR/backend/requirements.txt"

# Verify frontend dependencies
echo "[3/5] Verifying frontend node dependencies..."
cd "$WORKSPACE_DIR/frontend"
npm install

# Run frontend build
echo "[4/5] Running production build for React frontend..."
npm run build

# Start FastAPI backend
echo "[5/5] Starting FastAPI backend on port 8000..."
export PYTHONPATH="$WORKSPACE_DIR/backend:$PYTHONPATH"
cd "$WORKSPACE_DIR"
python -m uvicorn backend.app.main:app --port 8000 &
BACKEND_PID=$!

# Start React Frontend Preview
echo "Serving built React frontend on port 5173..."
cd "$WORKSPACE_DIR/frontend"
npm run preview -- --port 5173 --host &
FRONTEND_PID=$!

# Function to clean up background processes
cleanup() {
    echo ""
    echo "============================================="
    echo "   Shutting down services...                 "
    echo "============================================="
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    exit 0
}

# Trap SIGINT and SIGTERM
trap cleanup SIGINT SIGTERM

echo "Waiting for services to start..."
sleep 3

# Open browser (macOS)
if command -v open >/dev/null; then
    open http://localhost:5173
fi

# Keep script running
wait
