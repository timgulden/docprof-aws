# Course Creation Debugging - Status Summary

**Last Updated:** 2025-12-17  
**Status:** Enhanced logging deployed, ready for testing  
**Next Step:** Test course creation and analyze CloudWatch logs

---

## Problem Statement

When creating a course, the UI shows:
- **Title:** Truncated prompt (e.g., "Learn DCF valuation" instead of proper course title)
- **Objective:** Full prompt
- **Sections:** Zero (no course content)

### What's Working ✅
- Course creation: Course ID created in PostgreSQL
- Book search: Finds 5 books via chunk-based search
- Parts generation: Creates parts_list in DynamoDB (3 parts found)
- Outline generation: Creates outline_text in DynamoDB (5,519+ characters with full structure)
- Outline reviewer: Runs and reports "No review needed, course stored"

### What's Broken ❌
- **Sections not stored:** PostgreSQL `course_sections` table has 0 sections for new courses
- **Title not updated:** PostgreSQL `courses.title` remains the truncated prompt
- **Parsing/storage:** `parse_text_outline_to_database` appears to run but sections aren't persisted

---

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

---

## Changes Made (Committed & Deployed)

### 1. Enhanced Logging Added

**Files Modified:**
- `src/lambda/shared/logic/courses.py` - Parsing and review logic
- `src/lambda/course_outline_reviewer/handler.py` - Handler entry point
- `src/lambda/shared/command_executor.py` - Command execution

**Key Logging Added:**
- Outline text length and preview
- Parsing results (parts count, sections count)
- Section creation details
- Command generation and execution
- Database verification after inserts
- Error conditions and empty results

### 2. Deployment Status

**✅ Shared Code Layer (Version 37)**
- **Deployed:** 2025-12-17 02:46:25 UTC
- **Status:** Active
- **Contains:** All enhanced logging in shared code
- **Impact:** All Lambda functions using this layer have the new logging

**✅ Course Outline Reviewer Lambda**
- **Function Name:** `docprof-dev-course-outline-reviewer`
- **Status:** Active (created via AWS CLI, bypassing Terraform issues)
- **Deployed:** 2025-12-17 03:16:56 UTC
- **Layers:** 
  - `docprof-dev-python-deps:15`
  - `docprof-dev-shared-code:37` ✅
- **EventBridge:** Connected and ready
- **Lambda Permission:** Configured

**⚠️ Terraform State Note:**
- Function was created via AWS CLI due to Terraform deployment issues
- Function works correctly but may not be in Terraform state
- Can be imported later if needed

---

## Key Files to Review

### Logic Layer
- **`src/lambda/shared/logic/courses.py`**
  - `parse_text_outline_to_database()` - Lines ~599-1043
  - `check_and_review_outline()` - Lines ~484-501
  - Enhanced logging throughout

### Command Execution
- **`src/lambda/shared/command_executor.py`**
  - `execute_create_sections_command()` - Lines ~467-574
  - Enhanced logging and database verification

### Handler
- **`src/lambda/course_outline_reviewer/handler.py`**
  - Enhanced logging for command execution
  - Error checking for empty commands

---

## Testing Instructions

### 1. Create a New Course
- Use the UI to create a course
- Note the course_id that gets created

### 2. Monitor CloudWatch Logs

**Log Group:** `/aws/lambda/docprof-dev-course-outline-reviewer`

**Key Logs to Look For:**

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
   - **Critical:** If this shows 0 commands, that's the problem

3. **Parsing:**
   ```
   parse_text_outline_to_database: Parsed outline: found X parts with Y total sections
   parse_text_outline_to_database: Created X sections for course Y
   ```
   - **Critical:** If Y is 0, parsing is failing

4. **Command Execution:**
   ```
   execute_create_sections_command: Starting execution with X sections
   execute_create_sections_command: Verified X sections in database
   CreateSectionsCommand succeeded: stored X sections
   ```
   - **Critical:** If X is 0, sections aren't being created

### 3. Check Database

```sql
-- Check if course exists
SELECT course_id, title, user_id, created_at 
FROM courses 
WHERE course_id = '<course_id_from_ui>';

-- Check if sections exist
SELECT COUNT(*) as section_count, 
       COUNT(DISTINCT parent_section_id) as part_count
FROM course_sections 
WHERE course_id = '<course_id_from_ui>';

-- Check section details
SELECT section_id, order_index, title, estimated_minutes, parent_section_id
FROM course_sections 
WHERE course_id = '<course_id_from_ui>'
ORDER BY order_index;
```

---

## Expected Diagnostic Flow

When you create a course, the logs should show:

1. **Outline Reviewer Triggered**
   - EventBridge sends `AllPartsComplete` event
   - Handler loads state from DynamoDB

2. **Review Check**
   - Calculates time variance
   - Decides if review needed (usually not needed if variance < 5%)

3. **Parsing**
   - Parses outline_text (5,519+ chars)
   - Should find 3 parts with multiple sections each
   - Creates CourseSection objects

4. **Command Generation**
   - Returns `CreateCourseCommand` (updates title)
   - Returns `CreateSectionsCommand` (stores sections)
   - Returns `RecordCourseHistoryCommand` (history)

5. **Command Execution**
   - Execute CreateCourseCommand → Updates course title
   - Execute CreateSectionsCommand → Stores sections in database
   - Verify sections in database

---

## Potential Issues to Investigate

### If Parsing Returns 0 Sections
- Check outline_text format in DynamoDB
- Verify regex patterns match the actual outline format
- Check if outline_text is being truncated or corrupted

### If Commands Are Empty
- Check if `check_and_review_outline` is returning commands
- Verify `parse_text_outline_to_database` is being called
- Check for early returns or exceptions

### If Commands Execute But Sections Don't Appear
- Check database transaction commits
- Verify course_id matches between command and database
- Check for constraint violations or foreign key issues
- Verify user_id is correct

### If Title Isn't Updated
- Check if CreateCourseCommand is executed
- Verify ON CONFLICT clause in database update
- Check if course_id matches

---

## Deployment Details

### Function Configuration
- **Runtime:** python3.11
- **Timeout:** 300 seconds
- **Memory:** 1024 MB
- **VPC:** Private subnets with security group
- **Environment Variables:**
  - `DYNAMODB_COURSE_STATE_TABLE_NAME=docprof-dev-course-state`
  - `DB_CLUSTER_ENDPOINT=docprof-dev-aurora.cluster-c6dky642a6o1.us-east-1.rds.amazonaws.com`
  - `DB_NAME=docprof`
  - `DB_MASTER_USERNAME=docprof_admin`
  - `DB_PASSWORD_SECRET_ARN=arn:aws:secretsmanager:us-east-1:176520790264:secret:docprof-dev-aurora-master-password-Sy9Wwc`

### EventBridge Configuration
- **Rule:** `docprof-dev-all-parts-complete`
- **Event Pattern:** `source: docprof.course, detail-type: AllPartsComplete`
- **Target:** `docprof-dev-course-outline-reviewer` Lambda function

---

## Next Steps

1. **Test Course Creation**
   - Create a new course via UI
   - Monitor CloudWatch logs immediately
   - Look for the diagnostic messages

2. **Analyze Logs**
   - Identify where the flow breaks
   - Check if parsing finds sections
   - Check if commands are created
   - Check if commands execute successfully

3. **Fix Based on Findings**
   - If parsing fails → Fix regex patterns or outline format
   - If commands empty → Fix logic layer return values
   - If execution fails → Fix database operations or constraints

4. **Verify Fix**
   - Create another course
   - Verify sections appear in database
   - Verify title is updated correctly

---

## Related Documentation

- `docs/troubleshooting/Course_Creation_Debugging_Fixes.md` - Detailed fix documentation
- `docs/troubleshooting/Deployment_Status.md` - Deployment status
- `docs/troubleshooting/Deployment_Complete.md` - Deployment completion

---

## Git Status

**Last Commit:** `d46b2de` - "Add enhanced logging for course creation debugging"  
**Branch:** `main`  
**Status:** All changes committed and pushed

---

## Quick Reference Commands

```bash
# Check function status
aws lambda get-function --function-name docprof-dev-course-outline-reviewer

# View recent logs
aws logs tail /aws/lambda/docprof-dev-course-outline-reviewer --follow

# Check EventBridge target
aws events list-targets-by-rule --rule docprof-dev-all-parts-complete

# Query database for course
psql -h <endpoint> -U docprof_admin -d docprof -c "SELECT * FROM courses WHERE course_id = '<id>';"
```

---

**Ready for testing!** Create a course and check the CloudWatch logs to see where the flow breaks.

