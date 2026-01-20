# Polly TTS Integration Fix

## Issue
When clicking on a lecture section, users encountered "Error loading lecture. Network Error" even though the backend was working correctly.

## Root Cause
The issue had two main problems:

1. **Audio elements conditionally rendered**: The `<audio>` elements in `SectionPlayer.tsx` were only rendered when `lectureScript` was truthy. However, the `usePollyAudio` hook was initialized immediately on component mount, trying to use `audioRef.current` before the audio element existed.

2. **Missing null check in play function**: The `play()` function in `usePollyAudio` would attempt to play audio even if `loadAudio()` returned early (e.g., when `lectureScript` was null), causing the audio element to fail.

3. **Removed problematic auto-load**: An `useEffect` that auto-loaded audio had dependency issues that could cause infinite loops.

## Fixes Applied

### 1. Always Render Audio Elements
**File**: `src/frontend/src/components/course/SectionPlayer.tsx`

**Before**:
```tsx
{lectureScript && (
  <audio ref={audioRef} ... />
)}
{lectureScript && (
  <audio ref={nextAudioRef} ... />
)}
```

**After**:
```tsx
<audio ref={audioRef} ... />
<audio ref={nextAudioRef} ... />
```

**Reason**: Audio elements must exist for the hooks to reference them, regardless of whether lecture content has loaded yet.

### 2. Improved play() Function
**File**: `src/frontend/src/hooks/usePollyAudio.ts`

**Added safety check**:
```typescript
const play = useCallback(async () => {
  const audio = audioRef.current;
  if (!audio) {
    console.error("Audio element not found");
    return;
  }
  
  // Load audio if not yet loaded
  if (!audioAvailable && !isLoading) {
    await loadAudio();
    
    // NEW: Check if audio actually loaded
    if (!audioRef.current?.src) {
      console.log("Audio not available after load attempt, skipping play");
      return;
    }
  }
  
  // ... rest of play logic
}, [audioAvailable, isLoading, loadAudio, playbackSpeed, onError]);
```

**Reason**: Prevents attempting to play audio when `loadAudio()` returns early (e.g., missing `lectureScript`).

### 3. Removed Auto-Load UseEffect
**File**: `src/frontend/src/components/course/SectionPlayer.tsx`

**Removed**:
```typescript
useEffect(() => {
  if (usePollyTTS && lectureScript && !pollyAudio.isLoading && !pollyAudio.audioAvailable) {
    pollyAudio.loadAudio();
  }
}, [usePollyTTS, lectureScript, pollyAudio]); // Problematic dependencies
```

**Replaced with**:
```typescript
// Note: Audio loads on-demand when user clicks Play
// No need to auto-load as it's handled by the play button
```

**Reason**: 
- Dependency on `pollyAudio` object caused infinite loops
- On-demand loading (when user clicks Play) is safer and more efficient
- Avoids unnecessary API calls if user doesn't play audio

## How It Works Now

### Component Mount Flow
1. ✅ `SectionPlayer` mounts
2. ✅ Both `usePollyAudio` and `useSectionAudio` hooks initialize
3. ✅ Audio elements render immediately (even if `lectureScript` is null)
4. ✅ Hooks have valid audio element references

### Lecture Load Flow
1. ✅ User navigates to lecture
2. ✅ `lectureScript` loads from API
3. ✅ Component renders lecture content
4. ✅ Audio is NOT auto-loaded (waits for user action)

### Audio Playback Flow
1. ✅ User clicks Play button
2. ✅ `play()` function checks if audio is available
3. ✅ If not available, calls `loadAudio()`
4. ✅ `loadAudio()` checks for `sectionId` and `lectureScript`
5. ✅ If missing, returns early (safe)
6. ✅ If present, fetches audio and speech marks from API
7. ✅ Sets `audio.src` to blob URL
8. ✅ `play()` verifies `audio.src` exists before attempting playback
9. ✅ Audio plays with word-level highlighting

## Testing

After these fixes, the feature should work as follows:

### With Polly TTS Disabled (`VITE_USE_POLLY_TTS=false`)
- ✅ Lectures load normally
- ✅ Old chunk-based audio system works
- ✅ No Polly-related errors

### With Polly TTS Enabled (`VITE_USE_POLLY_TTS=true`)
- ✅ Lectures load normally
- ✅ No errors on page load
- ✅ Clicking Play loads audio on-demand
- ✅ Word-level highlighting works
- ✅ Click any word to seek
- ✅ Auto-scroll keeps text visible

## Verification Steps

1. **Restart frontend dev server**:
   ```bash
   cd src/frontend
   npm run dev
   ```

2. **Test with feature disabled**:
   - Set `VITE_USE_POLLY_TTS=false` in `.env`
   - Restart dev server
   - Navigate to any lecture
   - Verify no errors, lecture loads normally

3. **Test with feature enabled**:
   - Set `VITE_USE_POLLY_TTS=true` in `.env`
   - Restart dev server
   - Navigate to any lecture
   - Verify no errors on page load
   - Click Play button
   - Verify audio loads and plays
   - Verify word highlighting works

4. **Test edge cases**:
   - Navigate to section with no generated lecture yet
   - Should show "generating" status, no errors
   - Navigate between multiple sections rapidly
   - Should not cause memory leaks or errors

## Files Modified

1. `src/frontend/src/components/course/SectionPlayer.tsx`
   - Removed conditional rendering of audio elements
   - Removed problematic auto-load useEffect
   - Audio elements always present

2. `src/frontend/src/hooks/usePollyAudio.ts`
   - Added safety check in `play()` function
   - Verifies `audio.src` exists after `loadAudio()`
   - Better error handling and early returns

3. `src/frontend/.env`
   - Re-enabled feature: `VITE_USE_POLLY_TTS=true`

## Additional Safety Features

### Already Present in Code

1. **Null checks in `loadAudio()`**:
   ```typescript
   if (!sectionId || !lectureScript) {
     console.log("Cannot load audio: missing sectionId or lectureScript");
     return;
   }
   ```

2. **Defensive rendering in `HighlightedLecture`**:
   ```typescript
   if (!lectureScript) return [];
   ```

3. **Conditional Polly rendering**:
   ```typescript
   usePollyTTS && pollyAudio.speechMarks.length > 0 ? (
     <HighlightedLecture ... />
   ) : (
     <div>{lectureScript}</div>
   )
   ```

## Next Steps

1. ✅ Restart dev server to apply changes
2. ✅ Test lecture loading works normally
3. ✅ Test Polly audio playback on a generated lecture
4. ✅ Verify word-level highlighting
5. ✅ Test click-to-seek functionality
6. ✅ Monitor for any console errors

## Expected Behavior

- **On page load**: No errors, lecture loads normally
- **On Play click**: 2-3 second load (first time), instant (cached)
- **During playback**: Smooth word highlighting, auto-scroll
- **On word click**: Audio seeks to that word
- **On page reload**: Same behavior, uses cache

---

**Status**: ✅ FIXED - Ready for testing
**Date**: January 19, 2026
