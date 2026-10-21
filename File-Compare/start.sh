#!/bin/bash

# File Compare - Startup Script
# ==========================================
# - Uses the shared Python venv
# - Installs backend/frontend dependencies when missing
# - Starts the backend (FastAPI) on port 8060
# - Starts the frontend (Vite) on port 5240
# Ctrl+C stops both and releases the ports.

VENV_PATH="/Users/paragjain/dev-works/myenv"
BACKEND_PORT=8060
FRONTEND_PORT=5240
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
warn()    { echo -e "${YELLOW}[!]${NC} $1"; }
fail()    { echo -e "${RED}[✗]${NC} $1"; exit 1; }

BACKEND_PID=""
FRONTEND_PID=""

# Only processes LISTENING on the port, so a browser tab connected to it is never killed.
listener_pids() { lsof -tiTCP:"$1" -sTCP:LISTEN 2>/dev/null; }

free_port() {
  local port=$1 pids
  pids="$(listener_pids "$port")"
  if [ -n "$pids" ]; then
    warn "Port $port is in use - stopping the existing process"
    echo "$pids" | xargs kill -9 2>/dev/null || true
    sleep 1
    [ -n "$(listener_pids "$port")" ] && fail "Could not free port $port"
  fi
}

cleanup() {
  trap - EXIT INT TERM
  echo ""
  warn "Shutting down File Compare..."
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
  sleep 0.5
  for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
    leftover="$(listener_pids "$port")"
    [ -n "$leftover" ] && echo "$leftover" | xargs kill -9 2>/dev/null
  done
  success "Stopped"
  exit 0
}
trap cleanup EXIT INT TERM

echo -e "${CYAN}════════════════════════════════════════${NC}"
echo -e "${CYAN}   File Compare${NC}"
echo -e "${CYAN}════════════════════════════════════════${NC}"

# --- Prerequisites ----------------------------------------------------------
[ -x "$VENV_PATH/bin/python" ] || fail "Python venv not found at $VENV_PATH"
command -v node >/dev/null 2>&1 || fail "Node.js is not installed (https://nodejs.org)"
command -v npm  >/dev/null 2>&1 || fail "npm is not installed"
success "Python: $("$VENV_PATH/bin/python" --version 2>&1), Node $(node -v)"

if [ ! -f "$BACKEND_DIR/.env" ]; then
  warn "backend/.env not found - copy backend/.env.example and add your IBM ICA endpoint and key"
fi

# --- Dependencies -----------------------------------------------------------
if ! "$VENV_PATH/bin/python" -c "import fastapi, uvicorn, multipart, pypdf, docx, PIL, pydantic_settings" 2>/dev/null; then
  info "Installing backend dependencies..."
  "$VENV_PATH/bin/pip" install -r "$BACKEND_DIR/requirements.txt" || fail "pip install failed"
fi
success "Backend dependencies ready"

cd "$FRONTEND_DIR" || fail "frontend directory not found"
if [ ! -d node_modules ]; then
  info "Installing frontend dependencies..."
  npm install --no-fund --no-audit || fail "npm install failed"
fi
success "Frontend dependencies ready"

# --- Ports ------------------------------------------------------------------
free_port "$BACKEND_PORT"
free_port "$FRONTEND_PORT"

# --- Start ------------------------------------------------------------------
info "Starting backend on http://localhost:$BACKEND_PORT"
cd "$BACKEND_DIR" || fail "backend directory not found"
"$VENV_PATH/bin/uvicorn" app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" --reload &
BACKEND_PID=$!

info "Starting frontend on http://localhost:$FRONTEND_PORT"
cd "$FRONTEND_DIR" || fail "frontend directory not found"
# Started by the Lab Launcher (root start.sh sets LAB_LAUNCHER): don't pop a browser tab.
OPEN_FLAG="--open"
[ -n "$LAB_LAUNCHER" ] && OPEN_FLAG=""
npm run dev -- --port "$FRONTEND_PORT" --strictPort $OPEN_FLAG &
FRONTEND_PID=$!

echo ""
success "File Compare:  http://localhost:$FRONTEND_PORT   (API: http://localhost:$BACKEND_PORT/docs)"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

# Exit (and clean up) as soon as either service dies.
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 2
done
warn "A service exited unexpectedly"
