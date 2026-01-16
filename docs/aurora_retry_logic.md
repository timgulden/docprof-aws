# Aurora Cold-Start Retry Logic

## Problem
Aurora Serverless v2 with `MinCapacity: 0.0` scales down to zero ACUs when idle. When a user tries to access data after idle period, the Lambda times out waiting for Aurora to wake up (15-30 seconds).

## Solution
Implemented automatic retry logic in the frontend API client to gracefully handle database cold starts.

## Implementation

### 1. **Retry Utility (`src/frontend/src/api/client.ts`)**
Added `withRetry()` function with configurable retry behavior:
- **Max Retries:** 2 (3 total attempts)
- **Retry Delay:** 3 seconds (enough for Aurora to wake up)
- **Retryable Status Codes:** 500, 502, 503, 504 (server errors only)
- **Non-retryable:** Client errors (400, 401, 404, etc.) fail immediately

### 2. **Applied to Key Endpoints**
- **Books API:** `fetchAllBooks()`
- **Courses API:** `listCourses()`, `getCourseOutline()`

### 3. **User Experience Improvements**
- Loading messages inform users that database may be waking up
- Console logs show retry attempts for debugging
- Automatic retry is transparent to the user
- Only shows error if all 3 attempts fail

## How It Works

1. **First Request (Cold Start):**
   - User loads Sources page
   - Frontend calls `/books` endpoint
   - Lambda times out connecting to Aurora (15-30s)
   - Returns 500 error

2. **Automatic Retry:**
   - Frontend waits 3 seconds
   - Retries `/books` endpoint
   - Aurora is now awake and responsive
   - Request succeeds ✅

3. **User Experience:**
   - Sees "Loading books... If database is waking up, this may take up to 30 seconds"
   - Wait time: ~18-33 seconds on first access after idle
   - Subsequent requests: < 1 second (database stays warm for ~1 hour)

## Cost Savings
- **Without retry:** Need `MinCapacity: 0.5` → **$43/month idle**
- **With retry:** Keep `MinCapacity: 0.0` → **~$1/month idle**
- **Savings:** **$42/month** ($504/year)

## Trade-offs
- **Pro:** Massive cost savings on idle database
- **Pro:** Still fast for active usage (database stays warm for 1 hour)
- **Con:** First request after 1 hour idle takes 18-33 seconds
- **Con:** Slightly more complex error handling

## Testing
1. Let database idle for 1+ hour
2. Load Sources page
3. Should see loading message, then books load after ~30s
4. Immediate subsequent requests should be fast

## Future Enhancements
- Add exponential backoff for longer outages
- Add visual "waking up database" indicator
- Implement predictive warm-up (ping DB before user action)
