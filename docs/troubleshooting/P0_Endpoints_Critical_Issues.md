# P0 Endpoints - Critical Issues Found

**Date:** 2025-01-XX  
**Severity:** HIGH - Must fix before deployment  
**Status:** Identified during Max mode review

---

## Critical Issues

### 1. ❌ Missing `section_deliveries` Table

**Impact:** HIGH - `section_lecture_handler` will fail on first invocation

**Problem:**
- `section_lecture_handler` queries `section_deliveries` table (line 149-156)
- `schema_init/handler.py` does NOT create this table
- Table is referenced in MAExpert code but never created in AWS version

**Evidence:**
```python
# section_lecture_handler/handler.py line 149
cur.execute("""
    SELECT delivery_id, section_id, user_id, lecture_script,
           delivered_at, duration_actual_minutes, user_notes, style_snapshot
    FROM section_deliveries
    WHERE section_id = %s::uuid AND user_id = %s::uuid
    ...
""")
```

**Schema needed:**
```sql
CREATE TABLE IF NOT EXISTS section_deliveries (
    delivery_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id UUID NOT NULL REFERENCES course_sections(section_id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    lecture_script TEXT NOT NULL,
    delivered_at TIMESTAMP DEFAULT NOW(),
    duration_actual_minutes INTEGER,
    user_notes TEXT,
    style_snapshot JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS deliveries_section_idx ON section_deliveries(section_id);
CREATE INDEX IF NOT EXISTS deliveries_user_idx ON section_deliveries(user_id, section_id);
```

**Fix Required:**
1. Add `section_deliveries` table to `schema_init/handler.py`
2. Add alongside `courses` and `course_sections` table creation (~line 156)

---

### 2. ❌ `StoreLectureCommand` Not Implemented

**Impact:** HIGH - Lecture storage will fail silently

**Problem:**
- Logic layer emits `StoreLectureCommand` to save lectures
- Command executor has stub implementation that only logs warning
- Lectures won't be saved to database

**Evidence:**
```python
# src/lambda/shared/command_executor.py line 458
def execute_store_lecture_command(command: StoreLectureCommand) -> Dict[str, Any]:
    """Execute StoreLectureCommand - store lecture delivery."""
    try:
        logger.warning("StoreLectureCommand not yet implemented")
        return {
            'status': 'success',  # Lies! Not actually stored
            'delivery_id': command.delivery.delivery_id,
        }
```

**Fix Required:**
Implement `execute_store_lecture_command`:
```python
def execute_store_lecture_command(command: StoreLectureCommand) -> Dict[str, Any]:
    """Execute StoreLectureCommand - store lecture delivery to database."""
    try:
        delivery = command.delivery
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO section_deliveries (
                        delivery_id, section_id, user_id, lecture_script,
                        delivered_at, duration_actual_minutes, user_notes, style_snapshot
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (delivery_id) DO UPDATE SET
                        lecture_script = EXCLUDED.lecture_script,
                        delivered_at = EXCLUDED.delivered_at,
                        duration_actual_minutes = EXCLUDED.duration_actual_minutes,
                        user_notes = EXCLUDED.user_notes,
                        style_snapshot = EXCLUDED.style_snapshot
                    RETURNING delivery_id
                """, (
                    delivery.delivery_id,
                    delivery.section_id,
                    delivery.user_id,
                    delivery.lecture_script,
                    delivery.delivered_at,
                    delivery.duration_actual_minutes,
                    delivery.user_notes,
                    json.dumps(delivery.style_snapshot)
                ))
                delivery_id = cur.fetchone()[0]
                conn.commit()
        
        return {
            'status': 'success',
            'delivery_id': str(delivery_id),
        }
    except Exception as e:
        logger.error(f"Error storing lecture: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e)
        }
```

---

### 3. ⚠️ Lecture Generation Trigger Not Implemented

**Impact:** MEDIUM - Returns 202 but doesn't actually start generation

**Problem:**
- `section_lecture_handler` returns 202 when lecture doesn't exist
- Comment says "TODO: Implement actual async trigger"
- Frontend will poll for status but nothing will happen

**Evidence:**
```python
# section_lecture_handler/handler.py line 187
# Lecture doesn't exist - trigger async generation
logger.info(f"Lecture not found for section {section_id_db}, triggering generation")

# TODO: Implement actual async trigger via EventBridge or direct Lambda invocation

return http_response(202, {
    "message": "Lecture generation in progress",
    ...
})
```

**Current Behavior:**
1. Frontend requests lecture
2. Handler returns 202 "generating..."
3. Frontend polls status
4. **Nothing actually happens** - lecture never generates
5. Frontend polls forever

**Fix Options:**

**Option A: Synchronous Generation (Simple)**
- Generate lecture inline (30-60 seconds)
- Increase Lambda timeout to 120s
- Return 200 with lecture when done
- Frontend doesn't need to poll

**Option B: Async via Direct Invocation**
- Invoke `section_lecture_generator` Lambda asynchronously
- Lambda generates and stores lecture
- Frontend polls for completion

**Option C: Async via EventBridge**
- Publish `SectionLectureRequested` event
- Event handler generates lecture
- Frontend polls for completion

**Recommended:** Option A for P0 (simpler, fewer moving parts)

---

### 4. ⚠️ Missing QA Tables

**Impact:** LOW for P0 (not used yet)

**Problem:**
- `QASession` model exists in code
- No database tables for Q&A storage
- Will be needed for P3 (lecture Q&A feature)

**Tables Needed (for future):**
```sql
CREATE TABLE IF NOT EXISTS qa_sessions (
    qa_session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id UUID NOT NULL REFERENCES course_sections(section_id) ON DELETE CASCADE,
    delivery_id UUID REFERENCES section_deliveries(delivery_id) ON DELETE SET NULL,
    user_id UUID NOT NULL,
    started_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP,
    lecture_position_seconds INTEGER,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS qa_messages (
    qa_message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    qa_session_id UUID NOT NULL REFERENCES qa_sessions(qa_session_id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    chunk_index INTEGER,
    sources JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Fix Required:** Add to schema_init (can defer to Phase 4)

---

## Compatibility with Existing Tests

### ✅ Course Generation Workflow Still Works

The existing event-driven course generation is **NOT affected**:
- `POST /courses` → `course_request_handler` ✅
- EventBridge events ✅
- 6-phase generation pipeline ✅
- Course storage in Aurora ✅
- DynamoDB state management ✅

**New endpoints** are **additions**, not modifications.

### ⚠️ Test Coverage Gaps

**What's tested:**
- Course creation and storage
- Event-driven workflow
- DynamoDB state persistence

**What's NOT tested:**
- Course outline retrieval
- Section lecture retrieval/generation
- Section completion tracking
- User-specific course filtering

**Recommendation:** Add integration tests for new endpoints after fixes applied.

---

## Recommended Fix Priority

### Must Fix Before Deployment (CRITICAL)

1. **Add `section_deliveries` table to schema_init** - 15 minutes
   - Without this, `section_lecture_handler` will crash immediately

2. **Implement `StoreLectureCommand` execution** - 30 minutes  
   - Without this, lectures won't be saved

3. **Implement lecture generation trigger** - 2 hours (Option A) or 4 hours (Option B/C)
   - Without this, feature is non-functional

### Can Defer (for Phase 4)

4. **Add QA tables** - Only needed for lecture Q&A feature (Phase 4/P3)

---

## Additional Improvements Found

### 1. ✅ Good: User Isolation Pattern

All handlers properly extract `user_id` from Cognito token and filter by user. This prevents users from accessing other users' courses.

### 2. ✅ Good: Error Handling

Handlers have comprehensive try/catch and return proper HTTP status codes (400, 403, 404, 500).

### 3. ✅ Good: Parts Hierarchy Logic

`course_outline_handler` correctly builds hierarchical parts structure from flat sections.

### 4. ⚠️ Potential Issue: Empty Parts

If a course has no parts (all sections are top-level), the parts array will be empty. Frontend should handle this gracefully.

**Test Case:**
```python
# Course with no hierarchical structure
sections = [
    {"section_id": "1", "parent_section_id": None, "title": "Section 1"},
    {"section_id": "2", "parent_section_id": None, "title": "Section 2"},
]
# Result: parts = []
```

**Fix:** Update `build_parts_hierarchy` to create default part if none exist.

### 5. ⚠️ Performance: N+1 Query Potential

`course_outline_handler` fetches course, then fetches all sections. This is fine for now but could be optimized with a JOIN.

**Current:** 2 queries
**Optimized:** 1 JOIN query

**Not critical for P0** - optimize later if needed.

---

## Action Plan

### Step 1: Fix Database Schema (15 min)
```bash
# Edit src/lambda/schema_init/handler.py
# Add section_deliveries table creation after course_sections
```

### Step 2: Implement StoreLectureCommand (30 min)
```bash
# Edit src/lambda/shared/command_executor.py
# Replace stub with actual implementation
```

### Step 3: Choose Lecture Generation Strategy (30 min discussion)
- **Simple:** Synchronous generation (Option A) - works but slower
- **Proper:** Async generation (Option B/C) - faster but more complex

### Step 4: Implement Chosen Strategy (2-4 hours)

### Step 5: Test End-to-End (1 hour)
- Create course (existing - should work)
- Get outline (new - test)
- Get lecture (new - test generation)
- Mark complete (new - test)

### Step 6: Deploy (30 min)

---

## Estimated Total Fix Time

- **Minimum (Option A):** 4-5 hours
- **Recommended (Option B):** 6-8 hours
- **Full (Option C):** 8-10 hours

---

## Decision Needed

**Should we:**
1. Fix all 3 critical issues before deployment? (Recommended)
2. Deploy with known limitations and fix iteratively?
3. Implement full async architecture now or defer?

**My recommendation:** Fix issues 1 & 2 (schema + command), implement Option A for issue 3 (synchronous generation for P0), then refactor to async in Phase 2.
