# API Validation Guide

**Date**: 2025-01-XX  
**Status**: Infrastructure Deployed ✅

## API Gateway URL

```
https://xp2vbfyu3f.execute-api.us-east-1.amazonaws.com/dev
```

## Available Endpoints

### 1. AI Services Status
**GET** `/ai-services/status`

**Test**:
```bash
curl https://xp2vbfyu3f.execute-api.us-east-1.amazonaws.com/dev/ai-services/status
```

**Expected Response**:
```json
{
  "enabled": false,
  "status": "offline",
  "bedrock": {
    "endpoint_id": null,
    "status": "offline"
  },
  "polly": {
    "endpoint_id": null,
    "status": "offline"
  },
  "message": "AI services are offline. Enable to use AI features."
}
```

### 2. Enable AI Services
**POST** `/ai-services/enable`

**Test**:
```bash
curl -X POST https://xp2vbfyu3f.execute-api.us-east-1.amazonaws.com/dev/ai-services/enable
```

**Expected Response**:
```json
{
  "enabled": true,
  "status": "working",
  "bedrock": {
    "endpoint_id": "vpce-xxx",
    "status": "working"
  },
  "polly": {
    "endpoint_id": "vpce-yyy",
    "status": "working"
  },
  "message": "AI services are being enabled. This may take 3-5 minutes."
}
```

### 3. Disable AI Services
**POST** `/ai-services/disable`

**Test**:
```bash
curl -X POST https://xp2vbfyu3f.execute-api.us-east-1.amazonaws.com/dev/ai-services/disable
```

### 4. Book Upload
**POST** `/books/upload`

**Test** (with a PDF file):
```bash
curl -X POST https://xp2vbfyu3f.execute-api.us-east-1.amazonaws.com/dev/books/upload \
  -H "Content-Type: application/pdf" \
  -H "X-Book-Title: Test Book" \
  -H "X-Book-Author: Test Author" \
  --data-binary @test.pdf
```

## Validation Checklist

- [x] API Gateway deployed
- [x] AI Services Manager Lambda deployed
- [x] Book Upload Lambda deployed
- [x] Document Processor Lambda deployed
- [ ] AI Services Status endpoint working
- [ ] AI Services Enable endpoint working
- [ ] AI Services Disable endpoint working
- [ ] Book Upload endpoint working
- [ ] S3 event notification configured (pending fix)

## Known Issues

1. **S3 Event Notification**: Currently failing with "Unable to validate destination configurations". This may be a timing issue with VPC-configured Lambda. Can be fixed manually or retried later.

2. **API Gateway Stage**: Successfully imported existing stage.

## Next Steps

1. Test all API endpoints
2. Fix S3 event notification (if needed)
3. Test document processing pipeline
4. Migrate frontend UI

