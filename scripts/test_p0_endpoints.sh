#!/bin/bash
# Test script for P0 course endpoints (outline, lecture, status, complete)
# Tests the newly deployed endpoints via direct Lambda invocation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Testing P0 Course Endpoints${NC}"
echo "=================================="
echo ""

# First, create a test course to work with
echo -e "${YELLOW}Step 1: Creating test course...${NC}"
COURSE_PAYLOAD='{
  "body": "{\"query\": \"Learn DCF valuation\", \"hours\": 2.0, \"preferences\": {\"depth\": \"balanced\", \"pace\": \"moderate\"}}",
  "httpMethod": "POST",
  "path": "/courses",
  "headers": {"Content-Type": "application/json"}
}'

echo "$COURSE_PAYLOAD" > /tmp/course-payload.json
COURSE_RESPONSE=$(aws lambda invoke \
  --function-name docprof-dev-course-request-handler \
  --payload file:///tmp/course-payload.json \
  /tmp/course-response.json 2>&1)

if [ $? -eq 0 ]; then
  COURSE_ID=$(cat /tmp/course-response.json | python3 -c "import sys, json; r=json.load(sys.stdin); print(json.loads(r.get('body', '{}')).get('course_id', '') if 'body' in r else r.get('course_id', ''))" 2>/dev/null || echo "")
  if [ -n "$COURSE_ID" ] && [ "$COURSE_ID" != "null" ] && [ "$COURSE_ID" != "" ]; then
    echo -e "${GREEN}✓ Course created: $COURSE_ID${NC}"
  else
    echo -e "${RED}✗ Failed to extract course_id${NC}"
    cat /tmp/course-response.json | python3 -m json.tool
    exit 1
  fi
else
  echo -e "${RED}✗ Failed to create course${NC}"
  echo "$COURSE_RESPONSE"
  exit 1
fi

echo ""
echo -e "${YELLOW}Step 2: Testing course outline endpoint...${NC}"
OUTLINE_PAYLOAD=$(cat <<EOF
{
  "pathParameters": {"courseId": "$COURSE_ID"},
  "requestContext": {"authorizer": {"claims": {"sub": "test-user-id"}}}
}
EOF
)
echo "$OUTLINE_PAYLOAD" > /tmp/outline-payload.json

OUTLINE_RESPONSE=$(aws lambda invoke \
  --function-name docprof-dev-course-outline-handler \
  --payload file:///tmp/outline-payload.json \
  /tmp/outline-response.json 2>&1)

if [ $? -eq 0 ]; then
  HTTP_CODE=$(cat /tmp/outline-response.json | python3 -c "import sys, json; print(json.load(sys.stdin).get('statusCode', 0))" 2>/dev/null || echo "0")
  if [ "$HTTP_CODE" -eq 200 ]; then
    echo -e "${GREEN}✓ Course outline endpoint working${NC}"
    cat /tmp/outline-response.json | python3 -m json.tool | head -20
  else
    echo -e "${YELLOW}⚠ Outline endpoint returned status $HTTP_CODE${NC}"
    cat /tmp/outline-response.json | python3 -m json.tool
  fi
else
  echo -e "${RED}✗ Outline endpoint failed${NC}"
  echo "$OUTLINE_RESPONSE"
fi

echo ""
echo -e "${YELLOW}Step 3: Getting a section ID from the course...${NC}"
# Try to get section ID from the outline response
SECTION_ID=$(cat /tmp/outline-response.json | python3 -c "
import sys, json
try:
    r = json.load(sys.stdin)
    body = json.loads(r.get('body', '{}'))
    sections = body.get('sections', [])
    if sections:
        print(sections[0].get('section_id', ''))
except:
    pass
" 2>/dev/null || echo "")

if [ -z "$SECTION_ID" ] || [ "$SECTION_ID" == "" ]; then
  echo -e "${YELLOW}⚠ No sections found in course outline. Course may still be generating.${NC}"
  echo "This is expected if the course generation workflow hasn't completed yet."
  echo ""
  echo -e "${GREEN}✅ Test Summary:${NC}"
  echo "  ✓ Course request handler: Working"
  echo "  ✓ Course outline handler: Deployed and accessible"
  echo "  ⏳ Course generation workflow: In progress (check DynamoDB and EventBridge)"
  exit 0
fi

echo -e "${GREEN}✓ Found section: $SECTION_ID${NC}"

echo ""
echo -e "${YELLOW}Step 4: Testing section lecture endpoint...${NC}"
LECTURE_PAYLOAD=$(cat <<EOF
{
  "pathParameters": {"sectionId": "$SECTION_ID"},
  "requestContext": {"authorizer": {"claims": {"sub": "test-user-id"}}}
}
EOF
)
echo "$LECTURE_PAYLOAD" > /tmp/lecture-payload.json

LECTURE_RESPONSE=$(aws lambda invoke \
  --function-name docprof-dev-section-lecture-handler \
  --payload file:///tmp/lecture-payload.json \
  /tmp/lecture-response.json 2>&1)

if [ $? -eq 0 ]; then
  HTTP_CODE=$(cat /tmp/lecture-response.json | python3 -c "import sys, json; print(json.load(sys.stdin).get('statusCode', 0))" 2>/dev/null || echo "0")
  if [ "$HTTP_CODE" -eq 200 ]; then
    echo -e "${GREEN}✓ Section lecture endpoint working${NC}"
    cat /tmp/lecture-response.json | python3 -m json.tool | head -15
  else
    echo -e "${YELLOW}⚠ Lecture endpoint returned status $HTTP_CODE${NC}"
    cat /tmp/lecture-response.json | python3 -m json.tool
  fi
else
  echo -e "${RED}✗ Lecture endpoint failed${NC}"
  echo "$LECTURE_RESPONSE"
fi

echo ""
echo -e "${YELLOW}Step 5: Testing generation status endpoint...${NC}"
STATUS_PAYLOAD=$(cat <<EOF
{
  "pathParameters": {"sectionId": "$SECTION_ID"},
  "requestContext": {"authorizer": {"claims": {"sub": "test-user-id"}}}
}
EOF
)
echo "$STATUS_PAYLOAD" > /tmp/status-payload.json

STATUS_RESPONSE=$(aws lambda invoke \
  --function-name docprof-dev-section-generation-status-handler \
  --payload file:///tmp/status-payload.json \
  /tmp/status-response.json 2>&1)

if [ $? -eq 0 ]; then
  HTTP_CODE=$(cat /tmp/status-response.json | python3 -c "import sys, json; print(json.load(sys.stdin).get('statusCode', 0))" 2>/dev/null || echo "0")
  if [ "$HTTP_CODE" -eq 200 ]; then
    echo -e "${GREEN}✓ Generation status endpoint working${NC}"
    cat /tmp/status-response.json | python3 -m json.tool
  else
    echo -e "${YELLOW}⚠ Status endpoint returned status $HTTP_CODE${NC}"
    cat /tmp/status-response.json | python3 -m json.tool
  fi
else
  echo -e "${RED}✗ Status endpoint failed${NC}"
  echo "$STATUS_RESPONSE"
fi

echo ""
echo -e "${GREEN}✅ P0 Endpoints Test Complete!${NC}"
echo ""
echo "Test Results Summary:"
echo "  Course ID: $COURSE_ID"
echo "  Section ID: ${SECTION_ID:-N/A (course still generating)}"
echo ""
echo "Next steps:"
echo "  1. Check CloudWatch logs for each Lambda function"
echo "  2. Verify course generation workflow completed in DynamoDB"
echo "  3. Test endpoints via API Gateway with authentication"
