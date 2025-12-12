# Source Summaries Research and Implementation Plan

## User Preferences
- ✅ Use "source" terminology instead of "book" (generalize for future non-book sources)
- ✅ Research how summaries were generated in MAExpert
- ✅ Add summary generation to ingestion pipeline as final step
- ⚠️ Investigate figures discrepancy (expected ~400, found 145)

## Current State

### Database
- ✅ `source_summaries` table exists (created in schema)
- ❌ Missing `embedding` column (needed for vector search)
- ❌ No data in table (summaries not generated)
- ✅ 1 source (book) ingested: "Valuation: Measuring and Managing the Value of Companies"

### Figures Discrepancy
- **Expected**: ~400 figure records
- **Found**: 145 figure records in `figures` table
- **Found**: 145 figure chunks in `chunks` table
- **Question**: Are there duplicate figure IDs or missing figures from ingestion?

## Research Tasks

### 1. MAExpert Summary Generation
**Goal**: Understand how summaries were generated in original codebase

**Questions to Answer**:
- What prompts were used for summary generation?
- How were summaries structured (JSON format)?
- When were summaries generated (during or after ingestion)?
- How were embeddings generated for summaries?
- What information was included in summaries (chapters, key topics, etc.)?

**Location**: Check `../MAExpert/src/` for:
- Summary generation logic
- Prompts used
- Effects/commands for summary generation
- Database schema for summaries

### 2. Figures Investigation
**Goal**: Understand why only 145 figures instead of ~400

**Questions to Answer**:
- Are figures stored separately from figure chunks?
- Could there be duplicate figure_ids causing undercounting?
- Were some figures filtered out during ingestion?
- Is there a different ID system for figures?

**Actions**:
- Query `figures` table directly to see all records
- Check if `figure_id` in `chunks` table matches `figure_id` in `figures` table
- Verify figure extraction logic in ingestion pipeline

## Implementation Plan

### Phase 1: Update Terminology
- [ ] Rename `book_summaries` → `source_summaries` in course generator code
- [ ] Update `SearchBookSummariesCommand` → `SearchSourceSummariesCommand`
- [ ] Update all references from "book" to "source" in course generation
- [ ] Keep `book_id` as `source_id` or maintain `book_id` for backward compatibility?

### Phase 2: Enhance `source_summaries` Table
- [ ] Add `embedding` column (vector(1536))
- [ ] Add `source_title` column (for easy access without JOIN)
- [ ] Create vector index on `embedding` column
- [ ] Update schema creation script

### Phase 3: Research MAExpert Implementation
- [ ] Review MAExpert summary generation code
- [ ] Extract prompt templates
- [ ] Understand summary JSON structure
- [ ] Document the process

### Phase 4: Integrate into Ingestion Pipeline
- [ ] Add summary generation as final step in ingestion
- [ ] Generate summary JSON using LLM (Claude)
- [ ] Generate embedding for summary
- [ ] Store in `source_summaries` table
- [ ] Update ingestion Lambda/document processor

### Phase 5: Implement Search
- [ ] Implement `SearchSourceSummariesCommand` execution
- [ ] Vector similarity search on `source_summaries.embedding`
- [ ] Return results with similarity scores
- [ ] Update course generator to use new command

## Next Steps

1. **Research MAExpert**: Check `../MAExpert/src/` for summary generation code
2. **Investigate Figures**: Query database to understand figure discrepancy
3. **Update Terminology**: Start renaming "book" → "source" in course generator
4. **Enhance Schema**: Add embedding column to `source_summaries` table
