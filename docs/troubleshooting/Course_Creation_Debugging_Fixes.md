# Course Creation Debugging - Enhanced Logging & Fixes

**Date:** 2025-01-XX  
**Issue:** Sections not being stored in database, title not updated  
**Status:** Enhanced logging added, ready for deployment and testing

## Problem Summary

When creating a course:
- ✅ Course ID created in PostgreSQL
- ✅ Book search works (finds 5 books)
- ✅ Parts generation works (3 parts in DynamoDB)
- ✅ Outline generation works (5,519+ chars in DynamoDB)
- ✅ Outline reviewer runs and reports "No review needed, course stored"
- ❌ **Sections not stored** (0 sections in PostgreSQL)
- ❌ **Title not updated** (remains truncated prompt)

## Root Cause Hypothesis

The outline reviewer completes in ~400ms, which is too fast for:
1. Querying database for user_id
2. Parsing 5,519 character outline text
3. Creating CourseSection objects
4. Executing CreateSectionsCommand to store sections

This suggests either:
- Commands aren't being returned from `parse_text_outline_to_database`
- Commands are returned but not executed
- Commands are executed but fail silently
- Parsing returns empty sections list

## Changes Made

### 1. Enhanced Logging in `parse_text_outline_to_database`

**File:** `src/lambda/shared/logic/courses.py`

Added comprehensive logging to track:
- Outline text length and preview
- Course ID from state
- Parsing results (parts count, sections count)
- Details about each part and section
- Section creation details
- Command creation and return

**Key logs to watch for:**
```
parse_text_outline_to_database: Starting parse. Outline text length: X
parse_text_outline_to_database: Parsed outline: found X parts with Y total sections
parse_text_outline_to_database: Created X sections for course Y
parse_text_outline_to_database: Returning X commands: [...]
```

### 2. Enhanced Logging in `check_and_review_outline`

**File:** `src/lambda/shared/logic/courses.py`

Added logging to track:
- Which path is taken (review needed vs. direct storage)
- Time variance calculation
- Decision logic

**Key logs to watch for:**
```
check_and_review_outline: Total minutes from outline: X, Target: Y
check_and_review_outline: Time variance: X% (threshold: 5%)
check_and_review_outline: Variance <= 5%, proceeding directly to parse and store
```

### 3. Enhanced Logging in Handler

**File:** `src/lambda/course_outline_reviewer/handler.py`

Added logging to track:
- State information before processing
- Command count and types returned
- Detailed command execution results
- Section count verification

**Key logs to watch for:**
```
Outline reviewer: Logic returned X commands
Outline reviewer: Command types: [...]
CreateSectionsCommand execution result: status=..., sections_count=X
SUCCESS: X sections stored in database for course Y
```

### 4. Enhanced Logging in Command Executor

**File:** `src/lambda/shared/command_executor.py`

Added logging to track:
- Section details before insert
- Batch insert execution
- Database verification after insert
- Error conditions

**Key logs to watch for:**
```
execute_create_sections_command: Starting execution with X sections
execute_create_sections_command: Executing batch insert of X sections
execute_create_sections_command: Verified X sections in database for course Y
```

### 5. Error Handling Improvements

- Changed empty sections list from warning to error (returns error status)
- Added database verification query after insert
- Added explicit error checking for zero sections stored

## Next Steps

### 1. Deploy Updated Code

**Critical:** The handler code changes need to be deployed. The problem report mentioned:
> "course_outline_reviewer_lambda was tainted but apply failed due to Terraform lock"

**Action:**
1. Resolve Terraform lock (if still present)
2. Deploy updated Lambda function code
3. Ensure shared layer is also updated (contains logic and command_executor changes)

### 2. Test with Fresh Course

After deployment:
1. Create a new course
2. Monitor CloudWatch logs for the outline reviewer Lambda
3. Look for the new log messages to identify where the flow breaks

### 3. Key Logs to Check

**In CloudWatch Logs for `course_outline_reviewer_lambda`:**

1. **State Loading:**
   ```
   Outline reviewer: State has outline_text length: X
   Outline reviewer: State has parts_list: X parts
   ```

2. **Command Generation:**
   ```
   Outline reviewer: Logic returned X commands
   Outline reviewer: Command types: [...]
   ```

3. **Parsing:**
   ```
   parse_text_outline_to_database: Parsed outline: found X parts with Y total sections
   ```

4. **Command Execution:**
   ```
   CreateSectionsCommand execution result: status=..., sections_count=X
   execute_create_sections_command: Verified X sections in database
   ```

### 4. Diagnostic Queries

If sections still aren't stored, run these queries:

```sql
-- Check if course exists
SELECT course_id, title, user_id FROM courses WHERE course_id = '...';

-- Check if sections exist
SELECT COUNT(*) FROM course_sections WHERE course_id = '...';

-- Check recent course creation
SELECT course_id, title, created_at 
FROM courses 
ORDER BY created_at DESC 
LIMIT 5;
```

## Expected Behavior After Fix

1. **Parsing logs** should show sections being created
2. **Command execution logs** should show sections being stored
3. **Database verification** should confirm sections in database
4. **Course title** should be updated from parsed outline

## Potential Issues to Watch For

1. **Empty sections list:** If parsing returns 0 sections, check outline text format
2. **Database transaction:** If insert fails silently, check connection/transaction handling
3. **Command not executed:** If commands aren't in the list, check `check_and_review_outline` logic
4. **UUID format issues:** If course_id or section_id format is wrong, check UUID generation

## Files Modified

1. `src/lambda/shared/logic/courses.py` - Enhanced parsing and review logging
2. `src/lambda/course_outline_reviewer/handler.py` - Enhanced handler logging
3. `src/lambda/shared/command_executor.py` - Enhanced command execution logging

## Related Issues

- Terraform lock preventing deployment
- Handler code changes not deployed
- Only shared layer was updated previously

## Success Criteria

After deployment and testing:
- ✅ Logs show sections being parsed
- ✅ Logs show commands being executed
- ✅ Logs show sections being stored
- ✅ Database contains sections for new courses
- ✅ Course title is updated correctly

