# Backend TODO Summary

## ✅ Completed

1. **Source Summary Generation** - Working perfectly (100% JSON success rate)
2. **Source Summary Embedding Generation** - Working, EventBridge integrated
3. **Book Summary Search** - Implemented and tested
4. **Course Generation Pipeline** - Fixed and working end-to-end
5. **Database Schema** - Tables exist: `courses`, `course_sections`, `section_deliveries`, `section_qa_sessions`

## ⚠️ Critical: Course Storage Not Implemented

### Issue
`CreateCourseCommand` and `CreateSectionsCommand` are **not implemented** - they just return mock data.

**Current State:**
```python
# command_executor.py
def execute_create_course_command(command: CreateCourseCommand):
    logger.warning("CreateCourseCommand not yet implemented")
    return {'status': 'success', 'course_id': command.course.course_id, ...}
```

**Impact:** Courses are generated but **not persisted**. Users can't retrieve them later.

**Fix Needed:**
1. Implement `execute_create_course_command` to INSERT into `courses` table
2. Implement `execute_create_sections_command` to batch INSERT into `course_sections` table
3. Ensure course outline structure is properly stored

---

## 🔧 High Priority: Course Retrieval

### Issue
No Lambda function to retrieve courses by ID.

**Missing:**
- GET `/courses/{courseId}` endpoint
- Lambda handler to fetch course + sections from database
- API Gateway route configuration

**Fix Needed:**
1. Create `course_retriever` Lambda handler
2. Query `courses` table by `course_id`
3. Query `course_sections` table for all sections
4. Return complete course structure
5. Add API Gateway route

---

## 🔧 High Priority: Section-to-Sections Conversion

### Issue
Course generation creates outline structure, but needs to convert to `CourseSection` objects.

**Current Flow:**
- Logic generates outline text (parts + sections)
- But doesn't create `CourseSection` Pydantic models
- `CreateSectionsCommand` expects `List[CourseSection]`

**Fix Needed:**
1. Parse outline text into structured `CourseSection` objects
2. Map parts → sections hierarchy
3. Extract learning objectives, estimated minutes, etc.
4. Create `CreateSectionsCommand` with proper section objects

---

## 🔧 Medium Priority: Lecture Generation

### Status
Logic exists in `shared/logic/courses.py` (`generate_section_lecture`), but:
- Handler may not exist or be incomplete
- Needs to retrieve chunks for section
- Needs to generate lecture script
- Needs to store in `section_deliveries` table

**Fix Needed:**
1. Verify/implement `lecture_generator` Lambda handler
2. Implement `RetrieveChunksCommand` (currently TODO)
3. Implement lecture generation flow
4. Store lecture in `section_deliveries` table
5. Add API Gateway route: GET `/lectures/{sectionId}`

---

## 🔧 Medium Priority: Audio Generation

### Status
TTS functionality mentioned but not implemented.

**Missing:**
- Lambda handler for audio generation
- Integration with AWS Polly
- Audio streaming via API Gateway
- Audio storage (optional - S3 or in-memory)

**Fix Needed:**
1. Create `audio_streamer` Lambda handler
2. Integrate AWS Polly Neural TTS
3. Handle long text (chunking for Polly's 3000 char limit)
4. Stream MP3 response via API Gateway
5. Add API Gateway route: GET `/audio/{lectureId}`

---

## 🔧 Medium Priority: Chat Handler

### Status
Handler exists but needs verification.

**Check Needed:**
1. Verify chat handler works end-to-end
2. Test vector search integration
3. Verify session management (DynamoDB)
4. Test Bedrock Claude integration
5. Verify API Gateway route: POST `/chat`

---

## 🔧 Low Priority: Course State Management

### Status
`course_state_manager.py` exists but may need updates.

**Check Needed:**
1. Verify DynamoDB course state table exists
2. Test state save/load operations
3. Verify state persistence across Lambda invocations
4. Check TTL configuration

---

## 🔧 Low Priority: Missing Command Executors

### TODOs Found:
1. **RetrieveChunksCommand** - Not implemented
   - Needed for lecture generation
   - Should query `chunks` table by `chunk_ids`

2. **GetBookTitlesCommand** - Not implemented
   - Needed for displaying book names
   - Should query `books` table by `book_ids`

3. **StoreLectureCommand** - Not implemented
   - Needed for storing generated lectures
   - Should INSERT into `section_deliveries` table

---

## 📋 API Gateway Configuration

### Current Status
API Gateway module exists, but need to verify all endpoints are configured:

**Expected Endpoints:**
- POST `/courses` → course_request_handler ✅ (tested)
- GET `/courses/{courseId}` → course_retriever ❌ (missing)
- POST `/chat` → chat_handler ⚠️ (needs verification)
- GET `/lectures/{sectionId}` → lecture_generator ⚠️ (needs verification)
- GET `/audio/{lectureId}` → audio_streamer ❌ (missing)

**Action:** Verify all endpoints are configured in Terraform

---

## 🎯 Recommended Priority Order

### Phase 1: Course Persistence (Critical)
1. ✅ Fix course generation pipeline (DONE)
2. ⚠️ **Implement `CreateCourseCommand`** - Store courses
3. ⚠️ **Implement `CreateSectionsCommand`** - Store sections
4. ⚠️ **Fix outline → sections conversion** - Parse outline into CourseSection objects

### Phase 2: Course Retrieval (High Priority)
5. ⚠️ **Create course_retriever Lambda** - GET course by ID
6. ⚠️ **Add API Gateway route** - GET `/courses/{courseId}`

### Phase 3: Lecture Generation (Medium Priority)
7. ⚠️ **Implement `RetrieveChunksCommand`** - Get chunks for section
8. ⚠️ **Verify/implement lecture_generator** - Generate lecture scripts
9. ⚠️ **Implement `StoreLectureCommand`** - Store lectures

### Phase 4: Audio & Chat (Medium Priority)
10. ⚠️ **Create audio_streamer Lambda** - TTS with Polly
11. ⚠️ **Verify chat_handler** - Test end-to-end

### Phase 5: Polish (Low Priority)
12. ⚠️ **Implement `GetBookTitlesCommand`** - Book name lookup
13. ⚠️ **Verify course state management** - DynamoDB integration

---

## Files That Need Updates

1. **`src/lambda/shared/command_executor.py`**
   - `execute_create_course_command` - Implement database INSERT
   - `execute_create_sections_command` - Implement batch INSERT
   - `execute_retrieve_chunks_command` - Implement chunk retrieval
   - `execute_store_lecture_command` - Implement lecture storage
   - `execute_get_book_titles_command` - Implement book lookup

2. **`src/lambda/shared/logic/courses.py`**
   - `store_course_outline` - Convert outline text to CourseSection objects
   - Ensure proper course/section structure

3. **New Lambda Handlers Needed:**
   - `course_retriever/handler.py` - GET course by ID
   - `audio_streamer/handler.py` - TTS audio generation (if missing)

4. **Terraform Configuration:**
   - Add course_retriever Lambda module
   - Add API Gateway routes for missing endpoints
   - Verify all endpoints are configured

---

## Testing Checklist

After implementing fixes:

- [ ] Course generation stores course in database
- [ ] Course generation stores sections in database
- [ ] Can retrieve course by ID via API
- [ ] Can retrieve course sections
- [ ] Lecture generation works for a section
- [ ] Audio generation works for a lecture
- [ ] Chat handler works end-to-end
- [ ] All API Gateway routes respond correctly
