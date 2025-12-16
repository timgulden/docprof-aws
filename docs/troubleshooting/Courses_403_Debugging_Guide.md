# Courses Tab 403 Error - Debugging Guide

**Date:** 2025-12-14  
**Issue:** Still getting 403 error on Courses tab  
**Status:** 🔍 **DEBUGGING IN PROGRESS**

---

## What We've Fixed

1. ✅ **GET /courses method** - Added to API Gateway
2. ✅ **Lambda integration** - Configured correctly
3. ✅ **Method responses** - Added 200 response with CORS headers
4. ✅ **Lambda permissions** - API Gateway can invoke Lambda

---

## Current Configuration

### API Gateway
- **Resource:** `/courses` (ID: `g0sodn`)
- **Method:** `GET`
- **Authorizer:** Cognito User Pools (`vy3b35`)
- **Integration:** AWS_PROXY to `docprof-dev-courses-list` Lambda
- **CORS:** OPTIONS method configured

### Lambda Function
- **Name:** `docprof-dev-courses-list`
- **Status:** ✅ Deployed
- **Permissions:** ✅ API Gateway can invoke

---

## Possible Causes of 403

### 1. **Authentication Token Not Sent**
- Frontend not including `Authorization: Bearer <token>` header
- Token expired or invalid
- Amplify auth session not available

### 2. **CORS Preflight Failure**
- OPTIONS request failing
- CORS headers not configured correctly
- Browser blocking the request

### 3. **Authorizer Rejection**
- Token format incorrect
- Token not from correct Cognito User Pool
- Authorizer configuration issue

### 4. **API Gateway Configuration**
- Method not properly deployed
- Authorizer not attached correctly
- Integration response missing

---

## Debugging Steps

### Step 1: Check Browser DevTools

1. Open browser DevTools (F12)
2. Go to Network tab
3. Click "Courses" tab in UI
4. Look for the `GET /courses` request
5. Check:
   - **Request Headers:** Is `Authorization: Bearer ...` present?
   - **Response Status:** What's the exact status code?
   - **Response Body:** What error message?
   - **Response Headers:** Any CORS headers?

### Step 2: Check Frontend Console

Look for:
- `[API Client] Using API Gateway URL: ...` - Is it correct?
- Any auth errors?
- Any CORS errors?

### Step 3: Verify API Gateway URL

Check if frontend is using correct API Gateway URL:
```bash
# Should be:
https://evjgcsghvi.execute-api.us-east-1.amazonaws.com/dev
```

Check frontend `.env` file or environment variables:
```bash
VITE_API_GATEWAY_URL=https://evjgcsghvi.execute-api.us-east-1.amazonaws.com/dev
```

### Step 4: Test with curl (with token)

```bash
# Get token from browser DevTools (Application > Local Storage or Network tab)
TOKEN="your-cognito-id-token-here"

# Test endpoint
curl -v -H "Authorization: Bearer $TOKEN" \
  "https://evjgcsghvi.execute-api.us-east-1.amazonaws.com/dev/courses"
```

### Step 5: Check CloudWatch Logs

```bash
# API Gateway logs (if enabled)
aws logs tail /aws/apigateway/docprof-dev-api --follow

# Lambda logs
aws logs tail /aws/lambda/docprof-dev-courses-list --follow
```

---

## Common Issues & Fixes

### Issue 1: Token Not Being Sent

**Symptom:** Request has no `Authorization` header

**Fix:**
- Check if user is logged in
- Verify Amplify auth is configured
- Check `src/frontend/src/config/amplify.ts`

### Issue 2: CORS Error

**Symptom:** Browser console shows CORS error

**Fix:**
- Verify OPTIONS method is configured
- Check CORS headers in method responses
- Ensure `Access-Control-Allow-Origin` includes frontend origin

### Issue 3: Authorizer Rejection

**Symptom:** 403 with `UnauthorizedException` or similar

**Fix:**
- Verify token is from correct Cognito User Pool
- Check authorizer configuration
- Ensure token hasn't expired

### Issue 4: Wrong API URL

**Symptom:** Request going to wrong endpoint

**Fix:**
- Set `VITE_API_GATEWAY_URL` in frontend `.env`
- Verify frontend is using correct base URL

---

## Quick Test Commands

### Test Lambda Directly
```bash
echo '{"requestContext":{"authorizer":{"claims":{"sub":"test-user-123"}}}}' | base64 > /tmp/test.json
aws lambda invoke --function-name docprof-dev-courses-list \
  --payload fileb:///tmp/test.json /tmp/response.json
cat /tmp/response.json | python3 -m json.tool
```

### Test API Gateway (without auth - should get 401/403)
```bash
curl -v "https://evjgcsghvi.execute-api.us-east-1.amazonaws.com/dev/courses"
```

### Test API Gateway (with auth token)
```bash
# Get token from browser
TOKEN="..."
curl -v -H "Authorization: Bearer $TOKEN" \
  "https://evjgcsghvi.execute-api.us-east-1.amazonaws.com/dev/courses"
```

---

## Next Steps

1. **Get exact error from browser DevTools**
   - What's the full request/response?
   - What headers are being sent?
   - What's the error message?

2. **Check frontend environment**
   - Is `VITE_API_GATEWAY_URL` set correctly?
   - Is user logged in?
   - Is Amplify auth working?

3. **Verify token**
   - Is token being sent?
   - Is token valid?
   - Is token from correct User Pool?

---

## Current Status

- ✅ GET /courses method exists
- ✅ Lambda integration configured
- ✅ Method responses added
- ⚠️ **Need browser DevTools output to diagnose further**

**Please provide:**
1. Browser DevTools Network tab screenshot or details
2. Browser console errors
3. Exact error message from the 403 response
