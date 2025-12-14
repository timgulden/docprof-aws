# Debug: Frontend Still Calling Localhost

## Quick Check

Open browser DevTools (F12) and check:

1. **Console Tab** - Look for:
   ```
   [API Client] Using API Gateway URL: https://xp2vbfyu3f.execute-api.us-east-1.amazonaws.com/dev
   [API Client] Final API_URL: https://xp2vbfyu3f.execute-api.us-east-1.amazonaws.com/dev
   ```
   
   If you DON'T see these logs, the dev server wasn't restarted after the code changes.

2. **Network Tab** - Look for the `/books` request:
   - Should be: `https://xp2vbfyu3f.execute-api.us-east-1.amazonaws.com/dev/books`
   - NOT: `http://localhost:8000/api/books`

## If Still Seeing Localhost

### Step 1: Verify .env File
```bash
cd src/frontend
cat .env
```

Should show:
```
VITE_API_GATEWAY_URL=https://xp2vbfyu3f.execute-api.us-east-1.amazonaws.com/dev
```

### Step 2: Stop Dev Server
Press `Ctrl+C` in the terminal where `npm run dev` is running.

### Step 3: Restart Dev Server
```bash
cd src/frontend
npm run dev
```

### Step 4: Hard Refresh Browser
- Mac: `Cmd+Shift+R`
- Windows/Linux: `Ctrl+Shift+R`

### Step 5: Check Console Again
You should now see the `[API Client]` logs.

## If Still Not Working

Check if there are multiple `.env` files:
```bash
find src/frontend -name ".env*"
```

Make sure `.env` is in `src/frontend/` directory, not `src/` or root.

## Alternative: Check Environment Variables at Runtime

Add this to browser console:
```javascript
console.log('VITE_API_GATEWAY_URL:', import.meta.env.VITE_API_GATEWAY_URL);
console.log('All VITE_ vars:', Object.keys(import.meta.env).filter(k => k.startsWith('VITE_')));
```

This will show what Vite actually loaded.

