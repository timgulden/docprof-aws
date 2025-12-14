# Ingestion Pipeline Testing Strategy

**Status**: Ready for testing  
**Date**: 2025-12-12

---

## Testing Approach: Integration First, Then Unit Tests

### Why This Order?

1. **Verify Integration Works**: The biggest risk is that the pieces don't work together (async/await, AWS services, database connections)
2. **Pure Logic is Easy to Test**: The chunking functions have no side effects - perfect for unit tests, but lower risk
3. **Get Quick Feedback**: Integration test gives immediate feedback on whether the system works
4. **Then Add Safety Net**: Unit tests for pure logic are quick to write and provide ongoing confidence

---

## Phase 1: Integration Test (Do This First)

### Goal: Verify the end-to-end pipeline works

**Test**: Upload a small PDF and verify:
- [ ] Book record is created
- [ ] Cover is extracted and stored
- [ ] Text is extracted
- [ ] Chunks are created (~1 per page)
- [ ] Embeddings are generated (parallel)
- [ ] Chunks are stored in database
- [ ] Figures are extracted (if any)
- [ ] Figures are described (parallel)
- [ ] Figures are stored in database

**How to Test**:
1. Deploy updated Lambda
2. Upload a test PDF (10-20 pages is ideal)
3. Monitor CloudWatch logs
4. Check database directly

**Success Criteria**:
- No errors in logs
- All expected data in database
- Cover displays in frontend
- Can search for content from the book

**Time**: ~30 minutes

---

## Phase 2: Unit Tests for Pure Logic (Do After Integration Works)

### Goal: Test the pure chunking functions

**Why These First?**:
- No side effects = easy to test
- No AWS dependencies = fast tests
- High confidence = these are the core logic

**Functions to Test** (`shared/logic/chunking.py`):

1. **`build_page_chunks()`**
   - Test: Simple 3-page document
   - Verify: Creates 3 chunks
   - Verify: Overlap is correct (20% from adjacent pages)
   - Verify: Chunk boundaries are correct

2. **`build_chapter_chunks_simple()`**
   - Test: Text with chapter markers
   - Verify: Detects chapters correctly
   - Verify: Chapter boundaries are correct
   - Test: Text without chapters (should return empty list)

3. **`attach_content_hash()`**
   - Test: Adds hash to metadata
   - Verify: Hash is consistent for same content
   - Verify: Hash is different for different content

4. **`split_chunk_if_needed()`**
   - Test: Small chunk (no split needed)
   - Test: Large chunk (split into multiple)
   - Verify: Split chunks have correct metadata
   - Verify: Total content length preserved

5. **`build_figure_chunk()`**
   - Test: Basic figure chunk creation
   - Test: With key takeaways and use cases
   - Verify: Content format is correct

**Test File**: `tests/unit/test_chunking_logic.py`

**Time**: ~1-2 hours to write comprehensive tests

---

## Phase 3: Unit Tests for Orchestrator Functions (Optional)

### Goal: Test orchestrator logic with mocks

**Functions to Test** (`shared/ingestion_orchestrator.py`):

1. **`_expand_chunks()`**
   - Test: Expands chunks correctly
   - Test: Attaches hashes

2. **`_deduplicate_chunks()`**
   - Test: Removes duplicates
   - Test: Preserves non-duplicates

3. **`_filter_duplicate_figures()`**
   - Test: Filters by hash
   - Test: Preserves non-duplicates

**Note**: These require mocking AWS clients, so more complex. Lower priority.

---

## Recommended Order

### ✅ Step 1: Integration Test (Now)
- Deploy and test with real PDF
- Verify everything works end-to-end
- Fix any integration issues

### ✅ Step 2: Unit Tests for Pure Logic (After Integration Works)
- Write tests for `shared/logic/chunking.py`
- These are easy and high-value
- Provides ongoing confidence

### ⏸️ Step 3: Unit Tests for Orchestrator (Later)
- Mock AWS services
- Test orchestrator functions
- Lower priority since integration test covers this

---

## Quick Integration Test Script

```python
# tests/integration/test_ingestion_pipeline.py (to be created)
"""
Integration test for ingestion pipeline.

This test:
1. Uploads a test PDF
2. Waits for processing
3. Verifies data in database
"""

def test_ingestion_pipeline():
    # 1. Upload PDF via API
    # 2. Wait for processing (poll status)
    # 3. Query database
    # 4. Verify chunks, figures, cover
    pass
```

---

## Why This Approach?

1. **Fastest Path to Working System**: Integration test tells us immediately if it works
2. **Pure Logic Tests are Easy**: No mocking needed, fast to write
3. **Orchestrator Tests are Complex**: Require mocking AWS services, lower ROI
4. **Pragmatic**: Get it working, then add safety net

---

## Recommendation

**Do integration test first** - deploy and test with a real PDF. This gives immediate feedback on:
- Async/await works correctly
- AWS services are called correctly
- Database operations work
- Parallelization works

**Then add unit tests for pure logic** - these are quick wins and provide ongoing confidence.

**Skip orchestrator unit tests for now** - integration test covers this, and mocking AWS services is complex.

---

*This approach gets you a working system quickly, then adds tests where they provide the most value.*

