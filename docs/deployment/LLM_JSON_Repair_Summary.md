# LLM-Based JSON Repair - Implementation Summary

## Problem

The LLM (Claude Sonnet 4.5) sometimes returns malformed JSON with syntax errors, primarily missing commas between properties. This causes parsing failures and requires fallback to manual regex extraction, which loses data quality.

## Solution: LLM Self-Repair

Implemented LLM-based JSON repair that leverages the model's ability to find and fix its own mistakes.

## Implementation Details

### 1. New Prompt: `source_summaries.repair_json`

**Key Features:**
- Provides original chapter context (number, title, TOC structure)
- Shows the malformed JSON and specific parse error
- Lists common JSON errors to look for (missing commas, trailing commas, etc.)
- **Temperature: 0.0** - Zero creativity, pure precision
- Explicit instruction: "Preserve all content - only fix syntax"

**Context Provided:**
- Chapter number and title
- Table of Contents structure (helps LLM understand expected format)
- Malformed JSON with errors
- Specific parse error message
- Checklist of common errors

### 2. New Function: `repair_json_with_llm()`

Returns an `LLMCommand` configured for JSON repair:
- `temperature=0.0`: No creativity needed - just fix syntax
- `max_tokens=2500`: Slightly more than original to allow for fixes
- `task="repair_json"`: Identifies this as a repair operation

### 3. Updated Parsing Flow

**New Multi-Layered Approach:**

1. **Try `json.loads()`** on original response
2. **Basic cleaning**: Remove markdown, trailing commas, comments
3. **Aggressive cleaning**: Fix common patterns (missing commas, etc.)
4. **🆕 LLM Repair**: If still fails, call LLM with temperature 0.0 to repair
5. **Manual extraction**: Last resort if LLM repair also fails

**Handler Flow:**
```
generate_chapter_summary → JSON parse fails
  → repair_json_with_llm() → Handler executes repair command
    → LLM repairs JSON (temperature 0.0)
      → handle_chapter_summary_generated() called again with repaired JSON
        → Success! Continue with full chapter summary
        → Or fall through to manual extraction if repair fails
```

### 4. Temperature Settings

**Changed:**
- **Original generation**: `0.7 → 0.3` (better JSON adherence)
- **JSON repair**: `0.0` (zero creativity, pure precision)

**Rationale:**
- JSON repair is a mechanical task - we need exact fixes
- Temperature 0.0 ensures deterministic, correct syntax fixes
- No creativity needed - just fix commas and brackets

## Benefits

1. **LLM finds its own mistakes**: Better than regex at complex nested structures
2. **Context-aware**: TOC structure helps LLM understand expected format
3. **Preserves full data**: Repaired JSON has complete structure vs. minimal manual extraction
4. **Precision**: Temperature 0.0 ensures correct fixes
5. **Better quality**: Full chapter summaries instead of minimal extraction

## Expected Impact

- **Manual extraction rate**: Should decrease from ~10-15% to <3%
- **Data quality**: Repaired summaries preserve full structure (sections, topics, concepts)
- **Success rate**: LLM repair should succeed >80% of the time
- **Performance**: Adds one LLM call per JSON failure (acceptable trade-off)

## Monitoring

Track these metrics:
1. **LLM repair attempts**: How often repair is attempted
2. **LLM repair success rate**: Should be >80%
3. **Manual extraction rate**: Should decrease significantly
4. **Complete failures**: Should decrease further

## Example Flow

```
Original JSON: {"chapter_number": 2, "chapter_title": "Finance" "summary": "..."}
                    ↑ Missing comma here

Basic cleaning: Still fails

LLM Repair Request (temperature 0.0):
- Shows malformed JSON
- Shows error: "Expecting ',' delimiter: line 1 column 45"
- Provides TOC context
- Lists common errors

LLM Repair Response:
{"chapter_number": 2, "chapter_title": "Finance", "summary": "..."}
                    ↑ Comma added

Success! Full chapter summary preserved with all sections, topics, concepts.
```

## Testing Recommendations

After deployment:
1. Monitor logs for "LLM-based JSON repair" messages
2. Track repair success rate
3. Compare manual extraction rate before/after
4. Verify repaired summaries have full structure
5. Check performance impact (one extra LLM call per failure)
