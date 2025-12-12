# Course Generation Flow: Step-by-Step Comparison

## Purpose
Compare our Lambda implementation step-by-step with MAExpert to ensure:
1. **Design Principle Adherence** - Follows FP patterns
2. **Functional Equivalence** - Produces same results as MAExpert

## Current Lambda Implementation Flow

### Step 1: User Request
**Input:**
```json
{
  "query": "Learn DCF valuation",
  "hours": 2.0,
  "preferences": {...}
}
```

**Handler Action:**
- Parse request body
- Create `CourseRequestedEvent`
- Call `reduce_course_event(state, CourseRequestedEvent)`

**Expected Logic Result:**
- `new_state`: State with `pending_course_query`, `pending_course_hours`
- `commands`: `[EmbedCommand(text=query, task="find_relevant_corpus")]`
- `ui_message`: "Analyzing your request..."

**✅ Status:** Implemented correctly

---

### Step 2: Embedding Generation
**Command:** `EmbedCommand(text=query)`

**Handler Action:**
- Execute `execute_command(EmbedCommand)`
- Get result: `{'status': 'success', 'embedding': [0.123, ...]}`
- **Current Issue:** Handler manually converts to `EmbeddingGeneratedEvent`
- Call `reduce_course_event(state, EmbeddingGeneratedEvent)`

**Expected Logic Result:**
- `new_state`: State with `pending_book_search: True`
- `commands`: `[SearchBookSummariesCommand(query_embedding=..., top_k=10, min_similarity=0.2)]`
- `ui_message`: "Searching knowledge base..."

**✅ Status:** Works, but handler does manual conversion

---

### Step 3: Book Summary Search
**Command:** `SearchBookSummariesCommand(query_embedding=..., top_k=10)`

**Handler Action:**
- Execute `execute_command(SearchBookSummariesCommand)`
- Get result: `{'status': 'success', 'books': [{book_id, book_title, summary_json, similarity}, ...]}`
- **Current Issue:** Handler manually converts to `BookSummariesFoundEvent`
- Call `reduce_course_event(state, BookSummariesFoundEvent)`

**Expected Logic Result:**
- `new_state`: State with `book_summaries_json` (stringified JSON), `pending_book_search: False`
- `commands`: `[LLMCommand(task="generate_course_parts", ...)]`
- `ui_message`: "Generating course outline..."

**✅ Status:** Works, but handler does manual conversion

---

### Step 4: Generate Course Parts (Phase 1)
**Command:** `LLMCommand(task="generate_course_parts", prompt=..., temperature=0.0)`

**Handler Action:**
- Execute `execute_command(LLMCommand)`
- Get result: `{'status': 'success', 'content': '{"parts": [...]}'}`
- **Current Issue:** Handler doesn't convert LLM result to event!
- **Problem:** Logic layer expects `PartsGeneratedEvent` but handler doesn't create it

**Expected Logic Result:**
- Should receive `PartsGeneratedEvent(parts_text=...)`
- `new_state`: State with parts structure
- `commands`: `[LLMCommand(task="generate_part_sections", part_index=0, ...), ...]`
- `ui_message`: "Expanding course sections..."

**❌ Status:** **BROKEN** - LLM result not converted to event

---

### Step 5: Generate Part Sections (Phase 2-N)
**Command:** `LLMCommand(task="generate_part_sections", part_index=0, ...)`

**Handler Action:**
- Execute `execute_command(LLMCommand)`
- Get result: `{'status': 'success', 'content': '{"sections": [...]}'}`
- **Current Issue:** Handler doesn't convert LLM result to event!
- **Problem:** Logic layer expects `PartSectionsGeneratedEvent` but handler doesn't create it

**Expected Logic Result:**
- Should receive `PartSectionsGeneratedEvent(sections_text=..., part_index=0)`
- `new_state`: State with sections for part 0
- `commands`: `[LLMCommand(task="generate_part_sections", part_index=1, ...)]` (next part)
- OR: `[AllPartsCompleteEvent]` if all parts done

**❌ Status:** **BROKEN** - LLM result not converted to event

---

### Step 6: All Parts Complete
**Event:** `AllPartsCompleteEvent`

**Handler Action:**
- Logic should generate this event when all parts have sections
- Handler should call `reduce_course_event(state, AllPartsCompleteEvent)`

**Expected Logic Result:**
- `new_state`: State with complete outline
- `commands`: `[LLMCommand(task="review_outline", ...)]` (Phase N+1)
- `ui_message`: "Reviewing course outline..."

**❌ Status:** **BROKEN** - Never reaches this step because Step 4/5 broken

---

### Step 7: Review Outline (Phase N+1)
**Command:** `LLMCommand(task="review_outline", ...)`

**Handler Action:**
- Execute `execute_command(LLMCommand)`
- Get result: `{'status': 'success', 'content': '{"reviewed_outline": {...}}'}`
- **Current Issue:** Handler doesn't convert LLM result to event!

**Expected Logic Result:**
- Should receive `OutlineReviewEvent(reviewed_outline_text=...)`
- `new_state`: State with reviewed outline
- `commands`: `[CreateCourseCommand(...)]` or `[StoreCourseCommand(...)]`
- `ui_message`: "Finalizing course..."

**❌ Status:** **BROKEN** - LLM result not converted to event

---

### Step 8: Store Course
**Command:** `CreateCourseCommand(...)` or `StoreCourseCommand(...)`

**Handler Action:**
- Execute `execute_command(CreateCourseCommand)`
- Get result: `{'status': 'success', 'course_id': '...'}`
- **Current Issue:** Handler doesn't convert to `CourseStoredEvent`

**Expected Logic Result:**
- Should receive `CourseStoredEvent`
- `new_state`: Final state
- `commands`: `[]` (empty - pipeline complete)
- `ui_message`: "Course created successfully!"

**❌ Status:** **BROKEN** - Command result not converted to event

---

## Critical Issues Found

### Issue 1: LLM Command Results Not Converted to Events
**Problem:** Handler executes LLM commands but doesn't convert results to events that logic layer expects.

**Impact:** Pipeline stops after book search. Course parts are never generated.

**Fix Needed:**
```python
elif isinstance(command, LLMCommand):
    if command_result.get('status') == 'success' and 'content' in command_result:
        # Determine event type based on command.task
        if command.task == 'generate_course_parts':
            event = PartsGeneratedEvent(parts_text=command_result['content'])
        elif command.task == 'generate_part_sections':
            part_index = command.prompt_variables.get('part_index', 0)
            event = PartSectionsGeneratedEvent(
                sections_text=command_result['content'],
                part_index=part_index
            )
        elif command.task == 'review_outline':
            event = OutlineReviewEvent(reviewed_outline_text=command_result['content'])
        else:
            logger.warning(f"Unknown LLM task: {command.task}")
            break
        
        # Continue pipeline
        current_result = reduce_course_event(current_state, event)
        current_state = current_result.new_state
```

### Issue 2: Missing Event Types
**Problem:** Some events may not be generated correctly (e.g., `AllPartsCompleteEvent`).

**Impact:** Pipeline may not progress correctly through all phases.

**Fix Needed:** Ensure logic layer properly generates `AllPartsCompleteEvent` when all parts have sections.

### Issue 3: Command Result → Event Mapping
**Problem:** Handler has manual if/elif blocks for each command type.

**Impact:** Violates DRY, hard to maintain, easy to miss cases.

**Fix Needed:** Create generic `command_result_to_event()` mapper function.

---

## What to Verify Against MAExpert

### Questions to Answer:
1. **Does MAExpert use the same event flow?**
   - `CourseRequestedEvent` → `EmbeddingGeneratedEvent` → `BookSummariesFoundEvent` → `PartsGeneratedEvent` → `PartSectionsGeneratedEvent` → `AllPartsCompleteEvent` → `OutlineReviewEvent` → `CourseStoredEvent`

2. **How does MAExpert handle LLM command results?**
   - Does it convert them to events automatically?
   - Is there a mapper function?
   - How does it determine event type from command task?

3. **What is the exact format of course output?**
   - JSON structure
   - Field names
   - Data types
   - Nested structures

4. **What are the exact prompts used?**
   - Phase 1: Generate parts
   - Phase 2-N: Generate sections
   - Phase N+1: Review outline
   - Are they identical to what we're using?

5. **What are the exact parameters?**
   - `top_k` for book search (we use 10)
   - `min_similarity` (we use 0.2)
   - Temperature for each phase
   - Max tokens for each phase

---

## Action Items

### Immediate Fixes Needed:
1. ✅ **Fix LLM command result → event conversion** in handler
2. ✅ **Add support for all LLM task types** (generate_course_parts, generate_part_sections, review_outline)
3. ✅ **Verify event flow matches MAExpert** (need to check MAExpert code)
4. ✅ **Test end-to-end flow** after fixes

### Verification Needed:
1. ⏳ **Compare prompts** with MAExpert
2. ⏳ **Compare output format** with MAExpert
3. ⏳ **Compare parameters** (top_k, min_similarity, temperature)
4. ⏳ **Test with same input** and compare outputs

---

## Next Steps

1. **Fix LLM event conversion** - Critical blocker
2. **Create command result mapper** - Improve architecture
3. **Compare with MAExpert** - Ensure functional equivalence
4. **Test end-to-end** - Verify same results
