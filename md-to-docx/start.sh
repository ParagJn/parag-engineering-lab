#!/bin/bash
# MD → DOCX Converter – startup script
# - Updates all npm dependencies (within package.json ranges) on every start
# - Frees the dev port and launches the Vite dev server
#
# Usage:
#   ./start.sh            update deps (minor/patch) and start
#   ./start.sh --latest   also bump to the latest MAJOR versions (may need code changes)
#   ./start.sh --no-update  skip updating (e.g. when offline)

set -e

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
warn()    { echo -e "${YELLOW}[!]${NC} $1"; }
fail()    { echo -e "${RED}[✗]${NC} $1"; exit 1; }

PORT=5173
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="update"
case "$1" in
  --latest)    MODE="latest" ;;
  --no-update) MODE="skip" ;;
  "")          ;;
  *)           fail "Unknown option: $1 (use --latest or --no-update)" ;;
esac

cd "$PROJECT_ROOT"
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo -e "${BLUE}   MD → DOCX Converter${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}"

# --- Prerequisites ----------------------------------------------------------
command -v node >/dev/null 2>&1 || fail "Node.js is not installed (https://nodejs.org)"
command -v npm  >/dev/null 2>&1 || fail "npm is not installed"
NODE_MAJOR=$(node -p 'process.versions.node.split(".")[0]')
[ "$NODE_MAJOR" -ge 20 ] || fail "Node.js 20+ required (found $(node -v))"
success "Node $(node -v), npm $(npm -v)"

# --- Dependencies -----------------------------------------------------------
if [ "$MODE" = "latest" ]; then
  info "Bumping all dependencies to their latest versions..."
  npx --yes npm-check-updates -u || fail "npm-check-updates failed"
fi

info "Installing dependencies..."
npm install --no-fund --no-audit || fail "npm install failed"

if [ "$MODE" != "skip" ]; then
  info "Updating dependencies..."
  if npm update --no-fund --no-audit; then
    success "Dependencies up to date"
  else
    warn "Update failed (offline?) – continuing with installed versions"
  fi
  if [ "$MODE" = "update" ]; then
    OUTDATED=$(npm outdated 2>/dev/null || true)
    if [ -n "$OUTDATED" ]; then
      warn "Newer major versions are available (run ./start.sh --latest to upgrade):"
      echo "$OUTDATED"
    fi
  fi
fi

# --- Port -------------------------------------------------------------------
if lsof -ti:"$PORT" >/dev/null 2>&1; then
  warn "Port $PORT is in use – stopping the existing process"
  lsof -ti:"$PORT" | xargs kill -9 2>/dev/null || true
  sleep 1
fi

# --- Start ------------------------------------------------------------------
success "Starting app at http://localhost:$PORT (Ctrl+C to stop)"
exec npm run dev -- --open
