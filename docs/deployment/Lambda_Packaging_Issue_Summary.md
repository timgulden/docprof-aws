# Lambda Packaging Issue - Current State Summary

## Date: December 12, 2025

## Problem Statement

The `course_request_handler` Lambda function is failing with:
```
Runtime.ImportModuleError: Unable to import module 'handler': No module named 'shared.logic'
```

This error persists even though:
- ✅ Terraform state shows `shared/logic` files are included in the package
- ✅ The `shared/logic` directory exists in the source code
- ✅ Other Lambda functions successfully include `shared/logic`

## What We've Accomplished

### ✅ 1. EventBridge Default Bus Migration (COMPLETE)

**Status**: All code changes complete, ready to deploy

**Changes Made**:
- Updated all 9 EventBridge rules to use default bus (commented out `event_bus_name`)
- Removed `EVENT_BUS_NAME` environment variables from all Lambda functions
- Updated `event_publisher.py` to use default bus when `EVENT_BUS_NAME` is empty
- Updated direct event publishing in `document_processor` and `source_summary_generator`

**Files Modified**:
- `terraform/modules/eventbridge/main.tf` - All rules use default bus
- `terraform/environments/dev/main.tf` - Removed EVENT_BUS_NAME env vars
- `src/lambda/shared/event_publisher.py` - Default bus support
- `src/lambda/document_processor/handler.py` - Default bus support
- `src/lambda/source_summary_generator/handler.py` - Default bus support

**Next Step**: Apply Terraform changes (blocked by Lambda packaging issue)

### ✅ 2. Lambda Function Recreation Attempts

**Status**: Attempted but blocked by Terraform state lock

**What We Tried**:
1. `terraform taint` to mark function for recreation
2. `terraform apply -target=module.course_request_handler_lambda.aws_lambda_function.this`
3. Verified Terraform state includes `shared/logic` files

**Current Issue**: 
- Terraform state lock prevents recreation
- Lambda still failing with import error
- No recent logs (function may not be invoking or logs not accessible)

## Current State

### Lambda Function Status
- **Function Name**: `docprof-dev-course-request-handler`
- **Status**: Deployed but failing at runtime
- **Error**: `Runtime.ImportModuleError: No module named 'shared.logic'`
- **Last Modified**: Unknown (need to check)

### Terraform State
- **State Lock**: Present (ID: `919558de-a6ca-1ac7-7af6-9196f6aa69da`)
- **Lock Created**: 2025-12-12 16:31:11 UTC
- **Lock Owner**: `tgulden@mac.lan`
- **Operation**: `OperationTypeApply`

### Source Code Structure
```
src/lambda/
├── shared/
│   ├── logic/
│   │   ├── __init__.py ✅
│   │   ├── courses.py ✅
│   │   ├── chat.py ✅
│   │   └── source_summaries.py ✅
│   └── ... (other shared modules)
└── course_request_handler/
    ├── handler.py (imports from shared.logic.courses)
    └── requirements.txt
```

### Terraform Lambda Module
**File**: `terraform/modules/lambda/main.tf`

**Packaging Logic**:
- Uses `fileset()` to collect files from function directory and shared directory
- Creates `local_file` resources for each file
- Uses `archive_file` to create ZIP
- Lambda function references ZIP via `source_code_hash`

**Key Code**:
```hcl
shared_files = fileexists("${local.shared_path}/__init__.py") ? fileset(local.shared_path, "**") : []
shared_content = fileexists("${local.shared_path}/__init__.py") ? {
  for f in local.shared_files :
  "shared/${f}" => file("${local.shared_path}/${f}")
} : {}
```

**Terraform State Shows**:
- ✅ `module.course_request_handler_lambda.local_file.lambda_staging["shared/logic/__init__.py"]`
- ✅ `module.course_request_handler_lambda.local_file.lambda_staging["shared/logic/courses.py"]`
- ✅ `module.course_request_handler_lambda.local_file.lambda_staging["shared/logic/chat.py"]`
- ✅ `module.course_request_handler_lambda.local_file.lambda_staging["shared/logic/source_summaries.py"]`

## Root Cause Hypothesis

### Theory 1: ZIP Package Corruption
The Lambda ZIP package may be missing `shared/logic` files even though Terraform state shows they should be included.

**Evidence**:
- Terraform state includes logic files
- Lambda runtime can't find them
- Suggests ZIP creation or upload issue

### Theory 2: Manual Package Deployment
A previous manual package deployment (using `package_lambda.py` and `aws lambda update-function-code`) may have overwritten the correct Terraform-managed package with a broken one.

**Evidence**:
- We attempted manual packaging earlier in the session
- Manual packaging may not include all shared files correctly
- Lambda function may still be using the broken manual package

### Theory 3: Terraform State Drift
Terraform state may not match actual deployed Lambda package.

**Evidence**:
- State shows files should be included
- Deployed function doesn't have them
- Suggests state drift or deployment issue

## Investigation Steps Needed

### 1. Check Actual Lambda Package
```bash
# Download current Lambda package
AWS_PROFILE=docprof-dev aws lambda get-function \
  --function-name docprof-dev-course-request-handler \
  --query 'Code.Location' \
  --output text | xargs curl -o /tmp/lambda-package.zip

# Inspect contents
unzip -l /tmp/lambda-package.zip | grep -E "(shared/logic|handler.py)"
```

### 2. Verify Terraform Package
```bash
# Check Terraform-generated ZIP
cd terraform/environments/dev
ls -la ../../modules/lambda/.terraform/course-request-handler.zip
unzip -l ../../modules/lambda/.terraform/course-request-handler.zip | grep shared/logic
```

### 3. Compare Packages
Compare Terraform-generated ZIP with actual deployed Lambda package to identify discrepancies.

### 4. Check Lambda Function Configuration
```bash
AWS_PROFILE=docprof-dev aws lambda get-function-configuration \
  --function-name docprof-dev-course-request-handler \
  --query '[LastModified,CodeSize,CodeSha256]' \
  --output json
```

### 5. Clear Terraform State Lock
```bash
cd terraform/environments/dev
terraform force-unlock 919558de-a6ca-1ac7-7af6-9196f6aa69da
```

## Recommended Solution Path

### Option 1: Force Terraform Recreation (Recommended)
1. Clear Terraform state lock
2. Taint Lambda function resource
3. Apply Terraform to recreate function with correct package
4. Verify package contents match Terraform state

### Option 2: Manual Package Fix (If Terraform fails)
1. Use `package_lambda.py` script correctly
2. Ensure it includes all shared files
3. Upload via `aws lambda update-function-code`
4. Verify package contents

### Option 3: Debug Terraform Module
1. Add debug output to Lambda module
2. Verify `fileset()` is finding all files
3. Check ZIP creation process
4. Compare with working Lambda functions

## Files to Review

### Critical Files
1. `terraform/modules/lambda/main.tf` - Lambda packaging logic
2. `scripts/package_lambda.py` - Manual packaging script
3. `src/lambda/course_request_handler/handler.py` - Handler imports
4. `src/lambda/shared/logic/__init__.py` - Logic module init

### Reference Files (Working Examples)
- `terraform/environments/dev/main.tf` - Other Lambda definitions
- `terraform/state` - Current Terraform state
- Other Lambda functions that work correctly

## Next Steps for New Chat

1. **Clear Terraform State Lock**
   ```bash
   cd terraform/environments/dev
   terraform force-unlock 919558de-a6ca-1ac7-7af6-9196f6aa69da
   ```

2. **Investigate Package Contents**
   - Download actual Lambda package
   - Compare with Terraform-generated package
   - Identify missing files

3. **Fix Package Issue**
   - Either fix Terraform module
   - Or manually package correctly
   - Or force Terraform recreation

4. **Apply EventBridge Changes**
   - Once Lambda is fixed, apply default bus migration
   - Test end-to-end course generation

5. **Verify End-to-End**
   - Test course generation API
   - Verify EventBridge events are matched
   - Check Lambda logs for successful execution

## Related Documentation

- `docs/deployment/EventBridge_Functionality_Assessment.md` - EventBridge analysis
- `docs/deployment/Default_Bus_Migration_Complete.md` - Migration details
- `docs/troubleshooting/AWS_Credentials_Troubleshooting.md` - AWS credentials guide
- `docs/deployment/Lambda_Packaging_Fix.md` - Previous packaging fixes

## Environment Details

- **AWS Profile**: `docprof-dev`
- **Region**: `us-east-1`
- **Account**: `176520790264`
- **Terraform Version**: `1.5.7`
- **Python Version**: `3.11`

## Commands to Run in New Chat

```bash
# Set up environment
export AWS_PROFILE=docprof-dev
export AWS_DEFAULT_REGION=us-east-1
cd /Users/tgulden/Documents/AI\ Projects/docprof-aws

# Clear state lock
cd terraform/environments/dev
terraform force-unlock 919558de-a6ca-1ac7-7af6-9196f6aa69da

# Check Lambda package
aws lambda get-function --function-name docprof-dev-course-request-handler --query 'Code.Location' --output text

# Check Terraform package
ls -la ../../modules/lambda/.terraform/course-request-handler.zip
unzip -l ../../modules/lambda/.terraform/course-request-handler.zip | grep shared/logic

# Recreate Lambda
terraform taint module.course_request_handler_lambda.aws_lambda_function.this
terraform apply -target=module.course_request_handler_lambda.aws_lambda_function.this
```

---

**Status**: Blocked on Lambda packaging issue. EventBridge migration code complete and ready to deploy once Lambda is fixed.
