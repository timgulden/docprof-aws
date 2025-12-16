# Expected API Endpoints - Frontend Analysis

This document lists all API endpoints that the frontend code expects, extracted from `src/frontend/src/api/*.ts` files.

**Last Updated:** 2025-01-XX  
**Purpose:** Identify missing endpoints by comparing frontend expectations vs. Terraform API Gateway configuration

---

## Courses Endpoints

### ✅ Implemented
- `GET /courses` - List all courses for user (just added)
- `POST /courses` - Create new course (via `course_request_handler`)
- `POST /courses/create` - Create new course (alternative path)
- `GET /course-status/{courseId}` - Get course generation status

### ❌ Missing
- `DELETE /courses/{courseId}` - Delete a course
- `GET /courses/{courseId}/outline` - Get course outline with sections
- `POST /courses/{courseId}/next` - Get next section to play
- `POST /courses/{courseId}/standalone` - Get standalone section
- `POST /courses/{courseId}/revise` - Revise course outline
- `GET /courses/section/{sectionId}/generation-status` - Get section generation status
- `GET /courses/section/{sectionId}/lecture` - Get section lecture script
- `POST /courses/section/{sectionId}/regenerate` - Regenerate section lecture
- `POST /courses/section/{sectionId}/pause-qa` - Pause lecture for Q&A
- `POST /courses/section/{sectionId}/qa-question` - Ask question during lecture
- `POST /courses/section/{sectionId}/lecture-question` - Submit question with full context
- `GET /courses/section/{sectionId}/audio` - Get section audio (blob)
- `GET /courses/section/{sectionId}/lecture-metadata` - Get lecture metadata
- `GET /courses/section/{sectionId}/audio-chunk/{chunkIndex}` - Get audio chunk
- `GET /courses/section/{sectionId}/audio-stream` - Stream audio
- `POST /courses/section/{sectionId}/generate-audio-stream` - Generate audio with SSE progress
- `POST /courses/section/{sectionId}/generate-audio` - Generate audio (non-streaming)
- `POST /courses/section/{sectionId}/resume` - Resume lecture
- `POST /courses/section/{sectionId}/complete` - Mark section as complete

**Note:** The `GET /course` (singular) endpoint exists but frontend uses `/courses/{courseId}` paths.

---

## Books Endpoints

### ✅ Implemented
- `GET /books` - List all books
- `GET /books/{bookId}/cover` - Get book cover image
- `POST /books/covers` - Batch fetch book covers
- `DELETE /books/{bookId}` - Delete a book
- `POST /books/upload-initial` - Get pre-signed S3 URL for upload
- `POST /books/{bookId}/analyze` - Analyze book (extract cover/metadata)
- `POST /books/{bookId}/start-ingestion` - Start background ingestion
- `GET /books/{bookId}/ingestion-status` - Get ingestion status
- `GET /books/{bookId}/pdf` - Get presigned PDF URL

---

## Chat Endpoints

### ✅ Implemented
- `POST /chat/message` - Send chat message
- `POST /chat/message-stream` - Stream chat response (SSE)
- `POST /chat/generate-audio` - Generate audio for text

---

## Sessions Endpoints

### ✅ Implemented
- `GET /chat/sessions` - List all sessions
- `POST /chat/sessions` - Create new session
- `GET /chat/sessions/{sessionId}` - Get session metadata (with optional `include_messages` query param)
- `PATCH /chat/sessions/{sessionId}` - Update session
- `DELETE /chat/sessions/{sessionId}` - Delete session

---

## Other Endpoints

### ✅ Implemented
- `GET /tunnel/status` - Get tunnel status (VPC endpoints)
- `GET /ai-services/status` - Get AI services status
- `GET /metrics` - Get metrics

---

## Currently Configured in Terraform

### Courses Endpoints (Configured)
- ✅ `POST /courses` - Create course (`course_request`)
- ✅ ✅ `GET /courses` - List courses (just added - `courses_list`)
- ✅ `GET /course` - Get single course (singular path - `course_retriever`)
- ✅ `GET /course-status/{courseId}` - Get course status (`course_status_handler`)

### Books Endpoints (Configured)
- ✅ `GET /books` - List books (`books_list`)
- ✅ `POST /books/upload` - Upload book (`book_upload`)
- ✅ `POST /books/upload-initial` - Get presigned URL (`book_upload`)
- ✅ `GET /books/{bookId}/cover` - Get cover (`book_cover`)
- ✅ `GET /books/{bookId}/pdf` - Get PDF (`book_pdf`)
- ✅ `POST /books/{bookId}/analyze` - Analyze book (likely in `book_upload`)
- ✅ `DELETE /books/{bookId}` - Delete book (`book_delete`)
- ✅ `POST /books/{bookId}/start-ingestion` - Start ingestion (likely in `book_upload`)

### Chat Endpoints (Configured)
- ✅ `POST /chat/message` - Send message (`chat_handler`)

### Sessions Endpoints (Configured)
- ✅ `GET /chat/sessions` - List sessions (`session_handler`)
- ✅ `POST /chat/sessions` - Create session (`session_handler`)
- ✅ `GET /chat/sessions/{sessionId}` - Get session (`session_handler`)
- ✅ `PATCH /chat/sessions/{sessionId}` - Update session (`session_handler`)
- ✅ `DELETE /chat/sessions/{sessionId}` - Delete session (`session_handler`)

### Other Endpoints (Configured)
- ✅ `GET /tunnel/status` - Tunnel status (`tunnel_status`)
- ✅ `GET /ai-services/status` - AI services status (`ai_services_manager`)
- ✅ `POST /ai-services/enable` - Enable AI services (`ai_services_manager`)
- ✅ `POST /ai-services/disable` - Disable AI services (`ai_services_manager`)
- ✅ `GET /metrics/chat` - Chat metrics (`metrics_handler`)

---

## Summary

### Courses: 23 endpoints expected, 4 configured
**Missing:** 19 course-related endpoints need to be implemented
- Most critical: `/courses/{courseId}/outline`, `/courses/section/{sectionId}/lecture`

### Books: 9 endpoints expected, 8+ configured ✅
- May need to verify `/books/{bookId}/ingestion-status` endpoint

### Chat: 3 endpoints expected, 1 configured
**Missing:**
- `POST /chat/message-stream` - Streaming chat (SSE)
- `POST /chat/generate-audio` - Generate audio for text

### Sessions: 5 endpoints expected, 5 configured ✅

---

## Next Steps

1. **Priority 1 - Core Course Functionality:**
   - `GET /courses/{courseId}/outline` - Required for course dashboard
   - `GET /courses/section/{sectionId}/lecture` - Required for section player
   - `POST /courses/section/{sectionId}/complete` - Required for progress tracking

2. **Priority 2 - Course Management:**
   - `DELETE /courses/{courseId}` - Delete course
   - `POST /courses/{courseId}/revise` - Revise outline

3. **Priority 3 - Section Navigation:**
   - `POST /courses/{courseId}/next` - Get next section
   - `POST /courses/{courseId}/standalone` - Get standalone section

4. **Priority 4 - Lecture Features:**
   - All section lecture, audio, and Q&A endpoints

---

## Notes

- The frontend uses `/courses/{courseId}` paths, but Terraform has `GET /course` (singular) endpoint
- Many course endpoints are nested under `/courses/section/{sectionId}/`
- Audio endpoints support both blob download and streaming
- Some endpoints use SSE (Server-Sent Events) for streaming responses
