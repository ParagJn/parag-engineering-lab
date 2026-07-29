#!/bin/bash
# Test script for the LLM API

echo "Testing LLM API Endpoints"
echo "========================="
echo ""

BASE_URL="http://localhost:8000"

# Test 1: Health Check
echo "1. Health Check"
echo "   GET $BASE_URL/health"
curl -s "$BASE_URL/health" | python3 -m json.tool
echo ""
echo ""

# Test 2: List Models
echo "2. List Available Models"
echo "   GET $BASE_URL/models"
curl -s "$BASE_URL/models" | python3 -m json.tool
echo ""
echo ""

# Test 3: Get Default Model
echo "3. Get Default Model"
echo "   GET $BASE_URL/models/default"
curl -s "$BASE_URL/models/default" | python3 -m json.tool
echo ""
echo ""

# Test 4: Generate Text (using defaults)
echo "4. Generate Text with Defaults"
echo "   POST $BASE_URL/generate"
curl -s -X POST "$BASE_URL/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is the capital of France? Answer in one word."
  }' | python3 -m json.tool
echo ""
echo ""

# Test 5: Generate Text (with max_tokens)
echo "5. Generate Text with Max Tokens"
echo "   POST $BASE_URL/generate"
curl -s -X POST "$BASE_URL/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain artificial intelligence in 2 sentences.",
    "max_tokens": 1000
  }' | python3 -m json.tool
echo ""
echo ""

# Test 6: Task Analysis
echo "6. Analyze a Task"
echo "   POST $BASE_URL/analyze/task"
curl -s -X POST "$BASE_URL/analyze/task" \
  -H "Content-Type: application/json" \
  -d '{
    "task_description": "Implement user authentication with OAuth 2.0",
    "context": {
      "project_type": "web_app",
      "tech_stack": "React, FastAPI"
    }
  }' | python3 -m json.tool
echo ""
echo ""

echo "All tests completed!"
