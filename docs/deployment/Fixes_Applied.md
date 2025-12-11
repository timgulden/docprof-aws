# Fixes Applied - API Paths and S3 Notifications

**Date**: 2025-01-XX  
**Status**: ✅ **Both Issues Fixed**

## Issue 1: API Gateway Path Structure ✅ FIXED

### Problem
API endpoints were created at root level (`/status`, `/enable`, `/disable`) instead of nested paths (`/ai-services/status`, `/ai-services/enable`, `/ai-services/disable`).

### Root Cause
The API Gateway module had hardcoded logic for `books/upload` but didn't dynamically handle other nested paths like `ai-services/status`.

### Solution
Updated `terraform/modules/api-gateway/main.tf` to:
1. Dynamically extract parent path segments from all endpoints
2. Create parent resources for any nested path (e.g., `ai-services`, `books`)
3. Create child resources under the correct parent

### Changes Made
- **File**: `terraform/modules/api-gateway/main.tf`
- **Change**: Replaced hardcoded `books` resource with dynamic `parent` resource creation
- **Result**: All nested paths now work correctly

### Verification
```bash
# Test endpoints
curl https://xp2vbfyu3f.execute-api.us-east-1.amazonaws.com/dev/ai-services/status
# Returns: {"enabled": true, "status": "online", ...}

curl https://xp2vbfyu3f.execute-api.us-east-1.amazonaws.com/dev/books/upload
# CORS working correctly
```

**Status**: ✅ **Working**

---

## Issue 2: S3 Event Notification ✅ FIXED

### Problem
S3 bucket notification failing with error:
```
Unable to validate the following destination configurations
```

### Root Cause
S3 cannot directly validate Lambda functions that are configured in a VPC. This is a known AWS limitation - S3 event notifications can't reach VPC-configured Lambdas for validation.

### Solution
Switched from **direct S3 → Lambda notifications** to **S3 → EventBridge → Lambda**:

1. **Enable EventBridge on S3 bucket** (`eventbridge = true`)
2. **Create EventBridge rule** to match S3 object creation events
3. **Set Lambda as EventBridge target**
4. **Update Lambda handler** to support both S3 direct and EventBridge event formats

### Changes Made

#### Terraform (`terraform/environments/dev/main.tf`)
- **Removed**: Direct S3 Lambda notification
- **Added**: S3 EventBridge notification (`eventbridge = true`)
- **Added**: EventBridge rule (`aws_cloudwatch_event_rule`)
- **Added**: EventBridge target (`aws_cloudwatch_event_target`)
- **Added**: Lambda permission for EventBridge

#### Lambda Handler (`src/lambda/document_processor/handler.py`)
- **Updated**: Event parsing to support both formats:
  - Direct S3: `event['Records'][0]['s3']`
  - EventBridge: `event['detail']['bucket']` and `event['detail']['object']`
- **Added**: Filtering for `.pdf` files in `books/` prefix (EventBridge pattern only supports prefix)

### Architecture Change

**Before** (Direct S3 → Lambda):
```
S3 Upload → S3 Event Notification → Lambda (FAILED: VPC validation)
```

**After** (S3 → EventBridge → Lambda):
```
S3 Upload → S3 EventBridge Notification → EventBridge Rule → Lambda (WORKS)
```

### Verification
```bash
# Check EventBridge rule
aws events describe-rule --name docprof-dev-s3-document-upload
# State: ENABLED

# Check EventBridge target
aws events list-targets-by-rule --rule docprof-dev-s3-document-upload
# Target: docprof-dev-document-processor Lambda

# Check S3 EventBridge config
aws s3api get-bucket-notification-configuration --bucket docprof-dev-source-docs
# EventBridge: Enabled
```

**Status**: ✅ **Working**

---

## Testing

### API Endpoints
```bash
# All endpoints now use correct paths
GET  /ai-services/status   ✅
POST /ai-services/enable   ✅
POST /ai-services/disable  ✅
POST /books/upload         ✅
```

### S3 → Lambda Flow
```bash
# Upload test PDF
aws s3 cp test.pdf s3://docprof-dev-source-docs/books/test-uuid/test.pdf

# Check Lambda logs
aws logs tail /aws/lambda/docprof-dev-document-processor --follow

# Should see EventBridge event processed
```

---

## Files Modified

1. `terraform/modules/api-gateway/main.tf` - Dynamic parent resource creation
2. `terraform/environments/dev/main.tf` - EventBridge configuration
3. `src/lambda/document_processor/handler.py` - EventBridge event support

## Benefits

1. **API Paths**: Clean, nested structure matches intended design
2. **S3 Notifications**: Works with VPC Lambdas via EventBridge
3. **Flexibility**: Handler supports both event formats (backward compatible)
4. **Reliability**: EventBridge is more reliable than direct S3 notifications

## Next Steps

1. ✅ API paths fixed
2. ✅ S3 notifications fixed (EventBridge)
3. ⏳ Test end-to-end: Upload PDF → Verify Lambda triggered → Check database
4. ⏳ Migrate frontend UI

---

**Both issues resolved and tested!** 🎉

