# Course Generation Workflow Test Results

## Test Date
2025-12-11

## Test Summary
✅ **Course Request Handler**: Working successfully
✅ **DynamoDB State Persistence**: Working (with Decimal conversion)
✅ **EventBridge Publishing**: Working (with VPC endpoint)
⚠️ **API Gateway**: Needs deployment refresh

## Issues Found and Fixed

### 1. DynamoDB Float/Decimal Conversion
**Issue**: DynamoDB doesn't support Python `float` types, requires `Decimal`
**Error**: `Float types are not supported. Use Decimal types instead.`
**Fix**: Updated `course_state_manager.py` to convert `float` → `Decimal` on save, `Decimal` → `float` on load
**Status**: ✅ Fixed

### 2. IAM Permissions for Course State Table
**Issue**: Lambda execution role didn't have permissions for `docprof-dev-course-state` table
**Error**: `AccessDeniedException: User is not authorized to perform: dynamodb:PutItem`
**Fix**: Updated `lambda_roles.tf` to include course-state table in DynamoDB policy
**Status**: ✅ Fixed

### 3. EventBridge VPC Endpoint Missing
**Issue**: Lambda in VPC couldn't reach EventBridge (no internet access)
**Error**: `ConnectTimeoutError: Connect timeout on endpoint URL: "https://events.us-east-1.amazonaws.com/"`
**Fix**: Added EventBridge Interface VPC endpoint in `vpc/endpoints.tf`
**Status**: ✅ Fixed

### 4. API Gateway Deployment
**Issue**: New `/courses` endpoint not accessible via API Gateway (403 error)
**Status**: ⚠️ Needs deployment refresh (endpoint exists but deployment may be stale)

## Test Results

### Direct Lambda Invocation
```bash
$ bash scripts/test_course_request_lambda.sh
```

**Result**: ✅ Success
- HTTP Status: 200
- Course ID: `8270c8fc-0ac6-422e-bc47-8ada29b62ef4`
- Response: `{"course_id": "...", "ui_message": "Analyzing your request...", "status": "generating", "phase": "embedding"}`

### Workflow Verification
1. ✅ Course state created in DynamoDB
2. ✅ Embedding generated
3. ✅ EventBridge event published
4. ⏳ Next phase handlers (need to verify EventBridge routing)

## Next Steps

1. **Refresh API Gateway Deployment**: Force new deployment to pick up `/courses` endpoint
2. **Verify EventBridge Routing**: Check that events are being routed to correct Lambda functions
3. **Test Full Workflow**: Verify all 7 phases execute correctly
4. **Monitor CloudWatch Logs**: Check each handler's logs for errors

## Test Scripts

- `scripts/test_course_request_lambda.sh`: Test Lambda function directly
- `scripts/test_course_generation.sh`: Test via API Gateway (needs API Gateway fix)
