# Course Generator Complexity Analysis

This document captures all intentional complexity in the course generation logic to ensure functional equivalence when implementing the event-driven architecture.

## Critical Logic Details

### 1. Time Accuracy Validation

**Location**: `parse_parts_text()`, `check_and_review_outline()`

**Intentional Complexity**:
- **5% tolerance** for parts total vs target minutes
- **Multiple parsing strategies** with fallbacks:
  1. Parse section times: `### Section N: Title - X minutes`
  2. Fallback to part totals: `Total for this part: X minutes`
  3. Final fallback: `Total: X minutes` at end
- **Variance calculation**: `abs(current_total - target_total) / target_total * 100`
- **Acceptable range**: 95% to 105% of target (5% tolerance on both sides)

**Why Important**: LLM outputs can be slightly off. The system tolerates small errors but triggers review if variance > 5%.

**Must Preserve**: All three parsing strategies, tolerance thresholds, variance calculation.

---

### 2. Course Length Guidance

**Location**: `generate_course_parts()`

**Intentional Complexity**:
- **< 2 hours**: "IMPORTANT: Courses under 2 hours should normally have only ONE part"
- **2-4 hours**: "Aim for 2-3 parts"
- **≥ 4 hours**: "Aim for 3-5 parts"
- **Part size limit**: No single part exceeds 2 hours (enforced in prompt)

**Why Important**: Different course lengths need different structures. Short courses shouldn't be artificially split.

**Must Preserve**: Exact guidance text, thresholds, part count ranges.

---

### 3. Incremental Outline Building

**Location**: `handle_parts_generated()`, `handle_part_sections_generated()`

**Intentional Complexity**:
- Outline text built **incrementally** across phases:
  1. Phase 1: Parts text → `outline_text = parts_text + "\n\n"`
  2. Phase 2-N: Each part's sections appended → `outline_text += sections_text + "\n\n"`
  3. Phase N+1: Review uses **full accumulated outline**
- **State tracking**: `current_part_index` tracks progress through parts
- **Context preservation**: Each phase sees:
  - `existing_outline` - What's been generated so far
  - `remaining_text` - What's coming next

**Why Important**: LLM needs context of what's already generated to maintain consistency and avoid duplication.

**Must Preserve**: Incremental building, state tracking, context passing.

---

### 4. Multi-Phase Prompt Construction

**Location**: `generate_course_parts()`, `generate_part_sections()`, `review_and_adjust_outline()`

**Intentional Complexity**:

**Phase 1 Variables**:
- `query`, `hours`, `target_minutes`
- `summaries_context` (JSON formatted book summaries)
- `parts_guidance` (dynamic based on course length)
- `parts_count_guidance` (dynamic)

**Phase 2-N Variables**:
- `query`, `book_summaries_context`
- `existing_outline` (accumulated so far)
- `remaining_text` (parts not yet expanded)
- `part_index` (1-based display index)
- `part_title`, `part_minutes`

**Phase N+1 Variables**:
- `query`, `hours`, `target_total`
- `book_summaries_context`
- `outline_text` (complete outline)
- `current_total`, `variance_percent`
- `min_acceptable`, `max_acceptable` (95%-105% range)

**Why Important**: Each phase needs specific context. Missing variables break prompt resolution.

**Must Preserve**: All prompt variables, exact variable names, dynamic guidance generation.

---

### 5. Error Handling and Validation

**Location**: Multiple functions

**Intentional Complexity**:

**Parse Validation**:
- `parse_parts_text()`: Returns empty list if parsing fails → triggers error message
- `parse_outline_total_time()`: Multiple regex fallbacks, returns 0 if nothing found
- Time validation: Warns if variance > 5% but continues

**State Validation**:
- Checks `if not books:` → returns error early
- Checks `if part_index >= len(state.parts_list):` → triggers review
- Checks `if not parts_list:` → returns error message

**Why Important**: Graceful degradation. System handles LLM output variations without crashing.

**Must Preserve**: All validation checks, error messages, fallback parsing strategies.

---

### 6. Lecture Generation Complexity

**Location**: `generate_section_lecture()`, `refine_section_lecture()`

**Intentional Complexity**:

**Context Building**:
- `format_previous_lectures()` - Formats completed sections for context
- `format_course_outline()` - Formats full outline
- `completed_context` - What's been covered (TODO: Query from DB)
- `part_context` - Context from same part

**Style Instructions**:
- **Podcast style**: "IMPORTANT: Style is 'podcast' - Present all material in an engaging podcast format..."
- **Additional notes**: User-provided custom instructions appended
- **Presentation style**: Passed through from preferences

**Refinement Process**:
- `generate_objective_content()` - Generate content for one objective
- `refine_section_lecture()` - Refine complete lecture for consistency
- Figure integration - Search for relevant figures, incorporate descriptions

**Why Important**: Lecture quality depends on:
- Consistent style throughout
- Context from previous sections
- Figure integration
- User preferences

**Must Preserve**: All context building, style instructions, refinement steps.

---

### 7. State Management Details

**Location**: Throughout `courses.py`

**Intentional Complexity**:

**CourseState Fields**:
- `pending_course_query` - User's original query
- `pending_course_hours` - Target duration
- `pending_course_prefs` - User preferences
- `book_summaries_json` - JSON string of book summaries (preserved across phases)
- `parts_list` - Parsed parts structure
- `current_part_index` - Progress tracker
- `outline_text` - Incrementally built outline
- `outline_complete` - Flag when all parts done

**State Updates**:
- **Immutable updates**: `state.model_copy(update={...})`
- **Incremental building**: `outline_text += new_content`
- **Progress tracking**: `current_part_index` increments

**Why Important**: State must persist across phases. Each phase reads previous state and updates it.

**Must Preserve**: All state fields, immutable update pattern, incremental building.

---

## Event-Driven Architecture Requirements

To preserve all this complexity, the event-driven architecture must:

### 1. State Persistence
- **Store CourseState in DynamoDB** between phases
- **Key**: `course_id` or `session_id`
- **Include all fields**: Don't lose any state data

### 2. Event Payload Completeness
- **Include full state** in events (or state reference)
- **Include all context**: books, outline_text, parts_list, etc.
- **Preserve parsing results**: Don't re-parse, pass parsed data

### 3. Phase Sequencing
- **Maintain order**: Parts must be expanded sequentially (or track dependencies)
- **Preserve context**: Each phase needs accumulated outline
- **Handle failures**: Retry individual phases without losing progress

### 4. Prompt Variable Preservation
- **Pass all variables**: Don't simplify or omit prompt variables
- **Preserve dynamic guidance**: Calculate guidance based on course length
- **Maintain JSON formatting**: Book summaries must be JSON strings

### 5. Error Handling Preservation
- **Keep all validations**: Parse validation, time validation, state checks
- **Preserve error messages**: Exact same user-facing messages
- **Maintain fallbacks**: Multiple parsing strategies

---

## Implementation Checklist

When implementing event-driven architecture:

- [ ] **State Storage**: DynamoDB table with all CourseState fields
- [ ] **Event Payloads**: Include full state or state reference in events
- [ ] **Phase Handlers**: Each handler preserves all logic from original functions
- [ ] **Prompt Variables**: All variables passed correctly to LLMCommand
- [ ] **Parsing Logic**: All parsing functions preserved exactly
- [ ] **Validation Logic**: All checks and error handling preserved
- [ ] **Context Building**: All context formatting functions preserved
- [ ] **State Updates**: Immutable update pattern maintained
- [ ] **Error Messages**: Exact same user-facing messages
- [ ] **Time Calculations**: All time validation logic preserved

---

## Testing Requirements

To ensure functional equivalence:

1. **Unit Tests**: Test all parsing functions with various LLM outputs
2. **Integration Tests**: Test full workflow with real state transitions
3. **Edge Cases**: Test with edge cases (empty books, parsing failures, time mismatches)
4. **State Persistence**: Verify state survives phase transitions
5. **Prompt Variables**: Verify all variables passed to prompts correctly

---

## Key Principle

**Don't simplify anything that was intentionally complex.** Every validation, every parsing strategy, every context variable exists for a reason. The event-driven architecture should be a **structural change** (how phases communicate), not a **logical simplification** (what each phase does).
