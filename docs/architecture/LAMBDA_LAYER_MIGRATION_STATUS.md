# Lambda Layer Migration Status

**Started:** 2025-01-XX  
**Status:** Phase 1 & 3 Complete, Phase 2 Ready to Test

## Progress

### ✅ Phase 1: Create Shared Code Layer Module (COMPLETE)

**Created:**
- `terraform/modules/lambda-shared-code-layer/`
  - `main.tf` - Packages shared code into Lambda layer
  - `variables.tf` - Module variables
  - `outputs.tf` - Layer ARN and version
  - `README.md` - Documentation

**Layer Structure:**
```
python/
└── shared/
    ├── __init__.py
    ├── db_utils.py
    ├── bedrock_client.py
    ├── response.py
    ├── core/
    └── logic/
```

### ✅ Phase 3: Update Lambda Module (COMPLETE)

**Updated:**
- `terraform/modules/lambda/variables.tf` - Added `bundle_shared_code` variable (default: true for backward compatibility)
- `terraform/modules/lambda/main.tf` - Added logic to skip bundling when `bundle_shared_code = false`

**Backward Compatibility:**
- Default behavior unchanged (bundles shared code)
- Existing functions continue to work
- Migration is opt-in per function

### 🔄 Phase 2: Test with One Function (IN PROGRESS)

**Test Function:** `connection_test_lambda`

**Changes Made:**
- Added shared code layer to `layers` list
- Set `bundle_shared_code = false`
- Added layer dependency to `depends_on`

**Next Steps:**
1. Run `terraform plan` to validate
2. Run `terraform apply` to create layer and update test function
3. Test the function to verify imports work
4. Check CloudWatch logs for any errors

### ⏳ Phase 4: Migrate All Functions (PENDING)

Once Phase 2 is validated, will update all ~20 Lambda functions:
- Add shared code layer to all functions
- Set `bundle_shared_code = false` for all
- Deploy incrementally and test

## Files Changed

### New Files
- `terraform/modules/lambda-shared-code-layer/main.tf`
- `terraform/modules/lambda-shared-code-layer/variables.tf`
- `terraform/modules/lambda-shared-code-layer/outputs.tf`
- `terraform/modules/lambda-shared-code-layer/README.md`

### Modified Files
- `terraform/modules/lambda/main.tf` - Added conditional shared code bundling
- `terraform/modules/lambda/variables.tf` - Added `bundle_shared_code` variable
- `terraform/environments/dev/main.tf` - Added shared code layer module, updated connection_test_lambda

## Testing Checklist

- [ ] Terraform validates successfully
- [ ] Layer creates successfully
- [ ] Layer ZIP structure is correct
- [ ] connection_test_lambda deploys with layer
- [ ] Function imports work (from shared.*)
- [ ] Function executes correctly
- [ ] Database connections work
- [ ] No import errors in CloudWatch logs

## Rollback Plan

If issues arise:
1. Revert `bundle_shared_code = false` to `true` (or remove the variable)
2. Remove shared code layer from layers list
3. Terraform apply will restore previous state
4. Zero downtime (old code still works)

