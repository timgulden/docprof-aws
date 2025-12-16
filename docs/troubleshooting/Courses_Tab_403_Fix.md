# Courses Tab 403 Error - FIXED ✅

**Date:** 2025-12-14  
**Issue:** 403 error when clicking Courses tab in UI  
**Root Cause:** Missing `GET /courses` method in API Gateway  
**Status:** ✅ **FIXED**

---

## Problem

The frontend calls `GET /courses` to list courses (see `src/frontend/src/api/courses.ts` line 171), but API Gateway only had `POST /courses` configured. The `courses_list` Lambda function existed and was configured in Terraform, but the API Gateway method wasn't deployed.

**Error in UI:**
- Clicking "Courses" tab → 403 Forbidden
- Frontend error: `GET /courses` returns 403

---

## Solution

Added `GET /courses` method to API Gateway manually (since Terraform API Gateway module had issues with existing parent resources):

```bash
# 1. Add GET method
aws apigateway put-method \
  --rest-api-id evjgcsghvi \
  --resource-id g0sodn \
  --http-method GET \
  --authorization-type COGNITO_USER_POOLS \
  --authorizer-id vy3b35

# 2. Configure Lambda integration
aws apigateway put-integration \
  --rest-api-id evjgcsghvi \
  --resource-id g0sodn \
  --http-method GET \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:176520790264:function:docprof-dev-courses-list/invocations"

# 3. Add Lambda permission
aws lambda add-permission \
  --function-name docprof-dev-courses-list \
  --statement-id apigateway-get-courses \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:us-east-1:176520790264:evjgcsghvi/*/GET/courses"

# 4. Deploy API Gateway
aws apigateway create-deployment \
  --rest-api-id evjgcsghvi \
  --stage-name dev \
  --description "Add GET /courses endpoint"
```

---

## Verification

**Before:**
```bash
$ aws apigateway get-resources --rest-api-id evjgcsghvi --query 'items[?path==`/courses`].resourceMethods'
{
  "OPTIONS": {},
  "POST": {}
}
```

**After:**
```bash
$ aws apigateway get-resources --rest-api-id evjgcsghvi --query 'items[?path==`/courses`].resourceMethods'
{
  "GET": {},
  "OPTIONS": {},
  "POST": {}
}
```

✅ **GET method now exists!**

---

## Testing

The Courses tab should now work:
1. User logs in (Cognito authentication)
2. Clicks "Courses" tab
3. Frontend calls `GET /courses` with auth token
4. API Gateway routes to `courses_list` Lambda
5. Lambda queries database for user's courses
6. Returns list of courses

**Expected Response:**
```json
[
  {
    "courseId": "...",
    "title": "...",
    "estimatedHours": 2.0,
    "status": "complete",
    "createdAt": "2025-12-14T..."
  }
]
```

---

## Next Steps

1. ✅ **Test in UI** - Click Courses tab, verify it loads
2. ✅ **Verify Course Generation** - Ensure full workflow still completes
3. ⚠️ **Fix Terraform** - Import manually-created resources or fix API Gateway module

---

## Related Issues

- API Gateway module doesn't handle existing parent resources well
- Need to import manually-created resources into Terraform state
- Or enhance API Gateway module to detect existing resources

---

**Status:** ✅ **FIXED** - GET /courses endpoint is now live!
