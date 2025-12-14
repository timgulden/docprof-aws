# Lambda Layer Migration Plan: Shared Code to Layer

**Goal:** Move shared application code from bundled ZIPs to Lambda Layer (best practice)  
**Risk Level:** **LOW-MEDIUM** (well-managed risk with good mitigation strategies)  
**Estimated Effort:** 2-4 hours  
**Benefits:** Demonstrates AWS best practices, faster deployments, cleaner architecture

## Risk Assessment

### ✅ Low Risk Factors

1. **Lambda Layers are Mature & Stable**
   - Released in 2018, widely used
   - Well-documented AWS service
   - No known major issues

2. **We Already Use Layers Successfully**
   - Python dependencies layer is working
   - We understand the pattern
   - Terraform modules are proven

3. **Shared Code is Well-Structured**
   - 33 files, ~484KB (well under 250MB layer limit)
   - Clear module structure (`shared/`)
   - No complex build requirements

4. **Can Test Incrementally**
   - Migrate one function first
   - Test thoroughly before migrating all
   - Easy to roll back (keep old approach)

### ⚠️ Medium Risk Factors

1. **Import Path Changes**
   - Need to ensure imports work with layer structure
   - Python path resolution may differ
   - **Mitigation:** Test imports carefully, use relative imports

2. **All Functions Must Update**
   - ~20 Lambda functions to update
   - Need to coordinate deployment
   - **Mitigation:** Do in phases, test each phase

3. **Layer Version Management**
   - Need to version layers properly
   - Old layer versions remain (cost)
   - **Mitigation:** Clean up old versions, use clear versioning

### 📊 Overall Risk: **LOW-MEDIUM**

**Conclusion:** This is a safe refactoring with clear benefits. Risk is manageable with proper testing.

## Migration Strategy

### Phase 1: Create Shared Code Layer Module (1 hour)

**Step 1.1:** Create new Terraform module
```bash
terraform/modules/lambda-shared-code-layer/
├── main.tf
├── variables.tf
├── outputs.tf
└── README.md
```

**Step 1.2:** Package `shared/` directory into layer
- Structure: `python/shared/` (Lambda layers use `python/` prefix)
- Include all 33 files from `src/lambda/shared/`
- No build needed (just Python files)

**Step 1.3:** Test layer creation
- Verify layer ZIP structure
- Check file sizes
- Ensure all imports will resolve

### Phase 2: Test with One Function (30 min)

**Step 2.1:** Pick a test function (recommend: `connection_test_lambda` - simple, low risk)

**Step 2.2:** Update function to use layer
- Remove `shared/` from function ZIP
- Add shared code layer to function layers
- Test imports work

**Step 2.3:** Deploy and test
- Invoke function
- Verify all imports resolve
- Check CloudWatch logs

### Phase 3: Migrate All Functions (1-2 hours)

**Step 3.1:** Update Lambda module
- Add parameter to control shared code bundling
- When layer provided, skip bundling shared code

**Step 3.2:** Update all function modules
- Add shared code layer to all functions
- Remove shared code from ZIPs

**Step 3.3:** Deploy incrementally
- Deploy non-critical functions first
- Test each batch
- Deploy critical functions last

### Phase 4: Cleanup & Documentation (30 min)

**Step 4.1:** Remove old layer versions (optional, cost optimization)

**Step 4.2:** Update documentation
- Update architecture docs
- Document layer versioning strategy
- Update deployment guides

## Technical Details

### Layer Structure

```
Lambda Layer ZIP:
python/
└── shared/
    ├── __init__.py
    ├── db_utils.py
    ├── bedrock_client.py
    ├── response.py
    ├── core/
    │   ├── commands.py
    │   ├── chat_models.py
    │   └── ...
    └── logic/
        ├── chat.py
        ├── courses.py
        └── ...
```

### Import Changes

**Current (bundled):**
```python
from shared.db_utils import get_db_connection
```

**After (layer):**
```python
# No change! Lambda adds python/ to path automatically
from shared.db_utils import get_db_connection
```

**No code changes needed!** Lambda automatically adds `python/` to `sys.path`.

### Terraform Changes

**Current:**
```hcl
module "book_upload_lambda" {
  source = "../../modules/lambda"
  # ... bundles shared code automatically
}
```

**After:**
```hcl
module "shared_code_layer" {
  source = "../../modules/lambda-shared-code-layer"
  # Creates layer with shared code
}

module "book_upload_lambda" {
  source = "../../modules/lambda"
  layers = [
    module.lambda_layer.layer_arn,          # Python deps
    module.shared_code_layer.layer_arn      # Shared code
  ]
  # ... shared code NOT bundled
}
```

## Testing Checklist

- [ ] Layer creates successfully
- [ ] Test function imports work
- [ ] Test function executes correctly
- [ ] All shared imports resolve
- [ ] Database connections work
- [ ] Bedrock client works
- [ ] Response utilities work
- [ ] One full workflow end-to-end
- [ ] All 20 functions migrated
- [ ] CloudWatch logs show no import errors

## Rollback Plan

If issues arise:

1. **Immediate Rollback:**
   - Revert Terraform changes
   - Functions still work (old code still deployed)
   - No downtime

2. **Gradual Rollback:**
   - Keep layer, but bundle shared code again
   - Layer is ignored if code is in function ZIP
   - Zero risk

3. **Layer Version Rollback:**
   - Keep previous layer version
   - Point functions back to old version
   - Layer versions are immutable (safe)

## Success Criteria

✅ All functions use shared code layer  
✅ Function ZIP sizes reduced (~500KB → ~10-50KB)  
✅ Deployments faster  
✅ No import errors  
✅ All functionality works  
✅ Demonstrates AWS best practices

## Timeline

- **Phase 1:** 1 hour (create layer module)
- **Phase 2:** 30 min (test with one function)
- **Phase 3:** 1-2 hours (migrate all functions)
- **Phase 4:** 30 min (cleanup)
- **Total:** 2-4 hours

## Next Steps

Ready to proceed? This is a great showcase of:
- ✅ Understanding AWS Lambda best practices
- ✅ Infrastructure as Code (Terraform)
- ✅ Careful, incremental migration
- ✅ Risk management
- ✅ Testing strategy

Would you like me to start with Phase 1?

