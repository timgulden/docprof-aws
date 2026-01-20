# Lecture TTS with AWS Polly - Deployment Summary

## Date: January 19, 2026

## Status: ✅ DEPLOYED

## What Was Deployed

### Backend Infrastructure
1. **Lambda Function**: `docprof-dev-section-audio-handler`
   - Runtime: Python 3.11
   - Memory: 512 MB
   - Timeout: 120 seconds
   - VPC-enabled for database access
   - Environment variables configured

2. **S3 Bucket**: `docprof-dev-audio-cache`
   - Server-side encryption enabled
   - 30-day lifecycle policy
   - CORS configured for frontend access

3. **API Gateway Routes**:
   - `GET /courses/section/{sectionId}/audio` → Returns MP3 audio
   - `GET /courses/section/{sectionId}/speech-marks` → Returns timing JSON
   - Both protected with Cognito authentication
   - Lambda proxy integration

### Backend Code
- `src/lambda/shared/polly_client.py` - Polly client with chunking and speech marks
- `src/lambda/section_audio_handler/handler.py` - Lambda handler for audio endpoints

### Frontend Code
1. **New Components**:
   - `src/frontend/src/hooks/usePollyAudio.ts` - Audio playback and sync hook
   - `src/frontend/src/components/course/HighlightedLecture.tsx` - Word-level highlighting
   
2. **Updated Components**:
   - `src/frontend/src/components/course/SectionPlayer.tsx` - Integrated Polly system
   - `src/frontend/src/api/courses.ts` - Added audio API calls

3. **Configuration**:
   - `src/frontend/.env` - Set `VITE_USE_POLLY_TTS=true`

## API Endpoints

Base URL: `https://evjgcsghvi.execute-api.us-east-1.amazonaws.com/dev`

### Get Audio
```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://evjgcsghvi.execute-api.us-east-1.amazonaws.com/dev/courses/section/{sectionId}/audio \
  -o lecture_audio.mp3
```

### Get Speech Marks
```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://evjgcsghvi.execute-api.us-east-1.amazonaws.com/dev/courses/section/{sectionId}/speech-marks
```

## How It Works

1. **User clicks Play** on a lecture
2. **Frontend** (`usePollyAudio` hook):
   - Fetches audio and speech marks from API
   - Creates audio element for playback
   - Starts binary search through marks as audio plays
3. **Lambda** (`section_audio_handler`):
   - Checks S3 cache for existing audio/marks
   - If not cached: generates via Polly, saves to S3
   - Returns MP3 or JSON to frontend
4. **UI** (`HighlightedLecture`):
   - Renders lecture as individual word spans
   - Highlights current word (yellow) and sentence (subtle)
   - Auto-scrolls to keep current word visible
   - Click any word to seek audio to that position

## Testing

To test the feature:

1. **Start frontend dev server**:
   ```bash
   cd src/frontend
   npm run dev
   ```

2. **Navigate to a lecture** in the app

3. **Click Play** - Audio should load in 2-3 seconds (first time)

4. **Verify**:
   - ✓ Words highlight in yellow as spoken
   - ✓ Current sentence has subtle background
   - ✓ Auto-scroll keeps text visible
   - ✓ Click any word to jump to that position
   - ✓ Reload page and play again - should be instant (cached)

## Features

- **Word-level highlighting**: Precise sync with audio
- **Sentence context**: Subtle highlighting of current sentence
- **Click-to-seek**: Jump to any word in the lecture
- **Auto-scroll**: Keeps current word visible
- **S3 caching**: First play generates, subsequent plays instant
- **On-demand generation**: Only creates audio when requested
- **Smooth playback**: No gaps, even for long lectures
- **Neural voice**: AWS Polly Matthew (male, professional)

## Configuration

### Change Polly Voice

Edit `terraform/environments/dev/main.tf`:
```hcl
environment_variables = {
  POLLY_VOICE_ID = "Joanna"  # Matthew, Joanna, Kevin, Ruth, Stephen
  POLLY_ENGINE   = "neural"  # neural, standard
}
```

Then run: `terraform apply`

### Disable Feature

Edit `src/frontend/.env`:
```
VITE_USE_POLLY_TTS=false
```

Or remove the line entirely. Restart dev server.

## Recent Fixes (Jan 19, 2026)

### Fixed: "Network Error" on Lecture Load
**Issue**: Audio elements were conditionally rendered, causing hooks to reference non-existent elements.

**Solution**:
1. Audio elements now always render (not conditional on lectureScript)
2. Added safety check in `play()` to verify audio loaded before playing
3. Removed problematic auto-load useEffect

**See**: `POLLY_TTS_FIX.md` for detailed explanation.

## Known Issues

None currently.

## Cost Estimates

- **Polly TTS**: ~$16 per 1M characters
- **S3 Storage**: ~$0.023 per GB-month
- **Lambda**: Minimal (execution time <2s per lecture)
- **API Gateway**: Minimal (2 requests per lecture)

Example for 100 lectures (10,000 chars each):
- First generation: 1M chars × $16/1M = $16
- Storage: 50MB × $0.023/GB = $0.001/month
- Subsequent plays: Free (served from cache)

## Troubleshooting

### Audio doesn't load

Check Lambda logs:
```bash
aws logs tail /aws/lambda/docprof-dev-section-audio-handler --follow
```

Common causes:
- Lecture not yet generated
- Polly quota exceeded
- Database connection issue

### Speech marks don't sync

- Clear browser cache
- Delete audio from S3 cache: `aws s3 rm s3://docprof-dev-audio-cache/lectures/{sectionId}/`
- Regenerate audio

### API returns 403/401

- Token expired - re-login
- User doesn't have access to section
- Cognito authorizer misconfigured

## Documentation

See `docs/features/LECTURE_TTS_POLLY.md` for full documentation.

## Next Steps

1. Monitor usage and costs
2. Consider pre-generating audio during lecture creation
3. Add playback speed controls in UI
4. Add keyboard shortcuts (space=play/pause)
5. Consider adding download button for offline use
