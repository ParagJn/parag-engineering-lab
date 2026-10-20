#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_ENV="/Users/paragjain/dev-works/myenv"

echo "Starting Strategy Analyzer backend on http://localhost:8050"
cd "$ROOT_DIR/backend"
if [ ! -x "$PYTHON_ENV/bin/python" ]; then
  echo "Python environment not found at $PYTHON_ENV"
  exit 1
fi
"$PYTHON_ENV/bin/pip" install -r requirements.txt
"$PYTHON_ENV/bin/uvicorn" app.main:app --reload --port 8050 &
BACKEND_PID=$!

echo "Starting Strategy Analyzer frontend on http://localhost:5220"
cd "$ROOT_DIR/frontend"
npm install
npm run dev -- --port 5220 --strictPort &
FRONTEND_PID=$!

trap 'kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true' EXIT
wait
