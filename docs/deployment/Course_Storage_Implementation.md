# Course Storage and Retrieval Implementation

## Summary

Implemented critical backend functionality for course persistence and retrieval:

1. ✅ **Course Storage** - `CreateCourseCommand` now stores courses in Aurora
2. ✅ **Section Storage** - `CreateSectionsCommand` now stores sections in Aurora  
3. ✅ **Course Retrieval** - New `course_retriever` Lambda handler
4. ✅ **API Gateway Route** - GET `/courses/get?courseId=...` endpoint

## Changes Made

### 1. Course Storage (`command_executor.py`)

**`execute_create_course_command`:**
- Converts Course model to database INSERT
- Handles UUID conversion (course_id, user_id)
- Converts preferences to JSONB
- Uses `ON CONFLICT` for idempotency
- Returns stored course_id

**Key Features:**
- Proper UUID handling for PostgreSQL
- JSONB storage for preferences
- Timestamp management (created_at, last_modified)
- Error handling and logging

### 2. Section Storage (`command_executor.py`)

**`execute_create_sections_command`:**
- Batch inserts sections using `execute_values`
- Handles UUID arrays (chunk_ids, prerequisites)
- Converts TEXT[] for learning_objectives
- Supports hierarchical structure (parent_section_id)
- Uses `ON CONFLICT` for idempotency

**Key Features:**
- Efficient batch insertion
- Proper array type handling (UUID[], TEXT[])
- Supports optional parent_section_id for parts/sections hierarchy
- Error handling for partial failures

### 3. Course Retriever Lambda (`course_retriever/handler.py`)

**New Lambda Handler:**
- Retrieves course by ID from Aurora
- Fetches all associated sections
- Converts database types to Pydantic models
- Handles both path parameters and query string parameters
- Returns complete course structure with sections

**Key Features:**
- UUID validation
- Proper type conversion (UUID arrays, TEXT arrays, JSONB)
- Error handling (404 for not found, 400 for invalid UUID)
- Returns structured JSON response

### 4. API Gateway Configuration (`main.tf`)

**New Endpoint:**
- `GET /courses/get?courseId={uuid}`
- Integrated with `course_retriever` Lambda
- CORS enabled
- No authentication (TODO: Add Cognito in prod)

**Lambda Module:**
- Created `course_retriever_lambda` module
- Configured with VPC access for Aurora
- Database environment variables set
- 30s timeout, 256MB memory

## Database Schema

Uses existing tables:
- `courses` - Course metadata
- `course_sections` - Section details with hierarchical support

## API Usage

### Store Course
**Endpoint:** `POST /courses`  
**Handler:** `course_request_handler`  
**Flow:** Generates course → Stores via `CreateCourseCommand` → Returns course_id

### Retrieve Course
**Endpoint:** `GET /courses/get?courseId={uuid}`  
**Handler:** `course_retriever`  
**Response:**
```json
{
  "course": {
    "course_id": "...",
    "title": "...",
    "original_query": "...",
    "estimated_hours": 2.0,
    "preferences": {...},
    "status": "active",
    ...
  },
  "sections": [
    {
      "section_id": "...",
      "course_id": "...",
      "title": "...",
      "learning_objectives": [...],
      "estimated_minutes": 15,
      ...
    }
  ],
  "section_count": 5
}
```

## Testing Checklist

- [ ] Deploy updated Lambda functions
- [ ] Deploy Terraform changes (API Gateway + Lambda)
- [ ] Test course generation (should now persist to database)
- [ ] Verify course appears in `courses` table
- [ ] Verify sections appear in `course_sections` table
- [ ] Test course retrieval via API Gateway
- [ ] Test with invalid courseId (should return 404)
- [ ] Test with malformed UUID (should return 400)
- [ ] Verify sections are ordered by `order_index`
- [ ] Verify hierarchical structure (parts → sections)

## Next Steps

1. **Deploy Infrastructure:**
   ```bash
   cd terraform/environments/dev
   terraform plan
   terraform apply
   ```

2. **Deploy Lambda Functions:**
   ```bash
   # Package and deploy course_retriever
   python scripts/package_lambda.py course_retriever
   aws lambda update-function-code \
     --function-name docprof-dev-course-retriever \
     --zip-file fileb://course_retriever.zip
   
   # Update shared module (command_executor.py)
   # This affects course_request_handler, so redeploy it too
   python scripts/package_lambda.py course_request_handler
   aws lambda update-function-code \
     --function-name docprof-dev-course-request-handler \
     --zip-file fileb://course_request_handler.zip
   ```

3. **Test Course Generation:**
   ```bash
   # Generate a course
   curl -X POST https://{api-id}.execute-api.{region}.amazonaws.com/dev/courses \
     -H "Content-Type: application/json" \
     -d '{
       "query": "Learn DCF valuation",
       "hours": 2.0,
       "preferences": {}
     }'
   
   # Note the course_id from response
   ```

4. **Test Course Retrieval:**
   ```bash
   # Retrieve the course
   curl https://{api-id}.execute-api.{region}.amazonaws.com/dev/courses/get?courseId={course_id}
   ```

## Files Modified

1. `src/lambda/shared/command_executor.py`
   - Implemented `execute_create_course_command`
   - Implemented `execute_create_sections_command`

2. `src/lambda/course_retriever/handler.py` (NEW)
   - Course retrieval handler

3. `src/lambda/course_retriever/requirements.txt` (NEW)
   - Dependencies

4. `terraform/environments/dev/main.tf`
   - Added `course_retriever_lambda` module
   - Added `course_get` endpoint to API Gateway

## Notes

- Course storage now happens automatically during course generation
- Courses are persisted in Aurora (not just DynamoDB state)
- Sections support hierarchical structure (parts → sections)
- All UUIDs are properly converted for PostgreSQL
- JSONB is used for preferences (flexible schema)
- Arrays (UUID[], TEXT[]) are properly handled
