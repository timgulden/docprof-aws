# MAExpert vs AWS Schema Comparison

## Purpose

Compare the legacy MAExpert database schema with the AWS implementation to ensure we're ingesting the same data.

## Chunks Table Comparison

### MAExpert `insert_chunks` Fields (from code):
1. `book_id`
2. `chunk_type`
3. `content`
4. `embedding`
5. `chapter_number`
6. `chapter_title`
7. `section_title`
8. `page_start`
9. `page_end`
10. `keywords`
11. `figure_id`
12. `figure_caption`
13. `figure_type`
14. `context_text` (from chunk dict) → stored as `figure_context` in DB
15. `metadata`

### AWS `insert_chunks_batch` Fields:
1. `book_id`
2. `chunk_type`
3. `content`
4. `embedding`
5. `chapter_number`
6. `chapter_title`
7. `section_title`
8. `page_start`
9. `page_end`
10. `keywords`
11. `figure_id`
12. `figure_caption`
13. `figure_type`
14. `figure_context` (from chunk dict)
15. `metadata`

### ⚠️ FIELD NAME MISMATCH

**MAExpert**: Uses `context_text` in chunk dictionary, stores as `figure_context` in DB  
**AWS**: Uses `figure_context` in chunk dictionary, stores as `figure_context` in DB

**Impact**: Need to check if MAExpert's chunk_builder creates chunks with `context_text` key, and if our adapter correctly maps it.

## Tables Comparison

### Books Table
| Field | MAExpert | AWS | Match |
|-------|----------|-----|-------|
| book_id | ✅ | ✅ | ✅ |
| title | ✅ | ✅ | ✅ |
| author | ✅ | ✅ | ✅ |
| edition | ✅ | ✅ | ✅ |
| isbn | ✅ | ✅ | ✅ |
| total_pages | ✅ | ✅ | ✅ |
| ingestion_date | ❌ | ✅ | ⚠️ AWS has extra |
| created_at | ❌ | ✅ | ⚠️ AWS has extra |
| metadata | ✅ | ✅ | ✅ |
| pdf_data | ✅ | ✅ | ✅ |

### Figures Table
| Field | MAExpert | AWS | Match |
|-------|----------|-----|-------|
| figure_id | ✅ | ✅ | ✅ |
| book_id | ✅ | ✅ | ✅ |
| page_number | ✅ | ✅ | ✅ |
| image_data | ✅ | ✅ | ✅ |
| image_format | ✅ | ✅ | ✅ |
| width | ✅ | ✅ | ✅ |
| height | ✅ | ✅ | ✅ |
| caption | ✅ | ✅ | ✅ |
| metadata | ✅ | ✅ | ✅ |
| created_at | ❌ | ✅ | ⚠️ AWS has extra |

### Chapter Documents Table
| Field | MAExpert | AWS | Match |
|-------|----------|-----|-------|
| chapter_document_id | ✅ | ✅ | ✅ |
| book_id | ✅ | ✅ | ✅ |
| chapter_number | ✅ | ✅ | ✅ |
| chapter_title | ✅ | ✅ | ✅ |
| content | ✅ | ✅ | ✅ |
| metadata | ✅ | ✅ | ✅ |
| created_at | ❌ | ✅ | ⚠️ AWS has extra |
| updated_at | ✅ | ✅ | ✅ |

## Key Finding: `context_text` vs `figure_context`

MAExpert's `chunk_builder.py` creates chunks with `context_text` key, but `database_client.py` maps it to `figure_context` column. We need to verify our adapter does the same mapping.

## Recommendations

1. ✅ **Schema matches**: All core fields are present
2. ⚠️ **Field name mapping**: Verify `context_text` → `figure_context` mapping
3. ✅ **Extra fields**: AWS has `created_at` timestamps (harmless addition)
4. ✅ **Ready for comparison**: Can query both databases to compare actual data

