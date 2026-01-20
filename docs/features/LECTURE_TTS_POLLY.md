# Lecture Text-to-Speech with AWS Polly

## Overview

This feature provides word-level text highlighting synchronized with AWS Polly neural TTS audio for lecture playback.

## Features

- **Word-level highlighting**: Current word highlighted in yellow as it's spoken
- **Sentence-level context**: Subtle highlighting of current sentence
- **Click-to-seek**: Click any word to jump audio to that position
- **Auto-scroll**: Automatically keeps current word visible during playback
- **On-demand generation**: Audio generated the first time a lecture is played
- **S3 caching**: Subsequent plays are instant (served from cache)
- **Smooth continuous audio**: No gaps between chunks, even for long lectures

## How It Works

1. **Backend**: When a user plays a lecture, the `section_audio_handler` Lambda:
   - Checks S3 cache for existing audio and speech marks
   - If not cached, calls AWS Polly to generate both
   - Returns MP3 audio and JSON speech marks (word/sentence timing)

2. **Frontend**: The `usePollyAudio` hook:
   - Fetches audio and speech marks from API
   - Tracks current playback position
   - Updates highlight position via binary search through speech marks
   - Provides word/sentence objects for UI highlighting

3. **UI**: The `HighlightedLecture` component:
   - Parses lecture text into individual word spans
   - Maps speech marks to text positions
   - Highlights current word and sentence
   - Auto-scrolls to keep highlighted text visible

## Enabling the Feature

### Option 1: Environment Variable (Recommended for testing)

Add to `src/frontend/.env`:

```env
VITE_USE_POLLY_TTS=true
```

Then restart the frontend dev server:

```bash
cd src/frontend
npm run dev
```

### Option 2: Make it Default

Edit `src/frontend/src/components/course/SectionPlayer.tsx`:

```typescript
// Change this line:
const usePollyTTS = import.meta.env.VITE_USE_POLLY_TTS === 'true' || false;

// To:
const usePollyTTS = true;
```

## Deployment

### 1. Deploy Backend Infrastructure

```bash
cd terraform/environments/dev
terraform plan
terraform apply
```

This creates:
- S3 bucket: `docprof-dev-audio-cache`
- Lambda function: `section_audio_handler`
- API routes: `/courses/section/{sectionId}/audio` and `/speech-marks`

### 2. Verify API Endpoints

```bash
# Get your auth token
export TOKEN=$(aws cognito-idp admin-initiate-auth ...)

# Test audio endpoint
curl -H "Authorization: Bearer $TOKEN" \
  https://your-api.execute-api.us-east-1.amazonaws.com/dev/courses/section/{sectionId}/audio \
  -o test_audio.mp3

# Test speech marks endpoint
curl -H "Authorization: Bearer $TOKEN" \
  https://your-api.execute-api.us-east-1.amazonaws.com/dev/courses/section/{sectionId}/speech-marks \
  | jq '.marks | length'
```

### 3. Deploy Frontend

The frontend changes are already included. Just rebuild and deploy:

```bash
cd src/frontend
npm run build
# Deploy dist/ to S3 or serve locally with `npm run dev`
```

## Testing

1. **Navigate to a lecture**:
   - Create or open a course
   - Click on a section to view the lecture

2. **Verify audio loads**:
   - Check browser console for "Loading Polly audio..."
   - Audio should load in 2-3 seconds

3. **Test highlighting**:
   - Click Play button
   - Current word should highlight in yellow
   - Current sentence should have subtle yellow background
   - Highlighting should advance as audio plays

4. **Test click-to-seek**:
   - Click any word in the lecture
   - Audio should jump to that word

5. **Test caching**:
   - Reload the page and play the same lecture
   - Audio should start instantly (cached in S3)

## Configuration

### Polly Voice Settings

Edit environment variables in Terraform (`terraform/environments/dev/main.tf`):

```hcl
environment_variables = {
  ...
  POLLY_VOICE_ID = "Matthew"  # Options: Matthew, Joanna, Kevin, etc.
  POLLY_ENGINE   = "neural"   # Options: standard, neural, long-form
}
```

Available neural voices:
- **Matthew**: Male, clear, professional (default)
- **Joanna**: Female, clear, professional
- **Kevin**: Male, warm, conversational
- **Ruth**: Female, clear, youthful
- **Stephen**: Male, authoritative

See [AWS Polly Voices](https://docs.aws.amazon.com/polly/latest/dg/voicelist.html) for full list.

### Cache Expiration

Audio cache expires after 30 days (configured in `terraform/modules/s3/main.tf`). To change:

```hcl
resource "aws_s3_bucket_lifecycle_configuration" "audio_cache" {
  rule {
    expiration {
      days = 90  # Change to your preference
    }
  }
}
```

## Cost Estimates

- **Polly Neural TTS**: $16 per 1 million characters
- **S3 Storage**: ~$0.023 per GB-month
- **S3 Requests**: Negligible for cached audio

**Example**: 
- 10 lectures, 10,000 chars each = 100,000 chars
- First generation: 100,000 × $16/1M = $1.60
- Storage: 100 lectures × ~500KB = 50MB = ~$0.001/month
- Subsequent plays: Free (served from cache)

## Troubleshooting

### Audio doesn't load

Check Lambda logs:

```bash
aws logs tail /aws/lambda/docprof-dev-section-audio-handler --follow
```

Common issues:
- Lecture not yet generated
- Polly service quota exceeded
- VPC endpoint not configured

### Speech marks don't sync with audio

- Clear browser cache
- Regenerate audio (delete from S3 cache)
- Check that voice/engine settings match between audio and marks generation

### Highlighting is off by a few words

This can happen with:
- Very fast playback speeds (>2x)
- Browser throttling (background tab)
- Network latency

Solution: Regenerate audio, try slower playback speed.

## Architecture

```
┌─────────────┐
│   Browser   │
│  (Frontend) │
└──────┬──────┘
       │ GET /courses/section/{id}/audio
       │ GET /courses/section/{id}/speech-marks
       ↓
┌─────────────────┐
│  API Gateway    │
└────────┬────────┘
         │
         ↓
┌─────────────────────────┐
│  Lambda:                │
│  section_audio_handler  │
│  ┌──────────────────┐   │
│  │ 1. Check S3 cache│   │
│  │ 2. Generate if   │   │
│  │    not cached    │   │
│  │ 3. Cache result  │   │
│  │ 4. Return audio/ │   │
│  │    marks         │   │
│  └──────────────────┘   │
└───┬──────────────┬──────┘
    │              │
    ↓              ↓
┌─────────┐   ┌──────────┐
│   S3    │   │  Polly   │
│  Cache  │   │   TTS    │
└─────────┘   └──────────┘
```

## Comparison with MAExpert

| Feature | MAExpert (OpenAI TTS) | DocProf AWS (Polly) |
|---------|----------------------|---------------------|
| Text sync | Paragraph-level | **Word-level** |
| Transitions | Pauses between paragraphs | **Smooth continuous** |
| Latency | ~2-3s per chunk | ~2-3s first play only |
| Highlighting | Full paragraph | **Current word + sentence** |
| Click-to-seek | No | **Yes** |
| Cost | ~$15/1M chars | ~$16/1M chars |
| Caching | Database | **S3** |

## Future Enhancements

- [ ] Adjustable playback speed slider in UI
- [ ] Keyboard shortcuts (space=play/pause, left/right=skip word)
- [ ] Progress bar showing lecture position
- [ ] Option to download audio for offline use
- [ ] Support for multiple voices (let user choose)
- [ ] Background audio generation (generate during lecture creation)
