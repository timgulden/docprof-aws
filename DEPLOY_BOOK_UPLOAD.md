# Quick Deploy Guide: Book Upload Lambda

## Quick Deploy (Recommended)

```bash
cd /Users/tgulden/Documents/AI\ Projects/docprof-aws

# Package Lambda
python3 scripts/package_lambda.py \
  src/lambda/book_upload \
  src/lambda/shared \
  /tmp/book_upload.zip

# Deploy to AWS
aws lambda update-function-code \
  --function-name docprof-dev-book-upload \
  --zip-file fileb:///tmp/book_upload.zip \
  --region us-east-1
```

## Frontend Changes

**If running locally:**
- Frontend should auto-reload if using `npm run dev`
- Hard refresh browser: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows/Linux)

**If deployed:**
```bash
cd src/frontend
npm run build
# Then deploy to S3/CloudFront
```

## Verify Deployment

1. **Check Lambda logs:**
```bash
aws logs tail /aws/lambda/docprof-dev-book-upload --follow
```

2. **Test the endpoint:**
- Upload a book and check browser console for cover URL
- Check CloudWatch logs for any errors

## Changes Made

- ✅ Backend: Returns relative URL `/books/{book_id}/cover` (matches MAExpert)
- ✅ Frontend: Handles relative URLs correctly
- ✅ Better error handling for missing covers

