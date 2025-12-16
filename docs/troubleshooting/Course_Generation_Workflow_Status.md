# Course Generation Workflow Status

**Date:** 2025-12-14  
**Concern:** Full course generation from request to stored outline may not be completing  
**Status:** ⚠️ **INVESTIGATING**

---

## Current Status

### ✅ **What's Working**

1. **Course Request Handler**
   - ✅ Creates course state in DynamoDB
   - ✅ Generates embedding via Bedrock
   - ✅ Publishes `CourseRequested` event to EventBridge
   - ✅ Returns course_id immediately

2. **GET /courses Endpoint**
   - ✅ **FIXED** - Now deployed and working
   - ✅ Lists courses for authenticated user
   - ✅ Resolves 403 error on Courses tab

### ⚠️ **What Needs Verification**

1. **EventBridge Workflow**
   - ⚠️ Only 1 rule showing as ENABLED (should be 7)
   - ⚠️ Rules may be on default bus, not custom bus
   - ⚠️ Need to verify all handlers are being triggered

2. **Full Workflow Completion**
   - ⚠️ Need to verify course completes all 7 phases:
     1. Course Requested → Embedding Generator
     2. Embedding Generated → Book Search
     3. Book Summaries Found → Parts Generator
     4. Parts Generated → Sections Generator
     5. Part Sections Generated → Next Part or Review
     6. All Parts Complete → Outline Reviewer
     7. Outline Reviewed → Course Storage Handler

---

## Expected Workflow

```
POST /courses
  ↓
Course Request Handler
  - Creates DynamoDB state
  - Generates embedding
  - Publishes CourseRequested event
  ↓
EventBridge: CourseRequested
  ↓
Embedding Generator Handler
  - Publishes EmbeddingGenerated event
  ↓
EventBridge: EmbeddingGenerated
  ↓
Book Search Handler
  - Finds relevant books
  - Publishes BookSummariesFound event
  ↓
EventBridge: BookSummariesFound
  ↓
Parts Generator Handler
  - Generates course parts
  - Publishes PartsGenerated event
  ↓
EventBridge: PartsGenerated
  ↓
Sections Generator Handler
  - Generates sections for each part
  - Publishes PartSectionsGenerated event
  ↓
EventBridge: PartSectionsGenerated
  ↓
(Repeat for each part, then...)
  ↓
EventBridge: AllPartsComplete
  ↓
Outline Reviewer Handler
  - Reviews and adjusts outline
  - Publishes OutlineReviewed event
  ↓
EventBridge: OutlineReviewed
  ↓
Course Storage Handler
  - Stores course + sections in Aurora
  - Publishes CourseStored event
  ↓
✅ Course Complete!
```

---

## Verification Steps

### 1. Check EventBridge Rules

```bash
# Check default bus (rules may be there, not custom bus)
aws events list-rules --query 'Rules[?contains(Name, `docprof-dev`)].{Name:Name, State:State}' --output table

# Check custom bus
aws events list-rules --event-bus-name docprof-dev-course-events --query 'Rules[*].{Name:Name, State:State}' --output table
```

### 2. Test Course Generation

```bash
# Create a course
bash scripts/test_course_request_lambda.sh

# Monitor EventBridge events
aws events list-rules --query 'Rules[?contains(Name, `docprof-dev`)].Name' --output text

# Check CloudWatch logs for each handler
aws logs tail /aws/lambda/docprof-dev-course-embedding-handler --follow
aws logs tail /aws/lambda/docprof-dev-course-book-search-handler --follow
aws logs tail /aws/lambda/docprof-dev-course-parts-handler --follow
aws logs tail /aws/lambda/docprof-dev-course-sections-handler --follow
aws logs tail /aws/lambda/docprof-dev-course-outline-reviewer --follow
aws logs tail /aws/lambda/docprof-dev-course-storage-handler --follow
```

### 3. Check DynamoDB State

```bash
# Get course_id from test
COURSE_ID="..."

# Check state progression
aws dynamodb get-item \
  --table-name docprof-dev-course-state \
  --key "{\"course_id\": {\"S\": \"$COURSE_ID\"}}" \
  --query 'Item.current_phase.S'
```

### 4. Check Database for Stored Course

```bash
# Query Aurora to see if course was stored
# (Need to connect to database or use Lambda to query)
```

---

## Known Issues

### Issue 1: EventBridge Rules Not Showing

**Symptom:** Only 1 rule showing as ENABLED when querying custom bus

**Possible Causes:**
1. Rules are on default bus, not custom bus (see Terraform config - rules use default bus)
2. Rules exist but query is filtering incorrectly
3. Rules were deleted or not deployed

**Fix:**
- Check default bus: `aws events list-rules` (no --event-bus-name)
- Verify Terraform applied all rules
- Check rule targets are configured

### Issue 2: Events Not Matching

**Symptom:** Events published but handlers not triggered

**From Previous Tests:**
- Events publish successfully (no errors)
- EventBridge shows zero matched events
- Handlers work when invoked directly

**Possible Causes:**
1. Event pattern doesn't match event format
2. Custom bus vs default bus mismatch
3. Event source/detail-type mismatch

---

## Next Actions

1. ✅ **Verify EventBridge Rules** - Check default bus for all 7 rules
2. ✅ **Test Full Workflow** - Create course and monitor all phases
3. ✅ **Check CloudWatch Logs** - Verify each handler is invoked
4. ✅ **Verify Course Storage** - Check if course appears in Aurora database

---

## Test Results

**To be updated after verification...**
