# Bedrock Quota Monitoring

## Overview

This document describes the monitoring and alerting system for AWS Bedrock quota limits. The system is designed to **immediately alert** when quota limits are hit, rather than silently falling back to alternative models.

## Architecture

### Fallback Strategy

**Current Configuration**: Fallback model is **disabled** by default. We expect to stay within quota limits during normal operation.

**Rationale**: 
- Quota limits should be sufficient for normal usage
- If we hit limits, we want to know immediately and request increases
- Silent fallback masks the problem and delays resolution

### Monitoring Components

1. **Custom CloudWatch Metrics**
   - `BedrockDailyTokenQuotaHits`: Published when "Too many tokens per day" error occurs
   - `BedrockThrottlingExceptions`: Published for all throttling events (rate limits + quota limits)

2. **CloudWatch Alarms**
   - **Daily Token Quota Alarm**: Triggers on ANY quota hit (threshold: 0)
   - **Throttling Rate Alarm**: Triggers if >10 throttling exceptions in 5 minutes
   - **Lambda Error Alarm**: Triggers if >5 errors in Bedrock-related Lambdas in 5 minutes

3. **SNS Notifications**
   - All alarms send notifications to `docprof-dev-alarms` SNS topic
   - Email subscription can be configured via `alarm_email` variable

## Setup

### Email Notifications

To receive email notifications when quota limits are hit:

1. Set the `alarm_email` variable in `terraform.tfvars`:
   ```hcl
   alarm_email = "your-email@example.com"
   ```

2. Apply Terraform:
   ```bash
   terraform apply
   ```

3. **Confirm email subscription**: AWS will send a confirmation email. You must click the confirmation link before alarms will be delivered.

### Manual SNS Subscription

Alternatively, subscribe to the SNS topic manually:

1. Go to AWS SNS Console
2. Find topic: `docprof-dev-alarms`
3. Click "Create subscription"
4. Choose "Email" protocol
5. Enter your email address
6. Confirm the subscription email

## How It Works

### Metric Publishing

When `bedrock_client.py` encounters a Bedrock error:

1. **Daily Token Quota Detection**:
   - Checks if error is `ThrottlingException` with "too many tokens per day" message
   - Publishes `BedrockDailyTokenQuotaHits` metric
   - Logs ERROR-level message with 🚨 emoji for visibility

2. **General Throttling**:
   - Publishes `BedrockThrottlingExceptions` metric for all throttling events
   - Includes dimensions: `ModelId`, `QuotaType` (daily_token_limit vs rate_limit)

### Alarm Triggers

- **Daily Token Quota Alarm**: 
  - Evaluates every 5 minutes
  - Triggers if ANY quota hit detected (threshold: 0)
  - **Action**: Sends SNS notification immediately

- **Throttling Rate Alarm**:
  - Evaluates every 5 minutes
  - Triggers if >10 throttling exceptions in 5 minutes
  - **Action**: SNS notification (may indicate need for quota increase)

- **Lambda Error Alarm**:
  - Monitors `chapter-summary-processor` Lambda
  - Triggers if >5 errors in 5 minutes
  - **Action**: SNS notification (may indicate Bedrock issues)

## Response Actions

When an alarm triggers:

1. **Check CloudWatch Logs**: Review recent Bedrock API calls
2. **Check Service Quotas**: Verify current quota usage
3. **Request Increase**: File AWS Support case for quota increase
4. **Temporary Workaround**: If needed, temporarily enable fallback model

## Viewing Metrics

### CloudWatch Console

1. Go to CloudWatch → Metrics → Custom Namespaces
2. Select `DocProf/Custom`
3. View:
   - `BedrockDailyTokenQuotaHits`
   - `BedrockThrottlingExceptions`

### CloudWatch Insights Query

To find quota hits in logs:

```sql
fields @timestamp, @message
| filter @message like /DAILY TOKEN QUOTA LIMIT HIT/
| sort @timestamp desc
```

## Re-enabling Fallback (If Needed)

If you need to temporarily enable fallback:

1. Edit `terraform/environments/dev/main.tf`
2. Uncomment `LLM_FALLBACK_MODEL_ID` in:
   - `chapter_summary_processor_lambda`
   - `source_summary_generator_lambda`
   - `section_lecture_handler_lambda`
3. Apply Terraform:
   ```bash
   terraform apply -target=module.chapter_summary_processor_lambda \
                   -target=module.source_summary_generator_lambda \
                   -target=module.section_lecture_handler_lambda
   ```

**Note**: Fallback should only be used temporarily while waiting for quota increase approval.

## Cost

- **CloudWatch Metrics**: First 10 custom metrics free, then $0.30/metric/month
- **CloudWatch Alarms**: $0.10/alarm/month
- **SNS**: First 1M requests/month free, then $0.50/1M requests

**Estimated cost**: <$1/month for monitoring setup

## Troubleshooting

### Alarms Not Triggering

1. Check metric is being published:
   - CloudWatch → Metrics → DocProf/Custom
   - Verify metrics appear when quota hit occurs

2. Check alarm configuration:
   - CloudWatch → Alarms
   - Verify alarm state and threshold

3. Check SNS subscription:
   - SNS → Topics → `docprof-dev-alarms`
   - Verify subscription is confirmed

### Metrics Not Publishing

1. Check IAM permissions:
   - Lambda execution role needs `cloudwatch:PutMetricData`
   - Verify policy is attached

2. Check Lambda logs:
   - Look for "Failed to publish quota metric" warnings
   - Verify CloudWatch client initialization

## References

- [AWS Service Quotas](https://console.aws.amazon.com/servicequotas/)
- [CloudWatch Custom Metrics](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/publishingMetrics.html)
- [SNS Email Subscriptions](https://docs.aws.amazon.com/sns/latest/dg/sns-email-notifications.html)
