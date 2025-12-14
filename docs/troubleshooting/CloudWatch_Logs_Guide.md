# CloudWatch Logs Guide

## What is CloudWatch?

**AWS CloudWatch** is Amazon's monitoring and observability service. It automatically collects logs, metrics, and events from AWS services.

**CloudWatch Logs** is the logging component that stores log data from:
- Lambda functions
- EC2 instances
- Other AWS services
- Your applications

## How Lambda Logging Works

When your Lambda function runs:
1. Any `print()` statements or `logger.info()` calls are captured
2. Logs are automatically sent to CloudWatch Logs
3. Logs are organized by **Log Group** (one per Lambda function)
4. Each execution creates a **Log Stream**

**Log Group for document processor:**
```
/aws/lambda/docprof-dev-document-processor
```

---

## Method 1: AWS Console (Easiest - No Setup Required)

### Steps:

1. **Open AWS Console**
   - Go to https://console.aws.amazon.com
   - Sign in to your AWS account

2. **Navigate to CloudWatch**
   - Search for "CloudWatch" in the top search bar
   - Click on "CloudWatch" service

3. **View Logs**
   - In the left sidebar, click **"Logs"** → **"Log groups"**
   - Find: `/aws/lambda/docprof-dev-document-processor`
   - Click on it

4. **View Recent Logs**
   - You'll see recent **Log Streams** (one per Lambda execution)
   - Click on the most recent stream to see logs
   - Logs appear in real-time as the function runs

### Tips:
- **Auto-refresh**: Click the refresh button to see new logs
- **Filter**: Use the search box to filter logs (e.g., search for "error" or "chunk")
- **Time range**: Use the time selector to view logs from specific times

---

## Method 2: AWS CLI (Command Line)

### Prerequisites:
- AWS CLI installed: `brew install awscli` (Mac) or see https://aws.amazon.com/cli/
- AWS credentials configured: `aws configure`

### View Recent Logs:
```bash
# View last 50 log events
aws logs tail /aws/lambda/docprof-dev-document-processor

# Follow logs in real-time (like `tail -f`)
aws logs tail /aws/lambda/docprof-dev-document-processor --follow

# View logs from last 10 minutes
aws logs tail /aws/lambda/docprof-dev-document-processor --since 10m

# View logs from last hour
aws logs tail /aws/lambda/docprof-dev-document-processor --since 1h

# Filter for errors only
aws logs tail /aws/lambda/docprof-dev-document-processor --follow | grep -i error
```

### View Specific Time Range:
```bash
# View logs from a specific time (ISO format)
aws logs tail /aws/lambda/docprof-dev-document-processor \
  --since "2025-12-12T10:00:00" \
  --until "2025-12-12T11:00:00"
```

### Search Logs:
```bash
# Search for specific text
aws logs filter-log-events \
  --log-group-name /aws/lambda/docprof-dev-document-processor \
  --filter-pattern "error" \
  --max-items 20
```

---

## Method 3: CloudWatch Insights (Advanced Querying)

CloudWatch Insights lets you query logs using SQL-like syntax.

### Steps:

1. **Open CloudWatch Console**
2. **Go to Logs** → **Insights**
3. **Select Log Group**: `/aws/lambda/docprof-dev-document-processor`
4. **Write Query**:

```sql
-- View all logs from last hour
fields @timestamp, @message
| sort @timestamp desc
| limit 100

-- Find errors
fields @timestamp, @message
| filter @message like /(?i)(error|exception|failed)/
| sort @timestamp desc

-- Count chunks created
fields @message
| filter @message like /chunks_created/
| stats count() by @message

-- View ingestion pipeline progress
fields @timestamp, @message
| filter @message like /(Starting|complete|Processing|Stored)/
| sort @timestamp desc
```

---

## What to Look For in Logs

### Successful Ingestion:
```
INFO Starting AWS-native ingestion pipeline for [Book Title]
INFO Extracting cover image from first page
INFO Stored cover image (45,234 bytes, jpeg)
INFO Extracting text from PDF
INFO Building text chunks
INFO Built 5 chapter chunks and 500 page chunks
INFO Processing chunk batch 1 (50 chunks, 234,567 chars)
INFO Stored 500 figures
INFO Ingestion complete: 505 chunks, 200 figures
```

### Errors to Watch For:
```
ERROR Failed to extract cover: [error message]
ERROR Error generating embedding: [error message]
ERROR Failed to describe figure: [error message]
ERROR Database connection failed: [error message]
```

### Performance Indicators:
- **Processing time**: Look for timestamps between "Starting" and "complete"
- **Batch processing**: Check how many batches are processed
- **Parallelization**: Multiple "Processing chunk batch" messages at similar times

---

## Quick Reference Commands

### Most Common:
```bash
# Follow logs in real-time (best for testing)
aws logs tail /aws/lambda/docprof-dev-document-processor --follow

# View last 100 log lines
aws logs tail /aws/lambda/docprof-dev-document-processor --format short

# View logs from last 5 minutes
aws logs tail /aws/lambda/docprof-dev-document-processor --since 5m
```

### Troubleshooting:
```bash
# Find all errors
aws logs tail /aws/lambda/docprof-dev-document-processor --since 1h | grep -i error

# Find specific function calls
aws logs tail /aws/lambda/docprof-dev-document-processor --since 1h | grep "chunk"

# View full execution (with timestamps)
aws logs tail /aws/lambda/docprof-dev-document-processor --format short --since 10m
```

---

## Setting Up Log Monitoring (Optional)

### CloudWatch Dashboard:
You can create a dashboard to monitor Lambda metrics:
1. Go to CloudWatch → Dashboards
2. Create dashboard
3. Add widgets for:
   - Lambda invocations
   - Lambda errors
   - Lambda duration
   - Lambda memory usage

### Alarms:
Set up alarms to notify you of errors:
1. Go to CloudWatch → Alarms
2. Create alarm
3. Select metric: Lambda Errors
4. Set threshold (e.g., > 0 errors)
5. Configure SNS notification (optional)

---

## Tips

1. **Real-time Monitoring**: Use `--follow` flag when testing to see logs as they happen
2. **Filter Early**: Use grep or CloudWatch Insights to filter large log streams
3. **Time Ranges**: Use `--since` to limit log volume
4. **Log Retention**: Logs are kept for 30 days by default (configurable)
5. **Cost**: CloudWatch Logs has a free tier (5GB ingestion, 5GB storage per month)

---

## Example: Monitoring a PDF Upload

```bash
# 1. Start following logs
aws logs tail /aws/lambda/docprof-dev-document-processor --follow

# 2. Upload PDF via UI

# 3. Watch for:
#    - "Processing document: s3://..."
#    - "Starting AWS-native ingestion pipeline"
#    - "Processing chunk batch X"
#    - "Ingestion complete: X chunks, Y figures"
```

---

*CloudWatch Logs is your window into what's happening inside your Lambda functions!*

