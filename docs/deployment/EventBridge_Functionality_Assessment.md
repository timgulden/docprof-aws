# EventBridge Functionality Assessment

## Purpose

Assess whether we need EventBridge-specific features that would be lost by using the default bus, and verify that destroying/recreating the Lambda function won't require code rewrites.

## EventBridge Features We're Using

### 1. Event-Driven Orchestration ✅
**What it does**: Events trigger Lambda handlers in sequence, decoupling phases
**Default bus support**: ✅ **YES** - Fully supported
**Custom bus support**: ✅ **YES** - Fully supported
**Required?**: ✅ **YES** - Core to our architecture

### 2. Event Rules & Patterns ✅
**What it does**: Match events by source, detail-type, and detail content
**Default bus support**: ✅ **YES** - Fully supported
**Custom bus support**: ✅ **YES** - Fully supported
**Required?**: ✅ **YES** - How we route events to handlers

### 3. Multiple Targets per Rule ✅
**What it does**: One event can trigger multiple Lambda functions
**Default bus support**: ✅ **YES** - Fully supported
**Custom bus support**: ✅ **YES** - Fully supported
**Required?**: ⚠️ **NOT CURRENTLY USED** - We have one target per rule

### 4. Dead Letter Queue (DLQ) ✅
**What it does**: Failed events go to SQS DLQ for debugging/replay
**Default bus support**: ✅ **YES** - Fully supported
**Custom bus support**: ✅ **YES** - Fully supported
**Required?**: ✅ **YES** - We have DLQ configured

### 5. Retry & Error Handling ✅
**What it does**: EventBridge retries failed Lambda invocations
**Default bus support**: ✅ **YES** - Fully supported
**Custom bus support**: ✅ **YES** - Fully supported
**Required?**: ✅ **YES** - Built-in resilience

### 6. Asynchronous Processing ✅
**What it does**: Decouples event publishing from processing
**Default bus support**: ✅ **YES** - Fully supported
**Custom bus support**: ✅ **YES** - Fully supported
**Required?**: ✅ **YES** - Core requirement (avoids API Gateway timeout)

### 7. Event Replay ✅
**What it does**: Replay events for debugging
**Default bus support**: ✅ **YES** - Supported via EventBridge Archive
**Custom bus support**: ✅ **YES** - Supported via EventBridge Archive
**Required?**: ⚠️ **NOT CURRENTLY USED** - But available if needed

### 8. Cross-Account Event Sharing ⚠️
**What it does**: Share events between AWS accounts
**Default bus support**: ✅ **YES** - Supported with resource policy
**Custom bus support**: ✅ **YES** - Supported with resource policy
**Required?**: ❌ **NO** - Single account deployment

### 9. Event Isolation ⚠️
**What it does**: Separate application events from AWS service events
**Default bus support**: ❌ **NO** - AWS service events also go here
**Custom bus support**: ✅ **YES** - Only your events
**Required?**: ⚠️ **NICE TO HAVE** - Not critical for functionality

### 10. Resource-Based Policies ⚠️
**What it does**: Fine-grained access control per bus
**Default bus support**: ✅ **YES** - Supported
**Custom bus support**: ✅ **YES** - Supported
**Required?**: ❌ **NO** - Same-account access works without it

## Feature Comparison: Default vs Custom Bus

| Feature | Default Bus | Custom Bus | We Need? |
|---------|-------------|------------|----------|
| Event Rules & Patterns | ✅ | ✅ | ✅ YES |
| Multiple Targets | ✅ | ✅ | ⚠️ Not used |
| DLQ Support | ✅ | ✅ | ✅ YES |
| Retry & Error Handling | ✅ | ✅ | ✅ YES |
| Async Processing | ✅ | ✅ | ✅ YES |
| Event Replay | ✅ | ✅ | ⚠️ Nice to have |
| Cross-Account | ✅ | ✅ | ❌ No |
| Event Isolation | ❌ | ✅ | ⚠️ Nice to have |
| Resource Policies | ✅ | ✅ | ❌ No |

## Conclusion: Functionality Assessment

**✅ ALL required EventBridge features work on DEFAULT BUS**

The default bus supports:
- ✅ Event-driven orchestration
- ✅ Rules and patterns
- ✅ DLQ
- ✅ Retry/error handling
- ✅ Asynchronous processing
- ✅ All core functionality we need

**The ONLY differences are:**
1. **Event Isolation**: Custom bus isolates your events from AWS service events
   - **Impact**: Default bus will also receive AWS service events (EC2, S3, etc.)
   - **Mitigation**: Use event patterns to filter (we already do this with `source: "docprof.course"`)
   - **Risk**: Low - our patterns are specific enough

2. **Resource Policies**: Custom bus can have stricter access control
   - **Impact**: Default bus works fine for same-account access
   - **Risk**: None - we're single account

**Recommendation**: ✅ **Use default bus** - No functionality loss

---

## Lambda Function Recreation Assessment

### Current State
- **Function Name**: `docprof-dev-course-request-handler`
- **Handler**: `handler.lambda_handler`
- **Runtime**: Python 3.11
- **Role**: `docprof-dev-lambda-execution-role`
- **Issue**: Lambda package is broken (missing `shared.logic` module)

### What Terraform Will Do

When we destroy and recreate:

1. **Destroy Lambda Function**
   - Function code deleted
   - Function configuration deleted
   - **API Gateway integration**: ⚠️ Will break temporarily

2. **Recreate Lambda Function**
   - Function code repackaged correctly (includes `shared/logic`)
   - Function configuration recreated
   - **API Gateway integration**: ✅ Auto-reconnected (references function name)

### Dependencies to Check

#### 1. API Gateway Integration ✅ SAFE
**Current**: API Gateway route references function name
```hcl
# terraform/modules/api-gateway/main.tf
integration_uri = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${var.lambda_function_arn}/invocations"
```

**After recreation**: Function ARN changes, but Terraform will update integration
**Risk**: ✅ **LOW** - Terraform manages this automatically
**Downtime**: ~30 seconds during recreation

#### 2. EventBridge Rules ✅ SAFE
**Current**: Rules reference function ARN
```hcl
# terraform/modules/eventbridge/main.tf
target {
  arn = module.course_embedding_handler_lambda.function_arn
}
```

**After recreation**: Function ARN changes, but Terraform will update targets
**Risk**: ✅ **LOW** - Terraform manages this automatically

#### 3. IAM Permissions ✅ SAFE
**Current**: Lambda execution role has permissions
**After recreation**: Same role, same permissions
**Risk**: ✅ **NONE** - Role doesn't change

#### 4. CloudWatch Logs ✅ SAFE
**Current**: Log group `/aws/lambda/docprof-dev-course-request-handler`
**After recreation**: Same log group (created separately)
**Risk**: ✅ **NONE** - Log group persists

#### 5. Environment Variables ✅ SAFE
**Current**: Set in Terraform
**After recreation**: Recreated from Terraform
**Risk**: ✅ **NONE** - Managed by Terraform

### Code Changes Required

**✅ ZERO code changes needed**

The Lambda handler code (`handler.py`) doesn't reference:
- Function ARN
- Function name (hardcoded)
- Any Lambda-specific identifiers

The code only references:
- Handler function name (`lambda_handler`) - unchanged
- Imports (`from shared.logic.courses import ...`) - will work after recreation
- Environment variables - unchanged

### Terraform Plan Preview

```bash
terraform plan -target=module.course_request_handler_lambda.aws_lambda_function.this
```

**Expected changes:**
- `aws_lambda_function.this` - Destroy and recreate
- `aws_api_gateway_integration.*` - Update integration URI (automatic)
- `aws_cloudwatch_event_target.*` - Update target ARN (automatic)

**No changes to:**
- Lambda handler code
- Requirements.txt
- Shared modules
- IAM roles
- Environment variables

### Execution Plan

1. **Backup current state** (optional):
   ```bash
   terraform state pull > terraform-state-backup.json
   ```

2. **Destroy and recreate**:
   ```bash
   terraform destroy -target=module.course_request_handler_lambda.aws_lambda_function.this
   terraform apply -target=module.course_request_handler_lambda.aws_lambda_function.this
   ```

   OR use taint (safer):
   ```bash
   terraform taint module.course_request_handler_lambda.aws_lambda_function.this
   terraform apply -target=module.course_request_handler_lambda.aws_lambda_function.this
   ```

3. **Verify**:
   - Check Lambda function exists
   - Test API endpoint
   - Check CloudWatch logs

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| API Gateway integration breaks | Low | Medium | Terraform auto-updates |
| EventBridge targets break | Low | Medium | Terraform auto-updates |
| Code still broken | Low | High | Verify package includes `shared/logic` |
| Downtime | Medium | Low | ~30 seconds during recreation |

**Overall Risk**: ✅ **LOW** - Terraform manages dependencies automatically

---

## Final Recommendations

### 1. EventBridge Bus Strategy
**✅ Use DEFAULT BUS** - No functionality loss, simpler setup

**Rationale**:
- All required features work on default bus
- Simpler configuration (no custom bus setup)
- No resource policies needed
- Can always migrate to custom bus later if needed

**Action Items**:
- [ ] Update all rules to use default bus (remove `event_bus_name`)
- [ ] Remove `EVENT_BUS_NAME` env vars (or set to empty)
- [ ] Update `event_publisher.py` to use default bus
- [ ] Test end-to-end flow

### 2. Lambda Function Recreation
**✅ SAFE TO PROCEED** - No code changes needed

**Rationale**:
- Terraform manages all dependencies
- Code doesn't reference Lambda-specific identifiers
- Package will be rebuilt correctly
- Minimal downtime (~30 seconds)

**Action Items**:
- [ ] Backup Terraform state (optional)
- [ ] Taint and recreate Lambda function
- [ ] Verify API Gateway integration
- [ ] Verify EventBridge targets
- [ ] Test course generation flow

---

## Next Steps

1. ✅ **Assess EventBridge functionality** - COMPLETE (no loss on default bus)
2. ✅ **Assess Lambda recreation** - COMPLETE (safe, no code changes)
3. ⏳ **Fix Lambda packaging** - Destroy and recreate
4. ⏳ **Standardize on default bus** - Update Terraform
5. ⏳ **Test end-to-end** - Verify course generation works
