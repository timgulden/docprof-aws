# Courses Tab 403 Error - Step-by-Step Fix

**Date:** 2025-12-14  
**Issue:** 403 Forbidden when clicking Courses tab  
**Status:** 🔍 **DEBUGGING** - Endpoint configured, need to verify authentication

---

## ✅ What's Already Fixed

1. ✅ **GET /courses method** - Added to API Gateway
2. ✅ **Lambda integration** - Configured correctly  
3. ✅ **Method responses** - Added with CORS headers
4. ✅ **Authorizer** - Cognito User Pools (same as POST method)
5. ✅ **Frontend .env** - Has correct API Gateway URL

---

## 🔍 Step-by-Step Diagnosis

### Step 1: Check Browser DevTools

1. **Open Browser DevTools** (F12 or Cmd+Option+I)
2. **Go to Network tab**
3. **Clear network log** (trash icon)
4. **Click "Courses" tab** in the UI
5. **Find the `GET /courses` request**

**What to look for:**

#### Request Details:
- **URL:** Should be `https://evjgcsghvi.execute-api.us-east-1.amazonaws.com/dev/courses`
- **Method:** GET
- **Status Code:** What is it? (403, 401, 200?)

#### Request Headers:
- ✅ **Authorization:** Should be `Bearer eyJ...` (long token)
- ✅ **Origin:** Should match your frontend URL
- ✅ **Content-Type:** `application/json`

#### Response:
- **Status:** What's the exact status code?
- **Response Body:** What's the error message?
- **Response Headers:** Any CORS headers?

---

### Step 2: Check Frontend Console

Look for:
- `[API Client] Using API Gateway URL: ...` - Is it correct?
- Any authentication errors?
- Any CORS errors?
- Any network errors?

---

### Step 3: Verify User is Logged In

1. **Check Application tab** in DevTools
2. **Local Storage** or **Session Storage**
3. Look for:
   - Cognito tokens
   - Auth session data
   - User info

**If not logged in:**
- Log in first
- Then try Courses tab again

---

### Step 4: Check Token Validity

If you see an `Authorization` header in the request:

1. **Copy the token** (the part after `Bearer `)
2. **Check if it's expired:**
   - Go to https://jwt.io
   - Paste the token
   - Check the `exp` field
   - Compare with current time

**If token is expired:**
- Log out and log back in
- Try again

---

### Step 5: Test Endpoint Directly

If you have a valid token, test with curl:

```bash
# Get token from browser DevTools > Network tab > Request Headers > Authorization
TOKEN="your-token-here"

# Test endpoint
curl -v -H "Authorization: Bearer $TOKEN" \
  "https://evjgcsghvi.execute-api.us-east-1.amazonaws.com/dev/courses"
```

**Expected:**
- Status 200 with JSON array of courses
- Or status 200 with empty array `[]`

**If you get 403:**
- Token might be invalid
- Token might be from wrong User Pool
- Authorizer might be misconfigured

---

## 🐛 Common Issues & Fixes

### Issue 1: No Authorization Header

**Symptom:** Request has no `Authorization` header

**Fix:**
1. Check if user is logged in
2. Check `src/frontend/src/config/amplify.ts` - Is Amplify configured?
3. Check browser console for auth errors
4. Try logging out and back in

### Issue 2: Token Expired

**Symptom:** Token exists but is expired

**Fix:**
1. Log out
2. Log back in
3. Try Courses tab again

### Issue 3: Wrong API Gateway URL

**Symptom:** Request going to wrong URL

**Fix:**
1. Check `src/frontend/.env`:
   ```
   VITE_API_GATEWAY_URL=https://evjgcsghvi.execute-api.us-east-1.amazonaws.com/dev
   ```
2. **Restart frontend dev server** after changing .env
3. Check browser console for `[API Client] Using API Gateway URL: ...`

### Issue 4: CORS Error

**Symptom:** Browser console shows CORS error

**Fix:**
- OPTIONS method is configured
- CORS headers are set
- Check if preflight (OPTIONS) request succeeds

### Issue 5: Authorizer Rejection

**Symptom:** Token is valid but still 403

**Possible causes:**
1. Token from wrong Cognito User Pool
2. Authorizer configuration issue
3. API Gateway deployment issue

**Fix:**
- Verify Cognito User Pool ID matches:
  - Frontend: `VITE_COGNITO_USER_POOL_ID=us-east-1_JzXm5t3RT`
  - Authorizer: Check API Gateway authorizer config

---

## 🔧 Quick Fixes to Try

### Fix 1: Restart Frontend
```bash
cd src/frontend
# Stop dev server (Ctrl+C)
npm run dev
```

### Fix 2: Clear Browser Cache
- Clear browser cache and cookies
- Or use incognito/private window
- Log in again
- Try Courses tab

### Fix 3: Verify Environment Variables
```bash
# Check .env file
cat src/frontend/.env

# Should have:
# VITE_API_GATEWAY_URL=https://evjgcsghvi.execute-api.us-east-1.amazonaws.com/dev
# VITE_COGNITO_USER_POOL_ID=us-east-1_JzXm5t3RT
# VITE_COGNITO_USER_POOL_CLIENT_ID=547fdlbctm7ca93bcan5nlcc6o
```

### Fix 4: Test with curl (if you have token)
```bash
# Get token from browser DevTools
TOKEN="..."

# Test
curl -H "Authorization: Bearer $TOKEN" \
  "https://evjgcsghvi.execute-api.us-east-1.amazonaws.com/dev/courses"
```

---

## 📊 Current Configuration Status

### API Gateway
- ✅ GET /courses method: **CONFIGURED**
- ✅ Authorizer: **COGNITO_USER_POOLS (vy3b35)**
- ✅ Integration: **AWS_PROXY → docprof-dev-courses-list**
- ✅ CORS: **CONFIGURED**
- ✅ Deployment: **LATEST (oywbaa)**

### Lambda
- ✅ Function: **docprof-dev-courses-list**
- ✅ Permissions: **API Gateway can invoke**
- ✅ Code: **Deployed**

### Frontend
- ✅ .env file: **Has correct API Gateway URL**
- ✅ Amplify config: **Configured**
- ⚠️ **Needs restart** to pick up .env changes

---

## 🎯 Next Steps

1. **Open browser DevTools** and check the actual request/response
2. **Share the details:**
   - Request URL
   - Request headers (especially Authorization)
   - Response status code
   - Response body/error message
   - Any console errors

3. **Or test with curl** if you can get a token:
   ```bash
   # Get token from browser
   TOKEN="..."
   curl -v -H "Authorization: Bearer $TOKEN" \
     "https://evjgcsghvi.execute-api.us-east-1.amazonaws.com/dev/courses"
   ```

---

## 📝 What We Need From You

To diagnose the exact issue, please provide:

1. **Browser DevTools > Network tab:**
   - Screenshot of the `GET /courses` request
   - Or copy the request/response details

2. **Browser Console:**
   - Any error messages
   - The `[API Client] Using API Gateway URL:` message

3. **Application tab:**
   - Is user logged in?
   - Any auth tokens in storage?

With this information, we can pinpoint the exact cause and fix it!

---

**Current Status:** Endpoint is configured correctly. The 403 is likely an authentication/token issue that needs browser-level debugging to resolve.
