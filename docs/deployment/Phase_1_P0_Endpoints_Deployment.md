# Phase 1: P0 Endpoints Deployment Guide

**Created:** 2025-01-XX  
**Status:** Ready for Deployment  
**Goal:** Deploy critical course endpoints to enable basic course functionality

---

## Summary

✅ **All P0 Lambda functions created**  
✅ **All P0 API Gateway endpoints configured**  
⏳ **Ready for Terraform deployment**

---

## What Was Implemented

### Lambda Functions Created

1. **course_outline_handler** - `GET /courses/{courseId}/outline`
   - Returns complete course structure with parts and sections
   - Used by CourseDashboard component
   - ~250 lines, database query only

2. **section_lecture_handler** - `GET /courses/section/{sectionId}/lecture`
   - Returns lecture script if exists (200 OK)
   - Triggers async generation if needed (202 Accepted)
   - Used by SectionPlayer component
   - ~220 lines

3. **section_generation_status_handler** - `GET /courses/section/{sectionId}/generation-status`
   - Returns generation progress for polling
   - Fast in-memory/DynamoDB lookup
   - Used by SectionPlayer while generating
   - ~150 lines

4. **section_complete_handler** - `POST /courses/section/{sectionId}/complete`
   - Marks section as completed
   - Updates database with completion timestamp
   - Used when user finishes section
   - ~180 lines

### API Gateway Endpoints Added

All endpoints require Cognito authentication and extract `user_id` from JWT token:

| Endpoint | Method | Lambda | Purpose |
|----------|--------|--------|---------|
| `/courses/{courseId}/outline` | GET | course_outline_handler | Get course structure |
| `/courses/section/{sectionId}/lecture` | GET | section_lecture_handler | Get/trigger lecture |
| `/courses/section/{sectionId}/generation-status` | GET | section_generation_status_handler | Poll progress |
| `/courses/section/{sectionId}/complete` | POST | section_complete_handler | Mark complete |

---

## Deployment Steps

### 1. Verify Terraform Changes

```bash
cd terraform/environments/dev

# Initialize (if needed)
terraform init

# Review changes
terraform plan
```

**Expected changes:**
- 4 new Lambda functions
- 4 new API Gateway endpoints
- 4 new Lambda permissions
- API Gateway deployment update

### 2. Deploy to AWS

```bash
terraform apply
```

**Confirm changes** and wait for deployment (~5-10 minutes)

### 3. Verify Lambda Functions

```bash
# List new Lambda functions
aws lambda list-functions --query "Functions[?starts_with(FunctionName, 'docprof-dev-course-outline') || starts_with(FunctionName, 'docprof-dev-section-')].FunctionName"
```

**Expected output:**
```json
[
  "docprof-dev-course-outline-handler",
  "docprof-dev-section-lecture-handler",
  "docprof-dev-section-generation-status-handler",
  "docprof-dev-section-complete-handler"
]
```

### 4. Verify API Gateway Endpoints

```bash
# Get API Gateway URL
API_URL=$(terraform output -raw api_gateway_url)
echo "API Gateway URL: $API_URL"

# Test outline endpoint (requires valid course_id and auth token)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "$API_URL/courses/YOUR_COURSE_ID/outline"
```

### 5. Test with Frontend

**Prerequisites:**
- Frontend running locally or deployed
- User logged in (Cognito token available)
- At least one course created

**Test Flow:**
1. Navigate to Courses tab
2. Click on a course → Should load outline (new endpoint)
3. Click on a section → Should attempt to load lecture (new endpoint)
4. If lecture doesn't exist → Should see "Generating..." (202 response)
5. Frontend should poll generation status (new endpoint)
6. Mark section complete → Should update (new endpoint)

---

## Verification Checklist

### Lambda Functions
- [ ] All 4 Lambda functions deployed
- [ ] All functions in VPC (can access Aurora)
- [ ] All functions have shared code layer attached
- [ ] Environment variables set correctly

### API Gateway
- [ ] All 4 endpoints created
- [ ] All endpoints require Cognito auth
- [ ] CORS headers configured
- [ ] Deployment refreshed

### Database
- [ ] `courses` table exists
- [ ] `course_sections` table exists
- [ ] `section_deliveries` table exists (may not exist yet - will be created by schema_init)

### Frontend Integration
- [ ] Outline loads when clicking course
- [ ] Sections display correctly
- [ ] Lecture endpoint returns 200 (if exists) or 202 (if generating)
- [ ] Status endpoint polls correctly
- [ ] Complete endpoint updates section status

---

## Troubleshooting

### 403 Forbidden
- **Cause:** Cognito token missing or invalid
- **Fix:** Verify user is logged in, check token in API client

### 404 Not Found (Course)
- **Cause:** Course doesn't exist or user doesn't own it
- **Fix:** Verify course_id, check database for course ownership

### 500 Internal Error
- **Cause:** Database connection or query error
- **Fix:** Check CloudWatch logs for specific Lambda function

### Lambda Timeout
- **Cause:** Database query taking too long
- **Fix:** Check Aurora status (may be paused), verify VPC connectivity

---

## CloudWatch Logs

Monitor these log groups:

```bash
# Outline handler
aws logs tail /aws/lambda/docprof-dev-course-outline-handler --follow

# Lecture handler  
aws logs tail /aws/lambda/docprof-dev-section-lecture-handler --follow

# Status handler
aws logs tail /aws/lambda/docprof-dev-section-generation-status-handler --follow

# Complete handler
aws logs tail /aws/lambda/docprof-dev-section-complete-handler --follow
```

---

## Database Queries for Verification

### Check Course Outline
```sql
-- Get course
SELECT course_id, title, status FROM courses LIMIT 1;

-- Get sections for course
SELECT section_id, title, status, order_index 
FROM course_sections 
WHERE course_id = 'YOUR_COURSE_ID'
ORDER BY order_index;
```

### Check Section Deliveries
```sql
-- Check if any lectures exist
SELECT section_id, delivered_at 
FROM section_deliveries 
LIMIT 5;
```

### Check Completed Sections
```sql
-- Get completed sections
SELECT section_id, title, completed_at 
FROM course_sections 
WHERE status = 'completed';
```

---

## Next Steps After Deployment

1. **Test Course Viewing:** Verify outline loads correctly
2. **Test Section Playback:** Verify lectures load or trigger generation
3. **Test Progress Tracking:** Verify completion works
4. **Monitor Performance:** Check Lambda execution times
5. **Check Costs:** Monitor Lambda invocations and database queries

---

## Phase 2 (Next)

Once P0 endpoints are working, implement P1 endpoints:
- `DELETE /courses/{courseId}` - Delete course
- `POST /courses/{courseId}/next` - Get next section
- `POST /courses/{courseId}/standalone` - Get standalone section

**Estimated:** 7 hours (Phase 2)

---

## Files Modified

### New Lambda Handlers
- `src/lambda/course_outline_handler/handler.py`
- `src/lambda/section_lecture_handler/handler.py`
- `src/lambda/section_generation_status_handler/handler.py`
- `src/lambda/section_complete_handler/handler.py`

### Terraform
- `terraform/environments/dev/main.tf` - Added 4 Lambda modules and 4 API endpoints

### Documentation
- `docs/planning/Course_Endpoints_Implementation_Plan.md` - Implementation plan
- `docs/troubleshooting/Expected_API_Endpoints.md` - Endpoint inventory
- `docs/deployment/Phase_1_P0_Endpoints_Deployment.md` - This file

---

## Success Criteria

✅ All 4 Lambda functions deployed and invocable  
✅ All 4 API endpoints accessible via API Gateway  
✅ Frontend can load course outlines  
✅ Frontend can load section lectures (or trigger generation)  
✅ Frontend can mark sections complete  
✅ No errors in CloudWatch logs for valid requests  

**Result:** Basic course viewing and section playback working end-to-end
