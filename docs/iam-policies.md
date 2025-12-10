# IAM Policies Documentation

**Last Updated:** December 10, 2025  
**Environment:** dev

This document describes all IAM roles and policies created for DocProf AWS infrastructure.

---

## Lambda Execution Role

**Role Name:** `docprof-dev-lambda-execution-role`  
**ARN:** `arn:aws:iam::176520790264:role/docprof-dev-lambda-execution-role`  
**Trust Policy:** Allows `lambda.amazonaws.com` service to assume the role

### Policies Attached

#### 1. CloudWatch Logs Policy
**Policy Name:** `docprof-dev-lambda-cloudwatch-logs`

**Permissions:**
- `logs:CreateLogGroup`
- `logs:CreateLogStream`
- `logs:PutLogEvents`

**Resources:**
- `arn:aws:logs:us-east-1:176520790264:log-group:/aws/lambda/docprof-dev-*`

**Purpose:** Allows Lambda functions to write logs to CloudWatch Logs.

---

#### 2. VPC Access Policy
**Policy Name:** `docprof-dev-lambda-vpc`

**Permissions:**
- `ec2:CreateNetworkInterface`
- `ec2:DescribeNetworkInterfaces`
- `ec2:DeleteNetworkInterface`
- `ec2:AssignPrivateIpAddresses`
- `ec2:UnassignPrivateIpAddresses`

**Resources:** `*` (required for VPC access)

**Purpose:** Allows Lambda functions in VPC to create and manage network interfaces for accessing Aurora and VPC endpoints.

---

#### 3. RDS/Aurora Access Policy
**Policy Name:** `docprof-dev-lambda-rds`

**Permissions:**
- `rds-db:connect`

**Resources:**
- `arn:aws:rds-db:us-east-1:176520790264:dbuser:*/docprof_lambda_user`

**Purpose:** Allows Lambda functions to connect to Aurora Serverless via RDS Proxy using IAM authentication.

**Note:** The database user `docprof_lambda_user` must be created in Aurora with IAM authentication enabled.

---

#### 4. S3 Access Policy
**Policy Name:** `docprof-dev-lambda-s3`

**Permissions:**
- `s3:GetObject`
- `s3:PutObject`
- `s3:DeleteObject`
- `s3:ListBucket`

**Resources:**
- `arn:aws:s3:::docprof-dev-*`
- `arn:aws:s3:::docprof-dev-*/*`

**Purpose:** Allows Lambda functions to read and write objects in DocProf S3 buckets (source documents, processed chunks, frontend assets).

---

#### 5. Bedrock Access Policy
**Policy Name:** `docprof-dev-lambda-bedrock`

**Permissions:**
- `bedrock:InvokeModel`
- `bedrock:InvokeModelWithResponseStream`

**Resources:**
- `arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0`
- `arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-*`
- `arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v1`
- `arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0`

**Purpose:** Allows Lambda functions to invoke Claude 3.5 Sonnet for LLM tasks and Titan for embeddings.

---

#### 6. Polly Access Policy
**Policy Name:** `docprof-dev-lambda-polly`

**Permissions:**
- `polly:SynthesizeSpeech`

**Resources:** `*`

**Purpose:** Allows Lambda functions to synthesize speech using AWS Polly for lecture audio generation.

---

#### 7. DynamoDB Access Policy
**Policy Name:** `docprof-dev-lambda-dynamodb`

**Permissions:**
- `dynamodb:GetItem`
- `dynamodb:PutItem`
- `dynamodb:UpdateItem`
- `dynamodb:DeleteItem`
- `dynamodb:Query`
- `dynamodb:Scan`

**Resources:**
- `arn:aws:dynamodb:us-east-1:176520790264:table/docprof-dev-sessions`

**Purpose:** Allows Lambda functions to manage user sessions in DynamoDB.

---

## RDS Monitoring Role

**Role Name:** `docprof-dev-rds-monitoring-role`  
**ARN:** `arn:aws:iam::176520790264:role/docprof-dev-rds-monitoring-role`  
**Trust Policy:** Allows `monitoring.rds.amazonaws.com` service to assume the role

### Policy Attached

**Policy:** AWS Managed Policy `AmazonRDSEnhancedMonitoringRole`

**Purpose:** Allows RDS/Aurora to send enhanced monitoring metrics to CloudWatch.

---

## Security Principles

### Least Privilege
- All policies use specific resource ARNs where possible
- No wildcards except where required by AWS service design (VPC access, Polly)
- S3 bucket access limited to `docprof-dev-*` pattern
- DynamoDB access limited to sessions table only

### Separation of Concerns
- Lambda execution role separate from RDS monitoring role
- Each service has its own policy for clarity and maintainability

### Best Practices
- Inline policies used for Lambda role (easier to manage in Terraform)
- AWS managed policy used for RDS monitoring (proven and maintained by AWS)
- All resources tagged with Project and Environment

---

## Usage in Terraform

The IAM module is called in `terraform/environments/dev/main.tf`:

```hcl
module "iam" {
  source = "../../modules/iam"

  project_name = local.project_name
  environment  = local.environment
  aws_region   = local.aws_region
  account_id   = data.aws_caller_identity.current.account_id

  tags = {
    ManagedBy = "terraform"
  }
}
```

## Outputs

The module provides these outputs:

- `lambda_execution_role_arn` - ARN of Lambda execution role
- `lambda_execution_role_name` - Name of Lambda execution role
- `rds_monitoring_role_arn` - ARN of RDS monitoring role
- `rds_monitoring_role_name` - Name of RDS monitoring role

These outputs are used when creating Lambda functions and Aurora clusters.

---

## Future Enhancements

When implementing Lambda functions, assign the execution role:

```hcl
resource "aws_lambda_function" "chat_handler" {
  # ... other configuration ...
  role = module.iam.lambda_execution_role_arn
}
```

When creating Aurora cluster, assign the monitoring role:

```hcl
resource "aws_rds_cluster" "aurora" {
  # ... other configuration ...
  monitoring_role_arn = module.iam.rds_monitoring_role_arn
  monitoring_interval = 60
}
```

---

## Validation

To verify IAM roles are correctly configured:

```bash
# List Lambda role policies
aws iam list-role-policies --role-name docprof-dev-lambda-execution-role

# Get role details
aws iam get-role --role-name docprof-dev-lambda-execution-role

# Verify RDS monitoring role
aws iam get-role --role-name docprof-dev-rds-monitoring-role
```

---

**End of IAM Policies Documentation**


