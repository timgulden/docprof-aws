# DocProf Development Environment
# This file orchestrates all infrastructure modules

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.1"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }

  # TODO: Configure S3 backend for state storage
  # backend "s3" {
  #   bucket = "docprof-terraform-state"
  #   key    = "dev/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "docprof"
      Environment = "dev"
      ManagedBy   = "terraform"
    }
  }
}

# Get current AWS account ID
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Variables will be defined in variables.tf
# For now, using locals for initial setup
locals {
  project_name = var.project_name
  environment  = var.environment
  aws_region   = var.aws_region
}

# Get availability zones for the region
data "aws_availability_zones" "available" {
  state = "available"
}

# Get AWS account ID (already defined above at line 64)
# data "aws_caller_identity" "current" {}  # Already defined

# VPC Module
module "vpc" {
  source = "../../modules/vpc"

  project_name       = local.project_name
  environment        = local.environment
  aws_region         = local.aws_region
  vpc_cidr           = "10.0.0.0/16"
  availability_zones = slice(data.aws_availability_zones.available.names, 0, 2)

  # Enable AI endpoints on-demand (default: false to save costs)
  enable_ai_endpoints = var.enable_ai_endpoints

  tags = {
    ManagedBy = "terraform"
  }
}

# IAM Module
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

# Aurora Module
module "aurora" {
  source = "../../modules/aurora"

  project_name        = local.project_name
  environment         = local.environment
  aws_region          = local.aws_region
  private_subnet_ids  = module.vpc.private_subnet_ids
  security_group_id   = module.vpc.aurora_security_group_id
  monitoring_role_arn = module.iam.rds_monitoring_role_arn

  min_capacity             = 0 # Enable auto-pause (pauses after 60 min idle)
  max_capacity             = 2.0
  seconds_until_auto_pause = 3600 # 60 minutes (1 hour) - smoother UX, still saves costs

  tags = {
    ManagedBy = "terraform"
  }
}

# S3 Module
module "s3" {
  source = "../../modules/s3"

  project_name = local.project_name
  environment  = local.environment
  aws_region   = local.aws_region

  tags = {
    ManagedBy = "terraform"
  }
}

# DynamoDB Module for Sessions
module "dynamodb" {
  source = "../../modules/dynamodb"

  project_name = local.project_name
  environment  = local.environment

  tags = {
    ManagedBy = "terraform"
  }
}

# DynamoDB Module for Course State
module "dynamodb_course_state" {
  source = "../../modules/dynamodb-course-state"

  project_name = local.project_name
  environment  = local.environment

  tags = {
    ManagedBy = "terraform"
  }
}

# Cognito Module for Authentication
module "cognito" {
  source = "../../modules/cognito"

  project_name = local.project_name
  environment  = local.environment

  # MFA optional for dev (can enable in prod)
  mfa_enabled = false

  # Callback URLs - will be updated when CloudFront is deployed
  # For now, include localhost for development
  callback_urls = [
    "http://localhost:5173", # Vite dev server
    "http://localhost:3000", # Alternative dev port
    # TODO: Add CloudFront URL when deployed
  ]

  logout_urls = [
    "http://localhost:5173",
    "http://localhost:3000",
    # TODO: Add CloudFront URL when deployed
  ]

  tags = {
    ManagedBy = "terraform"
  }
}

# EventBridge Module for Course Generation Events
module "eventbridge" {
  source = "../../modules/eventbridge"

  project_name = local.project_name
  environment  = local.environment

  tags = {
    ManagedBy = "terraform"
  }
}

# Lambda Layer for Python Dependencies
module "lambda_layer" {
  source = "../../modules/lambda-layer"

  project_name      = local.project_name
  environment       = local.environment
  requirements_path = "${path.module}/../../modules/lambda-layer/requirements.txt"
  s3_bucket         = module.s3.processed_chunks_bucket_name # Use processed_chunks bucket for layer storage

  tags = {
    ManagedBy = "terraform"
  }
}

# Lambda Layer for Shared Application Code
module "shared_code_layer" {
  source = "../../modules/lambda-shared-code-layer"

  project_name     = local.project_name
  environment      = local.environment
  shared_code_path = "${path.module}/../../../src/lambda/shared"
  s3_bucket        = module.s3.processed_chunks_bucket_name

  tags = {
    ManagedBy = "terraform"
  }

  depends_on = [
    module.s3 # Ensure S3 bucket exists before creating layer
  ]
}

# Document Processor Lambda
module "document_processor_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "document-processor"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 900  # 15 minutes (max for Lambda)
  memory_size = 3008 # 3GB for large PDF processing (38MB PDF + processing overhead)

  source_path = "${path.module}/../../../src/lambda/document_processor"

  # Use shared Lambda execution role
  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  environment_variables = {
    SOURCE_BUCKET          = module.s3.source_docs_bucket_name
    PROCESSED_BUCKET       = module.s3.processed_chunks_bucket_name
    DB_CLUSTER_ENDPOINT    = module.aurora.cluster_endpoint
    DB_NAME                = module.aurora.database_name
    DB_MASTER_USERNAME     = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
    AWS_ACCOUNT_ID         = data.aws_caller_identity.current.account_id
    # Note: AWS_REGION is automatically set by Lambda runtime
  }

  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "document-processing"
    Function  = "ingestion"
  }

  depends_on = [
    module.aurora,
    module.s3,
    module.vpc,
    module.iam,
    module.lambda_layer,
    module.shared_code_layer
  ]
}

# S3 EventBridge Notification for Document Processor
# Using EventBridge instead of direct S3->Lambda because Lambda is in VPC
# S3 can't validate VPC Lambdas directly, but EventBridge can handle them
resource "aws_s3_bucket_notification" "document_processor_trigger" {
  bucket = module.s3.source_docs_bucket_name

  eventbridge = true # Enable EventBridge notifications
}

# EventBridge Rule to trigger Lambda on S3 object creation
resource "aws_cloudwatch_event_rule" "s3_document_upload" {
  name        = "${local.project_name}-${local.environment}-s3-document-upload"
  description = "Trigger document processor when PDF is uploaded to S3"

  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["Object Created"]
    detail = {
      bucket = {
        name = [module.s3.source_docs_bucket_name]
      }
      object = {
        key = [{
          prefix = "books/"
        }]
      }
    }
  })

  tags = {
    Project     = local.project_name
    Environment = local.environment
    ManagedBy   = "terraform"
  }
}

# EventBridge Target - Lambda function
resource "aws_cloudwatch_event_target" "document_processor" {
  rule      = aws_cloudwatch_event_rule.s3_document_upload.name
  target_id = "DocumentProcessorLambda"
  arn       = module.document_processor_lambda.function_arn
}

# Lambda permission for EventBridge to invoke
resource "aws_lambda_permission" "eventbridge_invoke_document_processor" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = module.document_processor_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.s3_document_upload.arn
}

# Note: IAM policies for Lambda are already configured in module.iam
# The shared Lambda execution role has all necessary permissions:
# - S3 access (via lambda_s3 policy)
# - Bedrock access (via lambda_bedrock policy)
# - Secrets Manager access (via lambda_rds policy - includes secrets)
# - VPC access (via lambda_vpc policy)
# - CloudWatch Logs (via lambda_cloudwatch_logs policy)

# Book Upload Lambda (for UI-driven ingestion)
module "book_upload_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "book-upload"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 120 # 2 minutes (needed for LLM metadata extraction)
  memory_size = 256 # 256MB sufficient for upload handling

  source_path = "${path.module}/../../../src/lambda/book_upload"

  # Use shared Lambda execution role
  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  environment_variables = {
    SOURCE_BUCKET          = module.s3.source_docs_bucket_name
    DB_CLUSTER_ENDPOINT    = module.aurora.cluster_endpoint
    DB_NAME                = module.aurora.database_name
    DB_MASTER_USERNAME     = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
    # API Gateway URL - hardcoded to avoid circular dependency with api_gateway module
    # TODO: Use module.api_gateway.api_url after resolving circular dependency
    API_GATEWAY_URL = "https://xp2vbfyu3f.execute-api.${data.aws_region.current.name}.amazonaws.com/${local.environment}"
    AWS_ACCOUNT_ID  = data.aws_caller_identity.current.account_id
    # Note: AWS_REGION is automatically set by Lambda runtime
  }

  # VPC config needed for database access (to store cover image)
  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "book-upload"
    Function  = "ingestion"
  }

  depends_on = [
    module.s3,
    module.aurora,
    module.vpc,
    module.iam,
    module.lambda_layer,
    module.shared_code_layer
  ]
}

# Books List Lambda (for fetching all books)
module "books_list_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "books-list"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 30  # 30 seconds (should be fast)
  memory_size = 256 # 256MB sufficient

  source_path = "${path.module}/../../../src/lambda/books_list"

  # Use shared Lambda execution role
  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  environment_variables = {
    DB_CLUSTER_ENDPOINT    = module.aurora.cluster_endpoint
    DB_NAME                = module.aurora.database_name
    DB_MASTER_USERNAME     = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
    # Note: AWS_REGION is automatically set by Lambda runtime
  }

  # VPC config needed for database access
  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "books"
    Function  = "query"
  }

  depends_on = [
    module.aurora,
    module.vpc,
    module.iam,
    module.lambda_layer,
    module.shared_code_layer
  ]
}

# Tunnel Status Lambda (stub endpoint - tunnel feature not used in AWS)
module "tunnel_status_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "tunnel-status"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 10  # Very fast stub endpoint
  memory_size = 128 # Minimal memory needed

  source_path = "${path.module}/../../../src/lambda/tunnel_status"

  # Use shared Lambda execution role
  role_arn = module.iam.lambda_execution_role_arn

  # Attach Python dependencies layer for shared utilities
  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  # No environment variables needed
  environment_variables = {}

  # No VPC needed for stub endpoint
  vpc_config = null

  tags = {
    Component = "tunnel"
    Function  = "status-stub"
  }

  depends_on = [
    module.iam,
    module.lambda_layer,
    module.shared_code_layer
  ]
}

# Book Cover Lambda (returns cover images from S3 or 404)
module "book_cover_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "book-cover"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 10  # Fast endpoint
  memory_size = 256 # Sufficient for image handling

  source_path = "${path.module}/../../../src/lambda/book_cover"

  # Use shared Lambda execution role
  role_arn = module.iam.lambda_execution_role_arn

  # Attach Python dependencies layer for shared utilities
  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  # Environment variables for database access
  environment_variables = {
    DB_CLUSTER_ENDPOINT    = module.aurora.cluster_endpoint
    DB_NAME                = module.aurora.database_name
    DB_MASTER_USERNAME     = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
  }

  # VPC config needed for database access
  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "books"
    Function  = "cover"
  }

  depends_on = [
    module.aurora,
    module.vpc,
    module.iam,
    module.lambda_layer,
    module.shared_code_layer
  ]
}

# Book PDF Lambda (returns PDF files from database)
module "book_pdf_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "book-pdf"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 60  # 60 seconds (PDFs can be large)
  memory_size = 512 # 512MB for larger PDFs

  source_path = "${path.module}/../../../src/lambda/book_pdf"

  # Use shared Lambda execution role
  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  # Environment variables for database access and S3
  environment_variables = {
    DB_CLUSTER_ENDPOINT    = module.aurora.cluster_endpoint
    DB_NAME                = module.aurora.database_name
    DB_MASTER_USERNAME     = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
    SOURCE_BUCKET          = module.s3.source_docs_bucket_name
  }

  # VPC config needed for database access
  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "books"
    Function  = "pdf"
  }

  depends_on = [
    module.aurora,
    module.vpc,
    module.iam,
    module.lambda_layer,
    module.shared_code_layer
  ]
}

# Book Delete Lambda
module "book_delete_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "book-delete"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 30 # May need time for cascading deletes
  memory_size = 256

  source_path = "${path.module}/../../../src/lambda/book_delete"

  # Use shared Lambda execution role
  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  environment_variables = {
    DB_CLUSTER_ENDPOINT    = module.aurora.cluster_endpoint
    DB_NAME                = module.aurora.database_name
    DB_MASTER_USERNAME     = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
  }

  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "books"
    Function  = "delete"
  }

  depends_on = [
    module.aurora,
    module.vpc,
    module.iam,
    module.lambda_layer,
    module.shared_code_layer
  ]
}

# Schema Initialization Lambda (for creating database schema)
module "schema_init_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "schema-init"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 60  # 1 minute (enough for schema creation)
  memory_size = 256 # 256MB sufficient

  source_path = "${path.module}/../../../src/lambda/schema_init"

  # Use shared Lambda execution role
  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  environment_variables = {
    DB_CLUSTER_ENDPOINT    = module.aurora.cluster_endpoint
    DB_NAME                = module.aurora.database_name
    DB_MASTER_USERNAME     = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
    # Note: AWS_REGION is automatically set by Lambda runtime
  }

  # VPC config needed for database access
  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "schema-init"
    Function  = "database"
  }

  depends_on = [
    module.aurora,
    module.iam,
    module.vpc,
    module.lambda_layer,     # Ensure Python deps layer is built
    module.shared_code_layer # Ensure shared code layer is built
  ]
}

# Connection Test Lambda (for testing infrastructure connectivity)
# TESTING: Using shared code layer instead of bundling (Phase 2 of migration)
module "connection_test_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "connection-test"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 60  # 1 minute (enough for tests)
  memory_size = 256 # 256MB sufficient for testing

  source_path = "${path.module}/../../../src/lambda/connection_test"

  # Use shared Lambda execution role
  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  environment_variables = {
    DB_CLUSTER_ENDPOINT    = module.aurora.cluster_endpoint
    DB_NAME                = module.aurora.database_name
    DB_MASTER_USERNAME     = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
    AWS_ACCOUNT_ID         = data.aws_caller_identity.current.account_id
    # Note: AWS_REGION is automatically set by Lambda runtime
  }

  # VPC config needed for database access
  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "connection-test"
    Function  = "testing"
  }

  depends_on = [
    module.aurora,
    module.iam,
    module.vpc,
    module.lambda_layer,     # Ensure Python deps layer is built
    module.shared_code_layer # Ensure shared code layer is built
  ]
}

# Database Content Check Lambda
module "db_check_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "db-check"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 60
  memory_size = 256

  source_path = "${path.module}/../../../src/lambda/db_check"

  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  environment_variables = {
    DB_CLUSTER_ENDPOINT    = module.aurora.cluster_endpoint
    DB_NAME                = module.aurora.database_name
    DB_MASTER_USERNAME     = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
    AWS_ACCOUNT_ID         = data.aws_caller_identity.current.account_id
  }

  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "database"
    Function  = "utility"
  }

  depends_on = [
    module.aurora,
    module.vpc,
    module.iam,
    module.lambda_layer,
    module.shared_code_layer
  ]
}

# Database Book ID Check Lambda
module "db_check_book_ids_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "db-check-book-ids"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 30
  memory_size = 256

  source_path = "${path.module}/../../../src/lambda/db_check_book_ids"

  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  environment_variables = {
    DB_CLUSTER_ENDPOINT    = module.aurora.cluster_endpoint
    DB_NAME                = module.aurora.database_name
    DB_MASTER_USERNAME     = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
    AWS_ACCOUNT_ID         = data.aws_caller_identity.current.account_id
  }

  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "database"
    Function  = "utility"
  }

  depends_on = [
    module.aurora,
    module.vpc,
    module.iam,
    module.lambda_layer,
    module.shared_code_layer
  ]
}

# Database Merge Books Lambda
module "db_merge_books_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "db-merge-books"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 60
  memory_size = 256

  source_path = "${path.module}/../../../src/lambda/db_merge_books"

  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  environment_variables = {
    DB_CLUSTER_ENDPOINT    = module.aurora.cluster_endpoint
    DB_NAME                = module.aurora.database_name
    DB_MASTER_USERNAME     = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
    AWS_ACCOUNT_ID         = data.aws_caller_identity.current.account_id
  }

  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "database"
    Function  = "utility"
  }

  depends_on = [
    module.aurora,
    module.vpc,
    module.iam,
    module.lambda_layer,
    module.shared_code_layer
  ]
}

# Database Check Duplicates Lambda
module "db_check_duplicates_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "db-check-duplicates"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 60
  memory_size = 512

  source_path = "${path.module}/../../../src/lambda/db_check_duplicates"

  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  environment_variables = {
    DB_CLUSTER_ENDPOINT    = module.aurora.cluster_endpoint
    DB_NAME                = module.aurora.database_name
    DB_MASTER_USERNAME     = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
    AWS_ACCOUNT_ID         = data.aws_caller_identity.current.account_id
  }

  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "database"
    Function  = "utility"
  }

  depends_on = [
    module.aurora,
    module.vpc,
    module.iam,
    module.lambda_layer,
    module.shared_code_layer
  ]
}

# Database Cleanup Lambda
module "db_cleanup_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "db-cleanup"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 60
  memory_size = 256

  source_path = "${path.module}/../../../src/lambda/db_cleanup"

  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  environment_variables = {
    DB_CLUSTER_ENDPOINT    = module.aurora.cluster_endpoint
    DB_NAME                = module.aurora.database_name
    DB_MASTER_USERNAME     = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
    AWS_ACCOUNT_ID         = data.aws_caller_identity.current.account_id
  }

  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "database"
    Function  = "utility"
  }

  depends_on = [
    module.aurora,
    module.vpc,
    module.iam,
    module.lambda_layer,
    module.shared_code_layer
  ]
}

# Database Deduplicate Chunks Lambda
module "db_deduplicate_chunks_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "db-deduplicate-chunks"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 120
  memory_size = 512

  source_path = "${path.module}/../../../src/lambda/db_deduplicate_chunks"

  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  environment_variables = {
    DB_CLUSTER_ENDPOINT    = module.aurora.cluster_endpoint
    DB_NAME                = module.aurora.database_name
    DB_MASTER_USERNAME     = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
    AWS_ACCOUNT_ID         = data.aws_caller_identity.current.account_id
  }

  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "database"
    Function  = "utility"
  }

  depends_on = [
    module.aurora,
    module.vpc,
    module.iam,
    module.lambda_layer,
    module.shared_code_layer
  ]
}

# Database Update Book Lambda
module "db_update_book_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "db-update-book"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 30
  memory_size = 256

  source_path = "${path.module}/../../../src/lambda/db_update_book"

  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  environment_variables = {
    DB_CLUSTER_ENDPOINT    = module.aurora.cluster_endpoint
    DB_NAME                = module.aurora.database_name
    DB_MASTER_USERNAME     = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
    AWS_ACCOUNT_ID         = data.aws_caller_identity.current.account_id
  }

  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "database"
    Function  = "utility"
  }

  depends_on = [
    module.aurora,
    module.vpc,
    module.iam,
    module.lambda_layer,
    module.shared_code_layer
  ]
}

# AI Services Manager Lambda (for managing VPC endpoints)
module "ai_services_manager_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "ai-services-manager"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 60  # 1 minute
  memory_size = 256 # 256MB sufficient

  source_path = "${path.module}/../../../src/lambda/ai_services_manager"

  # Use shared Lambda execution role
  role_arn = module.iam.lambda_execution_role_arn

  environment_variables = {
    VPC_ID       = module.vpc.vpc_id
    PROJECT_NAME = local.project_name
    ENVIRONMENT  = local.environment
    # Note: AWS_REGION is automatically set by Lambda, don't set it manually
  }

  # No VPC needed (manages VPC endpoints, doesn't need to be in VPC)
  vpc_config = null

  tags = {
    Component = "ai-services-manager"
    Function  = "infrastructure"
  }

  depends_on = [
    module.vpc,
    module.iam
  ]
}

# Chat Handler Lambda
module "chat_handler_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "chat-handler"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 300  # 5 minutes (RAG + LLM can take time)
  memory_size = 1024 # 1GB for RAG processing and LLM calls

  source_path = "${path.module}/../../../src/lambda/chat_handler"

  # Use shared Lambda execution role
  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  environment_variables = {
    DB_CLUSTER_ENDPOINT          = module.aurora.cluster_endpoint
    DB_NAME                      = module.aurora.database_name
    DB_MASTER_USERNAME           = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN       = module.aurora.master_password_secret_arn
    DYNAMODB_SESSIONS_TABLE_NAME = module.dynamodb.table_name
    AWS_ACCOUNT_ID               = data.aws_caller_identity.current.account_id
    # Note: AWS_REGION is automatically set by Lambda runtime
  }

  # Needs VPC access for Aurora and Bedrock VPC endpoints
  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "chat"
    Function  = "rag"
  }

  depends_on = [
    module.aurora,
    module.dynamodb,
    module.vpc,
    module.iam,
    module.lambda_layer,
    module.shared_code_layer
  ]
}

# API Gateway
module "api_gateway" {
  source = "../../modules/api-gateway"

  project_name = local.project_name
  environment  = local.environment
  api_name     = "${local.project_name}-${local.environment}-api"

  # Cognito authorizer
  cognito_user_pool_arn = module.cognito.user_pool_arn

  cors_origins = [
    "http://localhost:5173" # Frontend dev server
    # TODO: Add production frontend URL when deploying
    # Note: Cannot use "*" when using Authorization headers - must specify exact origin
  ]
  cors_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
  cors_headers = [
    "Content-Type",
    "Authorization",
    "X-Amz-Date",
    "X-Api-Key",
    "X-Book-Title",
    "X-Book-Author",
    "X-Book-Edition",
    "X-Book-Isbn"
  ]

  binary_media_types = [
    "application/pdf",
    "multipart/form-data",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/gif",
    "image/webp"
  ]

  endpoints = {
    books_list = {
      method               = "GET"
      lambda_function_name = module.books_list_lambda.function_name
      lambda_invoke_arn    = module.books_list_lambda.function_invoke_arn
      path                 = "books"
      require_auth         = true # Require authentication
    }
    book_upload = {
      method               = "POST"
      lambda_function_name = module.book_upload_lambda.function_name
      lambda_invoke_arn    = module.book_upload_lambda.function_invoke_arn
      path                 = "books/upload"
      require_auth         = true # Require authentication for book upload
    }
    book_upload_initial = {
      method               = "POST"
      lambda_function_name = module.book_upload_lambda.function_name
      lambda_invoke_arn    = module.book_upload_lambda.function_invoke_arn
      path                 = "books/upload-initial"
      require_auth         = true # Require authentication for book upload
    }
    ai_services_status = {
      method               = "GET"
      lambda_function_name = module.ai_services_manager_lambda.function_name
      lambda_invoke_arn    = module.ai_services_manager_lambda.function_invoke_arn
      path                 = "ai-services/status"
      require_auth         = true # Require authentication
    }
    ai_services_enable = {
      method               = "POST"
      lambda_function_name = module.ai_services_manager_lambda.function_name
      lambda_invoke_arn    = module.ai_services_manager_lambda.function_invoke_arn
      path                 = "ai-services/enable"
      require_auth         = true # Require authentication
    }
    ai_services_disable = {
      method               = "POST"
      lambda_function_name = module.ai_services_manager_lambda.function_name
      lambda_invoke_arn    = module.ai_services_manager_lambda.function_invoke_arn
      path                 = "ai-services/disable"
      require_auth         = true # Require authentication
    }
    chat_message = {
      method               = "POST"
      lambda_function_name = module.chat_handler_lambda.function_name
      lambda_invoke_arn    = module.chat_handler_lambda.function_invoke_arn
      path                 = "chat"
      require_auth         = true # Require authentication for chat
    }
    course_request = {
      method               = "POST"
      lambda_function_name = module.course_request_handler_lambda.function_name
      lambda_invoke_arn    = module.course_request_handler_lambda.function_invoke_arn
      path                 = "courses"
      require_auth         = true # Require authentication for course generation
    }
    course_get = {
      method               = "GET"
      lambda_function_name = module.course_retriever_lambda.function_name
      lambda_invoke_arn    = module.course_retriever_lambda.function_invoke_arn
      path                 = "course"
      require_auth         = true # Require authentication
    }
    course_status = {
      method               = "GET"
      lambda_function_name = module.course_status_handler_lambda.function_name
      lambda_invoke_arn    = module.course_status_handler_lambda.function_invoke_arn
      path                 = "course-status/{courseId}"
      require_auth         = true # Require authentication
    }
    tunnel_status = {
      method               = "GET"
      lambda_function_name = module.tunnel_status_lambda.function_name
      lambda_invoke_arn    = module.tunnel_status_lambda.function_invoke_arn
      path                 = "tunnel/status"
      require_auth         = false # Stub endpoint, no auth needed
    }
    book_cover = {
      method               = "GET"
      lambda_function_name = module.book_cover_lambda.function_name
      lambda_invoke_arn    = module.book_cover_lambda.function_invoke_arn
      path                 = "books/{bookId}/cover"
      require_auth         = true # Require authentication - frontend fetches via axios with auth headers
    }
    book_pdf = {
      method               = "GET"
      lambda_function_name = module.book_pdf_lambda.function_name
      lambda_invoke_arn    = module.book_pdf_lambda.function_invoke_arn
      path                 = "books/{bookId}/pdf"
      require_auth         = true # Require authentication - frontend fetches via axios with auth headers
    }
    book_analyze = {
      method               = "POST"
      lambda_function_name = module.book_upload_lambda.function_name
      lambda_invoke_arn    = module.book_upload_lambda.function_invoke_arn
      path                 = "books/{bookId}/analyze"
      require_auth         = true # Require authentication for analysis
    }
    book_delete = {
      method               = "DELETE"
      lambda_function_name = module.book_delete_lambda.function_name
      lambda_invoke_arn    = module.book_delete_lambda.function_invoke_arn
      path                 = "books/{bookId}"
      require_auth         = true # Require authentication for deletion
    }
    book_start_ingestion = {
      method               = "POST"
      lambda_function_name = module.book_upload_lambda.function_name
      lambda_invoke_arn    = module.book_upload_lambda.function_invoke_arn
      path                 = "books/{bookId}/start-ingestion"
      require_auth         = true # Require authentication for ingestion start
    }
  }

  tags = {
    ManagedBy = "terraform"
  }

  depends_on = [
    module.books_list_lambda,
    module.book_upload_lambda,
    module.ai_services_manager_lambda,
    module.chat_handler_lambda,
    module.course_request_handler_lambda,
    module.course_retriever_lambda,
    module.course_status_handler_lambda,
    module.tunnel_status_lambda,
    module.book_cover_lambda,
    module.book_pdf_lambda,
    module.book_delete_lambda,
    module.cognito # Ensure Cognito is created before API Gateway
  ]
}

# ============================================================================
# Course Generation Lambda Functions (Event-Driven Architecture)
# ============================================================================

# Course Request Handler - Entry point (API Gateway)
module "course_request_handler_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "course-request-handler"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 300 # 5 minutes
  memory_size = 1024

  source_path = "${path.module}/../../../src/lambda/course_request_handler"

  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  environment_variables = {
    DYNAMODB_COURSE_STATE_TABLE_NAME = module.dynamodb_course_state.table_name
    # EVENT_BUS_NAME removed - using default bus instead
    AWS_ACCOUNT_ID         = data.aws_caller_identity.current.account_id
    DB_CLUSTER_ENDPOINT    = module.aurora.cluster_endpoint
    DB_NAME                = module.aurora.database_name
    DB_MASTER_USERNAME     = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
  }

  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "course"
    Function  = "request-handler"
  }

  depends_on = [
    module.dynamodb_course_state,
    module.eventbridge,
    module.vpc,
    module.iam,
    module.lambda_layer,
    module.shared_code_layer,
    module.aurora
  ]
}

# Course Retriever Lambda - GET course by ID
module "course_retriever_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "course-retriever"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 30 # Quick database query
  memory_size = 256

  source_path = "${path.module}/../../../src/lambda/course_retriever"

  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  environment_variables = {
    DB_CLUSTER_ENDPOINT    = module.aurora.cluster_endpoint
    DB_NAME                = module.aurora.database_name
    DB_MASTER_USERNAME     = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
  }

  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "course"
    Function  = "retriever"
  }

  depends_on = [
    module.aurora,
    module.vpc,
    module.iam,
    module.lambda_layer,
    module.shared_code_layer
  ]
}

# Course Status Handler Lambda - GET course generation status
module "course_status_handler_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "course-status-handler"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 10 # Quick DynamoDB query
  memory_size = 256

  source_path = "${path.module}/../../../src/lambda/course_status_handler"

  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  environment_variables = {
    DYNAMODB_COURSE_STATE_TABLE_NAME = module.dynamodb_course_state.table_name
  }

  tags = {
    Component = "course"
    Function  = "status-handler"
  }

  depends_on = [
    module.dynamodb_course_state,
    module.iam,
    module.lambda_layer,
    module.shared_code_layer
  ]
}

# Course Embedding Handler - Phase 1
module "course_embedding_handler_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "course-embedding-handler"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 60
  memory_size = 512

  source_path = "${path.module}/../../../src/lambda/course_embedding_handler"

  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  environment_variables = {
    DYNAMODB_COURSE_STATE_TABLE_NAME = module.dynamodb_course_state.table_name
    # EVENT_BUS_NAME removed - using default bus instead
    AWS_ACCOUNT_ID         = data.aws_caller_identity.current.account_id
    DB_CLUSTER_ENDPOINT    = module.aurora.cluster_endpoint
    DB_NAME                = module.aurora.database_name
    DB_MASTER_USERNAME     = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
  }

  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "course"
    Function  = "embedding-handler"
  }

  depends_on = [
    module.dynamodb_course_state,
    module.eventbridge,
    module.vpc,
    module.iam,
    module.lambda_layer,
    module.shared_code_layer
  ]
}

# Course Book Search Handler - Phase 2
module "course_book_search_handler_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "course-book-search-handler"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 300 # LLM call can take time
  memory_size = 1024

  source_path = "${path.module}/../../../src/lambda/course_book_search_handler"

  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  environment_variables = {
    DYNAMODB_COURSE_STATE_TABLE_NAME = module.dynamodb_course_state.table_name
    # EVENT_BUS_NAME removed - using default bus instead
    AWS_ACCOUNT_ID         = data.aws_caller_identity.current.account_id
    DB_CLUSTER_ENDPOINT    = module.aurora.cluster_endpoint
    DB_NAME                = module.aurora.database_name
    DB_MASTER_USERNAME     = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
  }

  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "course"
    Function  = "book-search-handler"
  }

  depends_on = [
    module.dynamodb_course_state,
    module.eventbridge,
    module.vpc,
    module.iam,
    module.lambda_layer,
    module.shared_code_layer
  ]
}

# Course Parts Handler - Phase 3
module "course_parts_handler_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "course-parts-handler"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 300 # LLM call can take time
  memory_size = 1024

  source_path = "${path.module}/../../../src/lambda/course_parts_handler"

  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  environment_variables = {
    DYNAMODB_COURSE_STATE_TABLE_NAME = module.dynamodb_course_state.table_name
    # EVENT_BUS_NAME removed - using default bus instead
    AWS_ACCOUNT_ID         = data.aws_caller_identity.current.account_id
    DB_CLUSTER_ENDPOINT    = module.aurora.cluster_endpoint
    DB_NAME                = module.aurora.database_name
    DB_MASTER_USERNAME     = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
  }

  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "course"
    Function  = "parts-handler"
  }

  depends_on = [
    module.dynamodb_course_state,
    module.eventbridge,
    module.vpc,
    module.iam,
    module.lambda_layer,
    module.shared_code_layer
  ]
}

# Course Sections Handler - Phase 4
module "course_sections_handler_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "course-sections-handler"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 300 # LLM call can take time
  memory_size = 1024

  source_path = "${path.module}/../../../src/lambda/course_sections_handler"

  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  environment_variables = {
    DYNAMODB_COURSE_STATE_TABLE_NAME = module.dynamodb_course_state.table_name
    # EVENT_BUS_NAME removed - using default bus instead
    AWS_ACCOUNT_ID         = data.aws_caller_identity.current.account_id
    DB_CLUSTER_ENDPOINT    = module.aurora.cluster_endpoint
    DB_NAME                = module.aurora.database_name
    DB_MASTER_USERNAME     = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
  }

  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "course"
    Function  = "sections-handler"
  }

  depends_on = [
    module.dynamodb_course_state,
    module.eventbridge,
    module.vpc,
    module.iam,
    module.lambda_layer,
    module.shared_code_layer
  ]
}

# Course Outline Reviewer Handler - Phase 5
module "course_outline_reviewer_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "course-outline-reviewer"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 300 # LLM call can take time
  memory_size = 1024

  source_path = "${path.module}/../../../src/lambda/course_outline_reviewer"

  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  environment_variables = {
    DYNAMODB_COURSE_STATE_TABLE_NAME = module.dynamodb_course_state.table_name
    # EVENT_BUS_NAME removed - using default bus instead
    AWS_ACCOUNT_ID         = data.aws_caller_identity.current.account_id
    DB_CLUSTER_ENDPOINT    = module.aurora.cluster_endpoint
    DB_NAME                = module.aurora.database_name
    DB_MASTER_USERNAME     = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
  }

  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "course"
    Function  = "outline-reviewer"
  }

  depends_on = [
    module.dynamodb_course_state,
    module.eventbridge,
    module.vpc,
    module.iam,
    module.lambda_layer,
    module.shared_code_layer
  ]
}

# Course Storage Handler - Phase 6
module "course_storage_handler_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "course-storage-handler"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 120
  memory_size = 512

  source_path = "${path.module}/../../../src/lambda/course_storage_handler"

  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  environment_variables = {
    DYNAMODB_COURSE_STATE_TABLE_NAME = module.dynamodb_course_state.table_name
    DB_CLUSTER_ENDPOINT              = module.aurora.cluster_endpoint
    DB_NAME                          = module.aurora.database_name
    DB_MASTER_USERNAME               = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN           = module.aurora.master_password_secret_arn
    # EVENT_BUS_NAME removed - using default bus instead
    AWS_ACCOUNT_ID = data.aws_caller_identity.current.account_id
    # Note: AWS_REGION is automatically set by Lambda runtime - don't set it manually
  }

  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "course"
    Function  = "storage-handler"
  }

  depends_on = [
    module.dynamodb_course_state,
    module.aurora,
    module.eventbridge,
    module.vpc,
    module.iam,
    module.lambda_layer
  ]
}

# ============================================================================
# Source Summary Generator Lambda
# ============================================================================

module "source_summary_generator_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "source-summary-generator"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 900  # 15 minutes (max for Lambda) - may need multiple chapters
  memory_size = 2048 # 2GB for PDF processing and LLM calls

  source_path = "${path.module}/../../../src/lambda/source_summary_generator"

  # Use shared Lambda execution role
  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  environment_variables = {
    SOURCE_BUCKET          = module.s3.source_docs_bucket_name
    DB_CLUSTER_ENDPOINT    = module.aurora.cluster_endpoint
    DB_NAME                = module.aurora.database_name
    DB_MASTER_USERNAME     = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
    # EVENT_BUS_NAME removed - using default bus instead
    AWS_ACCOUNT_ID = data.aws_caller_identity.current.account_id
  }

  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "ingestion"
    Function  = "source-summary-generator"
  }

  depends_on = [
    module.aurora,
    module.eventbridge,
    module.vpc,
    module.iam,
    module.lambda_layer
  ]
}

# ============================================================================
# Source Summary Embedding Generator Lambda
# ============================================================================

module "source_summary_embedding_generator_lambda" {
  source = "../../modules/lambda"

  project_name  = local.project_name
  environment   = local.environment
  function_name = "source-summary-embedding-generator"

  handler     = "handler.lambda_handler"
  runtime     = "python3.11"
  timeout     = 300 # 5 minutes
  memory_size = 512 # Smaller memory - just embedding generation

  source_path = "${path.module}/../../../src/lambda/source_summary_embedding_generator"

  # Use shared Lambda execution role
  role_arn = module.iam.lambda_execution_role_arn

  # Attach layers: Python dependencies + Shared code
  layers = [
    module.lambda_layer.layer_arn,
    module.shared_code_layer.layer_arn
  ]

  # Don't bundle shared code - use layer instead
  bundle_shared_code = false

  environment_variables = {
    DB_CLUSTER_ENDPOINT    = module.aurora.cluster_endpoint
    DB_NAME                = module.aurora.database_name
    DB_MASTER_USERNAME     = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
    AWS_ACCOUNT_ID         = data.aws_caller_identity.current.account_id
  }

  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  tags = {
    Component = "ingestion"
    Function  = "source-summary-embedding-generator"
  }

  depends_on = [
    module.aurora,
    module.vpc,
    module.iam,
    module.lambda_layer,
    module.shared_code_layer
  ]
}

# ============================================================================
# EventBridge Targets - Connect Rules to Lambda Functions
# ============================================================================

# EmbeddingGenerated → Embedding Handler
resource "aws_cloudwatch_event_target" "embedding_generated" {
  rule = module.eventbridge.embedding_generated_rule_name
  # event_bus_name omitted - using default bus
  target_id = "CourseEmbeddingHandler"
  arn       = module.course_embedding_handler_lambda.function_arn

  depends_on = [
    module.course_embedding_handler_lambda,
    module.eventbridge
  ]
}

# BookSummariesFound → Book Search Handler
resource "aws_cloudwatch_event_target" "book_summaries_found" {
  rule = module.eventbridge.book_summaries_found_rule_name
  # event_bus_name omitted - using default bus
  target_id = "CourseBookSearchHandler"
  arn       = module.course_book_search_handler_lambda.function_arn

  depends_on = [
    module.course_book_search_handler_lambda,
    module.eventbridge
  ]
}

# PartsGenerated → Parts Handler
resource "aws_cloudwatch_event_target" "parts_generated" {
  rule = module.eventbridge.parts_generated_rule_name
  # event_bus_name omitted - using default bus
  target_id = "CoursePartsHandler"
  arn       = module.course_parts_handler_lambda.function_arn

  depends_on = [
    module.course_parts_handler_lambda,
    module.eventbridge
  ]
}

# PartSectionsGenerated → Sections Handler
resource "aws_cloudwatch_event_target" "part_sections_generated" {
  rule = module.eventbridge.part_sections_generated_rule_name
  # event_bus_name omitted - using default bus
  target_id = "CourseSectionsHandler"
  arn       = module.course_sections_handler_lambda.function_arn

  depends_on = [
    module.course_sections_handler_lambda,
    module.eventbridge
  ]
}

# AllPartsComplete → Outline Reviewer Handler
resource "aws_cloudwatch_event_target" "all_parts_complete" {
  rule = module.eventbridge.all_parts_complete_rule_name
  # event_bus_name omitted - using default bus
  target_id = "CourseOutlineReviewer"
  arn       = module.course_outline_reviewer_lambda.function_arn

  depends_on = [
    module.course_outline_reviewer_lambda,
    module.eventbridge
  ]
}

# OutlineReview → Storage Handler
resource "aws_cloudwatch_event_target" "outline_reviewed" {
  rule = module.eventbridge.outline_reviewed_rule_name
  # event_bus_name omitted - using default bus
  target_id = "CourseStorageHandler"
  arn       = module.course_storage_handler_lambda.function_arn

  depends_on = [
    module.course_storage_handler_lambda,
    module.eventbridge
  ]
}

# DocumentProcessed → Source Summary Generator
resource "aws_cloudwatch_event_target" "document_processed" {
  rule = module.eventbridge.document_processed_rule_name
  # event_bus_name omitted - using default bus
  target_id = "SourceSummaryGenerator"
  arn       = module.source_summary_generator_lambda.function_arn

  depends_on = [
    module.source_summary_generator_lambda,
    module.eventbridge
  ]
}

# SourceSummaryStored → Embedding Generator
resource "aws_cloudwatch_event_target" "source_summary_stored" {
  rule = module.eventbridge.source_summary_stored_rule_name
  # event_bus_name omitted - using default bus
  target_id = "SourceSummaryEmbeddingGenerator"
  arn       = module.source_summary_embedding_generator_lambda.function_arn

  depends_on = [
    module.source_summary_embedding_generator_lambda,
    module.eventbridge
  ]
}

# ============================================================================
# IAM Permissions for EventBridge
# ============================================================================

# Allow Lambda functions to publish events to EventBridge
resource "aws_iam_role_policy" "eventbridge_publish" {
  name = "${local.project_name}-${local.environment}-eventbridge-publish"
  role = module.iam.lambda_execution_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "events:PutEvents"
        ]
        Resource = module.eventbridge.event_bus_arn
      }
    ]
  })
}

# Allow EventBridge to invoke Lambda functions
resource "aws_lambda_permission" "eventbridge_invoke_embedding" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = module.course_embedding_handler_lambda.function_name
  principal     = "events.amazonaws.com"
  # Use rule ARN for default bus (rule ARN format: arn:aws:events:region:account-id:rule/rule-name)
  source_arn = "arn:aws:events:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:rule/${module.eventbridge.embedding_generated_rule_name}"
}

resource "aws_lambda_permission" "eventbridge_invoke_book_search" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = module.course_book_search_handler_lambda.function_name
  principal     = "events.amazonaws.com"
  # Use rule ARN for default bus
  source_arn = "arn:aws:events:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:rule/${module.eventbridge.book_summaries_found_rule_name}"
}

resource "aws_lambda_permission" "eventbridge_invoke_parts" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = module.course_parts_handler_lambda.function_name
  principal     = "events.amazonaws.com"
  # Use rule ARN for default bus
  source_arn = "arn:aws:events:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:rule/${module.eventbridge.parts_generated_rule_name}"
}

resource "aws_lambda_permission" "eventbridge_invoke_sections" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = module.course_sections_handler_lambda.function_name
  principal     = "events.amazonaws.com"
  # Use rule ARN for default bus
  source_arn = "arn:aws:events:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:rule/${module.eventbridge.part_sections_generated_rule_name}"
}

resource "aws_lambda_permission" "eventbridge_invoke_outline_reviewer" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = module.course_outline_reviewer_lambda.function_name
  principal     = "events.amazonaws.com"
  # Use rule ARN for default bus
  source_arn = "arn:aws:events:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:rule/${module.eventbridge.all_parts_complete_rule_name}"
}

resource "aws_lambda_permission" "eventbridge_invoke_storage" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = module.course_storage_handler_lambda.function_name
  principal     = "events.amazonaws.com"
  # Use rule ARN for default bus
  source_arn = "arn:aws:events:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:rule/${module.eventbridge.outline_reviewed_rule_name}"
}

resource "aws_lambda_permission" "eventbridge_invoke_source_summary_generator" {
  statement_id  = "AllowExecutionFromEventBridge-DocumentProcessed"
  action        = "lambda:InvokeFunction"
  function_name = module.source_summary_generator_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = "${module.eventbridge.event_bus_arn}/*/${module.eventbridge.document_processed_rule_name}"
}

resource "aws_lambda_permission" "eventbridge_invoke_source_summary_embedding_generator" {
  statement_id  = "AllowExecutionFromEventBridge-SourceSummaryStored"
  action        = "lambda:InvokeFunction"
  function_name = module.source_summary_embedding_generator_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = "${module.eventbridge.event_bus_arn}/*/${module.eventbridge.source_summary_stored_rule_name}"
}

# Outputs will be defined in outputs.tf

