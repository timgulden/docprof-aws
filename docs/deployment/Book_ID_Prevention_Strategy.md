# Book ID Consistency Prevention Strategy

## Problem Summary

MAExpert's `run_ingestion_pipeline` calls `database.find_book()` which matches by metadata (title/author/edition/isbn). If metadata doesn't match exactly, it creates a new book with a new `book_id`, causing chunks to be split across multiple books.

## Root Cause

**Handler flow**:
1. Extracts `book_id` from S3 metadata (`64A0CAB4...`)
2. Passes it to MAExpert pipeline
3. **MAExpert ignores this and calls `find_book(metadata)`**
4. If match found → uses that `book_id` (could be different!)
5. If no match → creates new book with NEW `book_id`
6. Chunks use MAExpert's determined `book_id`, NOT the S3 upload ID

## Current `find_book` Logic

MAExpert's `find_book()` matches on:
- `title` (exact match)
- `author` (exact match)
- `edition` (exact match)
- `isbn` (exact match)

**Problem**: If any field differs slightly, it creates a new book.

## Prevention Options

### Option A: Use S3 `book-id` Directly (Recommended)

**Modify handler to**:
1. Extract `book-id` from S3 metadata
2. Check if book exists with that `book_id`
3. If exists → use it (update metadata if needed)
4. If not → create book with that `book_id` (don't let MAExpert generate new one)

**Pros**: 
- Consistent `book_id` across uploads
- No duplicate books
- Chunks always reference correct book

**Cons**:
- Requires modifying handler logic
- Need to handle case where `book-id` not provided

### Option B: Improve `find_book` Matching

**Make `find_book` more flexible**:
- Fuzzy matching on title (handle minor variations)
- Normalize author names (handle comma/space differences)
- Case-insensitive matching

**Pros**:
- Works with existing MAExpert code
- Handles metadata variations

**Cons**:
- Still relies on metadata matching
- Could match wrong book if titles are similar

### Option C: Force `book_id` in MAExpert Pipeline

**Modify MAExpert's `run_ingestion_pipeline`**:
- Add optional `force_book_id` parameter
- If provided, use it instead of calling `find_book()`

**Pros**:
- Most reliable
- Guarantees `book_id` consistency

**Cons**:
- Requires modifying MAExpert code (we're trying to reuse as-is)
- More invasive change

## Recommended Solution

**Option A + B Hybrid**:
1. **Primary**: Use S3 `book-id` if provided
   - Check if book exists with that ID
   - If yes → use it (update metadata)
   - If no → create with that ID
2. **Fallback**: If no `book-id` in S3 metadata, use `find_book()` with improved matching

**Implementation**:
```python
# In handler.py, before calling MAExpert pipeline:
s3_book_id = s3_metadata.get('book-id')

if s3_book_id:
    # Check if book exists with this ID
    existing_book = database.get_book_by_id(s3_book_id)
    if existing_book:
        book_id = s3_book_id  # Use existing book
        # Update metadata if needed
        database.update_book_metadata(s3_book_id, metadata)
    else:
        # Create book with S3 book_id
        book_id = database.insert_book_with_id(s3_book_id, metadata, pdf_data)
else:
    # Fallback: Let MAExpert determine book_id via find_book()
    book_id = None  # Will be determined by MAExpert
```

## Current Status

✅ **Immediate fix**: Merged duplicate books  
✅ **Data consistency**: All chunks reference same `book_id`  
⚠️ **Prevention**: Need to implement Option A to prevent future duplicates

---

**Next Steps**: Implement Option A in handler to ensure future uploads use consistent `book_id`

