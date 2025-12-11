# Figure Extraction Fix Summary

## What Was Fixed

### 1. Caption Classifier Translation ✅

**Problem**: MAExpert's caption classifier uses Anthropic API directly, which isn't available in AWS.

**Solution**: Created AWS Bedrock version:
- `src/lambda/shared/caption_classifier.py` - Bedrock Claude Vision implementation
- `src/lambda/shared/maexpert_caption_classifier_adapter.py` - Drop-in replacement adapter
- Monkey-patched into MAExpert code at runtime

**How It Works**:
- Uses Bedrock Claude 3.5 Sonnet (vision model)
- Same API signature as MAExpert version
- Sends sample pages with images to classify caption types
- Returns which caption types indicate figures vs. tables/text boxes

### 2. Flow Optimization ✅

**Problem**: Even when all figures already exist, we still:
- Extract all figures from PDF (expensive)
- Classify caption types (expensive LLM call)

**Solution**: Early exit check:
- `src/lambda/shared/ingestion_flow_optimizer.py` - Wraps ingestion pipeline
- Checks for existing figures BEFORE extraction
- If >10 figures exist, skips extraction and classification
- Saves ~40-80 seconds on re-runs

**How It Works**:
```python
# Before expensive operations:
existing_figure_hashes = database.get_existing_figure_hashes(book_id)
if len(existing_figure_hashes) > 10:
    # Skip extraction and classification
    command.skip_figures = True
```

## Current Flow (Optimized)

1. **Extract text from PDF** (~3 seconds)
2. **Build text chunks** (~1 second)
3. **Get existing figure hashes** (fast - database query)
4. **Check: If >10 figures exist** → Skip extraction ✅
5. **Otherwise**: Extract figures → Classify → Process

## Testing

To test figure extraction:

1. **First run** (no figures exist):
   - Will extract and classify
   - Will process all figures
   - Takes ~5-10 minutes for large PDFs

2. **Re-run** (figures exist):
   - Will skip extraction and classification
   - Will skip figure processing
   - Takes ~20 seconds (just text chunks)

3. **Force re-extraction**:
   - Delete figures from database, OR
   - Ensure <10 figures exist

## Next Steps

1. ✅ Caption classifier translated to Bedrock
2. ✅ Early exit optimization added
3. ⏳ Test with actual PDF (needs VPC endpoints enabled for Bedrock)
4. ⏳ Verify figures are properly detected and stored
5. ⏳ Consider adding `--figures-only` flag for selective processing

## Files Created/Modified

- ✅ `src/lambda/shared/caption_classifier.py` - Bedrock implementation
- ✅ `src/lambda/shared/maexpert_caption_classifier_adapter.py` - Adapter
- ✅ `src/lambda/shared/ingestion_flow_optimizer.py` - Flow optimization
- ✅ `src/lambda/document_processor/handler.py` - Integration
- ✅ `docs/deployment/Figure_Extraction_Optimization.md` - Analysis
- ✅ `docs/deployment/Figure_Extraction_Fix_Summary.md` - This file

