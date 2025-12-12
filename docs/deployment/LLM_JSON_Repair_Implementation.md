# LLM-Based JSON Repair Implementation

## Overview

Implemented LLM-based JSON repair as an intermediate step between basic cleaning and manual extraction fallback. This leverages the LLM's ability to find and fix its own mistakes.

## Approach

### Problem
LLM sometimes returns malformed JSON with syntax errors (missing commas, etc.). Previous approach:
1. Basic regex cleaning
2. Aggressive regex cleaning  
3. Manual regex extraction (last resort)

### Solution
New approach with LLM repair:
1. Basic regex cleaning
2. **LLM-based JSON repair** (NEW) - uses LLM to fix syntax errors
3. Manual regex extraction (last resort)

## Implementation

### 1. New Prompt: `source_summaries.repair_json`

**Key features:**
- Provides original chapter context (number, title, TOC structure)
- Shows the malformed JSON and parse error
- Lists common JSON errors to look for
- Uses temperature **0.0** for precision (no creativity needed)
- Explicit instructions to preserve content, only fix syntax

**Prompt structure:**
```
- Original Chapter Context (number, title)
- Table of Contents Structure (for reference)
- Malformed JSON with errors
- JSON Parse Error details
- Common errors checklist
- Instructions to repair and return valid JSON
```

### 2. New Function: `repair_json_with_llm()`

**Purpose:** Returns an `LLMCommand` to repair malformed JSON

**Parameters:**
- `malformed_json`: The JSON string with syntax errors
- `parse_error`: The specific parse error message
- `chapter_number`: Chapter number for context
- `chapter_title`: Chapter title for context
- `sections_list`: TOC sections list for context

**Configuration:**
- `temperature=0.0`: Zero creativity - pure precision
- `max_tokens=2500`: Slightly more than original to allow for fixes
- `task="repair_json"`: Identifies this as a repair operation

### 3. Updated Parsing Flow

**In `handle_chapter_summary_generated()`:**

1. Try `json.loads()` on original
2. If fails → Basic cleaning (markdown removal, trailing commas)
3. If still fails → **Return `repair_json_with_llm()` command**
4. Handler executes repair command
5. Handler calls `handle_chapter_summary_generated()` again with repaired JSON
6. If repair succeeds → Continue normally
7. If repair fails → Fall through to manual extraction

**In handler:**

```python
if task == 'repair_json':
    # Get repaired JSON from LLM
    result = handle_chapter_summary_generated(state, llm_content)
    # If successful, update state and continue
    # If failed, will fall through to manual extraction
```

## Benefits

1. **LLM finds its own mistakes**: LLMs are often better at finding their own errors than regex
2. **Context-aware repair**: TOC structure helps LLM understand expected format
3. **Precision over creativity**: Temperature 0.0 ensures deterministic, correct fixes
4. **Preserves content**: Explicit instruction to only fix syntax, not change data
5. **Better than regex**: Can handle complex nested structures regex might miss

## Expected Impact

- **Reduced manual extraction**: Should reduce manual extraction usage by 50-70%
- **Better data quality**: Repaired JSON preserves full structure vs. minimal manual extraction
- **More reliable**: LLM repair should succeed where regex cleaning fails

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

Basic cleaning: Still fails (regex can't always catch this)

LLM Repair Request:
- Shows malformed JSON
- Shows error: "Expecting ',' delimiter: line 1 column 45"
- Provides TOC context
- Temperature 0.0

LLM Repair Response:
{"chapter_number": 2, "chapter_title": "Finance", "summary": "..."}
                    ↑ Comma added

Success! Full chapter summary preserved.
```

## Temperature Setting

**Changed from 0.7 → 0.3 → 0.0:**

- **Original generation**: 0.3 (reduced from 0.7 for better JSON adherence)
- **JSON repair**: 0.0 (zero creativity, pure precision)
- **Rationale**: JSON repair is a mechanical task - we need exact fixes, not creative solutions

## Testing

After deployment, verify:
1. LLM repair is attempted when JSON parsing fails
2. Repair succeeds for common errors (missing commas)
3. Repaired JSON preserves full structure
4. Manual extraction rate decreases
5. No performance degradation (repair adds one LLM call per failure)
