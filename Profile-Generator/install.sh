#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# Profile Generator — one-time dependency installer
# Usage:  bash install.sh
# ─────────────────────────────────────────────────────────
set -e

VENV="/Users/paragjain/dev-works/myenv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "════════════════════════════════════════════"
echo "  Profile Generator — Install Dependencies  "
echo "════════════════════════════════════════════"

# ── Python backend deps ──────────────────────────────────
echo ""
echo "▸ Installing Python backend dependencies…"
source "$VENV/bin/activate"
pip install -q -r "$SCRIPT_DIR/backend/requirements.txt"
echo "  ✓ Python packages installed"

# ── Frontend npm deps ────────────────────────────────────
echo ""
echo "▸ Installing frontend npm dependencies…"
cd "$SCRIPT_DIR/frontend"
npm install --silent
echo "  ✓ npm packages installed"

echo ""
echo "════════════════════════════════════════════"
echo "  Installation complete!"
echo ""
echo "  Next steps:"
echo "  1. Copy your .env file to: $SCRIPT_DIR/.env"
echo "     (or rename .env.example and add your keys)"
echo ""
echo "  2. Run the app:  bash start.sh"
echo "════════════════════════════════════════════"
echo ""
