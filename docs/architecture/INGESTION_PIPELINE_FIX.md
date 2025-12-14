# Ingestion Pipeline Book ID Fix

**Date:** 2025-12-13
**Issue:** Duplicate book records created during ingestion

## Problem

When a book was uploaded through the UI and then processed:
1. `book_upload` Lambda created book record with `book_id` = `ac311e24-d9f5-4a3c-aa11-c7f9f49c428c`
2. PDF stored in S3 at `books/ac311e24-d9f5-4a3c-aa11-c7f9f49c428c/filename.pdf`
3. S3 event triggered `document_processor` Lambda
4. `document_processor` extracted `book_id` from S3 path correctly
5. BUT `_ensure_book_record` only checked by metadata (title/author/isbn), not by `book_id`
6. Since metadata might not match exactly, it created a NEW book record with a different UUID
7. Result: Two book records - one with metadata/cover, one with chunks/figures

## Root Cause

In `src/lambda/shared/ingestion_orchestrator.py`, the `_ensure_book_record` function:
- Called `database.find_book(metadata)` which only searches by title/author/isbn
- Did NOT check if a book with the provided `book_id` already exists
- Created a new book record even when one with the correct `book_id` existed

## Fix

Updated `_ensure_book_record` to use this logic:

1. **First**: Check if book with provided `book_id` exists using `database.get_book_by_id(book_id)`
   - If found and rebuild=False → use existing book_id
   - If found and rebuild=True → clear contents and use existing book_id

2. **Second**: If no book with that `book_id`, try to find by metadata (title/author/isbn)
   - Useful if book was created elsewhere with different ID

3. **Third**: Only if neither exists, create new book record
   - **Important**: Use the provided `book_id` instead of generating a new UUID
   - This ensures consistency throughout the pipeline

## Code Changes

**File**: `src/lambda/shared/ingestion_orchestrator.py`

**Function**: `_ensure_book_record`

**Key change**: Added `get_book_by_id()` check BEFORE `find_book()` check, and use provided `book_id` when creating new record.

## Expected Flow (After Fix)

1. User uploads PDF → `book_upload` creates book with `book_id` = `A`
2. PDF stored in S3 at `books/A/filename.pdf`
3. S3 event triggers `document_processor`
4. `document_processor` extracts `book_id` = `A` from S3 path
5. `run_ingestion_pipeline` called with `book_id` = `A`
6. `_ensure_book_record` checks `get_book_by_id(A)` → finds existing book
7. Uses existing book_id `A` for all chunks/figures
8. **Result**: Single book record with metadata, cover, chunks, and figures ✅

## Testing

Before deploying:
1. Clean database: `python3 scripts/clean_database.py`
2. Upload new book through UI
3. Verify single book_id used throughout
4. Verify chunks/figures associated with correct book_id

## Deployment

The fix is in the shared code layer, so no Lambda redeployment needed initially. However, you should:
1. Deploy the updated shared code layer
2. Test with a clean database
3. Monitor CloudWatch logs to confirm single book_id usage

