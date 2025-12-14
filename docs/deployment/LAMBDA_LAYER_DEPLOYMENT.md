# Lambda Layer Deployment Guide

**Status:** Ready for Deployment  
**Date:** 2025-01-XX

## Prerequisites

1. **AWS Credentials Configured**
   ```bash
   aws configure
   # OR
   export AWS_ACCESS_KEY_ID=...
   export AWS_SECRET_ACCESS_KEY=...
   ```

2. **Terraform Installed**
   ```bash
   terraform version  # Should be >= 1.5.0
   ```

3. **Terraform Initialized**
   ```bash
   cd terraform/environments/dev
   terraform init
   ```

## Deployment Steps

### 1. Review Terraform Plan

```bash
cd terraform/environments/dev
terraform plan -out=tfplan
```

**Expected Changes:**
- ✅ Creates new `shared_code_layer` Lambda layer
- ✅ Updates all 27 Lambda functions to use the layer
- ✅ Function ZIP packages will be smaller (no bundled shared code)
- ✅ All functions will have `bundle_shared_code = false`

### 2. Apply Changes

```bash
terraform apply tfplan
```

**This will:**
1. Create the shared code layer in S3
2. Create the Lambda layer version
3. Update all Lambda functions to use the layer
4. Redeploy all function packages (smaller ZIPs)

**Expected Duration:** 10-15 minutes (depends on number of functions)

### 3. Verify Deployment

#### Option A: Use Test Script

```bash
./scripts/test_layer_deployment.sh
```

This script checks:
- ✅ Layer exists
- ✅ Function uses the layer
- ✅ Function invokes successfully
- ✅ No import errors in logs

#### Option B: Manual Verification

```bash
# Check layer exists
aws lambda list-layers --query "Layers[?contains(LayerName, 'shared-code')]"

# Check function uses layer
aws lambda get-function --function-name docprof-dev-connection-test \
  --query "Configuration.Layers[*].Arn"

# Test function
aws lambda invoke \
  --function-name docprof-dev-connection-test \
  --payload '{"test": "all"}' \
  response.json

# Check response
cat response.json | jq .
```

### 4. Test Key Functions

Test a few critical functions to ensure everything works:

```bash
# Connection test (our test function)
aws lambda invoke \
  --function-name docprof-dev-connection-test \
  --payload '{"test": "all"}' \
  /tmp/connection-test.json
cat /tmp/connection-test.json | jq .

# Book upload (for cover image issue)
# Use frontend or API Gateway to test

# Chat handler
aws lambda invoke \
  --function-name docprof-dev-chat-handler \
  --payload '{"body": "{\"message\": \"test\", \"session_id\": \"test-123\"}"}' \
  /tmp/chat-test.json
```

### 5. Monitor CloudWatch Logs

```bash
# Watch logs for import errors
aws logs tail /aws/lambda/docprof-dev-connection-test --follow

# Check for errors in last hour
aws logs filter-log-events \
  --log-group-name /aws/lambda/docprof-dev-connection-test \
  --start-time $(($(date +%s) - 3600))000 \
  --filter-pattern "ERROR ImportError ModuleNotFoundError"
```

## Rollback Plan

If issues occur:

### Quick Rollback (Single Function)

1. Edit `terraform/environments/dev/main.tf`
2. For the problematic function, change:
   ```hcl
   bundle_shared_code = true  # Change back to true
   # Remove shared_code_layer from layers list
   ```
3. Apply: `terraform apply`

### Full Rollback (All Functions)

1. Revert Terraform changes:
   ```bash
   git checkout terraform/environments/dev/main.tf
   terraform apply
   ```

2. Or manually revert:
   - Set `bundle_shared_code = true` for all functions
   - Remove `module.shared_code_layer.layer_arn` from all layers lists
   - Apply: `terraform apply`

## Success Criteria

✅ **Layer Created:**
- Layer exists: `docprof-dev-shared-code`
- Layer version > 0
- Layer size ~400-500KB (shared code)

✅ **Functions Updated:**
- All 27 functions use the layer
- Function ZIP sizes reduced significantly
- All functions deploy successfully

✅ **Functionality Works:**
- All functions invoke successfully
- No import errors in CloudWatch logs
- All features work as before
- Cover image extraction works (original issue)

## Troubleshooting

### Import Errors

**Symptom:** `ModuleNotFoundError: No module named 'shared'`

**Solution:**
1. Verify layer is attached to function:
   ```bash
   aws lambda get-function --function-name <name> --query "Configuration.Layers"
   ```
2. Check layer structure includes `python/shared/`
3. Verify function uses latest layer version

### Layer Not Found

**Symptom:** `ResourceNotFoundException: The layer version does not exist`

**Solution:**
1. Check layer was created:
   ```bash
   aws lambda list-layers
   ```
2. Verify Terraform apply completed successfully
3. Check CloudWatch logs for layer creation errors

### Function ZIP Still Large

**Symptom:** Function package size hasn't decreased

**Solution:**
1. Verify `bundle_shared_code = false` in Terraform
2. Check function actually uses the layer
3. Redeploy function: `terraform apply -replace=module.<function>_lambda`

## Next Steps

After successful deployment:

1. ✅ Monitor CloudWatch logs for 24 hours
2. ✅ Test all major user workflows
3. ✅ Return to cover image issue (original bug)
4. ✅ Document layer versioning strategy
5. ✅ Set up automated tests for layer updates

---

**Ready to Deploy!** 🚀

