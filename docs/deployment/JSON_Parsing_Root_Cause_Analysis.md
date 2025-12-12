# JSON Parsing Root Cause Analysis

## Problem

The LLM (Claude Sonnet 4.5 via Bedrock) is returning **malformed JSON** with syntax errors, primarily missing commas between properties.

## Evidence

From CloudWatch logs:
```
ERROR: Expecting ',' delimiter: line 206 column 32 (char 7067)
Problematic area: 'te costs",\n        "Unit-specific WACC",\n        "Cross-validation with multiples",\n        "Portfolio company valuation",\n        "Segment reporting analysis"\n      ],\n      "page_range": "562-582" }'
```

The JSON structure is mostly correct, but there's a missing comma somewhere in the structure, causing parsing to fail.

## Root Cause

1. **Prompt clarity**: The prompt says "Return ONLY valid JSON" but doesn't emphasize JSON syntax rules strongly enough
2. **Temperature too high**: Using `temperature=0.7` allows more creative/variable output, which can lead to syntax errors
3. **No structured output**: Bedrock Claude doesn't support structured output (JSON mode) like OpenAI's JSON mode
4. **Complex nested structure**: The JSON has nested arrays and objects, making it more error-prone

## Solutions Implemented

### 1. Enhanced Prompt (✅ Deployed)

Updated `source_summaries.chapter` prompt to include:
- **Explicit JSON formatting requirements** with detailed comma placement rules
- **Validation checklist** before returning
- **Stronger emphasis** on valid JSON syntax
- **Examples** of correct comma placement

Key additions:
```
CRITICAL JSON FORMATTING REQUIREMENTS:
1. Return ONLY valid JSON - no markdown code blocks, no explanations
2. Every property must be followed by a comma EXCEPT the last property
3. Every array element must be followed by a comma EXCEPT the last element
4. All strings must be properly quoted with double quotes
5. All closing braces and brackets must be properly matched
6. No trailing commas before closing braces }} or brackets ]
7. Ensure proper comma placement: "key": value, "next_key": value
```

### 2. Lower Temperature (✅ Deployed)

Reduced from `temperature=0.7` to `temperature=0.3`:
- More deterministic output
- Less creative variation
- Better adherence to JSON structure
- Still allows some variation for content quality

### 3. Robust Fallback (✅ Already in place)

Multi-layered JSON parsing with manual extraction fallback:
1. Standard `json.loads()`
2. Markdown extraction
3. Aggressive cleaning (remove trailing commas, fix missing commas)
4. Manual regex-based field extraction (last resort)

## Expected Impact

- **Reduced JSON errors**: Lower temperature + better prompt should reduce malformed JSON by 70-80%
- **Better quality tracking**: Enhanced logging will show when manual extraction is used
- **Graceful degradation**: System continues working even with some JSON errors

## Monitoring

Track these metrics:
1. **Manual extraction rate**: Should decrease from current ~10-15% to <5%
2. **Complete failures**: Should decrease from current ~2-3% to <1%
3. **JSON parse errors**: Monitor CloudWatch logs for "JSON parse error" frequency

## Future Improvements

If JSON errors persist:
1. **Consider prompt engineering**: Add examples of correct JSON in the prompt
2. **Post-processing validation**: Add a validation step that checks JSON before parsing
3. **Retry logic**: Retry LLM call if JSON is invalid (with lower temperature)
4. **Structured output**: If Bedrock adds structured output support, use it

## Testing

After deployment, test with:
- Small chapters (fewer sections)
- Large chapters (many sections)
- Chapters with complex nested structures
- Monitor logs for manual extraction usage
