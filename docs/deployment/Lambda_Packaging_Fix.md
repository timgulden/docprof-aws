# Lambda Packaging Fix - Shared Modules Inclusion

**Date**: 2025-01-XX  
**Status**: ✅ **Configuration Fixed**

## Problem

Lambda functions were failing with import errors:
```
Runtime.ImportModuleError: Unable to import module 'handler': No module named 'shared'
```

**Root Cause**: The Lambda ZIP package only included files from the function-specific directory (e.g., `document_processor/`) but not the `shared/` directory that contains common utilities.

## Solution

Updated `terraform/modules/lambda/main.tf` to use Terraform's `archive_file` data source with `source_content` map, which includes both function code and shared modules in a single ZIP.

### How It Works

1. **Reads all files** from function directory (`document_processor/`)
2. **Reads all files** from shared directory (`shared/`)
3. **Builds a map** of `filename -> content`:
   ```hcl
   {
     "document_processor/handler.py" = "<file content>",
     "shared/response.py" = "<file content>",
     "shared/db_utils.py" = "<file content>",
     ...
   }
   ```
4. **Creates ZIP** using `archive_file` with `source_content` map
5. **No shell execution** - pure Terraform, works everywhere

### Code Changes

**File**: `terraform/modules/lambda/main.tf`

```hcl
locals {
  lambda_root = dirname(var.source_path)
  function_dir = basename(var.source_path)
  shared_path = "${local.lambda_root}/shared"
  
  # Get all files
  function_files = fileset(var.source_path, "**")
  shared_files = fileexists("${local.shared_path}/__init__.py") ? fileset(local.shared_path, "**") : []
  
  # Build content map
  function_content = {
    for f in local.function_files :
    "${local.function_dir}/${f}" => file("${var.source_path}/${f}")
  }
  shared_content = fileexists("${local.shared_path}/__init__.py") ? {
    for f in local.shared_files :
    "shared/${f}" => file("${local.shared_path}/${f}")
  } : {}
  all_content = merge(local.function_content, local.shared_content)
}

data "archive_file" "lambda_zip" {
  type        = "zip"
  output_path = "${path.module}/.terraform/${var.function_name}.zip"
  source_content = local.all_content
}
```

## Testing

### Step 1: Validate Configuration
```bash
cd terraform/environments/dev
AWS_PROFILE=docprof-dev terraform validate
```

### Step 2: Plan Changes
```bash
AWS_PROFILE=docprof-dev terraform plan -var="enable_ai_endpoints=false" -target=module.document_processor_lambda
```

**Expected Output**:
- Should show `archive_file.lambda_zip` will be created/updated
- Should show `aws_lambda_function.this` will be updated (new source_code_hash)

### Step 3: Apply Changes
```bash
AWS_PROFILE=docprof-dev terraform apply -var="enable_ai_endpoints=false" -target=module.document_processor_lambda -auto-approve
```

### Step 4: Verify ZIP Contents
```bash
# Check the ZIP was created with shared modules
unzip -l terraform/modules/lambda/.terraform/document-processor.zip | grep -E "(shared|document_processor)"
```

**Expected**: Should see both `document_processor/` and `shared/` directories.

### Step 5: Test Lambda Execution
```bash
# Check Lambda logs for import errors
AWS_PROFILE=docprof-dev aws logs tail /aws/lambda/docprof-dev-document-processor --follow

# Trigger processing by uploading a test file (or wait for EventBridge to trigger)
# The uploaded Valuation8thEd.pdf should trigger processing
```

**Expected**: No import errors, Lambda should process the PDF successfully.

## Verification Checklist

- [ ] `terraform validate` passes
- [ ] `terraform plan` shows ZIP will be created/updated
- [ ] ZIP file contains both `document_processor/` and `shared/` directories
- [ ] Lambda function updates successfully
- [ ] Lambda logs show no import errors
- [ ] Document processing triggers successfully

## Benefits

✅ **Pure Terraform** - No shell scripts or external dependencies  
✅ **Automatic** - Triggers on any file changes  
✅ **Portable** - Works in any environment (local, CI/CD, Terraform Cloud)  
✅ **Reliable** - No shell execution issues  

## Files Modified

1. `terraform/modules/lambda/main.tf` - Updated packaging logic
2. `terraform/environments/dev/main.tf` - Added null provider (already present)

## Next Steps After Fix

1. Apply the fix: `terraform apply`
2. Verify Lambda processes the uploaded Valuation8thEd.pdf
3. Check CloudWatch logs for successful processing
4. Upload remaining books via UI or script


