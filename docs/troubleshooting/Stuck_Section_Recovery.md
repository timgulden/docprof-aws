# Stuck Section Recovery Guide

## Problem
A section got stuck at "in_progress" status after a generation failure.

**Common Causes:**
- Bedrock timeout (60 seconds → now fixed to 300 seconds)
- Lambda crash or error
- Invalid status transition attempt

## What Was Fixed

### 1. Bedrock Timeout (✅ Deployed)
**Before:** 60-second read timeout (default)
**After:** 300-second (5-minute) read timeout

This gives Bedrock more time for large refinement steps.

### 2. Error Handling (✅ Deployed)
**Before:** Tried to set status to `'failed'` → caused check constraint violation
**After:** Resets status to `'not_started'` on errors, allowing retry

### 3. Status Updates
**Before:** Status could get stuck at `'in_progress'` indefinitely  
**After:** Errors automatically reset to `'not_started'`, clearing progress

## How to Handle Stuck Sections

### Option 1: Try a Different Section (Recommended)
**Just click on a NEW section** that you haven't tried yet. The old stuck section won't interfere.

### Option 2: Wait for Auto-Reset
If you want to retry the SAME section:
1. Wait ~10 minutes (Lambda timeout)
2. The section will auto-reset to `'not_started'` when the Lambda times out
3. Click it again to retry

### Option 3: Manual Reset (Advanced)
If you need immediate reset, you would need to run SQL:
```sql
UPDATE course_sections 
SET status = 'not_started', generation_progress = NULL 
WHERE section_id = 'YOUR-SECTION-ID'::uuid;
```

But we can't execute this from local machine (VPC restriction).

## For Your Stuck Section

**Section ID:** `5758b872-ff7d-4e1b-a9d9-3ec175ecf4ab`  
**Section Name:** "Comparable Companies Analysis Methodology"

**What happened:**
1. Refinement step took > 60 seconds → Bedrock timeout
2. Error handler tried to set status='failed' → database constraint violation  
3. Section stuck at status='in_progress'

**What to do:**
1. ✅ **Try a different section now** (recommended) - the fixes are deployed
2. OR wait ~10 minutes, then retry this same section
3. With the 5-minute Bedrock timeout, it should complete successfully

## Monitoring Future Sections

The new error handling will:
- Auto-reset sections to `'not_started'` on any error
- Clear the `generation_progress` field
- Log detailed error info to CloudWatch
- Allow immediate retry without manual intervention

## Summary

✅ **Bedrock timeout increased:** 60s → 300s  
✅ **Error handling fixed:** Resets to `'not_started'` instead of `'failed'`  
✅ **All Lambdas redeployed:** Fixes are live now  

**Recommendation:** Try generating a NEW section now. The stuck one will resolve itself in ~10 minutes if you want to retry it later.

