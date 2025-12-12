# Source Summaries Implementation Plan

## Research Findings from MAExpert

### Summary Generation Process

**Location**: `../MAExpert/src/logic/book_summaries.py` and `../MAExpert/scripts/generate_book_summary.py`

**Process Flow**:
1. **Extract TOC** from PDF using PyMuPDF
2. **Parse TOC Structure** - Skip front matter, identify chapters and sections
3. **For Each Chapter**:
   - Extract chapter text (pages from TOC)
   - Generate chapter summary using LLM (prompt: `book_summaries.chapter`)
   - Store chapter summary in state
4. **Extract Book Overview** from Chapter 1 (prompt: `book_summaries.extract_overview`)
5. **Assemble JSON** - Combine all chapter summaries + book overview
6. **Store Summary** in `source_summaries` table
7. **Generate Embedding** - Convert JSON to text, generate embedding (separate step)

### Summary JSON Structure

```json
{
  "book_title": "Valuation: Measuring and Managing the Value of Companies",
  "author": "Tim Koller, Marc Goedhart, David Wessels",
  "total_chapters": 42,
  "book_summary": "3-5 sentence overview extracted from Chapter 1",
  "chapters": [
    {
      "chapter_number": 1,
      "chapter_title": "Why Value Value?",
      "sections": [
        {
          "section_title": "Section name from TOC",
          "topics": ["main topic 1", "main topic 2"],
          "key_concepts": ["important concept 1", "important concept 2"],
          "page_range": "X-Y"
        }
      ],
      "summary": "2-3 sentence overview of the chapter's main content and purpose"
    }
  ]
}
```

### Embedding Generation

**Location**: `../MAExpert/scripts/generate_book_summary_embeddings.py`

**Process**:
- Converts summary JSON to text representation:
  - Book title + author
  - Book overview
  - Chapter summaries (number, title, summary)
  - Section topics and key concepts
- Generates embedding for the full text
- Stores in `source_summaries.embedding` column

### Database Schema (MAExpert)

**Table**: `source_summaries`
- `summary_id` (UUID, primary key)
- `book_id` (UUID, foreign key to books)
- `summary_json` (JSONB) - Full summary structure
- `generated_at` (TIMESTAMP)
- `generated_by` (TEXT)
- `version` (INTEGER)
- `metadata` (JSONB)
- **Missing**: `embedding` column (added later via migration script)

## Implementation Plan

### Phase 1: Update Schema
- [ ] Add `embedding` column to `source_summaries` table (vector(1536))
- [ ] Add `source_title` column (for easy access without JOIN)
- [ ] Create vector index on `embedding` column
- [ ] Update `setup_database_schema.py`

### Phase 2: Update Terminology
- [ ] Rename `SearchBookSummariesCommand` → `SearchSourceSummariesCommand`
- [ ] Update course generator logic to use "source" terminology
- [ ] Keep `book_id` column name (for backward compatibility) but use "source" in code

### Phase 3: Extract MAExpert Logic
- [ ] Copy `book_summaries.py` logic to `src/lambda/shared/logic/source_summaries.py`
- [ ] Adapt for Lambda environment (no file paths, use S3)
- [ ] Extract prompts from `base_prompts.py`
- [ ] Create `SummaryGenerationState` model

### Phase 4: Create Summary Generation Lambda
- [ ] Create `source_summary_generator` Lambda function
- [ ] Integrate into ingestion pipeline as final step
- [ ] Use S3 for PDF access (instead of local file paths)
- [ ] Generate summaries using Bedrock Claude
- [ ] Store in `source_summaries` table

### Phase 5: Generate Embeddings
- [ ] Create `source_summary_embedding_generator` Lambda function
- [ ] Convert summary JSON to text (same as MAExpert)
- [ ] Generate embeddings using Bedrock Titan
- [ ] Store in `source_summaries.embedding` column
- [ ] Can be separate step or integrated into summary generation

### Phase 6: Implement Search
- [ ] Implement `SearchSourceSummariesCommand` execution
- [ ] Vector similarity search on `source_summaries.embedding`
- [ ] Return results with similarity scores
- [ ] Update course generator to use new command

## Figures Investigation

**Issue**: Expected ~400 figures, found 145

**Possible Causes**:
1. Figures stored separately from figure chunks
2. Duplicate figure_ids causing undercounting
3. Some figures filtered out during ingestion
4. Different ID system for figures

**Next Steps**:
- Query `figures` table directly to see all records
- Check if `figure_id` in `chunks` matches `figure_id` in `figures`
- Verify figure extraction logic in ingestion pipeline
- Check if there are multiple figure records per page (different IDs)

## Integration into Ingestion Pipeline

**Current Pipeline** (from `document_processor`):
1. Extract text from PDF
2. Extract figures
3. Chunk document
4. Generate embeddings for chunks
5. Store in database

**Enhanced Pipeline**:
1. Extract text from PDF
2. Extract figures
3. Chunk document
4. Generate embeddings for chunks
5. Store in database
6. **NEW**: Generate source summary
   - Extract TOC
   - Generate chapter summaries
   - Extract book overview
   - Store summary JSON
7. **NEW**: Generate summary embedding
   - Convert JSON to text
   - Generate embedding
   - Store embedding

**Implementation Options**:
- **Option A**: Add as final steps in `document_processor` Lambda
- **Option B**: Create separate Lambda functions triggered after ingestion completes
- **Option C**: Use Step Functions to orchestrate the full pipeline

**Recommendation**: Option B - Separate Lambda functions for better separation of concerns and easier debugging.
