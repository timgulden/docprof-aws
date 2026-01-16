# SAM + Terraform Hybrid Architecture

**Date:** December 26, 2025  
**Status:** ✅ Implemented

---

## 🎯 Architecture Overview

DocProf uses a **hybrid infrastructure approach** that combines the strengths of both Terraform and AWS SAM:

- **Terraform:** Manages infrastructure (VPC, databases, S3, IAM roles)
- **SAM:** Manages application code (Lambda functions, layers, API Gateway)
- **GitHub Actions:** Automates deployment on every push

---

## 📊 Why Hybrid?

### Problem with Terraform-Only:
- ❌ Lambda layer versioning issues
- ❌ No atomic updates across functions
- ❌ Manual coordination required
- ❌ Complex Lambda packaging

### Problem with SAM-Only:
- ❌ Less flexible for complex infrastructure
- ❌ Harder to manage VPC, Aurora, etc.
- ❌ Not ideal for non-Lambda resources

### Solution: Hybrid Approach
- ✅ Terraform for infrastructure (changes rarely)
- ✅ SAM for application code (changes frequently)
- ✅ Single command deploys all Lambdas
- ✅ Auto-versioned layers
- ✅ CI/CD integration

---

## 🏗️ Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     GitHub Repository                         │
│  ┌──────────────────┐         ┌─────────────────────────┐   │
│  │  Infrastructure  │         │   Application Code      │   │
│  │  (Terraform)     │         │   (SAM)                 │   │
│  │                  │         │                         │   │
│  │  - VPC/Subnets  │         │  - Lambda functions     │   │
│  │  - Aurora DB    │         │  - Shared code layer    │   │
│  │  - DynamoDB     │         │  - API Gateway          │   │
│  │  - S3 Buckets   │         │  - EventBridge rules    │   │
│  │  - Cognito      │         │                         │   │
│  │  - Base IAM     │         │                         │   │
│  └────────┬─────────┘         └───────────┬─────────────┘   │
│           │                               │                  │
│           │                               │                  │
│           ▼                               ▼                  │
│    terraform apply              sam build && sam deploy      │
│    (Manual, rare)               (Automatic via CI/CD)        │
└───────────┼───────────────────────────────┼──────────────────┘
            │                               │
            │                               │
            ▼                               ▼
      ┌──────────┐                  ┌──────────────┐
      │   AWS    │                  │  CloudForm   │
      │  Direct  │◄─────────────────│  Stack       │
      │          │  References      │  (SAM)       │
      └──────────┘                  └──────────────┘
            │                               │
            │                               │
            └───────────┬───────────────────┘
                        │
                        ▼
                  ┌────────────┐
                  │  Running   │
                  │  System    │
                  └────────────┘
```

---

## 📁 Project Structure

```
docprof-aws/
├── terraform/                    # Infrastructure as Code
│   └── environments/
│       └── dev/
│           ├── main.tf          # Terraform config
│           └── outputs.tf       # Exports for SAM
│
├── src/lambda/                   # Application code
│   ├── shared/                  # Shared code (becomes layer)
│   │   ├── db_utils.py
│   │   ├── logic/
│   │   │   └── courses.py
│   │   └── core/
│   │       └── commands.py
│   │
│   ├── course_request_handler/  # Lambda functions
│   │   └── handler.py
│   ├── course_storage_handler/
│   │   └── handler.py
│   └── ...                      # 14 course Lambdas
│
├── template.yaml                 # SAM template
├── samconfig.toml               # SAM configuration
├── .github/
│   └── workflows/
│       └── deploy.yml           # CI/CD pipeline
│
└── scripts/
    └── sync_terraform_to_sam.sh # Helper script
```

---

## 🚀 Deployment Workflows

### 1️⃣ Infrastructure Changes (Rare)

```bash
cd terraform/environments/dev
terraform plan
terraform apply

# Update SAM config with new outputs
cd ../../..
./scripts/sync_terraform_to_sam.sh
```

**When to use:**
- Adding new S3 bucket
- Changing VPC configuration
- Updating Aurora settings
- Modifying IAM roles

**Frequency:** Every few weeks

---

### 2️⃣ Application Changes (Frequent)

**Local testing:**
```bash
# Build SAM application
sam build

# Deploy to AWS
sam deploy

# Or deploy with live sync (auto-rebuild on changes)
sam sync --watch
```

**Automatic (via CI/CD):**
```bash
git add src/lambda/shared/courses.py
git commit -m "Fix course parsing bug"
git push origin main

# GitHub Actions automatically:
# 1. Runs tests
# 2. Builds SAM app
# 3. Deploys to AWS
# 4. All 14 Lambdas updated atomically!
```

**Frequency:** Multiple times per day

---

## 🔄 How It Works

### Step 1: Terraform Exports Values

`terraform/environments/dev/outputs.tf`:
```hcl
output "aurora_cluster_endpoint" {
  value = module.aurora.cluster_endpoint
}

output "vpc_private_subnet_ids" {
  value = module.vpc.private_subnet_ids
}

output "lambda_execution_role_arn" {
  value = module.iam.lambda_execution_role_arn
}
```

### Step 2: SAM Imports as Parameters

`template.yaml`:
```yaml
Parameters:
  DBClusterEndpoint:
    Type: String
  PrivateSubnetIds:
    Type: CommaDelimitedList
  LambdaExecutionRoleArn:
    Type: String
```

### Step 3: SAM Uses in Resources

```yaml
Resources:
  CourseRequestHandler:
    Type: AWS::Serverless::Function
    Properties:
      Role: !Ref LambdaExecutionRoleArn
      VpcConfig:
        SubnetIds: !Ref PrivateSubnetIds
      Environment:
        Variables:
          DB_CLUSTER_ENDPOINT: !Ref DBClusterEndpoint
```

### Step 4: Shared Code Layer Auto-Versions

```yaml
SharedCodeLayer:
  Type: AWS::Serverless::LayerVersion
  Properties:
    LayerName: docprof-dev-shared-code
    ContentUri: src/lambda/shared/
  # SAM automatically:
  # - Zips shared/ directory
  # - Creates new version on any change
  # - Updates all functions using this layer
```

---

## 🎯 Key Benefits

### 1. Automatic Synchronization

**Before (Terraform only):**
```bash
# Change shared code
edit src/lambda/shared/courses.py

# Manual deployment needed:
terraform taint module.shared_code_layer.null_resource.prepare_layer_structure
terraform apply -target=module.shared_code_layer
terraform apply -target=module.course_request_handler_lambda
terraform apply -target=module.course_storage_handler_lambda
terraform apply -target=module.course_parts_handler_lambda
# ... 11 more times ...
```

**After (SAM):**
```bash
# Change shared code
edit src/lambda/shared/courses.py

# Push to GitHub
git push

# Done! GitHub Actions deploys everything automatically
```

### 2. No Version Drift

**SAM ensures:**
- ✅ All functions use same layer version
- ✅ Atomic updates (all or nothing)
- ✅ Rollback capability
- ✅ Version tracking

### 3. Built-in Best Practices

**SAM provides:**
- ✅ Proper IAM permissions
- ✅ CloudWatch log groups
- ✅ X-Ray tracing support
- ✅ API Gateway CORS
- ✅ EventBridge integration

---

## 🧪 Testing

### Local Testing

```bash
# Build application
sam build

# Invoke function locally
sam local invoke CourseRequestHandler -e events/course_request.json

# Start API locally
sam local start-api
# Test at http://localhost:3000

# Start Lambda locally with hot-reload
sam sync --watch --stack-name test-stack
```

### Automated Testing (CI/CD)

GitHub Actions runs:
1. **Unit tests** - `pytest tests/unit/`
2. **Lint** - `flake8 src/lambda/`
3. **SAM validate** - Validates template
4. **Build** - Packages application
5. **Deploy** - Deploys to AWS
6. **Smoke test** - Verifies deployment

---

## 📊 Comparison: Before vs After

| Aspect | Terraform Only | SAM Hybrid |
|--------|---------------|------------|
| **Deploy all Lambdas** | Manual, ~10 min | Automatic, ~2 min |
| **Version drift** | Possible | Impossible |
| **Layer updates** | Manual taint + apply | Automatic |
| **CI/CD** | Complex setup | Built-in |
| **Local testing** | Difficult | `sam local` |
| **Rollback** | Manual | One command |
| **Debugging** | CloudWatch only | Local invoke |

---

## 🎓 Portfolio Value

**This architecture demonstrates:**

1. **Hybrid Cloud Architecture**
   - Understanding tool strengths
   - Pragmatic decision-making
   - Infrastructure vs application separation

2. **CI/CD Best Practices**
   - Automated testing
   - Deployment pipelines
   - Git-based workflows

3. **Serverless Expertise**
   - AWS SAM proficiency
   - Lambda layers
   - Event-driven architecture

4. **DevOps Skills**
   - Infrastructure as Code
   - Automation
   - Monitoring & observability

---

## 🔧 Maintenance

### Daily: Application Updates

```bash
git push
# Automatic deployment via GitHub Actions
```

### Weekly: Review Logs

```bash
sam logs --stack-name docprof-dev-course-pipeline --tail
```

### Monthly: Infrastructure Updates

```bash
cd terraform/environments/dev
terraform plan
terraform apply
./scripts/sync_terraform_to_sam.sh
```

---

## 📚 References

- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [SAM + Terraform Integration](https://aws.amazon.com/blogs/compute/better-together-aws-sam-and-hashicorp-terraform/)
- [GitHub Actions for SAM](https://github.com/aws-actions/setup-sam)

---

## 🚀 Next Steps

After this migration:

1. **Test course creation** - Verify end-to-end flow
2. **Migrate remaining Lambdas** - Chat, books, etc.
3. **Add staging environment** - Test before production
4. **Implement blue/green** - Zero-downtime deployments

---

**Created:** December 26, 2025  
**Last Updated:** December 26, 2025  
**Maintained By:** SAM + GitHub Actions

