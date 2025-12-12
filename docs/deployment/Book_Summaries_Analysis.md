# Book Summaries Analysis

## Current State

### Database Schema
- ✅ **`source_summaries` table exists** (created in `setup_database_schema.py`)
  - Columns: `summary_id`, `book_id`, `summary_json`, `generated_at`, `generated_by`, `version`, `metadata`
  - ❌ **NO `embedding` column** - Cannot do vector similarity search
  - ❌ **NO `book_title` column** - Title must be joined from `books` table

### Course Generator Expectations
- ❌ **Expects `book_summaries` table** (different name!)
- ✅ **Expects `embedding` column** for vector similarity search
- ✅ **Expects `book_title` column** for easy access
- ✅ **Expects `summary_json` column** (matches `source_summaries`)

## The Gap

1. **Table Name Mismatch**: 
   - Schema has: `source_summaries`
   - Code expects: `book_summaries`

2. **Missing Embedding Column**:
   - `source_summaries` has no `embedding` column
   - Course generator needs vector similarity search on book summaries

3. **Missing Book Title**:
   - `source_summaries` only has `book_id` (requires JOIN)
   - Course generator expects `book_title` directly in table

## What Needs to Happen

### Option 1: Create `book_summaries` Table (Recommended)
Create a new table specifically for course generation:
```sql
CREATE TABLE book_summaries (
    book_id UUID PRIMARY KEY REFERENCES books(book_id),
    book_title TEXT NOT NULL,
    summary_json JSONB NOT NULL,
    embedding vector(1536),  -- For vector similarity search
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX book_summaries_embedding_idx ON book_summaries 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);  -- Fewer lists since fewer books
```

### Option 2: Migrate `source_summaries` to `book_summaries`
- Add `embedding` column
- Add `book_title` column
- Rename table (or create view/alias)

### Option 3: Use `source_summaries` as-is
- Add `embedding` column to `source_summaries`
- Add `book_title` column (or use JOIN)
- Update course generator code to use `source_summaries`

## Book Summary Generation Process

**Question**: Are book summaries generated during ingestion?

**Current Evidence**:
- `source_summaries` table exists in schema
- No clear ingestion step that populates it
- Course generator expects summaries to exist

**Likely Answer**: Book summaries are a **separate post-ingestion step** that:
1. Takes ingested books
2. Generates summaries using LLM (Claude)
3. Generates embeddings for summaries
4. Stores in `book_summaries` (or `source_summaries`) table

## Next Steps

1. ✅ **Verify**: Check if `source_summaries` has any data
2. ✅ **Decide**: Choose table name (`book_summaries` vs `source_summaries`)
3. ⏳ **Create**: Add `book_summaries` table with embedding column (if needed)
4. ⏳ **Populate**: Generate summaries + embeddings for existing book(s)
5. ⏳ **Implement**: Book summary search in `command_executor.py`

## Recommendation

**Create `book_summaries` table** as a separate table optimized for course generation:
- Clear separation of concerns
- Optimized for vector search (fewer rows = smaller index)
- Can be populated independently from ingestion
- Matches course generator expectations
