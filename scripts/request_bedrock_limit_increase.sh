#!/bin/bash
# Request Bedrock rate limit increase for Claude Sonnet
# NOTE: Bedrock quotas are NOT adjustable via API - this script provides instructions

set -e

echo "📈 Bedrock Rate Limit Increase Request"
echo ""
echo "⚠️  IMPORTANT: Bedrock rate limits cannot be increased via API."
echo "   They require submitting a support case through AWS Support."
echo ""
echo "Current limits (for Claude 3.5 Sonnet, likely applies to Sonnet 4.5):"
echo "  - Requests per minute: 3"
echo "  - Tokens per minute: 400,000"
echo ""
echo "Recommended limits:"
echo "  - Requests per minute: 100"
echo "  - Tokens per minute: 1,000,000"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 HOW TO REQUEST INCREASE:"
echo ""
echo "Option 1: AWS Console (Easiest)"
echo "  1. Go to: https://console.aws.amazon.com/support/home"
echo "  2. Click 'Create case'"
echo "  3. Select: Service limit increase → Amazon Bedrock"
echo "  4. Copy/paste the use case description from:"
echo "     docs/troubleshooting/Request_Bedrock_Limit_Increase.md"
echo ""
echo "Option 2: Try AWS Support API (may not be enabled)"
echo ""

export AWS_PROFILE=${AWS_PROFILE:-docprof-dev}
export AWS_REGION=${AWS_REGION:-us-east-1}

# Try to create support case via API (will fail if Support API not enabled)
echo "Attempting to create support case via API..."
echo ""

SUPPORT_BODY="I need to increase rate limits for Claude Sonnet 4.5 (via inference profile) to support occasional bursts during document processing and lecture generation.

Current limits:
- Requests per minute: 3 (too low for document processing)
- Tokens per minute: 400,000

Requested limits:
- Requests per minute: 100
- Tokens per minute: 1,000,000

Use case: Educational document processing platform that occasionally needs to process multiple books and generate lectures. Usage is bursty (occasional high usage followed by idle periods), not sustained high throughput.

Account: 176520790264
Region: us-east-1
Model: Claude Sonnet 4.5 (via inference profile: us.anthropic.claude-sonnet-4-5-20250929-v1:0)
Quota codes (for reference):
- Requests: L-254CACF4 (On-demand model inference requests per minute for Anthropic Claude 3.5 Sonnet)
- Tokens: L-A50569E5 (On-demand model inference tokens per minute for Anthropic Claude 3.5 Sonnet)"

if aws support create-case \
  --service-code bedrock \
  --category-code limit-increase \
  --severity-code normal \
  --subject "Request Bedrock Rate Limit Increase for Claude Sonnet 4.5" \
  --communication-body "$SUPPORT_BODY" \
  --region $AWS_REGION \
  --output json 2>&1; then
  echo ""
  echo "✅ Support case created successfully via API!"
  echo ""
  echo "💡 You'll receive email updates on the case status."
  echo "   Response time: Usually 24-48 hours (often faster)"
else
  echo ""
  echo "⚠️  API method failed (Support API likely not enabled on this account)"
  echo ""
  echo "📝 Please use AWS Console method instead:"
  echo "   1. Go to: https://console.aws.amazon.com/support/home"
  echo "   2. Click 'Create case' → Service limit increase → Amazon Bedrock"
  echo "   3. Use the use case description from:"
  echo "      docs/troubleshooting/Request_Bedrock_Limit_Increase.md"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 While waiting for approval:"
echo "   - Retry logic with exponential backoff will handle throttling gracefully"
echo "   - System will still work, just slower during bursts"
echo "   - No code changes needed after approval"
echo ""
echo "💰 Cost impact: ZERO additional cost (still pay per token)"

