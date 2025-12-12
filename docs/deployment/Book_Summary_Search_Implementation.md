# Book Summary Search Implementation

## Summary

Implemented book summary search functionality for the course generator, enabling semantic search of source summaries to find relevant books for course generation.

## Changes Made

### 1. Implemented `execute_search_book_summaries_command`

**File:** `src/lambda/shared/command_executor.py`

- **Functionality**: Searches the `source_summaries` table using vector similarity (pgvector)
- **Query Logic**:
  - Gets the latest version of each book's summary (using CTE with DISTINCT ON)
  - Joins with `books` table to get book titles
  - Filters by minimum similarity threshold (`min_similarity`)
  - Orders by cosine similarity (most relevant first)
  - Limits to `top_k` results
- **Returns**: List of books with:
  - `book_id` (UUID)
  - `book_title` (from books table)
  - `summary_json` (JSONB with full summary)
  - `similarity` (cosine similarity score, 0-1)
  - `version` and `generated_at` (metadata)

**SQL Query Structure:**
```sql
WITH latest_summaries AS (
    SELECT DISTINCT ON (book_id)
        book_id, summary_json, embedding, version, generated_at
    FROM source_summaries
    WHERE embedding IS NOT NULL
    ORDER BY book_id, version DESC
)
SELECT 
    ls.book_id, b.title as book_title, ls.summary_json,
    1 - (ls.embedding <=> %s::vector) as similarity,
    ls.version, ls.generated_at
FROM latest_summaries ls
INNER JOIN books b ON ls.book_id = b.book_id
WHERE 1 - (ls.embedding <=> %s::vector) >= %s
ORDER BY ls.embedding <=> %s::vector
LIMIT %s
```

### 2. Updated Course Generator Handler

**File:** `src/lambda/course_generator/handler.py`

- **Pipeline Execution**: Implements iterative command execution pattern
- **Flow**:
  1. User requests course → `CourseRequestedEvent`
  2. Logic layer generates `EmbedCommand`
  3. Execute embedding → `EmbeddingGeneratedEvent`
  4. Logic layer generates `SearchBookSummariesCommand`
  5. Execute search → `BookSummariesFoundEvent`
  6. Logic layer generates `LLMCommand` for course parts
  7. Continue until pipeline completes
- **Features**:
  - Iterative command execution (max 20 iterations)
  - Proper event-driven pipeline continuation
  - Error handling and logging
  - State management throughout pipeline

**Key Improvements:**
- Properly executes `SearchBookSummariesCommand` using command executor
- Continues pipeline by creating `BookSummariesFoundEvent` with search results
- Logs book search results with similarity scores
- Handles empty results gracefully

## Integration Points

### Database Schema
- Uses existing `source_summaries` table with:
  - `book_id` (UUID, FK to books)
  - `summary_json` (JSONB)
  - `embedding` (vector(1536))
  - `version` (INTEGER)
- Uses existing `books` table for book titles
- Leverages `ivfflat` index on `embedding` column for fast similarity search

### Event Flow
```
CourseRequestedEvent
  → EmbedCommand
    → EmbeddingGeneratedEvent
      → SearchBookSummariesCommand
        → BookSummariesFoundEvent
          → LLMCommand (course parts generation)
            → ... (continues pipeline)
```

## Testing

### Manual Test
```bash
# Invoke course generator with a query
aws lambda invoke \
  --function-name docprof-dev-course-generator \
  --payload '{"body": "{\"query\": \"Learn DCF valuation\", \"hours\": 2.0}"}' \
  --cli-binary-format raw-in-base64-out /tmp/course-test.json

# Check logs
aws logs tail /aws/lambda/docprof-dev-course-generator --since 5m
```

### Expected Behavior
1. Course generator receives query
2. Generates embedding for query
3. Searches `source_summaries` table
4. Finds relevant books (e.g., "Valuation: Measuring and Managing the Value of Companies")
5. Logs book titles and similarity scores
6. Continues pipeline to generate course outline

### Verification Points
- ✅ Search returns books with similarity scores
- ✅ Books are ordered by relevance
- ✅ Minimum similarity threshold is respected
- ✅ Pipeline continues after search completes
- ✅ Empty results are handled gracefully

## Next Steps

1. **Test end-to-end**: Run full course generation with real query
2. **Monitor performance**: Check query execution time and similarity scores
3. **Tune parameters**: Adjust `min_similarity` threshold if needed (currently 0.2)
4. **Add book metadata**: Consider including author, edition in search results
5. **Optimize query**: Monitor index usage and query performance

## Related Files

- `src/lambda/shared/command_executor.py` - Command execution logic
- `src/lambda/course_generator/handler.py` - Course generator handler
- `src/lambda/shared/logic/courses.py` - Course generation logic
- `src/lambda/shared/core/commands.py` - Command definitions
- `src/lambda/shared/core/course_events.py` - Event definitions
- `scripts/setup_database_schema.py` - Database schema (source_summaries table)

## Notes

- The search uses cosine similarity (`<=>` operator in pgvector)
- Similarity score is converted to 0-1 range: `1 - (embedding <=> query_embedding)`
- Higher scores = more similar (closer to 1.0)
- Default `min_similarity` is 0.2 (fairly permissive)
- Default `top_k` is 10 books
