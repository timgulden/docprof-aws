# Lambda Layer Migration Testing Guide

## Pre-Deployment Validation

### ✅ Configuration Validation (COMPLETE)

```bash
cd terraform/environments/dev
terraform init    # Installed new module
terraform validate # Configuration is valid
```

### ⏳ Next Steps (Requires AWS Access)

Once AWS credentials are configured:

1. **Plan the Changes:**
   ```bash
   terraform plan -out=tfplan
   ```
   
   Expected changes:
   - Creates new `shared_code_layer` Lambda layer
   - Updates `connection_test_lambda` to use layer
   - Connection test function ZIP should be smaller

2. **Apply Changes:**
   ```bash
   terraform apply tfplan
   ```

3. **Test the Function:**
   ```bash
   # Invoke connection test lambda
   aws lambda invoke \
     --function-name docprof-dev-connection-test \
     --payload '{"test": "all"}' \
     response.json
   
   # Check response
   cat response.json | jq .
   ```

4. **Verify Layer Structure:**
   ```bash
   # Get layer details
   aws lambda get-layer-version \
     --layer-name docprof-dev-shared-code \
     --version-number <version> \
     --region us-east-1
   
   # Download and inspect layer ZIP
   # Layer should have python/shared/ structure
   ```

5. **Check CloudWatch Logs:**
   ```bash
   aws logs tail /aws/lambda/docprof-dev-connection-test --follow
   ```
   
   Look for:
   - ✅ No import errors
   - ✅ All shared imports resolve
   - ✅ Function executes successfully

## Validation Checklist

- [ ] Terraform plan succeeds
- [ ] Shared code layer created successfully
- [ ] Layer version number > 0
- [ ] connection_test_lambda updated
- [ ] Function ZIP size reduced (should be much smaller)
- [ ] Function invokes successfully
- [ ] No import errors in logs
- [ ] All shared modules import correctly
- [ ] Database connections work
- [ ] Bedrock client works (if tested)

## Rollback if Needed

If any issues occur:

```bash
# Revert connection_test_lambda to bundle shared code
# Edit terraform/environments/dev/main.tf:
# - Set bundle_shared_code = true (or remove the variable)
# - Remove shared_code_layer from layers list

terraform apply  # Will restore previous state
```

## Success Criteria

✅ Layer created with correct structure (`python/shared/`)  
✅ Function uses layer successfully  
✅ All imports work  
✅ No code changes needed (imports unchanged)  
✅ Function ZIP size significantly reduced  
✅ All functionality works as before

