#!/bin/bash
# Get Cognito ID token for API testing

set -e

cd "$(dirname "$0")/.."

# Get Cognito details from Terraform
cd terraform/environments/dev
POOL_ID=$(terraform output -raw cognito_user_pool_id 2>/dev/null || echo "")
CLIENT_ID=$(terraform output -raw cognito_user_pool_client_id 2>/dev/null || echo "")

if [ -z "$POOL_ID" ] || [ -z "$CLIENT_ID" ]; then
    echo "Error: Could not get Cognito details from Terraform"
    exit 1
fi

# Check if credentials provided
if [ -z "$USERNAME" ] || [ -z "$PASSWORD" ]; then
    echo "Usage: USERNAME=<email> PASSWORD=<password> $0"
    echo ""
    echo "Or export them first:"
    echo "  export USERNAME=your-email@example.com"
    echo "  export PASSWORD=your-password"
    echo "  $0"
    exit 1
fi

echo "Authenticating with Cognito..."
echo "User Pool ID: $POOL_ID"
echo "Client ID: $CLIENT_ID"
echo ""

# Get token
TOKEN=$(aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id "$CLIENT_ID" \
  --auth-parameters USERNAME="$USERNAME",PASSWORD="$PASSWORD" \
  --query 'AuthenticationResult.IdToken' \
  --output text 2>&1)

if [ $? -ne 0 ]; then
    echo "❌ Authentication failed!"
    echo "$TOKEN"
    exit 1
fi

echo "✅ Authentication successful!"
echo ""
echo "Token (export this to test course creation):"
echo "export COGNITO_TOKEN=\"$TOKEN\""
echo ""
echo "Or use it directly:"
echo "COGNITO_TOKEN=\"$TOKEN\" ./scripts/test_course_creation.sh"
