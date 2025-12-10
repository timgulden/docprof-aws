#!/bin/bash
# Disable AI services (Bedrock + Polly VPC endpoints)
# This stops hourly charges for VPC endpoints

set -e

echo "🛑 Disabling AI services..."
echo ""

cd "$(dirname "$0")/../terraform/environments/dev"

# Set AWS profile and run terraform
export AWS_PROFILE=docprof-dev
terraform apply \
  -var="enable_ai_endpoints=false" \
  -auto-approve

echo ""
echo "✅ AI services are now OFFLINE"
echo "💰 No longer incurring hourly charges"

