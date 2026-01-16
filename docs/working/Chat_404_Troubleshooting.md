# Chat 404 Error - Troubleshooting

**Issue:** Getting 404 error when sending chat message  
**Date:** December 26, 2025

---

## Quick Checks

### 1. Check Browser Console
Open Developer Tools (F12) → Network tab

Look for:
- Which exact URL is getting 404?
- Is it GET or POST?
- What's the request payload?
- What's the response?

### 2. Verify API Endpoints

**Available endpoints:**
- ✅ `POST /chat/message` - Send chat message (non-streaming)
- ✅ `GET /chat/sessions` - List sessions
- ✅ `POST /chat/sessions` - Create session
- ✅ `GET /chat/sessions/{sessionId}` - Get session
- ❌ `POST /chat/message-stream` - NOT AVAILABLE (streaming not implemented)

### 3. Check Frontend Configuration

```bash
cd src/frontend
cat .env
```

Should show:
```
VITE_API_GATEWAY_URL=https://evjgcsghvi.execute-api.us-east-1.amazonaws.com/dev
```

### 4. Test API Directly

```bash
export AWS_PROFILE=docprof-dev AWS_DEFAULT_REGION=us-east-1

# Get Cognito token first (from browser localStorage or login)
TOKEN="<your-token>"

# Test chat endpoint
curl -X POST https://evjgcsghvi.execute-api.us-east-1.amazonaws.com/dev/chat/message \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is DCF valuation?",
    "session_id": null,
    "with_audio": false
  }'
```

---

## Common Issues

### Issue 1: Wrong Endpoint Path

**Symptom:** 404 on `/chat/message-stream`

**Cause:** Frontend trying to use streaming (not implemented)

**Fix:** Frontend should use `sendChatMessage` not `streamChatMessage`

Check: `src/frontend/src/api/chatExecutor.ts` line 35 - should use `sendChatMessage`

### Issue 2: Missing Session

**Symptom:** 404 on `/chat/sessions/{sessionId}`

**Cause:** Trying to load a session that doesn't exist

**Fix:** Create new session or check session ID

### Issue 3: CORS Error (not 404 but similar)

**Symptom:** Request blocked by CORS

**Cause:** API Gateway CORS not configured for localhost

**Fix:** Check API Gateway CORS settings

---

## Backend Status

### Lambda Functions
```bash
aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `docprof-dev-chat`)].FunctionName'
```

Should show:
- `docprof-dev-chat-handler`

### API Gateway Resources
```bash
aws apigateway get-resources --rest-api-id evjgcsghvi \
  --query 'items[?contains(path, `chat`)].[path,resourceMethods]'
```

Should show:
- `/chat/message` with POST method
- `/chat/sessions` with GET, POST methods
- `/chat/sessions/{sessionId}` with GET, DELETE, PATCH methods

---

## Debug Steps

1. **Check exact URL in browser console**
   - Open DevTools → Network tab
   - Try sending message again
   - Click on failed request
   - Note the full URL

2. **Check if it's a session-related 404**
   - Look for requests to `/chat/sessions/{sessionId}`
   - Session might not exist or be expired

3. **Check authentication**
   - Look for 401/403 errors (not 404 but related)
   - Verify token in localStorage: `auth_token`

4. **Check CloudWatch logs**
   ```bash
   aws logs tail /aws/lambda/docprof-dev-chat-handler --follow
   ```

---

## Next Steps

Once you identify the exact 404 URL:

1. **If it's `/chat/message-stream`:**
   - Streaming not implemented yet
   - Frontend should use non-streaming endpoint

2. **If it's `/chat/sessions/{sessionId}`:**
   - Session doesn't exist
   - Create new session or use existing one

3. **If it's something else:**
   - Check if endpoint exists in API Gateway
   - Check Lambda function logs
   - Verify request format

---

**Status:** Awaiting browser console details to identify exact 404 URL

