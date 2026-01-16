# Lecture Generation Fix - Dec 26, 2024

## Issue
When clicking on a course section in the frontend, users encountered:
- "Error loading lecture. Network Error" in the UI
- CORS policy errors in the browser console
- 502 Bad Gateway responses from `/courses/section/{sectionId}/generation-status` and `/courses/section/{sectionId}/lecture`

## Root Cause Analysis

### 1. Missing OPTIONS Methods (CORS Preflight)
The API Gateway was missing OPTIONS methods for the lecture-related endpoints:
- `/courses/section/{sectionId}/lecture`
- `/courses/section/{sectionId}/generation-status`

This caused CORS preflight requests to fail, preventing the frontend from making actual GET requests.

### 2. Lambda Import Error (502 Bad Gateway)
The `section_generation_status_handler` Lambda was crashing on import with:
```
Runtime.ImportModuleError: Unable to import module 'handler': 
cannot import name 'get_course_state' from 'shared.course_state_manager'
```

**Problem:** The handler was trying to import `get_course_state`, but the actual function in `shared/course_state_manager.py` is named `load_course_state`.

**Location:** `/src/lambda/section_generation_status_handler/handler.py:14`

## Fixes Applied

### Fix 1: Added OPTIONS Methods to API Gateway
Manually configured API Gateway to add OPTIONS methods with MOCK integrations and proper CORS headers for both endpoints:

**Headers:**
- `Access-Control-Allow-Origin: *`
- `Access-Control-Allow-Methods: GET,OPTIONS`
- `Access-Control-Allow-Headers: Content-Type,Authorization`

**Status:** Applied manually via AWS Console (needs to be added to Terraform)

### Fix 2: Fixed Import Statement
Changed `section_generation_status_handler/handler.py`:

```python
# BEFORE (line 14)
from shared.course_state_manager import get_course_state

# AFTER (line 14) - removed unused import
# (function wasn't actually being used in the handler)
```

The import was removed entirely since the handler doesn't actually use that function - it queries the database directly.

**Deployment:**
```bash
cd /src/lambda/section_generation_status_handler
zip -r /tmp/section_generation_status_handler.zip handler.py
aws lambda update-function-code \
  --function-name docprof-dev-section-generation-status-handler \
  --zip-file fileb:///tmp/section_generation_status_handler.zip
```

## Status
✅ **FIXED** - Both endpoints should now respond correctly:
- CORS preflight requests succeed
- Lambda no longer crashes on import

## Next Steps

### 1. Add OPTIONS to Terraform
The OPTIONS methods need to be added to the Terraform configuration to ensure they persist:

**File:** `terraform/modules/api-gateway/main.tf`

Add OPTIONS method resources for:
- `aws_api_gateway_resource.section_lecture`
- `aws_api_gateway_resource.section_generation_status`

### 2. Verify Lecture Generation Works
Test the full lecture generation flow:
1. Navigate to a course in the UI
2. Click on a section
3. Verify lecture generates and displays correctly
4. Check CloudWatch logs for any errors

### 3. Check section_lecture_handler
The `section_lecture_handler` Lambda doesn't have the import bug, but verify it works:
- Check CloudWatch logs
- Test actual lecture generation
- Verify synchronous generation completes within Lambda timeout

## Related Files
- `/src/lambda/section_generation_status_handler/handler.py` - Fixed import
- `/src/lambda/section_lecture_handler/handler.py` - No changes needed
- `/src/lambda/shared/course_state_manager.py` - Reference for correct function names
- API Gateway: `/courses/section/{sectionId}/*` endpoints

## Verification Commands
```bash
# Check Lambda logs
aws logs tail /aws/lambda/docprof-dev-section-generation-status-handler --since 5m --format short
aws logs tail /aws/lambda/docprof-dev-section-lecture-handler --since 5m --format short

# Test endpoints directly (requires auth token)
curl -H "Authorization: Bearer $TOKEN" \
  https://evjgcsghvi.execute-api.us-east-1.amazonaws.com/dev/courses/section/$SECTION_ID/generation-status
```

