# Course Generator Terraform Configuration

## Overview

Complete Terraform configuration for the event-driven course generation workflow has been added to `terraform/environments/dev/main.tf`.

## Infrastructure Components

### 1. DynamoDB Course State Table
- **Module**: `terraform/modules/dynamodb-course-state/`
- **Table**: `docprof-dev-course-state`
- **Purpose**: Persist CourseState between workflow phases
- **TTL**: 7 days (automatic cleanup)

### 2. EventBridge Custom Bus
- **Module**: `terraform/modules/eventbridge/`
- **Bus**: `docprof-dev-course-events`
- **Purpose**: Event-driven workflow orchestration
- **Rules**: 6 event rules for each phase transition
- **DLQ**: Dead letter queue for failed events

### 3. Lambda Functions (7 total)

#### Entry Point
- **course-request-handler**: Receives API Gateway requests, creates initial state, publishes EmbeddingGeneratedEvent

#### Phase Handlers
- **course-embedding-handler**: Handles EmbeddingGeneratedEvent, searches book summaries
- **course-book-search-handler**: Handles BookSummariesFoundEvent, generates parts structure
- **course-parts-handler**: Handles PartsGeneratedEvent, starts section generation
- **course-sections-handler**: Handles PartSectionsGeneratedEvent, continues with next part or completes
- **course-outline-reviewer**: Handles AllPartsCompleteEvent, reviews outline if needed
- **course-storage-handler**: Handles OutlineReviewEvent, stores course in Aurora

### 4. EventBridge Targets
- All event rules connected to corresponding Lambda functions
- Lambda permissions granted for EventBridge invocation

### 5. IAM Permissions
- **EventBridge Publish**: Lambda functions can publish events
- **EventBridge Invoke**: EventBridge can invoke Lambda functions
- **DynamoDB Access**: All handlers can read/write course state
- **Aurora Access**: Storage handler can write courses/sections

### 6. API Gateway Endpoint
- **POST /courses**: Entry point for course generation requests

## Environment Variables

All Lambda functions receive:
- `DYNAMODB_COURSE_STATE_TABLE_NAME`: Course state table name
- `EVENT_BUS_NAME`: EventBridge custom bus name
- `AWS_ACCOUNT_ID`: AWS account ID

Storage handler additionally receives:
- `DB_CLUSTER_ENDPOINT`: Aurora cluster endpoint
- `DB_NAME`: Database name
- `DB_MASTER_USERNAME`: Database username
- `DB_PASSWORD_SECRET_ARN`: Secrets Manager ARN for password

## Event Flow

```
POST /courses
  ↓
course-request-handler
  ↓ EmbeddingGeneratedEvent
course-embedding-handler
  ↓ BookSummariesFoundEvent
course-book-search-handler
  ↓ PartsGeneratedEvent
course-parts-handler
  ↓ PartSectionsGeneratedEvent
course-sections-handler
  ↓ (loop for each part)
  ↓ AllPartsCompleteEvent
course-outline-reviewer
  ↓ OutlineReviewEvent (if review needed)
course-storage-handler
  ↓ CourseStoredEvent (complete)
```

## Deployment Steps

1. **Initialize Terraform**:
   ```bash
   cd terraform/environments/dev
   terraform init
   ```

2. **Plan Deployment**:
   ```bash
   terraform plan
   ```

3. **Deploy Infrastructure**:
   ```bash
   terraform apply
   ```

4. **Verify Deployment**:
   - Check Lambda functions exist in AWS Console
   - Verify EventBridge rules are connected
   - Test API Gateway endpoint

## Testing

After deployment, test the workflow:

```bash
# Get API Gateway URL
terraform output course_request_endpoint

# Send course generation request
curl -X POST https://<api-id>.execute-api.<region>.amazonaws.com/dev/courses \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Learn DCF valuation",
    "hours": 2.0,
    "preferences": {
      "depth": "balanced",
      "pace": "moderate"
    }
  }'
```

## Monitoring

- **CloudWatch Logs**: Each Lambda has its own log group
- **EventBridge Metrics**: Monitor event publishing/invocation
- **DynamoDB Metrics**: Track state persistence
- **Lambda Metrics**: Monitor execution time, errors, throttles

## Next Steps

1. Implement database operations (book search, course storage)
2. Add error handling and retry logic
3. Add CloudWatch alarms for failed events
4. Implement course status polling endpoint
5. Add integration tests
