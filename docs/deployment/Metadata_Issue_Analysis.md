# Metadata Issue Analysis

## Problem

Book metadata (title, author, edition) is showing as "Unknown" in the database, even though it was uploaded with proper metadata.

## Root Cause

**S3 Metadata Key Mismatch**:
- S3 metadata keys are prefixed with `book-`: `book-title`, `book-author`, `book-edition`, `book-isbn`
- Lambda handler was looking for unprefixed keys: `title`, `author`, `edition`, `isbn`
- Result: All metadata defaults to `None` or `'Unknown'`

## Impact Assessment

### ✅ Book Record (Fixable)
- **Current**: Title = "Unknown", Author = None
- **Impact**: Low - book record can be updated after ingestion
- **Fix**: Update handler to normalize S3 metadata keys

### ✅ Chunks (No Impact)
- **Chunks don't store book title directly**
- **Chunks store**: `book_id` (foreign key to books table)
- **Book title accessible via**: `JOIN books ON chunks.book_id = books.book_id`
- **Conclusion**: Chunks are fine - they reference book_id correctly

### ✅ Retrieval/Search (No Impact)
- Vector search uses `book_id` filter, not book title
- Chat/QA can join with books table to get title
- No functional impact on search/retrieval

## Fix Applied

Updated `src/lambda/document_processor/handler.py` to normalize S3 metadata keys:

```python
# Extract metadata from S3 object metadata
# S3 metadata keys are prefixed with 'book-' (e.g., 'book-title', 'book-author')
s3_metadata = pdf_response.get('Metadata', {})
book_id = s3_metadata.get('book-id', object_key.split('/')[1])

# Normalize S3 metadata keys (remove 'book-' prefix) for MAExpert compatibility
metadata = {
    'title': s3_metadata.get('book-title', 'Unknown'),
    'author': s3_metadata.get('book-author'),
    'edition': s3_metadata.get('book-edition'),
    'isbn': s3_metadata.get('book-isbn'),
    'extra': {
        'upload-timestamp': s3_metadata.get('upload-timestamp'),
        'book-id': book_id
    }
}
```

## Next Steps

1. ✅ **Fix applied** - Handler now correctly extracts metadata
2. ⏳ **Current ingestion** - Will continue with "Unknown" title (can't fix mid-run)
3. 🔄 **After ingestion** - Can update book record manually or re-ingest
4. ✅ **Future uploads** - Will have correct metadata

## Recommendation

**Option 1: Update current book record** (Quick fix)
```sql
UPDATE books 
SET title = 'Valuation: Measuring and Managing the Value of Companies',
    author = 'Tim Koller, Marc Goedhart, David Wessels',
    edition = '8th Edition',
    isbn = '978-1119610886'
WHERE book_id = '64A0CAB4-5585-4474-80CF-A1F79C0158B8';
```

**Option 2: Let ingestion finish, then update** (Safer)
- Current ingestion is 20% complete
- Can update book record after completion
- No need to re-ingest (chunks are fine)

**Option 3: Re-ingest after fix** (Cleanest, but wasteful)
- Wait for current ingestion to finish
- Delete book and re-ingest with fixed handler
- Ensures everything is correct, but wastes LLM calls

## Conclusion

✅ **Chunks are fine** - They reference book_id correctly  
✅ **Fix applied** - Future uploads will have correct metadata  
⚠️ **Current book** - Title is "Unknown" but can be updated manually  
✅ **No functional impact** - Search/retrieval works via book_id

---

**Status**: Fixed for future uploads  
**Action**: Update current book record after ingestion completes

