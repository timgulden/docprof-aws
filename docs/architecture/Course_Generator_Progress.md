# Course Generator Event-Driven Implementation Progress

## ✅ Completed Components

### 1. State Management
- **`course_state_manager.py`** - DynamoDB persistence for CourseState
  - `load_course_state()` - Load from DynamoDB
  - `save_course_state()` - Save to DynamoDB
  - `course_state_to_dict()` - Serialize with all fields preserved
  - `dict_to_course_state()` - Deserialize with nested models
  - Handles all CourseState fields including nested models

### 2. Command Executor
- **`command_executor.py`** - Execute all command types
  - `execute_embed_command()` - Generate embeddings
  - `execute_llm_command()` - Call Bedrock with prompts
  - `execute_search_book_summaries_command()` - TODO: Implement
  - `execute_search_corpus_command()` - Search chunks
  - `execute_create_course_command()` - TODO: Implement
  - `execute_create_sections_command()` - TODO: Implement
  - Preserves all command execution logic

### 3. Event Publisher
- **`event_publisher.py`** - Publish events to EventBridge
  - `publish_course_event()` - Generic event publisher
  - Specific publishers for each event type
  - Error handling and logging

### 4. Infrastructure (Terraform)
- **EventBridge Module** (`terraform/modules/eventbridge/`)
  - Custom bus: `docprof-course-events`
  - Event rules for all phases
  - Dead letter queue for failed events
  
- **Course State DynamoDB** (`terraform/modules/dynamodb-course-state/`)
  - Table: `docprof-dev-course-state`
  - TTL enabled (7 days)
  - Point-in-time recovery

### 5. Lambda Handlers
- **Course Request Handler** (`course_request_handler/handler.py`)
  - Entry point for course generation
  - Creates CourseState
  - Executes EmbedCommand
  - Publishes EmbeddingGeneratedEvent
  - Returns course_id for polling

## 🔄 In Progress

### EventBridge Targets
- Need to connect event rules to Lambda functions
- Need IAM permissions for Lambda → EventBridge publishing
- Need IAM permissions for EventBridge → Lambda invocation

## 📋 Remaining Lambda Handlers

### Phase 1: Embedding Generator
- Receives: EmbeddingGeneratedEvent
- Loads state from DynamoDB
- Calls: `handle_embedding_generated(state, embedding)`
- Executes: SearchBookSummariesCommand
- Publishes: BookSummariesFoundEvent

### Phase 2: Book Search Handler
- Receives: BookSummariesFoundEvent
- Loads state from DynamoDB
- Calls: `handle_book_summaries_found(state, books)`
- Calls: `generate_course_parts(state, books)`
- Executes: LLMCommand (courses.generate_parts)
- Publishes: PartsGeneratedEvent

### Phase 3: Parts Generator Handler
- Receives: PartsGeneratedEvent
- Loads state from DynamoDB
- Calls: `handle_parts_generated(state, parts_text)`
- Parses parts: `parse_parts_text()`
- Calls: `generate_part_sections(state, part_index=0)`
- Executes: LLMCommand (courses.expand_part)
- Publishes: PartSectionsGeneratedEvent

### Phase 4: Sections Generator Handler
- Receives: PartSectionsGeneratedEvent
- Loads state from DynamoDB
- Calls: `handle_part_sections_generated(state, sections_text, part_index)`
- If more parts: Calls `generate_part_sections()` for next part
- If all done: Publishes AllPartsCompleteEvent

### Phase 5: Outline Reviewer Handler
- Receives: AllPartsCompleteEvent
- Loads state from DynamoDB
- Calls: `check_and_review_outline(state)`
- If variance > 5%: Calls `review_and_adjust_outline()`
- Executes: LLMCommand (courses.review_outline)
- Publishes: OutlineReviewedEvent

### Phase 6: Course Storage Handler
- Receives: OutlineReviewedEvent
- Loads state from DynamoDB
- Calls: `handle_outline_reviewed(state, reviewed_text)`
- Calls: `parse_text_outline_to_database(state)`
- Executes: CreateCourseCommand, CreateSectionsCommand
- Publishes: CourseStoredEvent
- Deletes state from DynamoDB (course now in Aurora)

## 🔧 TODO: Database Operations

### Book Summary Search
- Need `book_summaries` table with:
  - `book_id` (UUID)
  - `book_title` (String)
  - `summary_json` (JSONB)
  - `embedding` (vector(1536))
- Function: `search_book_summaries(query_embedding, top_k, min_similarity)`

### Course Storage
- Need `courses` table:
  - `course_id`, `user_id`, `title`, `original_query`, `estimated_hours`, etc.
- Need `course_sections` table:
  - `section_id`, `course_id`, `order_index`, `title`, `learning_objectives`, etc.
- Functions: `store_course()`, `store_sections()`

## 📝 Next Steps

1. **Create remaining Lambda handlers** (one per phase)
2. **Add Terraform config** for all Lambda handlers
3. **Connect EventBridge rules to Lambda targets**
4. **Add IAM permissions** for EventBridge publishing/invocation
5. **Implement database operations** (book search, course storage)
6. **Write unit tests** for state manager and command executor
7. **Deploy and test** end-to-end workflow

## 🎯 Success Criteria

- [ ] State persists correctly across all phases
- [ ] All parsing logic works (parts, sections, outline)
- [ ] All prompt variables passed correctly
- [ ] Time validation triggers review when needed
- [ ] Error handling works (failed phases can retry)
- [ ] Full workflow completes successfully
