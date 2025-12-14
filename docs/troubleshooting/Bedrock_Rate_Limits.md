# AWS Bedrock Rate Limits - Troubleshooting Guide

## Overview

AWS Bedrock has default service quotas (rate limits) to ensure fair resource distribution. If you encounter `ThrottlingException` errors, it means you're hitting these rate limits.

**Important:** Throttling is about **rate limits** (requests per second/minute), not cost. You can request limit increases from AWS Support.

## Default Limits

AWS Bedrock imposes default quotas that vary by model. For Claude models (including Claude Sonnet 4.5), typical default limits are:

- **Requests per minute**: Varies (often starts at 100-400 requests/minute)
- **Tokens per minute**: Varies (often starts at 300K-1M tokens/minute)

These limits are shared across your AWS account for the specific model.

## Current Configuration

We're using:
- **Model**: Claude Sonnet 4.5 (via inference profile)
- **Region**: us-east-1
- **Service Tier**: Standard (default)

## Checking Your Current Limits

You can check your current service quotas via AWS Console:

1. Go to **Service Quotas** in AWS Console
2. Search for "Bedrock"
3. Filter by:
   - Service: Amazon Bedrock
   - Region: us-east-1
   - Quota name: Look for "Claude" or "Sonnet" related quotas

Or via AWS CLI:

```bash
aws service-quotas list-service-quotas \
  --service-code bedrock \
  --region us-east-1 \
  --query "Quotas[?contains(QuotaName, 'Claude') || contains(QuotaName, 'Sonnet')]"
```

## Requesting Limit Increases

To request a limit increase:

1. **Via AWS Console**:
   - Go to **Service Quotas** → **AWS services** → **Amazon Bedrock**
   - Find the quota you want to increase (e.g., "Claude Sonnet requests per minute")
   - Click "Request quota increase"
   - Fill out the form (justify your need - e.g., "Document processing application")
   - Submit the request

2. **Via AWS CLI**:
   ```bash
   aws service-quotas request-service-quota-increase \
     --service-code bedrock \
     --quota-code <QUOTA_CODE> \
     --desired-value <NEW_VALUE> \
     --region us-east-1
   ```

3. **Via AWS Support**:
   - Open a support case
   - Request: "Increase Bedrock rate limits for Claude Sonnet 4.5"
   - Specify desired limits (e.g., "1000 requests/minute")

**Typical response time**: 24-48 hours (often faster for reasonable requests)

## Retry Logic

Our code includes automatic retry logic with exponential backoff:

- **Max retries**: 3 attempts
- **Backoff delays**: 1s, 2s, 4s
- **Automatic**: Handles transient throttling gracefully

This means if you hit a temporary rate limit, the system will automatically retry after a short delay.

## Service Tiers

AWS Bedrock offers different service tiers:

1. **Standard Tier** (default):
   - Standard pricing
   - Shared capacity pool
   - Default quotas apply

2. **Priority Tier** (premium):
   - Higher rate limits
   - Faster response times
   - Reserved capacity
   - Higher cost per request

3. **Flex Tier** (economy):
   - Lower cost
   - Lower priority processing
   - Potentially higher latency

**To use Priority Tier**, you need to:
- Request access via AWS Support
- Specify you want Priority Tier for your use case
- Higher cost but guaranteed higher throughput

## Immediate Solutions

If you're hitting throttling right now:

1. **Wait a minute**: Rate limits are per-minute, so waiting usually resolves it
2. **Check concurrent requests**: Are multiple functions calling Bedrock simultaneously?
3. **Reduce request frequency**: Add delays between requests if needed
4. **Request limit increase**: Contact AWS Support to raise your quotas

## Monitoring Throttling

Check CloudWatch Logs for throttling patterns:

```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/docprof-dev-book-upload \
  --filter-pattern "ThrottlingException" \
  --region us-east-1
```

## Best Practices

1. **Batch requests when possible**: Instead of multiple small requests, combine them
2. **Use appropriate timeouts**: Set reasonable Lambda timeouts
3. **Monitor usage**: Set up CloudWatch alarms for throttling
4. **Request appropriate limits**: Don't request unnecessarily high limits (costs more in Priority Tier)

## Cost Impact

- **Standard Tier**: Pay per token/request, default quotas
- **Priority Tier**: Higher cost per request (~2x standard), but higher limits
- **Limit increases (Standard)**: Usually no additional cost (just higher ceilings)

**Recommendation**: Start with a limit increase request on Standard Tier. Only move to Priority Tier if you need guaranteed throughput for production workloads.

