#!/bin/bash
# -----------------------------------------------------------
# Project Schedule Tool - Start Script
# Runs npm build first, then launches the dev server.
# -----------------------------------------------------------

echo "============================================"
echo "  Project Schedule Tool - Starting Up..."
echo "============================================"
echo ""

# ---- Pre-flight checks ----

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

echo "✔ Node.js $(node --version) detected"
echo "✔ npm $(npm --version) detected"
echo ""

# Ensure we're running from the project directory (package.json must exist)
if [ ! -f "package.json" ]; then
  echo "❌ ERROR: 'package.json' not found in the current directory."
  echo "   Please run this script from the Project-Schedule-Tool root folder:"
  echo "   cd /path/to/Project-Schedule-Tool && ./start.sh"
  exit 1
fi

# Check if node_modules exists, if not run npm install
if [ ! -d "node_modules" ]; then
  echo "📦 node_modules not found. Installing dependencies..."
  npm install
  if [ $? -ne 0 ]; then
    echo ""
    echo "❌ ERROR: 'npm install' failed."
    echo "   Please check your network connection and try again."
    exit 1
  fi
  echo "✅ Dependencies installed successfully!"
  echo ""
fi

# ---- Step 1: Build ----
echo "🔨 Step 1/2: Running npm build..."
npm run build
if [ $? -ne 0 ]; then
  echo ""
  echo "❌ ERROR: Build failed!"
  echo "   Please check the TypeScript/Vite errors above and fix them before retrying."
  exit 1
fi

echo ""
echo "✅ Build completed successfully!"
echo ""

# ---- Step 2: Start dev server ----
echo "🚀 Step 2/2: Starting dev server..."
npm run dev
DEV_EXIT_CODE=$?

if [ $DEV_EXIT_CODE -ne 0 ] && [ $DEV_EXIT_CODE -ne 130 ]; then
  # Exit code 130 = Ctrl+C (normal user termination), so we only report other failures
  echo ""
  echo "❌ ERROR: Dev server exited unexpectedly (exit code: $DEV_EXIT_CODE)."
  echo "   Check if port 5173 is already in use or if there is a config issue."
  exit $DEV_EXIT_CODE
fi

echo ""
echo "👋 Dev server stopped. Goodbye!"
