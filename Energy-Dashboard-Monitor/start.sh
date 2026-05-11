#!/bin/bash

# Configuration
# Override VENV_PATH by setting it in your environment before running this script:
#   export VENV_PATH=/path/to/your/venv
VENV_PATH="${VENV_PATH:-/Users/paragjain/ibm-git-repositories/myenv}"
BACKEND_DIR="backend"
FRONTEND_DIR="frontend"

echo "=========================================="
echo " Starting Energy Dashboard Monitor"
echo "=========================================="

# 1. Verify Virtual Environment
echo "-> Checking Python virtual environment..."
if [ ! -d "$VENV_PATH" ]; then
  echo "Error: Virtual environment not found at $VENV_PATH"
  echo "Please create it or update the VENV_PATH in this script."
  exit 1
fi

source "$VENV_PATH/bin/activate"

# 2. Verify and install Backend Dependencies
echo "-> Verifying backend dependencies..."
cd "$BACKEND_DIR" || exit
# This will quickly check/install missing dependencies
"$VENV_PATH/bin/python" -m pip install -r requirements.txt

# Check if mock data exists, if not, generate it
if [ ! -f "../data/raw/smart_meter_data.json" ]; then
  echo "-> Mock data not found. Generating initial data files..."
  "$VENV_PATH/bin/python" generate_mock_data.py
fi
cd ..

# 3. Build Frontend
echo "-> Building frontend UI..."
cd "$FRONTEND_DIR" || exit
if [ ! -d "node_modules" ]; then
  echo "Installing frontend dependencies..."
  npm install
fi
npm run build
cd ..

# 4. Start Backend Server
echo "-> Starting FastAPI Backend..."
cd "$BACKEND_DIR" || exit
# Run backend in background
"$VENV_PATH/bin/python" -m uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# 5. Start Frontend Preview Server
echo "-> Starting React Frontend Preview..."
cd "$FRONTEND_DIR" || exit
# Run frontend preview in background
npm run preview &
FRONTEND_PID=$!
cd ..

echo "=========================================="
echo " All services started successfully!"
echo " Backend:  http://localhost:8000/docs"
echo " Frontend: http://localhost:4173"
echo " Press [CTRL+C] to stop all services."
echo "=========================================="

# Cleanup trap to kill background processes on exit
trap "echo -e '\nStopping services...'; kill $BACKEND_PID $FRONTEND_PID; exit" INT TERM

# Wait indefinitely for processes to run
wait
