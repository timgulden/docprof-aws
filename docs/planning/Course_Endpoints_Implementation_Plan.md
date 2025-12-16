# Course Endpoints Implementation Plan

**Created:** 2025-01-XX  
**Status:** Planning  
**Goal:** Implement missing course endpoints to enable full frontend functionality

---

## Executive Summary

The course generation **backend logic** is fully implemented and tested. We have:
- ✅ Event-driven course generation (6-phase pipeline)
- ✅ Course storage to Aurora database
- ✅ Course retrieval by ID
- ✅ DynamoDB state management
- ✅ Pure functional logic in `shared/logic/courses.py`

**What's Missing:** Lambda handlers and API Gateway endpoints to expose this functionality to the frontend.

---

## Implementation Principles

1. **Reuse MAExpert Logic:** All logic is already extracted to `shared/logic/courses.py`
2. **Lambda Best Practices:** Thin handlers, delegate to pure logic
3. **No Monkey Patching:** Use adapter pattern for AWS services
4. **Bedrock Claude 4.5:** Via `shared/bedrock_client.py`
5. **Polly TTS:** Via AWS SDK (to be implemented)
6. **User Isolation:** Extract `user_id` from Cognito token for all endpoints

---

## Priority Levels

- **P0 (Critical):** Required for basic course functionality
- **P1 (High):** Required for complete course experience
- **P2 (Medium):** Enhances user experience
- **P3 (Low):** Nice to have features

---

## Missing Endpoints by Priority

### P0: Critical - Core Course Functionality

#### 1. GET /courses/{courseId}/outline
**Priority:** P0  
**Purpose:** Get course outline with all sections (hierarchical structure)  
**Frontend Usage:** `CourseDashboard` component loads this on mount  
**Implementation:**
- **Lambda:** NEW `course_outline_handler`
- **Logic:** Query database for course + all sections
- **Returns:** Course metadata + parts + sections (hierarchical)
- **Complexity:** Low (database query + JSON formatting)
- **Estimate:** 2 hours

**Handler Pseudocode:**
```python
def lambda_handler(event, context):
    user_id = extract_user_id(event)
    course_id = event['pathParameters']['courseId']
    
    # Query course + sections from Aurora
    with get_db_connection() as conn:
        course = get_course(conn, course_id, user_id)
        sections = get_sections(conn, course_id)
        parts = group_sections_by_part(sections)
    
    return success_response({
        'course_id': course_id,
        'title': course['title'],
        'parts': parts,
        'sections': sections,
        'total_sections': len(sections),
        'completed_sections': count_completed(sections),
        'total_minutes': sum_minutes(sections),
    })
```

---

#### 2. GET /courses/section/{sectionId}/lecture
**Priority:** P0  
**Purpose:** Get lecture script for a section (or trigger generation if not exists)  
**Frontend Usage:** `SectionPlayer` component  
**Implementation:**
- **Lambda:** NEW `section_lecture_handler`
- **Logic:** 
  - Check if lecture exists in database
  - If exists: return immediately (200)
  - If not exists: trigger async generation, return 202 Accepted
  - Frontend polls `/courses/section/{sectionId}/generation-status`
- **Complexity:** Medium (async generation handling)
- **Estimate:** 4 hours

**Handler Pseudocode:**
```python
def lambda_handler(event, context):
    user_id = extract_user_id(event)
    section_id = event['pathParameters']['sectionId']
    
    # Check if lecture exists
    delivery = get_section_delivery(section_id)
    if delivery:
        return success_response({
            'section_id': section_id,
            'lecture_script': delivery['lecture_script'],
            'estimated_minutes': delivery['estimated_minutes'],
            'figures': get_section_figures(section_id),
        })
    
    # Lecture doesn't exist - trigger async generation
    trigger_lecture_generation(section_id, user_id)
    
    return http_response(202, {
        'message': 'Lecture generation in progress',
        'section_id': section_id,
    })
```

---

#### 3. GET /courses/section/{sectionId}/generation-status
**Priority:** P0  
**Purpose:** Poll for lecture generation progress  
**Frontend Usage:** `SectionPlayer` polls while generation is in progress  
**Implementation:**
- **Lambda:** NEW `section_generation_status_handler`
- **Logic:** Check generation progress from DynamoDB or in-memory cache
- **Returns:** Phase, progress_percent, current_step
- **Complexity:** Low (read from DynamoDB)
- **Estimate:** 2 hours

---

#### 4. POST /courses/section/{sectionId}/complete
**Priority:** P0  
**Purpose:** Mark section as completed  
**Frontend Usage:** User finishes section  
**Implementation:**
- **Lambda:** NEW `section_complete_handler`
- **Logic:** Update section status in database
- **Complexity:** Low (database update)
- **Estimate:** 1 hour

---

### P1: High - Essential Features

#### 5. DELETE /courses/{courseId}
**Priority:** P1  
**Purpose:** Delete a course and all its sections  
**Frontend Usage:** `CourseList` delete button  
**Implementation:**
- **Lambda:** NEW `course_delete_handler`
- **Logic:** 
  - Verify user owns course
  - Delete all section deliveries
  - Delete all sections
  - Delete course
- **Complexity:** Medium (cascading deletes)
- **Estimate:** 3 hours

---

#### 6. POST /courses/{courseId}/next
**Priority:** P1  
**Purpose:** Get next incomplete section  
**Frontend Usage:** "Next Section" button  
**Implementation:**
- **Lambda:** NEW `course_next_section_handler`
- **Logic:** Already implemented in `select_next_section()` in courses.py
- **Complexity:** Low (reuse existing logic)
- **Estimate:** 2 hours

---

#### 7. POST /courses/{courseId}/standalone
**Priority:** P1  
**Purpose:** Get standalone section based on available time  
**Frontend Usage:** "Quick Session" feature  
**Implementation:**
- **Lambda:** NEW `course_standalone_section_handler`
- **Logic:** Already implemented in `select_standalone_section()` in courses.py
- **Complexity:** Low (reuse existing logic)
- **Estimate:** 2 hours

---

### P2: Medium - Enhanced Experience

#### 8. POST /courses/{courseId}/revise
**Priority:** P2  
**Purpose:** Revise course outline (add/remove/modify sections)  
**Frontend Usage:** Course customization  
**Implementation:**
- **Lambda:** NEW `course_revise_handler`
- **Logic:** Already implemented in `request_outline_revision()` in courses.py
- **Complexity:** High (LLM-based revision)
- **Estimate:** 4 hours

---

#### 9. POST /courses/section/{sectionId}/regenerate
**Priority:** P2  
**Purpose:** Regenerate lecture with different style  
**Frontend Usage:** Style selector in player  
**Implementation:**
- **Lambda:** Reuse `section_lecture_handler` with `regenerate` flag
- **Logic:** Already implemented in `refine_section_lecture()` in courses.py
- **Complexity:** Medium
- **Estimate:** 3 hours

---

### P3: Low - Audio & Advanced Features

#### 10. POST /courses/section/{sectionId}/generate-audio
**Priority:** P3  
**Purpose:** Generate Polly audio for lecture  
**Frontend Usage:** Audio playback  
**Implementation:**
- **Lambda:** NEW `section_audio_generate_handler`
- **Logic:** 
  - Get lecture script
  - Call AWS Polly TTS
  - Store MP3 in S3
  - Return success
- **Complexity:** Medium (Polly integration)
- **Estimate:** 4 hours

---

#### 11. GET /courses/section/{sectionId}/audio
**Priority:** P3  
**Purpose:** Get audio file for section  
**Frontend Usage:** Audio player  
**Implementation:**
- **Lambda:** NEW `section_audio_handler`
- **Logic:** Return presigned S3 URL or stream audio
- **Complexity:** Low
- **Estimate:** 2 hours

---

#### 12. POST /courses/section/{sectionId}/lecture-question
**Priority:** P3  
**Purpose:** Ask question during lecture with full context  
**Frontend Usage:** Q&A during playback  
**Implementation:**
- **Lambda:** NEW `section_qa_handler`
- **Logic:** Already partially implemented in courses.py
- **Complexity:** High (context-aware Q&A)
- **Estimate:** 6 hours

---

## Implementation Roadmap

### Phase 1: Core Functionality (P0) - Week 1
**Goal:** Enable basic course outline viewing and section playback

**Tasks:**
1. ✅ GET /courses (list courses) - **DONE**
2. GET /courses/{courseId}/outline - **2 hours**
3. GET /courses/section/{sectionId}/lecture - **4 hours**
4. GET /courses/section/{sectionId}/generation-status - **2 hours**
5. POST /courses/section/{sectionId}/complete - **1 hour**

**Deliverable:** Users can view courses, see outlines, and play lectures

---

### Phase 2: Course Management (P1) - Week 2
**Goal:** Enable full course navigation and management

**Tasks:**
1. DELETE /courses/{courseId} - **3 hours**
2. POST /courses/{courseId}/next - **2 hours**
3. POST /courses/{courseId}/standalone - **2 hours**

**Deliverable:** Users can navigate courses and delete them

---

### Phase 3: Customization (P2) - Week 3
**Goal:** Enable course customization

**Tasks:**
1. POST /courses/{courseId}/revise - **4 hours**
2. POST /courses/section/{sectionId}/regenerate - **3 hours**

**Deliverable:** Users can customize course content and lecture style

---

### Phase 4: Audio & Advanced (P3) - Week 4
**Goal:** Enable audio playback and Q&A

**Tasks:**
1. POST /courses/section/{sectionId}/generate-audio - **4 hours**
2. GET /courses/section/{sectionId}/audio - **2 hours**
3. POST /courses/section/{sectionId}/lecture-question - **6 hours**
4. GET /courses/section/{sectionId}/lecture-metadata - **1 hour**
5. Other audio endpoints (streaming, chunks, etc.) - **4 hours**

**Deliverable:** Full audio experience with Q&A

---

## Lambda Functions Summary

### New Lambda Functions Needed

| Function | Endpoints | Priority | Estimate |
|----------|-----------|----------|----------|
| `course_outline_handler` | GET /courses/{courseId}/outline | P0 | 2h |
| `section_lecture_handler` | GET /courses/section/{sectionId}/lecture | P0 | 4h |
| `section_generation_status_handler` | GET /courses/section/{sectionId}/generation-status | P0 | 2h |
| `section_complete_handler` | POST /courses/section/{sectionId}/complete | P0 | 1h |
| `course_delete_handler` | DELETE /courses/{courseId} | P1 | 3h |
| `course_next_section_handler` | POST /courses/{courseId}/next | P1 | 2h |
| `course_standalone_section_handler` | POST /courses/{courseId}/standalone | P1 | 2h |
| `course_revise_handler` | POST /courses/{courseId}/revise | P2 | 4h |
| `section_audio_generate_handler` | POST /courses/section/{sectionId}/generate-audio | P3 | 4h |
| `section_audio_handler` | GET /courses/section/{sectionId}/audio | P3 | 2h |
| `section_qa_handler` | POST /courses/section/{sectionId}/lecture-question | P3 | 6h |

**Total Estimate:** 32 hours (approx. 4 weeks part-time)

---

## Existing Logic to Reuse

All logic functions are in `src/lambda/shared/logic/courses.py`:

- `select_next_section()` - For next section selection
- `select_standalone_section()` - For standalone section
- `generate_section_lecture()` - For lecture generation
- `mark_section_complete()` - For completing sections
- `request_outline_revision()` - For outline revision
- `refine_section_lecture()` - For regenerating lectures
- `generate_audio_for_section()` - For audio generation

**Pattern:** Lambda handlers are thin wrappers that:
1. Extract parameters from API Gateway event
2. Load state/data from database
3. Call pure logic function
4. Execute returned commands (if any)
5. Save state/data to database
6. Return formatted response

---

## AWS Services Integration

### Already Integrated ✅
- **Bedrock Claude 4.5:** `shared/bedrock_client.py`
- **Aurora PostgreSQL:** `shared/db_utils.py`
- **DynamoDB:** `shared/course_state_manager.py`
- **EventBridge:** `shared/event_publisher.py`

### To Be Integrated
- **AWS Polly:** Need to create `shared/polly_client.py`
- **S3 Audio Storage:** Extend existing S3 utilities

---

## Testing Strategy

### Unit Tests
- Logic functions already have unit tests in `tests/unit/test_course_logic.py`
- Add tests for new handler parameter extraction and response formatting

### Integration Tests
- Test each endpoint via API Gateway
- Verify database state changes
- Test async generation (202 → poll → 200)

### End-to-End Tests
1. Create course (existing - working)
2. Get outline (new)
3. Play section (new)
4. Mark complete (new)
5. Get next section (new)
6. Delete course (new)

---

## Dependencies & Prerequisites

### Required
- ✅ Aurora database with course tables
- ✅ DynamoDB for course state
- ✅ EventBridge for async generation
- ✅ Cognito for authentication
- ✅ Bedrock for LLM
- ✅ Course generation logic extracted

### Optional (for audio)
- AWS Polly access
- S3 bucket for audio storage

---

## Next Steps

1. **Review & Approve Plan:** Confirm priorities and estimates
2. **Start Phase 1:** Implement P0 endpoints
3. **Deploy & Test:** After each phase, deploy and test with frontend
4. **Iterate:** Adjust based on user feedback

---

## Notes

- All business logic is already implemented and tested
- Handlers are straightforward wrappers around pure functions
- Following MAExpert patterns but adapted for Lambda/Serverless
- No monkey patching - using adapter pattern for AWS services
- Bedrock Claude 4.5 for all LLM calls
- Polly for TTS (to be implemented in Phase 4)
