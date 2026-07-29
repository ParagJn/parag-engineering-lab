#!/bin/bash
# ============================================================================
# Project Schedule Tool - Unified Start Script
# Starts both Backend (FastAPI) and Frontend (React/Vite) services
# ============================================================================

# Trap Ctrl+C to cleanup background processes
trap cleanup INT

cleanup() {
    echo ""
    echo "🛑 Shutting down services..."
    if [ ! -z "$BACKEND_PID" ]; then
        echo "  Stopping backend (PID: $BACKEND_PID)..."
        kill $BACKEND_PID 2>/dev/null
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        echo "  Stopping frontend (PID: $FRONTEND_PID)..."
        kill $FRONTEND_PID 2>/dev/null
    fi
    echo "👋 All services stopped. Goodbye!"
    exit 0
}

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                                                                ║"
echo "║          Project Schedule Tool - Starting Services            ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# ============================================================================
# FRONTEND PRE-FLIGHT CHECKS
# ============================================================================

echo "🔍 Checking Frontend Requirements..."
echo ""

# Check if npm is installed
if ! command -v npm &> /dev/null; then
  echo "❌ ERROR: 'npm' is not installed or not found in PATH."
  echo "   Please install Node.js and npm first:"
  echo "   https://nodejs.org/"
  exit 1
fi

# Check if node is installed
if ! command -v node &> /dev/null; then
  echo "❌ ERROR: 'node' is not installed or not found in PATH."
  echo "   Please install Node.js first:"
  echo "   https://nodejs.org/"
  exit 1
fi

echo "✅ Node.js $(node --version) detected"
echo "✅ npm $(npm --version) detected"
echo ""

# Ensure we're running from the project directory
if [ ! -f "package.json" ]; then
  echo "❌ ERROR: 'package.json' not found in the current directory."
  echo "   Please run this script from the Project-Schedule-Tool root folder."
  exit 1
fi

# Check if node_modules exists, if not run npm install
if [ ! -d "node_modules" ]; then
  echo "📦 Installing frontend dependencies..."
  npm install
  if [ $? -ne 0 ]; then
    echo ""
    echo "❌ ERROR: 'npm install' failed."
    exit 1
  fi
  echo "✅ Frontend dependencies installed!"
  echo ""
fi

# ============================================================================
# BACKEND PRE-FLIGHT CHECKS
# ============================================================================

echo "🔍 Checking Backend Requirements..."
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
  echo "❌ ERROR: 'python3' is not installed or not found in PATH."
  exit 1
fi

echo "✅ Python $(python3 --version | cut -d' ' -f2) detected"
echo ""

# Check if backend directory exists
if [ ! -d "backend" ]; then
  echo "❌ ERROR: 'backend' directory not found."
  exit 1
fi

# Set the virtual environment path
VENV_PATH="/Users/paragjain/dev-works/myenv"

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo "❌ Virtual environment not found at: $VENV_PATH"
    echo "Please create a virtual environment first:"
    echo "  python3 -m venv $VENV_PATH"
    exit 1
fi

echo "✅ Virtual environment found at: $VENV_PATH"
echo ""

# ============================================================================
# BACKEND SETUP
# ============================================================================

echo "🔧 Setting up Backend..."
echo ""

cd backend

# Activate virtual environment
source "$VENV_PATH/bin/activate"

# Check if requirements are installed
if ! pip show fastapi > /dev/null 2>&1; then
    echo "📥 Installing backend dependencies..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "❌ ERROR: Failed to install backend dependencies."
        cd ..
        exit 1
    fi
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found in backend/"
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✅ Created .env file from .env.example"
        echo "   Please update backend/.env with your credentials before restarting."
    fi
fi

# Load environment variables
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs 2>/dev/null)
fi

echo "✅ Backend setup complete!"
echo ""

cd ..

# ============================================================================
# FRONTEND BUILD
# ============================================================================

echo "🔨 Building Frontend..."
npm run build
if [ $? -ne 0 ]; then
  echo ""
  echo "❌ ERROR: Frontend build failed!"
  exit 1
fi

echo "✅ Frontend build complete!"
echo ""

# ============================================================================
# START SERVICES
# ============================================================================

echo "🚀 Starting Services..."
echo ""

# Start Backend in background
echo "▶️  Starting Backend (FastAPI)..."
cd backend
source "$VENV_PATH/bin/activate"
python main.py > ../backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to start
sleep 2

# Check if backend is still running
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "❌ ERROR: Backend failed to start. Check backend.log for details."
    cat backend.log
    exit 1
fi

echo "✅ Backend started (PID: $BACKEND_PID)"
echo "   📍 API: http://localhost:8000"
echo "   📚 Docs: http://localhost:8000/docs"
echo ""

# Start Frontend in foreground
echo "▶️  Starting Frontend (Vite)..."
echo "   📍 App: http://localhost:5173"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Both services are running!"
echo "  Press Ctrl+C to stop all services"
echo "═══════════════════════════════════════════════════════════════"
echo ""

npm run dev
FRONTEND_EXIT_CODE=$?

# Cleanup when frontend exits
cleanup
