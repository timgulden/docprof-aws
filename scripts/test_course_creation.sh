#!/bin/bash
# Test course creation endpoint directly (outside of UI)

set -e

cd "$(dirname "$0")/.."

# Get API Gateway URL
API_URL=$(cd terraform/environments/dev && terraform output -raw api_gateway_url 2>/dev/null || echo "")
if [ -z "$API_URL" ]; then
    echo "Error: Could not get API Gateway URL from Terraform"
    exit 1
fi

echo "API Gateway URL: $API_URL"
echo ""

# Check if user provided Cognito token
if [ -z "$COGNITO_TOKEN" ]; then
    echo "Usage: COGNITO_TOKEN=<your_token> $0"
    echo ""
    echo "To get a token, you can:"
    echo "  1. Use AWS CLI to get token from Cognito User Pool"
    echo "  2. Use the browser DevTools after logging in to copy the token"
    echo ""
    echo "Example with AWS CLI:"
    echo "  USERNAME=your-username"
    echo "  PASSWORD=your-password"
    echo "  POOL_ID=$(cd terraform/environments/dev && terraform output -raw cognito_user_pool_id)"
    echo "  CLIENT_ID=$(cd terraform/environments/dev && terraform output -raw cognito_user_pool_client_id)"
    echo "  COGNITO_TOKEN=\$(aws cognito-idp initiate-auth \\"
    echo "    --auth-flow USER_PASSWORD_AUTH \\"
    echo "    --client-id \$CLIENT_ID \\"
    echo "    --auth-parameters USERNAME=\$USERNAME,PASSWORD=\$PASSWORD \\"
    echo "    --query 'AuthenticationResult.IdToken' \\"
    echo "    --output text)"
    echo "  $0"
    exit 1
fi

# Test course creation
echo "Testing course creation..."
echo "Request payload:"
cat <<EOF
{
  "query": "Learn DCF valuation fundamentals",
  "time_hours": 2.0
}
EOF
echo ""
echo ""

RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $COGNITO_TOKEN" \
  -d '{
    "query": "Learn DCF valuation fundamentals",
    "time_hours": 2.0
  }' \
  "${API_URL}/courses")

# Extract HTTP status and body
HTTP_BODY=$(echo "$RESPONSE" | sed -e 's/HTTP_STATUS\:.*//g')
HTTP_STATUS=$(echo "$RESPONSE" | tr -d '\n' | sed -e 's/.*HTTP_STATUS://')

echo "HTTP Status: $HTTP_STATUS"
echo ""
echo "Response body:"
echo "$HTTP_BODY" | jq '.' 2>/dev/null || echo "$HTTP_BODY"
echo ""

if [ "$HTTP_STATUS" -eq 200 ] || [ "$HTTP_STATUS" -eq 201 ]; then
    echo "✅ Course creation successful!"
    COURSE_ID=$(echo "$HTTP_BODY" | jq -r '.courseId // .course_id // empty' 2>/dev/null)
    if [ -n "$COURSE_ID" ] && [ "$COURSE_ID" != "null" ]; then
        echo "Course ID: $COURSE_ID"
        echo ""
        echo "You can check the course status with:"
        echo "  curl -H \"Authorization: Bearer \$COGNITO_TOKEN\" \"$API_URL/dev/course-status/$COURSE_ID\" | jq"
    fi
else
    echo "❌ Course creation failed!"
    exit 1
fi
