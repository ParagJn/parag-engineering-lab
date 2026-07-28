#!/bin/bash
# -----------------------------------------------------------
# Project Schedule Tool - Start Script
# Runs npm build first, then launches the dev server.
# -----------------------------------------------------------

set -e

echo "============================================"
echo "  Project Schedule Tool - Starting Up..."
echo "============================================"
echo ""

# Step 1: Build
echo "🔨 Step 1/2: Running npm build..."
npm run build

echo ""
echo "✅ Build completed successfully!"
echo ""

# Step 2: Start dev server
echo "🚀 Step 2/2: Starting dev server..."
npm run dev
