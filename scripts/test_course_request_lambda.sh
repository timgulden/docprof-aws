#!/bin/bash
# Test course_request_handler Lambda function directly

set -e

FUNCTION_NAME="${1:-docprof-dev-course-request-handler}"

echo "=========================================="
echo "Testing Course Request Handler Lambda"
echo "Function: $FUNCTION_NAME"
echo "=========================================="
echo ""

# Test payload - API Gateway event format
PAYLOAD='{
  "body": "{\"query\": \"Learn DCF valuation\", \"hours\": 2.0, \"preferences\": {\"depth\": \"balanced\", \"pace\": \"moderate\"}}",
  "httpMethod": "POST",
  "path": "/courses",
  "headers": {
    "Content-Type": "application/json"
  }
}'

echo "Invoking Lambda function..."
echo ""

# Invoke Lambda and capture response
RESPONSE=$(aws lambda invoke \
  --function-name "$FUNCTION_NAME" \
  --payload "$PAYLOAD" \
  --cli-binary-format raw-in-base64-out \
  /tmp/course-lambda-response.json 2>&1)

# Check if invocation succeeded
if [ $? -eq 0 ]; then
  echo "✓ Lambda invocation succeeded"
  echo ""
  echo "Response:"
  cat /tmp/course-lambda-response.json | python3 -m json.tool
  echo ""
  
  # Check for errors in response
  if grep -q "error\|Error\|ERROR" /tmp/course-lambda-response.json; then
    echo "⚠ WARNING: Errors detected in response!"
    grep -i "error" /tmp/course-lambda-response.json
  else
    echo "✓ No errors detected in response"
  fi
  
  # Extract course_id if present
  COURSE_ID=$(cat /tmp/course-lambda-response.json | python3 -c "import sys, json; print(json.load(sys.stdin).get('body', '{}').get('course_id', '') if 'body' in json.load(sys.stdin) else json.load(sys.stdin).get('course_id', ''))" 2>/dev/null || echo "")
  if [ -n "$COURSE_ID" ] && [ "$COURSE_ID" != "null" ] && [ "$COURSE_ID" != "" ]; then
    echo "✓ Course ID: $COURSE_ID"
  fi
else
  echo "❌ Lambda invocation failed"
  echo "$RESPONSE"
  exit 1
fi

echo ""
echo "Checking CloudWatch logs for errors..."
echo ""

# Get recent logs (last 5 minutes)
LOG_GROUP="/aws/lambda/$FUNCTION_NAME"
END_TIME=$(date +%s)000
START_TIME=$((END_TIME - 300000))  # 5 minutes ago

aws logs filter-log-events \
  --log-group-name "$LOG_GROUP" \
  --start-time "$START_TIME" \
  --end-time "$END_TIME" \
  --filter-pattern "ERROR Exception Traceback" \
  --query 'events[*].message' \
  --output text > /tmp/course-lambda-errors.txt 2>&1 || true

if [ -s /tmp/course-lambda-errors.txt ]; then
  echo "⚠ Errors found in logs:"
  cat /tmp/course-lambda-errors.txt | head -20
else
  echo "✓ No errors in recent logs"
fi

echo ""
echo "=========================================="
echo "✅ Test completed!"
echo "=========================================="
