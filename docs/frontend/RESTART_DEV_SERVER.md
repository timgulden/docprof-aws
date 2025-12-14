# Important: Restart Dev Server After .env Changes

## Problem
If you change `.env` file, **Vite does NOT automatically reload environment variables**. The dev server must be restarted.

## Solution

1. **Stop the dev server** (Ctrl+C in the terminal where `npm run dev` is running)

2. **Restart the dev server**:
   ```bash
   cd src/frontend
   npm run dev
   ```

3. **Hard refresh your browser** (Cmd+Shift+R on Mac, Ctrl+Shift+R on Windows/Linux)

4. **Check the browser console** - you should see:
   ```
   [API Client] Using API Gateway URL: https://xp2vbfyu3f.execute-api.us-east-1.amazonaws.com/dev
   [API Client] Final API_URL: https://xp2vbfyu3f.execute-api.us-east-1.amazonaws.com/dev
   ```

## Verify It's Working

1. Open browser DevTools (F12)
2. Go to Network tab
3. Reload the page
4. Look for requests to `/books`
5. Check the request URL - it should be:
   `https://xp2vbfyu3f.execute-api.us-east-1.amazonaws.com/dev/books`
   
   NOT:
   `http://localhost:8000/api/books`

## If Still Seeing Wrong URL

1. Check `.env` file exists in `src/frontend/`
2. Verify all variables start with `VITE_`
3. Make sure there are no spaces around `=`
4. Restart dev server again
5. Clear browser cache and hard refresh

