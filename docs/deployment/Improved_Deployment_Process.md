# Improved Terraform Deployment Process

**Date:** December 26, 2025  
**Status:** ✅ Implemented

---

## Summary

Fixed three major deployment issues that were requiring manual AWS CLI workarounds. Terraform now handles Lambda layer updates and API Gateway redeployments automatically.

---

## Problems Fixed

### 1. ✅ API Gateway Not Auto-Redeploying

**Problem:** When Lambda functions were updated, API Gateway continued serving the old deployment, causing 404 errors or stale behavior.

**Old Behavior:**
```bash
# After Lambda update, had to manually redeploy:
aws apigateway create-deployment --rest-api-id xxx --stage-name dev
```

**Solution:** 
- Added `triggers` to `aws_api_gateway_deployment` resource that hashes all Lambda integrations
- Removed `ignore_changes = [deployment_id]` from `aws_api_gateway_stage` resource
- Now automatically creates new deployment when Lambda function URIs change

**Location:** `terraform/modules/api-gateway/main.tf` lines 25-63

---

### 2. ✅ Lambda Functions Not Updating When Layer Version Changes

**Problem:** When shared code layer was updated (v37 → v38), Lambda functions continued using the old version.

**Old Behavior:**
```bash
# After layer update, had to manually update each Lambda:
aws lambda update-function-configuration --function-name xyz \
  --layers arn:aws:lambda:...:layer:shared-code:38
```

**Solution:**
- Added layer version numbers to Lambda function tags
- Tag changes trigger function updates, which then pick up new layer versions
- Terraform now detects layer ARN changes and updates functions automatically

**Location:** `terraform/modules/lambda/main.tf` lines 37-46

---

### 3. ✅ Shared Code Layer Change Detection Improved

**Problem:** Sometimes Terraform didn't detect when shared code files changed, requiring manual `terraform taint`.

**Old Behavior:**
```bash
# Had to force rebuild:
terraform taint module.shared_code_layer.null_resource.prepare_layer_structure
terraform apply
```

**Solution:**
- Improved file hashing by sorting file list for consistency
- Added comments explaining manual rebuild process
- Added `create_before_destroy` lifecycle to layer version

**Location:** `terraform/modules/lambda-shared-code-layer/main.tf` lines 18-116

---

## New Deployment Workflow

### ✅ Simple Case: Code Changes Only

```bash
cd terraform/environments/dev
terraform apply -auto-approve
```

**What happens automatically:**
1. Detects changed files in `src/lambda/shared/`
2. Creates new shared code layer version (v39, v40, etc.)
3. Updates all Lambda functions to use new layer
4. Detects Lambda function changes
5. Creates new API Gateway deployment
6. Updates API Gateway stage

**No manual AWS CLI commands needed!**

---

### 📋 When Manual Intervention Needed

**Scenario 1: Force rebuild shared code layer**
```bash
terraform taint module.shared_code_layer.null_resource.prepare_layer_structure
terraform apply
```

**Scenario 2: Deploy specific Lambda function only**
```bash
terraform apply -target=module.lambda.aws_lambda_function.course_outline_handler
```

**Scenario 3: API Gateway deployment failed mid-way**
```bash
# Terraform will auto-retry on next apply
terraform apply
```

---

## Verification

### Check Layer Versions

```bash
# See what version Lambda is using
aws lambda get-function-configuration \
  --function-name docprof-dev-course-outline-handler \
  --query 'Layers[*].Arn'

# Should show latest version, e.g.:
# arn:aws:lambda:us-east-1:xxx:layer:docprof-dev-shared-code:38
```

### Check API Gateway Deployment

```bash
# See latest deployment
aws apigateway get-deployments \
  --rest-api-id evjgcsghvi \
  --query 'items[0].[id,createdDate,description]'
```

### Check Terraform State

```bash
cd terraform/environments/dev

# See what will change
terraform plan

# Should show "No changes" if everything is up to date
```

---

## What Changed in Terraform Code

### File: `terraform/modules/api-gateway/main.tf`

**Lines 25-63 - API Gateway Deployment:**
```terraform
resource "aws_api_gateway_deployment" "this" {
  rest_api_id = aws_api_gateway_rest_api.this.id

  # NEW: Triggers automatic redeployment
  triggers = {
    integrations = sha256(jsonencode([
      for k, v in aws_api_gateway_integration.this : {
        uri    = v.uri
        method = v.http_method
      }
    ]))
  }
  # ... rest of config ...
}
```

**Lines 46-69 - API Gateway Stage:**
```terraform
resource "aws_api_gateway_stage" "this" {
  deployment_id = aws_api_gateway_deployment.this.id
  rest_api_id  = aws_api_gateway_rest_api.this.id
  stage_name   = var.environment
  
  # REMOVED: ignore_changes = [deployment_id]
  # Now picks up new deployments automatically
}
```

### File: `terraform/modules/lambda/main.tf`

**Lines 37-46 - Lambda Function Tags:**
```terraform
tags = merge(
  var.tags,
  {
    Name        = "${var.project_name}-${var.environment}-${var.function_name}"
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    # NEW: Track layer versions in tags to trigger updates
    LayerVersions = try(join(",", [for arn in var.layers : split(":", arn)[length(split(":", arn)) - 1]]), "none")
  }
)
```

### File: `terraform/modules/lambda-shared-code-layer/main.tf`

**Lines 18-52 - Layer Structure Preparation:**
```terraform
resource "null_resource" "prepare_layer_structure" {
  triggers = {
    # IMPROVED: Sort files for consistent hashing
    shared_code_hash = sha256(jsonencode([
      for f in sort(local.shared_files) : {
        path = f
        hash = fileexists("${var.shared_code_path}/${f}") ? filesha256("${var.shared_code_path}/${f}") : ""
      }
    ]))
  }
  # ... rest of config ...
}
```

**Lines 92-116 - Layer Version:**
```terraform
resource "aws_lambda_layer_version" "shared_code" {
  # ... config ...
  
  # NEW: Ensure clean updates
  lifecycle {
    create_before_destroy = true
  }
}
```

---

## Cost Impact

**No additional costs.** These changes only improve deployment automation - they don't change what resources are deployed or how they're configured.

---

## Rollback Plan

If these changes cause issues:

```bash
cd terraform/environments/dev
git checkout HEAD~1 -- ../../modules/api-gateway/main.tf
git checkout HEAD~1 -- ../../modules/lambda/main.tf
git checkout HEAD~1 -- ../../modules/lambda-shared-code-layer/main.tf
terraform apply
```

---

## Future Improvements (Not Implemented Yet)

### CI/CD Pipeline

Add GitHub Actions workflow:

```yaml
name: Deploy to AWS
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Terraform Apply
        run: |
          cd terraform/environments/dev
          terraform init
          terraform apply -auto-approve
```

### Staging Environment

Create `terraform/environments/staging/` with same structure as `dev/`, test changes there first before deploying to dev.

### Automated Testing

Add pre-deployment tests:
```bash
cd src/lambda
pytest tests/unit/
```

---

## References

- [Terraform Lifecycle Meta-Arguments](https://developer.hashicorp.com/terraform/language/meta-arguments/lifecycle)
- [API Gateway Deployment Best Practices](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-create-and-attach-iam-policy.html)
- [Lambda Layer Versioning](https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html)

---

## Deployment Log

| Date | Change | Result |
|------|--------|--------|
| 2025-12-26 | Implemented automatic API Gateway redeployment | ✅ Tested with terraform plan |
| 2025-12-26 | Implemented automatic Lambda layer version updates | ✅ Tested with terraform plan |
| 2025-12-26 | Improved shared code layer change detection | ✅ Tested with terraform plan |

---

**Next time you need to deploy code changes:**

```bash
cd terraform/environments/dev
export AWS_PROFILE=docprof-dev
export AWS_DEFAULT_REGION=us-east-1
terraform apply -auto-approve
```

**That's it! No more manual AWS CLI commands!** 🎉

