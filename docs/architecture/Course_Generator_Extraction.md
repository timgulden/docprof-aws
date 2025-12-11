# Course Generator Extraction Summary

## What We've Extracted

### ✅ Core Models (`shared/core/course_models.py`)
- `Course` - Course record
- `CourseSection` - Section within a course
- `CourseState` - State for course generation workflow
- `CoursePreferences` - User preferences (depth, pace, style)
- `SectionDelivery` - Generated lecture content
- `QASession` - Q&A session during lectures
- `QAMessage` - Individual Q&A messages

### ✅ Course Events (`shared/core/course_events.py`)
- `CourseRequestedEvent` - User requests new course
- `EmbeddingGeneratedEvent` - Embedding created for query
- `BookSummariesFoundEvent` - Relevant books found
- `PartsGeneratedEvent` - Phase 1: Parts structure generated
- `PartSectionsGeneratedEvent` - Phase 2-N: Sections generated for a part
- `OutlineReviewEvent` - Phase N+1: Outline reviewed/adjusted
- `CourseStoredEvent` - Course saved to database

### ✅ Course Logic (`shared/logic/courses.py`)
**Main Functions:**
- `reduce_course_event()` - Main reducer (routes events to handlers)
- `request_course()` - Entry point for course creation
- `find_relevant_corpus_areas()` - Search book summaries
- `generate_course_parts()` - Phase 1: Generate parts structure
- `generate_part_sections()` - Phase 2-N: Expand part into sections
- `review_and_adjust_outline()` - Phase N+1: Review and adjust
- `store_course_outline()` - Store final course
- `generate_section_lecture()` - Generate lecture content for a section
- `refine_section_lecture()` - Refine lecture for consistency

**Helper Functions:**
- `parse_parts_text()` - Parse Phase 1 output
- `parse_outline_total_time()` - Extract time from outline
- `format_course_outline()` - Format outline for display
- `format_previous_lectures()` - Format context for lecture generation

### ✅ Lambda Handler (`course_generator/handler.py`)
- Basic handler structure created
- Handles course request events
- Executes commands (embedding, LLM calls)

## Course Generation Flow

```
1. User Request
   ↓
2. Generate Embedding (EmbedCommand)
   ↓
3. Search Book Summaries (SearchBookSummariesCommand)
   ↓
4. Phase 1: Generate Parts (LLMCommand: courses.generate_parts)
   ↓
5. Phase 2-N: Expand Each Part (LLMCommand: courses.expand_part)
   ↓
6. Phase N+1: Review & Adjust (LLMCommand: courses.review_outline)
   ↓
7. Store Course (CreateCourseCommand, CreateSectionsCommand)
```

## What Still Needs to be Built

### 1. Command Executor Pattern
The handler needs to execute commands and continue the workflow:
- Execute `EmbedCommand` → Generate embedding → Trigger `EmbeddingGeneratedEvent`
- Execute `SearchBookSummariesCommand` → Search DB → Trigger `BookSummariesFoundEvent`
- Execute `LLMCommand` → Call Bedrock → Parse response → Trigger next event
- Continue until `CourseStoredEvent`

### 2. State Management
- Store `CourseState` during generation (DynamoDB or in-memory for single Lambda)
- Handle multi-phase workflow state
- Track progress through phases

### 3. Database Operations
- Search book summaries (vector similarity on book summary embeddings)
- Store course outline (insert Course + CourseSections)
- Query courses by user_id
- Update course status

### 4. Multi-Phase Workflow Options

**Option A: Single Lambda (Synchronous)**
- Handle all phases in one Lambda invocation
- Pros: Simple, no state management needed
- Cons: Long execution time (may hit timeout), expensive

**Option B: Step Functions (Asynchronous)**
- Each phase is a Lambda function
- Step Functions orchestrates the workflow
- Pros: Scalable, handles long-running workflows
- Cons: More complex, requires state management

**Option C: Event-Driven (Recommended)**
- Lambda publishes events to EventBridge
- Each phase is triggered by events
- State stored in DynamoDB
- Pros: Scalable, decoupled, handles failures well
- Cons: More setup, async (user needs to poll for status)

### 5. API Endpoints Needed

```
POST /courses
  - Request course generation
  - Returns: {course_id, status: "generating", ui_message}

GET /courses/{course_id}
  - Get course status/outline
  - Returns: Course with sections

GET /courses/{course_id}/sections/{section_id}
  - Get section details

POST /courses/{course_id}/sections/{section_id}/lecture
  - Generate lecture for section
  - Returns: Lecture script

GET /courses/{course_id}/sections/{section_id}/audio
  - Get audio for lecture (Polly)
```

### 6. Missing Components

**Book Summary Search:**
- Need to store book summaries with embeddings in Aurora
- Vector similarity search on book summary embeddings
- Function: `search_book_summaries(query_embedding, top_k)`

**Course Storage:**
- Insert Course record
- Insert CourseSection records (batch)
- Function: `store_course(course, sections)`

**Prompt System Integration:**
- LLMCommand uses `prompt_name` (e.g., "courses.generate_parts")
- Need to ensure prompt registry can resolve these
- Prompts already exist in `base_prompts.py`

## Next Steps

1. **Implement Command Executor** - Execute commands and trigger next events
2. **Add Book Summary Search** - Vector search on book summaries
3. **Add Course Storage** - Store courses and sections in Aurora
4. **Choose Workflow Pattern** - Single Lambda vs Step Functions vs Event-Driven
5. **Add API Gateway Endpoints** - Course CRUD operations
6. **Write Unit Tests** - Test course logic functions
7. **Deploy and Test** - Verify in Lambda runtime

## Key Insights from Code

1. **Multi-Phase Generation**: Course generation is iterative:
   - Parts → Sections → Review → Store
   - Each phase uses LLM with different prompts
   - Time accuracy is critical (must match target hours)

2. **State Management**: CourseState tracks:
   - Pending course query/hours/preferences
   - Book summaries JSON
   - Generated parts/sections
   - Current phase

3. **Command Pattern**: Logic emits commands, handler executes:
   - `EmbedCommand` → Generate embedding
   - `LLMCommand` → Call Bedrock with prompt
   - `SearchBookSummariesCommand` → Search database
   - `CreateCourseCommand` → Store course

4. **Prompt System**: Uses centralized prompts:
   - `courses.generate_parts` - Phase 1
   - `courses.expand_part` - Phase 2-N
   - `courses.review_outline` - Phase N+1
   - `courses.generate_section_lecture` - Lecture generation
