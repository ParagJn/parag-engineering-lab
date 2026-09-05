#!/bin/bash

# Daily Articles Pages - Startup Script
# ==========================================
# This script starts the Daily Articles Pages application
# - Checks and kills processes on required ports
# - Activates virtual environment
# - Builds frontend assets
# - Starts backend (FastAPI) on port 8000
# - Starts frontend (Vite) on port 5173

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
VENV_PATH="/Users/paragjain/dev-works/myenv"
BACKEND_PORT=8000
FRONTEND_PORT=5173
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# Log file
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

# PID files for cleanup
BACKEND_PID_FILE="$LOG_DIR/backend.pid"
FRONTEND_PID_FILE="$LOG_DIR/frontend.pid"

echo -e "${CYAN}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   Daily Articles Pages - Application Startup      ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to print status messages
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Function to check if a port is in use
check_port() {
    local port=$1
    lsof -ti:$port > /dev/null 2>&1
    return $?
}

# Function to kill process on a specific port
kill_port() {
    local port=$1
    local process_name=$2
    
    if check_port $port; then
        print_warning "Port $port is in use. Attempting to free it..."
        local pids=$(lsof -ti:$port)
        if [ ! -z "$pids" ]; then
            echo "$pids" | xargs kill -9 2>/dev/null || true
            sleep 2
            if check_port $port; then
                print_error "Failed to free port $port"
                return 1
            else
                print_success "Port $port is now available"
            fi
        fi
    else
        print_success "Port $port is available"
    fi
    return 0
}

# Function to cleanup on exit
cleanup() {
    echo ""
    print_warning "Shutting down services..."
    
    # Kill backend
    if [ -f "$BACKEND_PID_FILE" ]; then
        local backend_pid=$(cat "$BACKEND_PID_FILE")
        if ps -p $backend_pid > /dev/null 2>&1; then
            kill $backend_pid 2>/dev/null || true
            print_status "Backend stopped (PID: $backend_pid)"
        fi
        rm -f "$BACKEND_PID_FILE"
    fi
    
    # Kill frontend
    if [ -f "$FRONTEND_PID_FILE" ]; then
        local frontend_pid=$(cat "$FRONTEND_PID_FILE")
        if ps -p $frontend_pid > /dev/null 2>&1; then
            kill $frontend_pid 2>/dev/null || true
            print_status "Frontend stopped (PID: $frontend_pid)"
        fi
        rm -f "$FRONTEND_PID_FILE"
    fi
    
    # Final port cleanup
    kill_port $BACKEND_PORT "backend" > /dev/null 2>&1 || true
    kill_port $FRONTEND_PORT "frontend" > /dev/null 2>&1 || true
    
    print_success "Cleanup complete"
    exit 0
}

# Trap exit signals
trap cleanup SIGINT SIGTERM EXIT

# Step 1: Check directories
print_status "Checking project structure..."
if [ ! -d "$BACKEND_DIR" ]; then
    print_error "Backend directory not found: $BACKEND_DIR"
    exit 1
fi
if [ ! -d "$FRONTEND_DIR" ]; then
    print_error "Frontend directory not found: $FRONTEND_DIR"
    exit 1
fi
print_success "Project structure verified"

# Step 2: Check virtual environment
print_status "Checking virtual environment..."
if [ ! -d "$VENV_PATH" ]; then
    print_error "Virtual environment not found: $VENV_PATH"
    exit 1
fi
if [ ! -f "$VENV_PATH/bin/activate" ]; then
    print_error "Virtual environment activation script not found"
    exit 1
fi
print_success "Virtual environment found: $VENV_PATH"

# Step 3: Activate virtual environment
print_status "Activating virtual environment..."
source "$VENV_PATH/bin/activate"
if [ $? -eq 0 ]; then
    print_success "Virtual environment activated"
    print_status "Python: $(which python)"
    print_status "Python version: $(python --version)"
else
    print_error "Failed to activate virtual environment"
    exit 1
fi

# Step 4: Check backend dependencies
print_status "Checking backend dependencies..."
cd "$BACKEND_DIR"
if [ ! -f "requirements.txt" ]; then
    print_warning "requirements.txt not found in backend directory"
else
    if ! python -c "import fastapi" 2>/dev/null; then
        print_warning "FastAPI not found. Installing dependencies..."
        pip install -r requirements.txt
    fi
    print_success "Backend dependencies verified"
fi

# Step 5: Check frontend dependencies
print_status "Checking frontend dependencies..."
cd "$FRONTEND_DIR"
if [ ! -f "package.json" ]; then
    print_error "package.json not found in frontend directory"
    exit 1
fi
if [ ! -d "node_modules" ]; then
    print_warning "node_modules not found. Running npm install..."
    npm install
    if [ $? -ne 0 ]; then
        print_error "npm install failed"
        exit 1
    fi
fi
print_success "Frontend dependencies verified"

# Step 6: Build frontend
print_status "Building frontend assets..."
npm run build
if [ $? -eq 0 ]; then
    print_success "Frontend build completed"
else
    print_error "Frontend build failed"
    exit 1
fi

# Step 7: Check and free ports
echo ""
print_status "Checking port availability..."
kill_port $BACKEND_PORT "backend"
if [ $? -ne 0 ]; then
    exit 1
fi
kill_port $FRONTEND_PORT "frontend"
if [ $? -ne 0 ]; then
    exit 1
fi

# Step 8: Start Backend
echo ""
print_status "Starting backend server on port $BACKEND_PORT..."
cd "$BACKEND_DIR"

# Clear old log
> "$BACKEND_LOG"

# Start backend in background
uvicorn main:app --host 0.0.0.0 --port $BACKEND_PORT --reload > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > "$BACKEND_PID_FILE"

# Wait and verify backend started
sleep 3
if ps -p $BACKEND_PID > /dev/null 2>&1; then
    if check_port $BACKEND_PORT; then
        print_success "Backend started successfully (PID: $BACKEND_PID)"
        print_status "Backend URL: http://localhost:$BACKEND_PORT"
        print_status "Backend API docs: http://localhost:$BACKEND_PORT/docs"
        print_status "Backend logs: tail -f $BACKEND_LOG"
    else
        print_error "Backend process running but port $BACKEND_PORT not listening"
        cat "$BACKEND_LOG"
        exit 1
    fi
else
    print_error "Backend failed to start. Check logs:"
    cat "$BACKEND_LOG"
    exit 1
fi

# Step 9: Start Frontend
echo ""
print_status "Starting frontend server on port $FRONTEND_PORT..."
cd "$FRONTEND_DIR"

# Clear old log
> "$FRONTEND_LOG"

# Start frontend in background
npm run dev -- --port $FRONTEND_PORT --host > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$FRONTEND_PID_FILE"

# Wait and verify frontend started
sleep 3
if ps -p $FRONTEND_PID > /dev/null 2>&1; then
    # Give Vite a bit more time to bind to port
    sleep 2
    if check_port $FRONTEND_PORT; then
        print_success "Frontend started successfully (PID: $FRONTEND_PID)"
        print_status "Frontend URL: http://localhost:$FRONTEND_PORT"
        print_status "Frontend logs: tail -f $FRONTEND_LOG"
    else
        print_warning "Frontend process running but port $FRONTEND_PORT not yet listening"
        print_status "Frontend may still be initializing..."
    fi
else
    print_error "Frontend failed to start. Check logs:"
    cat "$FRONTEND_LOG"
    exit 1
fi

# Final status
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║        Application Started Successfully!           ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}🌐 Application URLs:${NC}"
echo -e "   Frontend:  ${GREEN}http://localhost:$FRONTEND_PORT${NC}"
echo -e "   Backend:   ${GREEN}http://localhost:$BACKEND_PORT${NC}"
echo -e "   API Docs:  ${GREEN}http://localhost:$BACKEND_PORT/docs${NC}"
echo ""
echo -e "${CYAN}📋 Logs:${NC}"
echo -e "   Backend:   tail -f $BACKEND_LOG"
echo -e "   Frontend:  tail -f $FRONTEND_LOG"
echo ""
echo -e "${CYAN}🛑 To stop:${NC}"
echo -e "   Press ${YELLOW}Ctrl+C${NC} to stop all services"
echo ""
echo -e "${YELLOW}Monitoring services... (Press Ctrl+C to stop)${NC}"
echo ""

# Keep script running and monitor processes
while true; do
    # Check if backend is still running
    if ! ps -p $BACKEND_PID > /dev/null 2>&1; then
        print_error "Backend process died unexpectedly!"
        print_status "Last backend log entries:"
        tail -20 "$BACKEND_LOG"
        exit 1
    fi
    
    # Check if frontend is still running
    if ! ps -p $FRONTEND_PID > /dev/null 2>&1; then
        print_error "Frontend process died unexpectedly!"
        print_status "Last frontend log entries:"
        tail -20 "$FRONTEND_LOG"
        exit 1
    fi
    
    sleep 5
done
