# Schema Comparison Results: MAExpert vs AWS

## Summary

✅ **Core schema matches** - All essential fields are present  
⚠️ **Field name mapping issue found and fixed** - `context_text` → `figure_context`

## Key Finding: Field Name Mismatch

### The Issue

**MAExpert**:
- `chunk_builder.py` creates chunks with `"context_text"` key (line 137)
- `database_client.py` maps `chunk.get("context_text")` to `figure_context` column (line 346)

**AWS (before fix)**:
- `db_utils.py` expected `chunk.get('figure_context')` (line 187)
- This would miss the `context_text` field from MAExpert chunks!

### The Fix

Updated `src/lambda/shared/db_utils.py` line 187 to handle both:
```python
chunk.get('figure_context') or chunk.get('context_text')  # MAExpert uses 'context_text', map to 'figure_context'
```

This ensures:
1. ✅ MAExpert chunks with `context_text` are correctly mapped
2. ✅ Future chunks with `figure_context` still work
3. ✅ Database column remains `figure_context` (consistent)

## Detailed Comparison

### Chunks Table

| Field | MAExpert Source | MAExpert DB Column | AWS DB Column | Status |
|-------|----------------|-------------------|---------------|--------|
| book_id | ✅ | ✅ | ✅ | ✅ Match |
| chunk_type | ✅ | ✅ | ✅ | ✅ Match |
| content | ✅ | ✅ | ✅ | ✅ Match |
| embedding | ✅ | ✅ | ✅ | ✅ Match |
| chapter_number | ✅ | ✅ | ✅ | ✅ Match |
| chapter_title | ✅ | ✅ | ✅ | ✅ Match |
| section_title | ✅ | ✅ | ✅ | ✅ Match |
| page_start | ✅ | ✅ | ✅ | ✅ Match |
| page_end | ✅ | ✅ | ✅ | ✅ Match |
| keywords | ✅ | ✅ | ✅ | ✅ Match |
| figure_id | ✅ | ✅ | ✅ | ✅ Match |
| figure_caption | ✅ | ✅ | ✅ | ✅ Match |
| figure_type | ✅ | ✅ | ✅ | ✅ Match |
| context_text | ✅ (chunk dict) | figure_context (DB) | figure_context (DB) | ✅ Fixed |
| metadata | ✅ | ✅ | ✅ | ✅ Match |

### Books Table

| Field | MAExpert | AWS | Status |
|-------|----------|-----|--------|
| book_id | ✅ | ✅ | ✅ Match |
| title | ✅ | ✅ | ✅ Match |
| author | ✅ | ✅ | ✅ Match |
| edition | ✅ | ✅ | ✅ Match |
| isbn | ✅ | ✅ | ✅ Match |
| total_pages | ✅ | ✅ | ✅ Match |
| metadata | ✅ | ✅ | ✅ Match |
| pdf_data | ✅ | ✅ | ✅ Match |
| ingestion_date | ❌ | ✅ | ⚠️ AWS extra (harmless) |
| created_at | ❌ | ✅ | ⚠️ AWS extra (harmless) |

### Figures Table

| Field | MAExpert | AWS | Status |
|-------|----------|-----|--------|
| figure_id | ✅ | ✅ | ✅ Match |
| book_id | ✅ | ✅ | ✅ Match |
| page_number | ✅ | ✅ | ✅ Match |
| image_data | ✅ | ✅ | ✅ Match |
| image_format | ✅ | ✅ | ✅ Match |
| width | ✅ | ✅ | ✅ Match |
| height | ✅ | ✅ | ✅ Match |
| caption | ✅ | ✅ | ✅ Match |
| metadata | ✅ | ✅ | ✅ Match |
| created_at | ❌ | ✅ | ⚠️ AWS extra (harmless) |

### Chapter Documents Table

| Field | MAExpert | AWS | Status |
|-------|----------|-----|--------|
| chapter_document_id | ✅ | ✅ | ✅ Match |
| book_id | ✅ | ✅ | ✅ Match |
| chapter_number | ✅ | ✅ | ✅ Match |
| chapter_title | ✅ | ✅ | ✅ Match |
| content | ✅ | ✅ | ✅ Match |
| metadata | ✅ | ✅ | ✅ Match |
| created_at | ❌ | ✅ | ⚠️ AWS extra (harmless) |
| updated_at | ✅ | ✅ | ✅ Match |

## Verification Steps

1. ✅ **Schema structure**: All core fields match
2. ✅ **Field mapping**: `context_text` → `figure_context` mapping fixed
3. ✅ **Data types**: All types match (TEXT, INTEGER, JSONB, vector)
4. ✅ **Indexes**: Core indexes match (embedding, book_id, chapter_number)

## Conclusion

✅ **Schema is compatible** - We're ingesting the same data as MAExpert  
✅ **Field mapping fixed** - `context_text` is now correctly mapped to `figure_context`  
✅ **Ready for ingestion** - No schema drift detected

The only differences are harmless additions (`created_at` timestamps) that don't affect functionality.

