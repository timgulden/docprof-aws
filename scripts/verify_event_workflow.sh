#!/bin/bash
# Verify event-driven workflow progression
# Checks CloudWatch logs and EventBridge events

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}=== Event-Driven Workflow Verification ===${NC}"
echo ""

# Step 1: Trigger a new course request
echo -e "${YELLOW}1. Triggering course request...${NC}"
cd /Users/tgulden/Documents/AI\ Projects/docprof-aws
aws lambda invoke \
  --function-name docprof-dev-course-request-handler \
  --payload '{"body": "{\"query\": \"Learn DCF valuation\", \"hours\": 2.0, \"preferences\": {\"depth\": \"balanced\", \"pace\": \"moderate\"}}", "httpMethod": "POST", "path": "/courses", "headers": {"Content-Type": "application/json"}}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/course-test-response.json > /dev/null 2>&1

if [ ! -f /tmp/course-test-response.json ]; then
    echo -e "${RED}✗ Failed to invoke Lambda${NC}"
    exit 1
fi

COURSE_ID=$(cat /tmp/course-test-response.json | python3 -c "import sys, json; data = json.load(sys.stdin); body = json.loads(data.get('body', '{}')); print(body.get('course_id', ''))" 2>/dev/null || echo "")

if [ -z "$COURSE_ID" ]; then
    echo -e "${RED}✗ Failed to get course_id${NC}"
    echo "Response:"
    cat /tmp/course-test-response.json | python3 -m json.tool 2>/dev/null || cat /tmp/course-test-response.json
    exit 1
fi

echo -e "${GREEN}✓ Course ID: $COURSE_ID${NC}"
echo ""

# Step 2: Wait for events to propagate
echo -e "${YELLOW}2. Waiting for EventBridge events to propagate...${NC}"
sleep 15
echo ""

# Step 3: Check course request handler logs
echo -e "${YELLOW}3. Checking course-request-handler logs...${NC}"
REQUEST_LOGS=$(aws logs tail /aws/lambda/docprof-dev-course-request-handler --since 1m --format short --region us-east-1 2>&1 | grep -E "Published event|ERROR|course_id.*$COURSE_ID" | tail -5)

if echo "$REQUEST_LOGS" | grep -q "Published event"; then
    echo -e "${GREEN}✓ Event published successfully${NC}"
elif echo "$REQUEST_LOGS" | grep -q "ERROR"; then
    echo -e "${RED}✗ Error publishing event:${NC}"
    echo "$REQUEST_LOGS" | grep "ERROR"
else
    echo -e "${YELLOW}⚠ No event publish logs found (may be INFO level)${NC}"
fi
echo ""

# Step 4: Check embedding handler logs
echo -e "${YELLOW}4. Checking course-embedding-handler logs...${NC}"
EMBEDDING_LOGS=$(aws logs tail /aws/lambda/docprof-dev-course-embedding-handler --since 2m --format short --region us-east-1 2>&1 | grep -E "START|END|ERROR|course_id|EmbeddingGenerated" | tail -10)

if echo "$EMBEDDING_LOGS" | grep -q "START"; then
    echo -e "${GREEN}✓ Embedding handler invoked${NC}"
    echo "$EMBEDDING_LOGS" | grep -E "START|END|ERROR" | head -5
elif echo "$EMBEDDING_LOGS" | grep -q "ERROR"; then
    echo -e "${RED}✗ Error in embedding handler:${NC}"
    echo "$EMBEDDING_LOGS" | grep "ERROR"
else
    echo -e "${YELLOW}⚠ Embedding handler not invoked yet (may need more time)${NC}"
fi
echo ""

# Step 5: Check book search handler logs
echo -e "${YELLOW}5. Checking course-book-search-handler logs...${NC}"
BOOK_SEARCH_LOGS=$(aws logs tail /aws/lambda/docprof-dev-course-book-search-handler --since 2m --format short --region us-east-1 2>&1 | grep -E "START|END|ERROR|BookSummariesFound" | tail -10)

if echo "$BOOK_SEARCH_LOGS" | grep -q "START"; then
    echo -e "${GREEN}✓ Book search handler invoked${NC}"
    echo "$BOOK_SEARCH_LOGS" | grep -E "START|END|ERROR" | head -5
else
    echo -e "${YELLOW}⚠ Book search handler not invoked yet${NC}"
fi
echo ""

# Step 6: Check EventBridge rule targets
echo -e "${YELLOW}6. Verifying EventBridge rule targets...${NC}"
RULES=$(aws events list-rules --event-bus-name docprof-dev-course-events --region us-east-1 2>&1 | jq -r '.Rules[] | select(.State == "ENABLED") | .Name')

for rule in $RULES; do
    TARGETS=$(aws events list-targets-by-rule --rule "$rule" --event-bus-name docprof-dev-course-events --region us-east-1 2>&1 | jq '.Targets | length')
    if [ "$TARGETS" -gt 0 ]; then
        echo -e "${GREEN}✓ $rule: $TARGETS target(s)${NC}"
    else
        echo -e "${RED}✗ $rule: No targets configured${NC}"
    fi
done
echo ""

# Step 7: Check DynamoDB state
echo -e "${YELLOW}7. Checking DynamoDB course state...${NC}"
STATE=$(aws dynamodb get-item --table-name docprof-dev-course-state --key "{\"course_id\": {\"S\": \"$COURSE_ID\"}}" --region us-east-1 2>&1)

if echo "$STATE" | grep -q "Item"; then
    echo -e "${GREEN}✓ Course state found in DynamoDB${NC}"
    PHASE=$(echo "$STATE" | jq -r '.Item.phase.S // "unknown"' 2>/dev/null || echo "unknown")
    echo "  Phase: $PHASE"
else
    echo -e "${YELLOW}⚠ Course state not found (may have expired or been deleted)${NC}"
fi
echo ""

echo -e "${YELLOW}=== Verification Complete ===${NC}"
echo ""
echo "Next steps:"
echo "1. Check CloudWatch logs for detailed execution traces"
echo "2. Monitor EventBridge events in AWS Console"
echo "3. Verify Lambda function invocations in CloudWatch Metrics"
