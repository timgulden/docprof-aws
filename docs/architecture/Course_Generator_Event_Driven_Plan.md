# Course Generator Event-Driven Architecture Plan

## Principle: Preserve All Intentional Complexity

**Goal**: Implement event-driven architecture as a **structural change** (how phases communicate), not a **logical simplification** (what each phase does).

Every validation, parsing strategy, context variable, and error handling exists for a reason. We must preserve it all.

---

## Event-Driven Architecture Design

### Event Flow

```
User Request (POST /courses)
    ↓
Course Request Handler Lambda
    ↓ Publishes: CourseRequestedEvent
    ↓
EventBridge Custom Bus: docprof-course-events
    ↓ Rule: course.requested → Embedding Generator Lambda
    ↓
Embedding Generator Lambda
    - Executes: EmbedCommand
    - Generates embedding
    - Loads CourseState from DynamoDB
    - Calls: handle_embedding_generated(state, embedding)
    - Saves updated CourseState to DynamoDB
    ↓ Publishes: EmbeddingGeneratedEvent
    ↓
EventBridge
    ↓ Rule: embedding.generated → Book Search Lambda
    ↓
Book Search Lambda
    - Executes: SearchBookSummariesCommand
    - Searches Aurora (vector similarity)
    - Loads CourseState from DynamoDB
    - Calls: handle_book_summaries_found(state, books)
    - Saves updated CourseState to DynamoDB
    ↓ Publishes: BookSummariesFoundEvent
    ↓
EventBridge
    ↓ Rule: book.summaries.found → Parts Generator Lambda (Phase 1)
    ↓
Parts Generator Lambda (Phase 1)
    - Loads CourseState from DynamoDB
    - Calls: generate_course_parts(state, books)
    - Executes: LLMCommand (courses.generate_parts)
    - Parses response: parse_parts_text()
    - Calls: handle_parts_generated(state, parts_text)
    - Saves updated CourseState to DynamoDB
    ↓ Publishes: PartsGeneratedEvent
    ↓
EventBridge
    ↓ Rule: parts.generated → Sections Generator Lambda (Phase 2-N)
    ↓
Sections Generator Lambda (Phase 2-N) - ONE PER PART
    - Loads CourseState from DynamoDB
    - Calls: generate_part_sections(state, part_index)
    - Executes: LLMCommand (courses.expand_part)
    - Parses response
    - Calls: handle_part_sections_generated(state, sections_text, part_index)
    - Appends to outline_text
    - If more parts: Publishes PartSectionsGeneratedEvent (triggers next part)
    - If all done: Publishes AllPartsCompleteEvent
    ↓
EventBridge
    ↓ Rule: all.parts.complete → Outline Reviewer Lambda (Phase N+1)
    ↓
Outline Reviewer Lambda (Phase N+1)
    - Loads CourseState from DynamoDB
    - Calls: check_and_review_outline(state)
    - If variance > 5%: Calls review_and_adjust_outline()
    - Executes: LLMCommand (courses.review_outline)
    - Calls: handle_outline_reviewed(state, reviewed_text)
    - Saves updated CourseState to DynamoDB
    ↓ Publishes: OutlineReviewedEvent
    ↓
EventBridge
    ↓ Rule: outline.reviewed → Course Storage Lambda
    ↓
Course Storage Lambda
    - Loads CourseState from DynamoDB
    - Calls: parse_text_outline_to_database(state)
    - Executes: CreateCourseCommand, CreateSectionsCommand
    - Stores Course + CourseSections in Aurora
    - Saves final CourseState to DynamoDB
    ↓ Publishes: CourseStoredEvent
    ↓
User polls: GET /courses/{course_id} → Returns course status
```

---

## State Persistence Strategy

### DynamoDB Table: `docprof-dev-course-state`

**Key**: `course_id` (UUID generated at request time)

**Attributes**:
- All fields from `CourseState` model:
  - `session_id` (String)
  - `pending_course_query` (String)
  - `pending_course_hours` (Number)
  - `pending_course_prefs` (Map) - CoursePreferences as JSON
  - `book_summaries_json` (String) - JSON string of book summaries
  - `parts_list` (List) - Parsed parts structure
  - `current_part_index` (Number)
  - `outline_text` (String) - Incrementally built outline
  - `outline_complete` (Boolean)
  - `current_course` (Map) - Course model as JSON
  - `current_section` (Map) - CourseSection model as JSON
  - `current_section_draft` (String)
  - `selected_lecture_figures` (List)
  - `covered_objectives` (List)
  - `previous_lectures_context` (String)
  - `course_outline_context` (String)
  - `is_revision` (Boolean)
  - `status` (String) - "generating", "reviewing", "storing", "complete", "error"
  - `error_message` (String) - If status is "error"
  - `created_at` (String) - ISO timestamp
  - `updated_at` (String) - ISO timestamp
  - `ttl` (Number) - For auto-cleanup (7 days)

**Why DynamoDB**:
- Fast reads/writes for state updates
- TTL for automatic cleanup
- Scales automatically
- No connection pooling needed

---

## Lambda Handler Pattern

Each Lambda handler follows this pattern:

```python
def lambda_handler(event, context):
    """
    Handler for [Phase Name].
    
    Event format (from EventBridge):
    {
        "source": "docprof.course",
        "detail-type": "[EventType]",
        "detail": {
            "course_id": "...",
            "state": {...},  # Full CourseState or reference
            "data": {...}    # Phase-specific data
        }
    }
    """
    try:
        # 1. Extract course_id and load state from DynamoDB
        course_id = event['detail']['course_id']
        state_dict = load_course_state(course_id)
        state = dict_to_course_state(state_dict)
        
        # 2. Create event object from EventBridge event
        course_event = create_event_from_detail(event['detail'])
        
        # 3. Call pure logic function (from shared/logic/courses.py)
        result = reduce_course_event(state, course_event)
        
        # 4. Execute commands (effects)
        for command in result.commands:
            execute_command(command, state)
        
        # 5. Save updated state to DynamoDB
        updated_dict = course_state_to_dict(result.new_state)
        save_course_state(course_id, updated_dict)
        
        # 6. Publish next event(s) to EventBridge
        publish_next_events(result.new_state, commands_executed)
        
        return {"statusCode": 200}
        
    except Exception as e:
        # Update state with error
        update_state_error(course_id, str(e))
        # Publish error event
        publish_error_event(course_id, str(e))
        raise
```

---

## Critical Preservation Requirements

### 1. State Field Preservation

**MUST preserve all CourseState fields**:
- Don't flatten nested structures
- Don't omit "optional" fields
- Preserve JSON strings (book_summaries_json)
- Preserve lists (parts_list, covered_objectives)

**Implementation**:
- Use Pydantic `model_dump_json()` for serialization
- Use `model_validate_json()` for deserialization
- Store as DynamoDB Map/List types (not JSON strings)

### 2. Parsing Logic Preservation

**MUST preserve all parsing functions exactly**:
- `parse_parts_text()` - All regex patterns, validation logic
- `parse_outline_total_time()` - All three parsing strategies
- `parse_text_outline_to_database()` - Complex outline parsing

**Implementation**:
- Copy parsing functions directly (no changes)
- Test with same edge cases
- Preserve all regex patterns

### 3. Prompt Variable Preservation

**MUST pass all prompt variables**:
- Phase 1: query, hours, target_minutes, summaries_context, parts_guidance, parts_count_guidance
- Phase 2-N: query, book_summaries_context, existing_outline, remaining_text, part_index, part_title, part_minutes
- Phase N+1: query, hours, target_total, book_summaries_context, outline_text, current_total, variance_percent, min_acceptable, max_acceptable

**Implementation**:
- Extract prompt variables from state exactly as original code does
- Don't simplify or omit variables
- Preserve dynamic guidance calculation

### 4. Time Validation Preservation

**MUST preserve all time validation**:
- 5% tolerance check
- Variance calculation
- Acceptable range (95%-105%)
- Multiple parsing strategies

**Implementation**:
- Copy validation logic exactly
- Use same thresholds
- Preserve warning vs error distinction

### 5. Context Building Preservation

**MUST preserve all context building**:
- `format_previous_lectures()` - Section markers, delivery mapping
- `format_course_outline()` - Part/section hierarchy
- Incremental outline building
- Book summaries JSON formatting

**Implementation**:
- Copy context formatting functions exactly
- Preserve all formatting details
- Don't simplify structure

### 6. Error Handling Preservation

**MUST preserve all error handling**:
- Parse failures → Return error message
- Empty results → Return early with message
- State validation → Check all conditions
- Time mismatches → Warn but continue

**Implementation**:
- Copy all validation checks
- Preserve exact error messages
- Maintain same error → state flow

---

## Implementation Checklist

### Phase 1: Infrastructure Setup

- [ ] Create DynamoDB table for course state
- [ ] Create EventBridge custom bus: `docprof-course-events`
- [ ] Create EventBridge rules for each event type
- [ ] Create IAM roles for Lambda → EventBridge publishing
- [ ] Create IAM roles for Lambda → DynamoDB access

### Phase 2: State Management

- [ ] Create `course_state_manager.py` in `shared/`
  - `load_course_state(course_id)` → CourseState
  - `save_course_state(course_id, state)` → void
  - `dict_to_course_state(dict)` → CourseState
  - `course_state_to_dict(state)` → dict
- [ ] Test state serialization/deserialization
- [ ] Verify all fields preserved

### Phase 3: Command Executor

- [ ] Create `command_executor.py` in `shared/`
  - `execute_command(command, state)` → result
  - Handles: EmbedCommand, LLMCommand, SearchBookSummariesCommand, etc.
- [ ] Integrate with Bedrock client
- [ ] Integrate with DB utils (book search)
- [ ] Test each command type

### Phase 4: Event Publishers

- [ ] Create `event_publisher.py` in `shared/`
  - `publish_course_event(event_type, course_id, data)` → void
- [ ] Create event objects from logic results
- [ ] Test event publishing

### Phase 5: Lambda Handlers

- [ ] Course Request Handler (entry point)
- [ ] Embedding Generator Handler
- [ ] Book Search Handler
- [ ] Parts Generator Handler (Phase 1)
- [ ] Sections Generator Handler (Phase 2-N)
- [ ] Outline Reviewer Handler (Phase N+1)
- [ ] Course Storage Handler

### Phase 6: Testing

- [ ] Unit tests for state serialization
- [ ] Unit tests for command executor
- [ ] Integration tests for each Lambda
- [ ] E2E test: Full course generation workflow
- [ ] Edge case tests (parsing failures, time mismatches)

---

## Key Implementation Details

### State Serialization

```python
# Convert CourseState to DynamoDB dict
def course_state_to_dict(state: CourseState) -> Dict[str, Any]:
    """Preserve all fields, handle nested models."""
    return {
        'course_id': state.session_id,  # Use session_id as course_id
        'pending_course_query': state.pending_course_query,
        'pending_course_hours': state.pending_course_hours,
        'pending_course_prefs': state.pending_course_prefs.model_dump() if state.pending_course_prefs else None,
        'book_summaries_json': state.book_summaries_json,  # Keep as JSON string
        'parts_list': state.parts_list,  # List of dicts
        'current_part_index': state.current_part_index,
        'outline_text': state.outline_text,  # Incrementally built
        'outline_complete': state.outline_complete,
        # ... all other fields
        'updated_at': datetime.utcnow().isoformat(),
        'ttl': int(time.time()) + (7 * 24 * 60 * 60),  # 7 days
    }

# Convert DynamoDB dict to CourseState
def dict_to_course_state(state_dict: Dict[str, Any]) -> CourseState:
    """Reconstruct CourseState with all fields."""
    # Handle nested models
    prefs_dict = state_dict.get('pending_course_prefs')
    prefs = CoursePreferences(**prefs_dict) if prefs_dict else CoursePreferences()
    
    return CourseState(
        session_id=state_dict.get('course_id'),
        pending_course_query=state_dict.get('pending_course_query'),
        pending_course_hours=state_dict.get('pending_course_hours'),
        pending_course_prefs=prefs,
        book_summaries_json=state_dict.get('book_summaries_json'),
        parts_list=state_dict.get('parts_list', []),
        current_part_index=state_dict.get('current_part_index', 0),
        outline_text=state_dict.get('outline_text', ''),
        outline_complete=state_dict.get('outline_complete', False),
        # ... all other fields
    )
```

### Event Payload Structure

```python
# EventBridge event format
{
    "source": "docprof.course",
    "detail-type": "PartsGenerated",
    "detail": {
        "course_id": "uuid-here",
        "parts_text": "...",  # LLM response
        "state_snapshot": {...}  # Optional: full state if needed
    }
}

# Lambda handler extracts course_id, loads full state from DynamoDB
# Then creates event object and calls logic
```

### Command Execution

```python
def execute_command(command: Command, state: CourseState) -> Any:
    """Execute command and return result."""
    if isinstance(command, EmbedCommand):
        embedding = generate_embeddings(command.text)
        return {'embedding': embedding}
    
    elif isinstance(command, LLMCommand):
        if command.prompt_name:
            # Get prompt from registry
            prompt = get_prompt(command.prompt_name, command.prompt_variables)
        else:
            prompt = command.prompt
        
        response = invoke_claude(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=command.max_tokens,
            temperature=command.temperature,
            stream=False
        )
        return {'content': response.get('content', '')}
    
    elif isinstance(command, SearchBookSummariesCommand):
        books = search_book_summaries(
            query_embedding=command.query_embedding,
            top_k=command.top_k,
            min_similarity=command.min_similarity
        )
        return {'books': books}
    
    # ... other command types
```

---

## Validation Strategy

### Before Each Phase

1. **Load state** → Verify all expected fields present
2. **Validate state** → Check state is valid for this phase
3. **Log state** → For debugging (redact sensitive data)

### After Each Phase

1. **Validate result** → Check logic result is valid
2. **Save state** → Verify all fields saved
3. **Publish event** → Verify event published successfully
4. **Log transition** → Log phase completion

### Error Scenarios

1. **State missing** → Return error, don't proceed
2. **Parse failure** → Update state with error, publish error event
3. **Command failure** → Retry with exponential backoff
4. **Event publish failure** → Retry, then DLQ

---

## Testing Requirements

### Unit Tests

- [ ] State serialization/deserialization preserves all fields
- [ ] Parsing functions handle all edge cases
- [ ] Prompt variable extraction works correctly
- [ ] Time validation logic preserved

### Integration Tests

- [ ] Each Lambda handler loads/saves state correctly
- [ ] Events published and received correctly
- [ ] Commands execute correctly
- [ ] State transitions work correctly

### E2E Tests

- [ ] Full course generation workflow
- [ ] State persists across all phases
- [ ] Error handling works correctly
- [ ] Time validation triggers review when needed

---

## Success Criteria

✅ **Functional Equivalence**:
- Same prompts used with same variables
- Same parsing logic with same edge cases
- Same validation logic with same thresholds
- Same error messages

✅ **State Preservation**:
- All state fields preserved across phases
- No data loss between Lambda invocations
- State can be inspected/debugged at any phase

✅ **Performance**:
- Each phase completes in < 30 seconds
- State load/save < 100ms
- Event publishing < 50ms

✅ **Reliability**:
- Failed phases can be retried independently
- State survives Lambda failures
- Errors are logged and recoverable

---

## Next Steps

1. **Create state manager** - DynamoDB CRUD for CourseState
2. **Create command executor** - Execute all command types
3. **Create event publisher** - Publish events to EventBridge
4. **Create first Lambda handler** - Course Request Handler
5. **Test state persistence** - Verify state survives Lambda invocations
6. **Add remaining handlers** - One phase at a time
7. **Test full workflow** - E2E test
