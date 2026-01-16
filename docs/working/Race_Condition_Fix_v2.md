# Race Condition Fix v2 - Status vs. Delivery Timing

**Date:** 2025-12-29  
**Issue:** "Lecture generation complete" at 100%, but immediately followed by "Lecture generation is in progress" error

## Root Cause

The race condition was more subtle than initially thought:

### The Timeline

```
1. Async handler stores lecture → section_deliveries record created ✓
2. Async handler clears progress → generation_progress = NULL ✓
3. Async handler updates status → section_sections.status = 'completed' ✓
   ↑
   BUT: Steps 1, 2, and 3 are separate database commits!
```

### The Race Condition

Between steps 1-2 and step 3, if the frontend polls:

**Status Handler:**
- Checks if delivery exists → YES (step 1 committed)
- Returns "Lecture generation complete" at 100%

**Frontend:**
- Sees 100% complete
- Immediately polls for lecture

**Lecture Handler:**
- Checks if delivery exists → YES
- Checks section_status → 'in_progress' (step 3 not committed yet!)
- Returns 202 "generation in progress"

## Solution

**Updated the status handler to check BOTH delivery existence AND section status:**

```python
# Before:
if delivery_row:
    return "Lecture generation complete" at 100%

# After:
if delivery_row and section_status == 'completed':
    return "Lecture generation complete" at 100%
```

Now the status handler will NOT report "complete" until the section status is also 'completed', eliminating the race condition window.

## Why This Works

- The lecture handler checks delivery existence FIRST (returns lecture if found)
- The status handler now requires status = 'completed' before reporting 100%
- This ensures both handlers see consistent state

### Flow After Fix

```
1. Async handler stores lecture ✓
2. Async handler clears progress ✓
3. Async handler updates status to 'completed' ✓
4. Frontend polls status:
   - Status handler checks: delivery exists? YES
   - Status handler checks: status = 'completed'? YES
   - Returns "Lecture generation complete" at 100%
5. Frontend polls for lecture:
   - Lecture handler finds delivery ✓
   - Returns lecture immediately ✓
```

## Files Changed

1. **`src/lambda/section_generation_status_handler/handler.py`**
   - Added `and section_status == 'completed'` check before reporting complete

2. **`src/lambda/section_lecture_handler/handler.py`**
   - No functional changes (cleanup only)

## Testing

Generate a lecture and watch the progress:
- ✅ Should progress smoothly to 85% (refining)
- ✅ Should jump to 100% "Lecture generation complete"
- ✅ Should load lecture immediately (no 202 error)
- ✅ No more race condition errors!

