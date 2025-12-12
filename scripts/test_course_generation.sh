#!/bin/bash
# Test script for course generation workflow
# Tests the event-driven course generation via API Gateway

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get API Gateway URL from Terraform output
API_URL=$(cd terraform/environments/dev && terraform output -raw course_request_endpoint 2>/dev/null || echo "")

if [ -z "$API_URL" ]; then
    echo -e "${RED}Error: Could not get API Gateway URL from Terraform${NC}"
    echo "Make sure Terraform is initialized and the infrastructure is deployed."
    exit 1
fi

echo -e "${GREEN}Testing Course Generation Workflow${NC}"
echo "API Endpoint: $API_URL"
echo ""

# Test payload
PAYLOAD='{
  "query": "Learn DCF valuation and financial modeling",
  "hours": 2.0,
  "preferences": {
    "depth": "balanced",
    "presentation_style": "conversational",
    "pace": "moderate"
  }
}'

echo -e "${YELLOW}Sending course generation request...${NC}"
echo "Payload:"
echo "$PAYLOAD" | jq '.'
echo ""

# Send request
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")

# Extract HTTP status code (last line)
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
# Extract response body (all but last line)
BODY=$(echo "$RESPONSE" | sed '$d')

echo -e "${YELLOW}Response:${NC}"
echo "HTTP Status: $HTTP_CODE"
echo "Body:"
echo "$BODY" | jq '.' 2>/dev/null || echo "$BODY"
echo ""

# Check if request was successful
if [ "$HTTP_CODE" -eq 200 ]; then
    echo -e "${GREEN}✓ Request successful${NC}"
    
    # Extract course_id from response
    COURSE_ID=$(echo "$BODY" | jq -r '.course_id' 2>/dev/null || echo "")
    
    if [ -n "$COURSE_ID" ] && [ "$COURSE_ID" != "null" ]; then
        echo -e "${GREEN}✓ Course ID received: $COURSE_ID${NC}"
        echo ""
        echo -e "${YELLOW}Next steps:${NC}"
        echo "1. Check CloudWatch logs for each Lambda function:"
        echo "   - course-request-handler"
        echo "   - course-embedding-handler"
        echo "   - course-book-search-handler"
        echo "   - course-parts-handler"
        echo "   - course-sections-handler"
        echo "   - course-outline-reviewer"
        echo "   - course-storage-handler"
        echo ""
        echo "2. Check EventBridge events in AWS Console"
        echo "3. Check DynamoDB table: docprof-dev-course-state"
        echo "   Key: course_id = $COURSE_ID"
        echo ""
        echo "4. Monitor the workflow progress via CloudWatch logs"
    else
        echo -e "${RED}✗ No course_id in response${NC}"
    fi
else
    echo -e "${RED}✗ Request failed with status $HTTP_CODE${NC}"
    echo "Check CloudWatch logs for course-request-handler Lambda function"
    exit 1
fi
