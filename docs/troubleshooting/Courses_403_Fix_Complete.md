# Courses Tab 403 Error - Complete Fix

**Date:** 2025-12-14  
**Issue:** 403 error when clicking Courses tab  
**Status:** ✅ **FIXED** (requires frontend restart)

---

## Root Cause

The `GET /courses` endpoint was missing from API Gateway. While the Lambda function existed and was configured in Terraform, the API Gateway method wasn't deployed.

---

## Fixes Applied

### 1. ✅ Added GET /courses Method
- Created `GET` method on `/courses` resource
- Configured Cognito User Pools authorizer
- Set up AWS_PROXY integration to Lambda

### 2. ✅ Configured Method Responses
- Added 200 status code response
- Configured CORS headers
- Set up integration responses

### 3. ✅ Added Lambda Permissions
- Granted API Gateway permission to invoke `docprof-dev-courses-list`
- Source ARN: `arn:aws:execute-api:us-east-1:176520790264:evjgcsghvi/*/GET/courses`

### 4. ✅ Updated Frontend .env
- Set `VITE_API_GATEWAY_URL` to correct API Gateway URL
- Verified Cognito configuration

### 5. ✅ Deployed API Gateway
- Created new deployment
- Deployed to `dev` stage

---

## Verification

### API Gateway Configuration
```bash
$ aws apigateway get-resource --rest-api-id evjgcsghvi --resource-id g0sodn
{
  "path": "/courses",
  "resourceMethods": {
    "GET": {},      # ✅ Now exists!
    "OPTIONS": {},
    "POST": {}
  }
}
```

### Method Configuration
- **HTTP Method:** GET
- **Authorization:** COGNITO_USER_POOLS
- **Authorizer ID:** vy3b35
- **Integration:** AWS_PROXY → docprof-dev-courses-list
- **Status:** ✅ Configured

---

## Next Steps for User

### 1. Restart Frontend Development Server

**Important:** The frontend needs to be restarted to pick up the updated `.env` file!

```bash
cd src/frontend
# Stop the current dev server (Ctrl+C)
# Then restart:
npm run dev
```

### 2. Verify in Browser

1. Open browser DevTools (F12)
2. Go to Network tab
3. Click "Courses" tab
4. Look for `GET /courses` request
5. Should see:
   - **Status:** 200 OK (not 403!)
   - **Request Headers:** `Authorization: Bearer ...` present
   - **Response:** List of courses (or empty array if no courses)

### 3. If Still Getting 403

Check:
- ✅ Is user logged in? (Check Application > Local Storage)
- ✅ Is `Authorization` header being sent? (Check Network tab)
- ✅ Is token valid? (Check if expired)
- ✅ Is frontend using correct API URL? (Check console for `[API Client] Using API Gateway URL:`)

---

## Troubleshooting

### Issue: Still 403 After Restart

**Check 1: Frontend Environment Variables**
```bash
# In browser console, check:
console.log(import.meta.env.VITE_API_GATEWAY_URL)
# Should be: https://evjgcsghvi.execute-api.us-east-1.amazonaws.com/dev
```

**Check 2: Authorization Header**
- Open DevTools > Network tab
- Find `GET /courses` request
- Check Request Headers
- Should have: `Authorization: Bearer eyJ...`

**Check 3: Token Validity**
- Check if token is expired
- Try logging out and back in
- Verify Cognito User Pool ID matches

**Check 4: API Gateway Deployment**
```bash
# Verify latest deployment is active
aws apigateway get-stage \
  --rest-api-id evjgcsghvi \
  --stage-name dev \
  --query 'deploymentId'
```

### Issue: CORS Error

If you see CORS errors:
- OPTIONS method should be configured (it is)
- Check if preflight request succeeds
- Verify CORS headers in response

### Issue: 401 Unauthorized

If you get 401 instead of 403:
- Token is being sent but is invalid/expired
- User needs to log in again
- Check Cognito configuration

---

## API Gateway Endpoint Details

**URL:** `https://evjgcsghvi.execute-api.us-east-1.amazonaws.com/dev/courses`

**Method:** GET

**Authentication:** Required (Cognito User Pools)

**Response Format:**
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

## Files Modified

1. ✅ API Gateway: Added GET method on `/courses`
2. ✅ `src/frontend/.env`: Updated with correct API Gateway URL
3. ✅ Lambda: Added API Gateway invoke permission

---

## Status

✅ **GET /courses endpoint is LIVE and configured correctly**

**Action Required:**
- ⚠️ **Restart frontend dev server** to pick up `.env` changes
- ⚠️ **Verify user is logged in** before testing
- ⚠️ **Check browser console** for any errors

After restarting the frontend, the Courses tab should work! 🎉
