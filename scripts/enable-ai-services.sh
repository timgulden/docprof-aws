#!/bin/bash
# Enable AI services (Bedrock + Polly VPC endpoints)
# This will take ~3-5 minutes and cost ~$0.04/hour while running

set -e

echo "🚀 Enabling AI services (Bedrock + Polly VPC endpoints)..."
echo "This will take ~3-5 minutes and cost ~$0.04/hour while running."
echo ""

cd "$(dirname "$0")/../terraform/environments/dev"

# Set AWS profile and run terraform
export AWS_PROFILE=docprof-dev
terraform apply \
  -var="enable_ai_endpoints=true" \
  -auto-approve

echo ""
echo "✅ AI services are now ONLINE"
echo "💡 Remember to disable when done to save costs"
echo "   Run: ./scripts/disable-ai-services.sh"

