# Lecture Generation Race Condition Fix

**Date:** 2025-12-29  
**Issue:** "Error loading lecture: Lecture generation is in progress" after completion

## Problem

When lecture generation reached 100% completion, the frontend would immediately poll for the lecture but get a "generation in progress" error. This was caused by a race condition in the progress tracking.

### Root Cause

The async handler was updating progress to indicate completion **before** actually storing the lecture:

```
1. ✓ Generate lecture content (Pass 1 & 2)
2. ✓ Update progress → "Refinement complete. Storing lecture..." (100%)
3. Frontend sees 100%, immediately polls for lecture
4. ✗ Lecture not stored yet!
5. ✓ Store lecture in database
6. ✓ Update section status to 'completed'
```

The frontend would poll between steps 3-5, finding no lecture delivery and getting a 202 response.

## Solution

**Moved the progress update to AFTER storing the lecture:**

```
1. ✓ Generate lecture content (Pass 1 & 2)
2. ✓ Update progress → "Saving lecture to database..." (95%)
3. ✓ Store lecture in database
4. ✓ Clear progress (lecture is ready)
5. ✓ Update section status to 'completed'
6. Frontend polls, finds lecture, loads immediately
```

Now the frontend never sees "100% complete" until the lecture is actually stored and ready to retrieve.

## Additional Fix: Disabled Tunnel Polling

The console was showing many network errors for `/tunnel/status` - this was a leftover from the local MAExpert setup (for ngrok tunneling). 

**Disabled the tunnel status polling** in `Layout.tsx` since it's not needed for AWS deployment.

## Files Changed

1. **`src/lambda/section_lecture_handler/handler.py`**
   - Moved progress update from before storage to after storage
   - Changed phase from "storing" to "refining" for the pre-storage update

2. **`src/frontend/src/components/common/Layout.tsx`**
   - Commented out tunnel status query
   - Set `tunnelStatus = undefined` to hide tunnel UI

## Testing

1. **Test lecture generation for a new section**
   - Should show smooth progress from 0% → 95% → immediately load lecture
   - No "generation in progress" error after 100%

2. **Check browser console**
   - No more `/tunnel/status` network errors
   - Should be much cleaner

## Result

✅ Lecture generation completes smoothly  
✅ No more race condition errors  
✅ Cleaner console output (no tunnel polling errors)

