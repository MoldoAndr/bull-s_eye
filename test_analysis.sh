#!/bin/bash

# Test script for Bull's Eye analysis
# This will submit the lightweight AI-SAST repository for analysis

API_KEY="${API_KEY:-bullseye_secret_key_2025}"
API_URL="${API_URL:-http://localhost:8000}"
MODEL="${MODEL:-qwen2.5-coder:7b}"

echo "🎯 Bull's Eye Test Analysis"
echo "=============================="
echo "API URL: $API_URL"
echo "Model: $MODEL"
echo ""

# Submit analysis job
echo "📤 Submitting analysis job..."
RESPONSE=$(curl -s -X POST "$API_URL/api/jobs" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "repo_url": "https://github.com/MoldoAndr/AI-SAST.git",
    "branch": "main",
    "name": "Test Analysis - AI-SAST",
    "model": "'"$MODEL"'"
  }')

echo "Response: $RESPONSE"
echo ""

# Extract job ID
JOB_ID=$(echo $RESPONSE | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$JOB_ID" ]; then
  echo "❌ Failed to create job"
  exit 1
fi

echo "✅ Job created: $JOB_ID"
echo "🔗 View progress: http://localhost:3000/jobs/$JOB_ID"
echo ""

# Monitor job status
echo "📊 Monitoring job status..."
while true; do
  STATUS=$(curl -s "$API_URL/api/jobs/$JOB_ID" -H "X-API-Key: $API_KEY" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
  PROGRESS=$(curl -s "$API_URL/api/jobs/$JOB_ID" -H "X-API-Key: $API_KEY" | grep -o '"progress":[0-9]*' | cut -d':' -f2)
  MESSAGE=$(curl -s "$API_URL/api/jobs/$JOB_ID" -H "X-API-Key: $API_KEY" | grep -o '"status_message":"[^"]*"' | cut -d'"' -f4)
  
  echo "[$(date '+%H:%M:%S')] Status: $STATUS | Progress: $PROGRESS% | $MESSAGE"
  
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
  
  sleep 5
done

echo ""
if [ "$STATUS" = "completed" ]; then
  echo "✅ Analysis completed successfully!"
  echo "📊 View full report: http://localhost:3000/jobs/$JOB_ID"
  
  # Get findings summary
  echo ""
  echo "📈 Findings Summary:"
  curl -s "$API_URL/api/jobs/$JOB_ID/findings/summary" -H "X-API-Key: $API_KEY" | python3 -m json.tool
else
  echo "❌ Analysis failed"
  echo "View details: http://localhost:3000/jobs/$JOB_ID"
fi
