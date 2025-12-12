# Async Course Generation Implementation

## Overview

Implemented asynchronous course generation to avoid API Gateway's 30-second timeout limit. Course generation now returns immediately and processes via EventBridge, with UI polling for status updates.

## Architecture Changes

### Before (Synchronous)
- API Gateway → Lambda → Execute all commands → Return result
- **Problem**: Course generation takes 30-60+ seconds, exceeds API Gateway timeout

### After (Asynchronous)
- API Gateway → Lambda → Save state → Publish EventBridge event → Return immediately
- EventBridge → Lambda handlers → Process pipeline → Update state
- UI → Poll status endpoint → Get progress updates

## Implementation Details

### 1. Modified `course_request_handler`

**File**: `src/lambda/course_request_handler/handler.py`

**Changes**:
- Returns immediately after generating embedding and publishing `EmbeddingGeneratedEvent`
- Saves initial state to DynamoDB
- Returns `course_id` and `status: "processing"` to UI

**Flow**:
1. Create initial course state
2. Process `CourseRequestedEvent` → get `EmbedCommand`
3. Execute `EmbedCommand` (fast, ~100ms)
4. Save state to DynamoDB
5. Publish `EmbeddingGeneratedEvent` to EventBridge
6. Return immediately with `course_id`

### 2. Created `course_status_handler`

**File**: `src/lambda/course_status_handler/handler.py`

**Purpose**: Read course state from DynamoDB and return status/progress

**Response Format**:
```json
{
  "course_id": "uuid",
  "status": "processing" | "complete" | "error",
  "phase": "searching_books" | "generating_sections" | "reviewing_outline",
  "progress": {
    "parts_count": 3,
    "sections_count": 12
  },
  "query": "Learn DCF valuation",
  "hours": 2.0,
  "error": "optional error message"
}
```

### 3. Added API Gateway Route

**Route**: `GET /courses/{courseId}/status`

**Terraform**: Added to `terraform/environments/dev/main.tf`:
- New Lambda module: `course_status_handler_lambda`
- New endpoint: `course_status` with path `courses/{courseId}/status`

## EventBridge Flow

The existing EventBridge handlers process the course generation:

1. **EmbeddingGeneratedEvent** → `course_embedding_handler`
   - Searches book summaries
   - Publishes `BookSummariesFoundEvent`

2. **BookSummariesFoundEvent** → `course_book_search_handler`
   - Generates course parts structure
   - Publishes `PartsGeneratedEvent`

3. **PartsGeneratedEvent** → `course_parts_handler`
   - Generates sections for first part
   - Publishes `PartSectionsGeneratedEvent`

4. **PartSectionsGeneratedEvent** → `course_sections_handler`
   - Generates sections for next part OR
   - Publishes `AllPartsCompleteEvent` if done

5. **AllPartsCompleteEvent** → `course_outline_reviewer`
   - Reviews outline
   - Publishes `OutlineReviewEvent`

6. **OutlineReviewEvent** → `course_storage_handler`
   - Stores course in database
   - Publishes `CourseStoredEvent`
   - Updates state status to "complete"

## UI Integration

### Request Course Generation
```javascript
POST /courses
{
  "query": "Learn DCF valuation",
  "hours": 2.0,
  "preferences": {}
}

Response:
{
  "course_id": "uuid-here",
  "status": "processing",
  "message": "Course generation started. Poll /courses/{course_id}/status for progress."
}
```

### Poll Status
```javascript
GET /courses/{courseId}/status

Response (processing):
{
  "course_id": "uuid",
  "status": "processing",
  "phase": "generating_sections",
  "progress": {
    "parts_count": 3
  }
}

Response (complete):
{
  "course_id": "uuid",
  "status": "complete",
  "phase": "complete",
  "progress": {
    "course_id": "final-uuid",
    "title": "DCF Valuation Course",
    "estimated_hours": 2.0
  }
}
```

### Polling Strategy
- **Initial**: Poll every 2 seconds
- **After 30 seconds**: Poll every 5 seconds
- **After 60 seconds**: Poll every 10 seconds
- **Stop**: When `status === "complete"` or `status === "error"`

## Benefits

1. ✅ **No timeout issues**: API returns in <1 second
2. ✅ **Better UX**: Immediate feedback + progress updates
3. ✅ **Scalable**: EventBridge handles orchestration
4. ✅ **Resilient**: Each phase can retry independently
5. ✅ **Observable**: Status endpoint shows exact progress

## Testing

### Test Async Flow
1. **Start generation**:
   ```bash
   curl -X POST https://api/courses \
     -H "Content-Type: application/json" \
     -d '{"query": "Learn DCF valuation", "hours": 2.0}'
   ```
   Should return immediately with `course_id` and `status: "processing"`

2. **Poll status**:
   ```bash
   curl https://api/courses/{courseId}/status
   ```
   Should show progress through phases

3. **Verify completion**:
   ```bash
   curl https://api/courses/{courseId}/status
   ```
   Should show `status: "complete"` with final `course_id`

4. **Retrieve course**:
   ```bash
   curl https://api/course?courseId={finalCourseId}
   ```
   Should return complete course with sections

## Files Modified

- `src/lambda/course_request_handler/handler.py` - Made async
- `src/lambda/course_status_handler/handler.py` - **NEW** - Status endpoint
- `terraform/environments/dev/main.tf` - Added Lambda and route
- `docs/deployment/Async_Course_Generation_Implementation.md` - **NEW** - This document

## Next Steps

1. ✅ Deploy Terraform changes - **COMPLETE**
2. ✅ Test end-to-end flow - **COMPLETE**
3. Update UI to use polling - **See [Course Generation UI Integration Guide](./Course_Generation_UI_Integration_Guide.md)**
4. Consider WebSocket support for real-time updates (future enhancement)

## UI Integration

See **[Course Generation UI Integration Guide](./Course_Generation_UI_Integration_Guide.md)** for:
- Complete API documentation
- Polling strategies and React hooks
- Error handling
- UI flow examples
- Best practices
