# Figure Extraction Flow Optimization

## Current Flow Analysis

### Current Order of Operations

1. **Extract text from PDF** (~3 seconds)
2. **Build text chunks** (~1 second)
3. **Get existing figure hashes** (fast - database query)
4. **Extract ALL figures from PDF** (expensive - renders pages, extracts images)
5. **Classify caption types** (expensive - LLM vision call with multiple images)
6. **Filter figures by captions**
7. **Check figure hashes** (fast - skip existing)
8. **Process new figures** (expensive - LLM calls per figure)

### Problem

Even if **all figures already exist**, we still do:
- Step 4: Extract all figures from PDF (expensive)
- Step 5: Classify caption types (expensive LLM call)

This is wasteful when re-running ingestion on a book that already has figures.

## Optimization Strategy

### Option 1: Early Exit Check (Recommended)

**Before** extracting figures, check if figures already exist:

```python
existing_figure_hashes = database.get_existing_figure_hashes(book_id)
if existing_figure_hashes and len(existing_figure_hashes) > 0:
    # Check if we have enough figures (e.g., > 50% of expected)
    # If yes, skip extraction and classification entirely
    logger.info(f"Found {len(existing_figure_hashes)} existing figures - skipping extraction")
    total_figures = 0
else:
    # Proceed with extraction
    ...
```

**Pros:**
- Simple to implement
- Saves time when figures already exist
- No API changes needed

**Cons:**
- Still extracts if no figures exist (first run)
- Can't selectively update figures

### Option 2: `--figures-only` Flag

Add a flag to process only figures, skipping text chunks:

```python
if command.figures_only:
    # Skip text chunking entirely
    chapter_chunks = []
    page_chunks = []
    # Only process figures
else:
    # Normal flow
    ...
```

**Pros:**
- Allows selective figure processing
- Useful for re-processing figures after fixing caption classifier

**Cons:**
- Requires command modification
- Still does extraction/classification even if figures exist

### Option 3: Smart Skip (Best of Both)

Combine early exit with selective processing:

1. **Check existing figures first**
2. **If all figures exist**: Skip extraction and classification
3. **If some figures missing**: Extract and classify, but skip existing ones
4. **Add `--figures-only` flag**: For selective re-processing

## Recommended Implementation

### Phase 1: Early Exit Check

Modify `run_ingestion_pipeline` to check for existing figures **before** extraction:

```python
# Get existing figure hashes EARLY (before extraction)
existing_figure_hashes = database.get_existing_figure_hashes(book_id)

# If we have many existing figures, check if we should skip extraction
if existing_figure_hashes and len(existing_figure_hashes) > 10:
    # Estimate total figures (rough heuristic)
    # If we have >80% of expected figures, skip extraction
    logger.info(f"Found {len(existing_figure_hashes)} existing figures - skipping extraction")
    total_figures = 0
    figures = []
else:
    # Proceed with extraction
    ...
```

### Phase 2: Add `--figures-only` Flag

Add to `RunIngestionPipelineCommand`:

```python
class RunIngestionPipelineCommand(Command):
    pdf_path: Path
    book_metadata: Dict[str, Any]
    run_id: str
    rebuild: bool = False
    skip_figures: bool = False
    figures_only: bool = False  # NEW
```

Use in pipeline:

```python
if command.figures_only:
    # Skip text chunking
    chapter_chunks = []
    page_chunks = []
    # Only process figures
```

## Implementation Plan

1. ✅ **Fix caption classifier** - Translate to Bedrock (done)
2. ⏳ **Add early exit check** - Skip extraction if figures exist
3. ⏳ **Add `--figures-only` flag** - For selective processing
4. ⏳ **Test with existing book** - Verify skipping works

## Expected Savings

- **First run**: No change (must extract and classify)
- **Re-run with existing figures**: 
  - Skip extraction: ~30-60 seconds saved
  - Skip classification: ~10-20 seconds saved
  - **Total: ~40-80 seconds saved**

## Code Changes Needed

1. **`src/lambda/shared/caption_classifier.py`** ✅ (created)
2. **`src/lambda/shared/maexpert_caption_classifier_adapter.py`** ✅ (created)
3. **`src/lambda/document_processor/handler.py`** ✅ (updated to use AWS classifier)
4. **`/Users/tgulden/Documents/AI Projects/MAExpert/src/effects/ingestion_effects.py`** (modify to check figures early)
   - Move `get_existing_figure_hashes` call earlier
   - Add early exit logic
5. **`/Users/tgulden/Documents/AI Projects/MAExpert/src/core/commands.py`** (add `figures_only` flag)

Note: Since we're reusing MAExpert code, we may need to patch it at runtime rather than modifying the source.

