# Missing Features Silenced (Frontend Cleanup)

**Date:** 2025-12-29  
**Issue:** Console errors for unimplemented AWS features (audio chunks, metadata)

## Problem

The frontend was trying to load features that haven't been migrated to AWS yet:
1. `/lecture-metadata` endpoint - For text highlighting during audio playback
2. `/audio-chunk/{index}` endpoints - For TTS audio playback

These were producing console errors:
- `GET .../audio-chunk/0 403 (Forbidden)`
- `GET .../lecture-metadata net::ERR_FAILED` with CORS error

## Solution

**Disabled audio preloading and metadata loading until AWS features are ready:**

1. **`useSectionAudio.ts`** - Disabled chunk preloading (both immediate and retry logic)
2. **`SectionPlayer.tsx`** - Disabled metadata loading call

These features will be re-enabled when:
- TTS audio generation is implemented (AWS Polly or Bedrock)
- Metadata endpoint is added for highlighting support

## Current Behavior

✅ **Lecture text displays perfectly** - No audio, no highlighting (graceful degradation)  
✅ **Clean console** - No 403/CORS errors  
✅ **Full functionality** - Chat, Q&A, figures all work

## Future Work

To re-enable these features:
1. Implement TTS audio generation Lambda
2. Add `/lecture-metadata` endpoint
3. Change `if (false ...)` back to `if (...)` in the disabled code
4. Uncomment metadata loading logic

## Files Changed

- `src/frontend/src/hooks/useSectionAudio.ts` - Disabled audio preloading
- `src/frontend/src/components/course/SectionPlayer.tsx` - Disabled metadata loading

