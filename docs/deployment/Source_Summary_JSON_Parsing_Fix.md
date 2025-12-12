# Source Summary JSON Parsing Fix

## Summary

Improved JSON parsing for LLM-generated chapter summaries with robust error handling and manual extraction fallback.

## Changes Made

### 1. Enhanced JSON Parsing (`src/lambda/shared/logic/source_summaries.py`)

**Multi-layered approach:**
1. **Initial parse**: Try standard `json.loads()`
2. **Markdown extraction**: Remove markdown code blocks if present
3. **JSON extraction**: Use regex to extract JSON object
4. **Cleaning**: Remove trailing commas, comments, control characters
5. **Aggressive cleaning**: Fix missing commas between properties
6. **Manual extraction**: Fallback to regex-based field extraction if all else fails

**Key improvements:**
- Handles markdown-wrapped JSON (```json ... ```)
- Fixes trailing commas before closing braces/brackets
- Fixes missing commas between object properties
- Removes comments and non-printable characters
- Manual extraction extracts essential fields (chapter_number, chapter_title, summary) even from malformed JSON

### 2. Error Handling (`src/lambda/source_summary_generator/handler.py`)

- Improved state management to handle BaseModel/dict conversion
- Better error messages with problematic JSON sections logged
- Graceful degradation: continues processing even if some chapters fail

### 3. Database Schema (`src/lambda/schema_init/handler.py`)

- Added `source_summaries` table creation to schema init
- Ensures table exists even if schema was created before this feature
- Includes `embedding` column for vector search

### 4. UUID Handling (`src/lambda/shared/command_executor.py`)

- Proper UUID validation and conversion for `book_id`
- Explicit UUID type casting in SQL

## Test Results

**Working:**
- ✅ TOC extraction (330 entries, 1321 pages)
- ✅ Chapter text extraction
- ✅ LLM chapter summary generation
- ✅ Manual extraction fallback ("Successfully extracted minimal chapter summary via manual extraction: Chapter 2")
- ✅ Processing multiple chapters (16+ chapters processed successfully)

**Issues Resolved:**
- ✅ JSON parsing errors now trigger manual extraction fallback
- ✅ State management issues fixed
- ✅ Database schema updated with `source_summaries` table

**Remaining:**
- Some chapters still have JSON syntax errors that manual extraction handles
- Full book processing takes ~15 minutes (many chapters)
- Bedrock throttling may occur with high-volume processing

## Next Steps

1. Monitor production usage to see if JSON quality improves
2. Consider adjusting LLM prompt to emphasize valid JSON output
3. Test with smaller books first to validate end-to-end flow
4. Generate embeddings for stored summaries
