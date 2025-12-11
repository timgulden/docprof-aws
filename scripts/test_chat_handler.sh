#!/bin/bash
# Test chat_handler Lambda function
# Tests that logic imports work correctly in Lambda runtime

set -e

FUNCTION_NAME="${1:-docprof-dev-chat-handler}"

echo "=========================================="
echo "Testing Chat Handler Lambda"
echo "Function: $FUNCTION_NAME"
echo "=========================================="
echo ""

# Test payload - minimal chat message
PAYLOAD='{
  "body": "{\"message\": \"Hello, test message\", \"session_id\": \"test-session-123\"}",
  "httpMethod": "POST",
  "path": "/chat",
  "headers": {
    "Content-Type": "application/json"
  }
}'

echo "Invoking Lambda function..."
echo "Payload: $PAYLOAD"
echo ""

# Invoke Lambda and capture response
RESPONSE=$(aws lambda invoke \
  --function-name "$FUNCTION_NAME" \
  --payload "$PAYLOAD" \
  --cli-binary-format raw-in-base64-out \
  /tmp/lambda-response.json 2>&1)

# Check if invocation succeeded
if [ $? -eq 0 ]; then
  echo "✓ Lambda invocation succeeded"
  echo ""
  echo "Response:"
  cat /tmp/lambda-response.json | python3 -m json.tool
  echo ""
  
  # Check for import errors in response
  if grep -q "ImportError\|ModuleNotFoundError\|shared.logic\|shared.core" /tmp/lambda-response.json; then
    echo "❌ ERROR: Import errors detected in response!"
    exit 1
  else
    echo "✓ No import errors detected"
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
  --filter-pattern "ERROR ImportError ModuleNotFoundError" \
  --query 'events[*].message' \
  --output text > /tmp/lambda-errors.txt 2>&1 || true

if [ -s /tmp/lambda-errors.txt ]; then
  echo "❌ Errors found in logs:"
  cat /tmp/lambda-errors.txt
  exit 1
else
  echo "✓ No import errors in recent logs"
fi

echo ""
echo "=========================================="
echo "✅ Test completed successfully!"
echo "=========================================="
