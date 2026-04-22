#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# Profile Generator — start both backend and frontend
# Usage:  bash start.sh
# ─────────────────────────────────────────────────────────

VENV="/Users/paragjain/dev-works/myenv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check .env exists
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  echo "⚠  No .env found at $SCRIPT_DIR/.env"
  echo "   Copy .env.example and fill in your API keys, then re-run."
  exit 1
fi

# Cleanup on Ctrl+C
cleanup() {
  echo ""
  echo "Shutting down Profile Generator…"
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  exit 0
}
trap cleanup SIGINT SIGTERM

echo ""
echo "════════════════════════════════════════════"
echo "  Profile Generator — Starting              "
echo "════════════════════════════════════════════"

# ── Start FastAPI backend ────────────────────────────────
echo ""
echo "▸ Starting FastAPI backend on http://localhost:8000 …"
source "$VENV/bin/activate"
cd "$SCRIPT_DIR/backend"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Brief pause to let backend start
sleep 2

# ── Start Vite frontend ──────────────────────────────────
echo ""
echo "▸ Starting frontend on http://localhost:5173 …"
cd "$SCRIPT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "════════════════════════════════════════════"
echo "  ✓  App running!"
echo ""
echo "  Frontend : http://localhost:5173"
echo "  Backend  : http://localhost:8000"
echo "  API docs : http://localhost:8000/docs"
echo ""
echo "  Press Ctrl+C to stop both servers."
echo "════════════════════════════════════════════"
echo ""

wait
