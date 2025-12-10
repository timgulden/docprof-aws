#!/bin/bash
# Check AI services status

set -e

cd "$(dirname "$0")/../terraform/environments/dev"

# Set AWS profile and check current state
export AWS_PROFILE=docprof-dev
ENABLED=$(terraform output -raw ai_endpoints_enabled 2>/dev/null || echo "unknown")

echo "Checking AI services status..."
echo ""

if [ "$ENABLED" = "true" ]; then
    echo "● AI Services: ONLINE"
    echo "💰 Costing ~\$0.04/hour"
    echo ""
    echo "To disable: ./scripts/disable-ai-services.sh"
elif [ "$ENABLED" = "false" ]; then
    echo "○ AI Services: OFFLINE"
    echo "💰 No hourly charges"
    echo ""
    echo "To enable: ./scripts/enable-ai-services.sh"
else
    echo "⚠️  Status: UNKNOWN (infrastructure may not be deployed)"
    echo ""
    echo "Deploy infrastructure first:"
    echo "  cd terraform/environments/dev"
    echo "  terraform apply"
fi

