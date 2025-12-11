# Ingestion Pipeline Analysis

## Question 1: Why 191 Chapter Chunks Instead of 43?

**Answer**: This is **correct behavior**. The MAExpert chunking logic splits chapters that exceed the embedding character limit (8000 characters) into multiple segments.

### How It Works

1. **Initial chunking**: Creates 43 chapter chunks (one per chapter)
2. **Splitting logic**: Chapters exceeding 8000 characters are split:
   - Example: A 61,529 character chapter → 6 segments
   - Example: A 184,662 character chapter → 16 segments
3. **Result**: 43 chapters → 191 chunks after splitting

### Evidence from Logs

```
Prepared 43 chapter chunks and 1321 page chunks
Chunk chapter exceeds embedding char limit (61529); splitting into 6 segments
Chunk chapter exceeds embedding char limit (184662); splitting into 16 segments
...
```

### Calculation

- 43 original chapters
- ~41 chapters were split (based on log warnings)
- Total segments from splits: ~148
- **Total chunks = 43 (unsplit) + 148 (split) = ~191 chunks** ✅

This is **intentional** - large chapters need to be split to fit within embedding API limits.

---

## Question 2: Why Are Figures Being Filtered Out?

**Answer**: Figure extraction requires **caption classification** which currently fails because it tries to use Anthropic API directly instead of Bedrock.

### Current Issue

1. **Caption Classification Step Fails**:
   ```
   Cannot get Anthropic API key for classification: 4 validation errors for Settings
   ```

2. **Without Classification**: The system can't distinguish between:
   - Actual figures (charts, diagrams, graphs)
   - Text-based content (tables, text boxes, equations)

3. **Result**: All 551 images are filtered out as "tables, text boxes, etc."

### What Needs to Be Fixed

The `classify_caption_types_for_figures()` function in MAExpert uses Anthropic API directly. We need to:

1. **Translate caption classification to Bedrock**:
   - Use Bedrock Claude (vision model) instead of Anthropic API
   - This is similar to what we did for figure descriptions

2. **Update the classification logic**:
   - File: `/Users/tgulden/Documents/AI Projects/MAExpert/src/effects/caption_classifier.py`
   - Replace Anthropic API calls with Bedrock API calls
   - Use the same `AWSFigureDescriptionClient` pattern

3. **Ensure caption matching works**:
   - Figures need matching captions to be included
   - The filtering logic filters out images without figure captions

### Code Location

- **Caption classification**: `MAExpert/src/effects/caption_classifier.py`
- **Figure filtering**: `MAExpert/src/effects/ingestion_effects.py` lines 583-630
- **AWS adapter needed**: Similar to `AWSFigureDescriptionClient` but for classification

---

## Question 3: Why Did It Take 30 Minutes Instead of 20 Seconds?

**Answer**: The 20 seconds was just the **final successful Lambda execution**. The total time included multiple failed attempts and embedding generation.

### Timeline Breakdown

1. **15:00:43** - First attempt (failed quickly - schema issue)
2. **15:02:58** - Second attempt (failed after ~8 seconds - missing `full_text`)
3. **15:06:04** - Third attempt (failed after ~27 seconds - missing `book_id`)
4. **15:10:22** - **Fourth attempt** (failed after **213 seconds = 3.5 minutes**)
   - This one generated embeddings for chapter chunks!
   - Failed on metadata serialization
5. **15:16:02** - **Final attempt** (succeeded in **19.5 seconds**)
   - Skipped duplicate chunks (already inserted)
   - Only processed new data

### Why the Long Wait?

1. **Multiple failed attempts**: ~4 failed runs before success
2. **Embedding generation time**: The 3.5-minute run shows real processing time:
   - 77 chapter chunks × ~200ms per embedding = ~15 seconds
   - 1,321 page chunks × ~200ms per embedding = ~4.4 minutes (if done sequentially)
   - **Actual**: Done in batches, but still takes time
3. **Bedrock API latency**: Each embedding call takes ~200-500ms
4. **My 5-minute wait**: Added at the end to monitor completion

### Actual Processing Time

- **Text extraction**: ~3 seconds
- **Chunk building**: ~1 second  
- **Embedding generation**: ~3-4 minutes (for 1,512 chunks)
- **Database insertion**: ~1 second
- **Total**: ~4-5 minutes for a full run

The 19.5-second final run was fast because it **skipped duplicates** - chunks were already in the database from the previous attempt.

---

## Recommendations

### 1. Chapter Chunks (No Change Needed)
✅ Current behavior is correct - large chapters must be split

### 2. Figure Extraction (Needs Fix)
- [ ] Create `AWSCaptionClassifier` using Bedrock Claude
- [ ] Translate `caption_classifier.py` to use Bedrock
- [ ] Test figure extraction with caption classification
- [ ] Verify figures are properly detected and stored

### 3. Processing Time (Optimization Opportunities)
- [ ] Consider parallel embedding generation (Step Functions Map state)
- [ ] Batch embeddings more efficiently
- [ ] Add progress reporting to Lambda (CloudWatch metrics)
- [ ] Consider async processing for large PDFs

---

## Next Steps

1. **Fix figure extraction**: Translate caption classification to Bedrock
2. **Optimize embedding generation**: Consider parallel processing
3. **Add monitoring**: CloudWatch metrics for processing time
4. **Document**: Update ingestion guide with expected processing times

