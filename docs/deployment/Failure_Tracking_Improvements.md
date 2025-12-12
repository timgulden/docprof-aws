# Failure Tracking and Visibility Improvements

## Problem

The source summary generator had several "quiet failures" where errors were handled silently or with minimal visibility:
1. Manual extraction fallback was logged as INFO, making it hard to track quality issues
2. Chapter failures were silently skipped, losing data without clear reporting
3. Event publishing failures were logged as warnings but ignored
4. No summary statistics about success/failure rates

## Solution

### 1. Failure Tracking

Added comprehensive tracking throughout the pipeline:
- `failed_chapters`: List of chapters that failed with details (index, title, error)
- `manual_extractions`: Track chapters using manual extraction fallback
- `warnings`: General warnings (e.g., event publishing failures)

### 2. Enhanced Logging

**Manual Extraction Fallback:**
- Changed from INFO to WARNING level
- Added metadata to chapter summaries (`_extraction_method: 'manual_fallback'`)
- Clear message: "MANUAL EXTRACTION FALLBACK USED" with chapter details
- Quality warning logged: "This indicates LLM JSON output quality issues"

**Chapter Failures:**
- Detailed error logging with chapter index and title
- CRITICAL level logging when manual extraction also fails
- Clear tracking of which chapters failed and why

**Event Publishing:**
- Changed from WARNING to ERROR level
- Clear message: "CRITICAL: Failed to publish SourceSummaryStored event"
- Added to warnings list for final reporting

### 3. Response Statistics

All responses now include comprehensive statistics:
```json
{
  "statistics": {
    "total_chapters_processed": 16,
    "failed_chapters": 0,
    "manual_extractions": 2,
    "event_published": true
  },
  "failed_chapters": [...],  // Only if failures occurred
  "warnings": [...]  // Only if warnings occurred
}
```

### 4. Final Summary Logging

At completion, logs include:
- Quality warnings if manual extraction was used
- Failure summary if chapters failed completely
- Clear indication of incomplete summaries

## Benefits

1. **Visibility**: All failures are now clearly visible in logs and responses
2. **Metrics**: Easy to track quality issues (manual extraction usage)
3. **Debugging**: Detailed failure information helps identify root causes
4. **Monitoring**: Statistics enable alerting on quality degradation
5. **Transparency**: Users know exactly what succeeded and what failed

## Example Output

**Success with some quality issues:**
```
WARNING: QUALITY WARNING: 2 chapters used manual extraction fallback.
WARNING: Summary generation completed with 0 failed chapters.
```

**Partial failure:**
```
ERROR: FAILURE SUMMARY: 3 chapters failed completely. Summary is incomplete.
WARNING: Failed: ["Chapter 5", "Chapter 12", "Chapter 19"]
```

**Critical event failure:**
```
ERROR: CRITICAL: Failed to publish SourceSummaryStored event: ...
ERROR: Embedding generation may not be triggered automatically.
```

## Monitoring Recommendations

1. **Alert on high manual extraction rate**: If >20% of chapters use fallback
2. **Alert on any chapter failures**: Any `failed_chapters` > 0
3. **Alert on event publishing failures**: Monitor `event_published: false`
4. **Track quality metrics**: Monitor `manual_extractions` count over time
