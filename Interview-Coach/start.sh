#!/usr/bin/env bash
# =============================================================================
# Interview Coach — Start Script
# Installs/verifies all dependencies and starts both servers.
# =============================================================================

set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
header()  { echo -e "\n${BOLD}$*${NC}"; }

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
SESSIONS_DIR="$SCRIPT_DIR/sessions"
VENV_PATH="/Users/paragjain/dev-works/myenv"

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║        Interview Coach — AI Platform     ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── Step 1: Sessions directory ────────────────────────────────────────────────
header "Step 1/5 — Session storage"
mkdir -p "$SESSIONS_DIR"
success "Sessions directory: $SESSIONS_DIR"

# ── Step 2: Python virtual environment ───────────────────────────────────────
header "Step 2/5 — Python virtual environment"
if [ ! -d "$VENV_PATH" ]; then
  warn "Virtual environment not found at $VENV_PATH"
  info "Creating virtual environment…"
  python3 -m venv "$VENV_PATH"
  success "Virtual environment created."
else
  success "Virtual environment found: $VENV_PATH"
fi

# Activate
# shellcheck disable=SC1090
source "$VENV_PATH/bin/activate"
success "Virtual environment activated (Python: $(python --version))"

# ── Step 3: Backend dependencies ─────────────────────────────────────────────
header "Step 3/5 — Backend dependencies"
cd "$BACKEND_DIR"

info "Checking/installing backend packages…"
pip install -r requirements.txt --upgrade -q
success "Backend dependencies up to date."

# Verify key packages
REQUIRED_PKGS=("fastapi" "uvicorn" "httpx" "aiofiles" "pydantic")
for pkg in "${REQUIRED_PKGS[@]}"; do
  if ! python -c "import ${pkg//-/_}" 2>/dev/null; then
    warn "$pkg not importable — reinstalling…"
    pip install "$pkg" -q
  fi
done
success "All backend packages verified."

# ── Step 4: Frontend dependencies ────────────────────────────────────────────
header "Step 4/5 — Frontend dependencies"

# Node.js check
if ! command -v node &>/dev/null; then
  error "Node.js not found. Install from https://nodejs.org"
  exit 1
fi
NODE_VER=$(node --version)
NPM_VER=$(npm --version)
success "Node.js $NODE_VER · npm $NPM_VER"

cd "$FRONTEND_DIR"
info "Installing frontend packages…"
npm install
success "Frontend dependencies installed."

# ── Step 5: Start servers ─────────────────────────────────────────────────────
header "Step 5/5 — Starting servers"

# Start backend
cd "$BACKEND_DIR"
info "Starting FastAPI backend on http://localhost:8000"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Wait for backend to be ready
TRIES=0
until curl -s http://localhost:8000/api/health > /dev/null 2>&1; do
  TRIES=$((TRIES + 1))
  if [ $TRIES -gt 20 ]; then
    error "Backend did not start in time."
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
  fi
  sleep 1
done
success "Backend is ready."

# Start frontend
cd "$FRONTEND_DIR"
info "Starting Vite frontend on http://localhost:5173"
npm run dev &
FRONTEND_PID=$!

# ── Ready ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║   Interview Coach is running!            ║${NC}"
echo -e "${BOLD}${GREEN}╠══════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  App:      http://localhost:5173          ║${NC}"
echo -e "${GREEN}║  Backend:  http://localhost:8000          ║${NC}"
echo -e "${GREEN}║  API Docs: http://localhost:8000/docs     ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all servers.${NC}"

# ── Cleanup on exit ───────────────────────────────────────────────────────────
cleanup() {
  echo ""
  info "Shutting down servers…"
  kill "$BACKEND_PID" 2>/dev/null || true
  kill "$FRONTEND_PID" 2>/dev/null || true
  success "All servers stopped."
}
trap cleanup EXIT INT TERM

wait "$BACKEND_PID" "$FRONTEND_PID"
