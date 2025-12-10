# IAM Module

This module creates IAM roles and policies for DocProf AWS infrastructure.

## Resources Created

### Lambda Execution Role
- **Name**: `{project_name}-{environment}-lambda-execution-role`
- **Permissions**:
  - CloudWatch Logs (write logs)
  - VPC access (create/delete network interfaces)
  - RDS/Aurora (connect via IAM authentication)
  - S3 (read/write on DocProf buckets)
  - Bedrock (invoke Claude and Titan models)
  - Polly (synthesize speech)
  - DynamoDB (session management)

### RDS Monitoring Role
- **Name**: `{project_name}-{environment}-rds-monitoring-role`
- **Permissions**: Enhanced monitoring for RDS/Aurora

## Usage

```hcl
module "iam" {
  source = "../../modules/iam"

  project_name = "docprof"
  environment  = "dev"
  aws_region   = "us-east-1"
  account_id   = "123456789012"

  tags = {
    ManagedBy = "terraform"
  }
}
```

## Security Notes

- All policies follow least-privilege principles
- Resource ARNs are specific (no wildcards except where necessary)
- Lambda role uses inline policies for clarity
- RDS monitoring role uses AWS managed policy

## Outputs

- `lambda_execution_role_arn` - ARN of Lambda execution role
- `lambda_execution_role_name` - Name of Lambda execution role
- `rds_monitoring_role_arn` - ARN of RDS monitoring role
- `rds_monitoring_role_name` - Name of RDS monitoring role


