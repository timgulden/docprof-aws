# How to Request Bedrock Rate Limit Increase

## Overview

Bedrock rate limits are **not adjustable via API** - they require submitting a support case through AWS Support.

## Current Limits

- **Requests per minute**: 3 (for Claude 3.5 Sonnet, likely applies to Sonnet 4.5)
- **Tokens per minute**: 400,000

## Requested Limits

- **Requests per minute**: 100 (reasonable for development/testing)
- **Tokens per minute**: 1,000,000 (supports lecture generation bursts)

## Option 1: AWS Console (Recommended - Easiest)

1. Go to **AWS Support Center**: https://console.aws.amazon.com/support/home
2. Click **"Create case"**
3. Select:
   - **Case type**: Service limit increase
   - **Service**: Amazon Bedrock
   - **Limit type**: On-demand model inference requests per minute
   - **Region**: US East (N. Virginia) / us-east-1
   - **Use case description**: Paste the text below
4. Submit the case

### Use Case Description (Copy/Paste):

```
I need to increase rate limits for Claude Sonnet 4.5 (via inference profile) to support occasional bursts during document processing and lecture generation.

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
- Tokens: L-A50569E5 (On-demand model inference tokens per minute for Anthropic Claude 3.5 Sonnet)

Note: These quotas are not adjustable via Service Quotas API, hence this support case.
```

### After Submitting

- **Response time**: Usually 24-48 hours (often faster)
- **Check status**: AWS Support Center → Your cases
- **You'll receive email updates** on the case status

## Option 2: AWS CLI (If Support API Enabled)

If your account has AWS Support API access enabled, you can create a case via CLI:

```bash
export AWS_PROFILE=docprof-dev

aws support create-case \
  --service-code bedrock \
  --category-code limit-increase \
  --severity-code normal \
  --subject "Request Bedrock Rate Limit Increase for Claude Sonnet 4.5" \
  --communication-body "I need to increase rate limits for Claude Sonnet 4.5 to support occasional bursts.

Current: 3 requests/min, 400K tokens/min
Requested: 100 requests/min, 1M tokens/min

Use case: Educational document processing platform with bursty usage patterns.
Account: 176520790264, Region: us-east-1" \
  --region us-east-1
```

**Note**: Most accounts don't have Support API enabled by default. If this fails, use Option 1 (Console).

## What Happens After Approval

1. AWS Support will approve/deny your request (usually approved for reasonable requests)
2. Limits will be increased automatically
3. No code changes needed - retry logic will handle remaining throttling gracefully
4. **No additional cost** - still pay per token, just higher ceilings

## Monitoring

After the increase, verify it worked:

```bash
aws service-quotas get-service-quota \
  --service-code bedrock \
  --quota-code L-A50569E5 \
  --region us-east-1 \
  --query 'Quota.Value'
```

## Cost Impact

✅ **Zero additional cost** - you still pay per token, just have higher rate limits

## Alternative: Use Retry Logic

While waiting for the limit increase, the retry logic with exponential backoff will handle throttling:
- Automatically retries on `ThrottlingException`
- Exponential backoff: 1s, 2s, 4s delays
- Gracefully handles temporary rate limit hits

This means your system will still work, just slower during bursts until the limit increase is approved.

