# Lambda Module

Reusable Terraform module for deploying Lambda functions.

## Usage

```hcl
module "document_processor" {
  source = "../../modules/lambda"

  project_name = "docprof"
  environment  = "dev"
  function_name = "document-processor"
  
  handler = "handler.lambda_handler"
  runtime = "python3.11"
  timeout = 900  # 15 minutes
  
  source_path = "../../../src/lambda/document_processor"
  
  environment_variables = {
    SOURCE_BUCKET        = module.s3.source_docs_bucket_name
    PROCESSED_BUCKET     = module.s3.processed_chunks_bucket_name
    DB_CLUSTER_ENDPOINT  = module.aurora.aurora_cluster_endpoint
    DB_NAME              = "docprof"
    DB_MASTER_USERNAME   = "docprof_admin"
    DB_PASSWORD_SECRET_ARN = module.aurora.aurora_master_password_secret_arn
  }
  
  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }
  
  tags = {
    Component = "document-processing"
  }
}
```

## Features

- Automatic ZIP creation from source directory
- CloudWatch log group with retention
- IAM role with basic execution permissions
- VPC configuration support
- Environment variable management
- Tagging support

## Variables

See `variables.tf` for complete list.

## Outputs

- `function_name` - Lambda function name
- `function_arn` - Lambda function ARN
- `function_invoke_arn` - Invoke ARN (for API Gateway)
- `role_arn` - Execution role ARN
- `role_name` - Execution role name

