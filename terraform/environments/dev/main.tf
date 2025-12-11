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

  project_name       = local.project_name
  environment        = local.environment
  aws_region         = local.aws_region
  private_subnet_ids = module.vpc.private_subnet_ids
  security_group_id  = module.vpc.aurora_security_group_id
  monitoring_role_arn = module.iam.rds_monitoring_role_arn

  min_capacity             = 0      # Enable auto-pause (pauses after 60 min idle)
  max_capacity             = 2.0
  seconds_until_auto_pause = 3600   # 60 minutes (1 hour) - smoother UX, still saves costs

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

  project_name     = local.project_name
  environment      = local.environment
  requirements_path = "${path.module}/../../modules/lambda-layer/requirements.txt"
  s3_bucket        = module.s3.processed_chunks_bucket_name  # Use processed_chunks bucket for layer storage

  tags = {
    ManagedBy = "terraform"
  }
}

# Document Processor Lambda
module "document_processor_lambda" {
  source = "../../modules/lambda"

  project_name = local.project_name
  environment  = local.environment
  function_name = "document-processor"
  
  handler = "handler.lambda_handler"
  runtime = "python3.11"
  timeout = 900  # 15 minutes (max for Lambda)
  memory_size = 3008  # 3GB for large PDF processing (38MB PDF + processing overhead)
  
  source_path = "${path.module}/../../../src/lambda/document_processor"
  
  # Use shared Lambda execution role
  role_arn = module.iam.lambda_execution_role_arn
  
  # Attach Python dependencies layer
  layers = [module.lambda_layer.layer_arn]
  
  environment_variables = {
    SOURCE_BUCKET        = module.s3.source_docs_bucket_name
    PROCESSED_BUCKET     = module.s3.processed_chunks_bucket_name
    DB_CLUSTER_ENDPOINT  = module.aurora.cluster_endpoint
    DB_NAME              = module.aurora.database_name
    DB_MASTER_USERNAME   = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
    AWS_ACCOUNT_ID       = data.aws_caller_identity.current.account_id
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
    module.iam
  ]
}

# S3 EventBridge Notification for Document Processor
# Using EventBridge instead of direct S3->Lambda because Lambda is in VPC
# S3 can't validate VPC Lambdas directly, but EventBridge can handle them
resource "aws_s3_bucket_notification" "document_processor_trigger" {
  bucket = module.s3.source_docs_bucket_name

  eventbridge = true  # Enable EventBridge notifications
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

  project_name = local.project_name
  environment  = local.environment
  function_name = "book-upload"
  
  handler = "handler.lambda_handler"
  runtime = "python3.11"
  timeout = 60  # 1 minute (enough for upload)
  memory_size = 256  # 256MB sufficient for upload handling
  
  source_path = "${path.module}/../../../src/lambda/book_upload"
  
  # Use shared Lambda execution role
  role_arn = module.iam.lambda_execution_role_arn
  
  # Attach Python dependencies layer
  layers = [module.lambda_layer.layer_arn]
  
  environment_variables = {
    SOURCE_BUCKET        = module.s3.source_docs_bucket_name
    DB_CLUSTER_ENDPOINT  = module.aurora.cluster_endpoint
    DB_NAME              = module.aurora.database_name
    DB_MASTER_USERNAME   = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
    # Note: AWS_REGION is automatically set by Lambda runtime
  }
  
  # No VPC needed for book upload (only needs S3 access)
  vpc_config = null
  
  tags = {
    Component = "book-upload"
    Function  = "ingestion"
  }
  
  depends_on = [
    module.s3,
    module.aurora,
    module.iam
  ]
}

# Schema Initialization Lambda (for creating database schema)
module "schema_init_lambda" {
  source = "../../modules/lambda"

  project_name = local.project_name
  environment  = local.environment
  function_name = "schema-init"
  
  handler = "handler.lambda_handler"
  runtime = "python3.11"
  timeout = 60  # 1 minute (enough for schema creation)
  memory_size = 256  # 256MB sufficient
  
  source_path = "${path.module}/../../../src/lambda/schema_init"
  
  # Use shared Lambda execution role
  role_arn = module.iam.lambda_execution_role_arn
  
  # Attach Python dependencies layer
  layers = [module.lambda_layer.layer_arn]
  
  environment_variables = {
    DB_CLUSTER_ENDPOINT  = module.aurora.cluster_endpoint
    DB_NAME              = module.aurora.database_name
    DB_MASTER_USERNAME   = module.aurora.master_username
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
    module.lambda_layer # Ensure layer is built before Lambda
  ]
}

# Connection Test Lambda (for testing infrastructure connectivity)
module "connection_test_lambda" {
  source = "../../modules/lambda"

  project_name = local.project_name
  environment  = local.environment
  function_name = "connection-test"
  
  handler = "handler.lambda_handler"
  runtime = "python3.11"
  timeout = 60  # 1 minute (enough for tests)
  memory_size = 256  # 256MB sufficient for testing
  
  source_path = "${path.module}/../../../src/lambda/connection_test"
  
  # Use shared Lambda execution role
  role_arn = module.iam.lambda_execution_role_arn
  
  # Attach Python dependencies layer
  layers = [module.lambda_layer.layer_arn]
  
  environment_variables = {
    DB_CLUSTER_ENDPOINT  = module.aurora.cluster_endpoint
    DB_NAME              = module.aurora.database_name
    DB_MASTER_USERNAME   = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
    AWS_ACCOUNT_ID       = data.aws_caller_identity.current.account_id
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
    module.lambda_layer # Ensure layer is built before Lambda
  ]
}

# Database Content Check Lambda
module "db_check_lambda" {
  source = "../../modules/lambda"

  project_name = local.project_name
  environment  = local.environment
  function_name = "db-check"
  
  handler = "handler.lambda_handler"
  runtime = "python3.11"
  timeout = 60
  memory_size = 256
  
  source_path = "${path.module}/../../../src/lambda/db_check"
  
  role_arn = module.iam.lambda_execution_role_arn
  layers = [module.lambda_layer.layer_arn]
  
  environment_variables = {
    DB_CLUSTER_ENDPOINT  = module.aurora.cluster_endpoint
    DB_NAME              = module.aurora.database_name
    DB_MASTER_USERNAME   = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
    AWS_ACCOUNT_ID       = data.aws_caller_identity.current.account_id
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
    module.lambda_layer
  ]
}

# Database Book ID Check Lambda
module "db_check_book_ids_lambda" {
  source = "../../modules/lambda"

  project_name = local.project_name
  environment  = local.environment
  function_name = "db-check-book-ids"
  
  handler = "handler.lambda_handler"
  runtime = "python3.11"
  timeout = 30
  memory_size = 256
  
  source_path = "${path.module}/../../../src/lambda/db_check_book_ids"
  
  role_arn = module.iam.lambda_execution_role_arn
  layers = [module.lambda_layer.layer_arn]
  
  environment_variables = {
    DB_CLUSTER_ENDPOINT  = module.aurora.cluster_endpoint
    DB_NAME              = module.aurora.database_name
    DB_MASTER_USERNAME   = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
    AWS_ACCOUNT_ID       = data.aws_caller_identity.current.account_id
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
    module.lambda_layer
  ]
}

# Database Merge Books Lambda
module "db_merge_books_lambda" {
  source = "../../modules/lambda"

  project_name = local.project_name
  environment  = local.environment
  function_name = "db-merge-books"
  
  handler = "handler.lambda_handler"
  runtime = "python3.11"
  timeout = 60
  memory_size = 256
  
  source_path = "${path.module}/../../../src/lambda/db_merge_books"
  
  role_arn = module.iam.lambda_execution_role_arn
  layers = [module.lambda_layer.layer_arn]
  
  environment_variables = {
    DB_CLUSTER_ENDPOINT  = module.aurora.cluster_endpoint
    DB_NAME              = module.aurora.database_name
    DB_MASTER_USERNAME   = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
    AWS_ACCOUNT_ID       = data.aws_caller_identity.current.account_id
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
    module.lambda_layer
  ]
}

# Database Check Duplicates Lambda
module "db_check_duplicates_lambda" {
  source = "../../modules/lambda"

  project_name = local.project_name
  environment  = local.environment
  function_name = "db-check-duplicates"
  
  handler = "handler.lambda_handler"
  runtime = "python3.11"
  timeout = 60
  memory_size = 512
  
  source_path = "${path.module}/../../../src/lambda/db_check_duplicates"
  
  role_arn = module.iam.lambda_execution_role_arn
  layers = [module.lambda_layer.layer_arn]
  
  environment_variables = {
    DB_CLUSTER_ENDPOINT  = module.aurora.cluster_endpoint
    DB_NAME              = module.aurora.database_name
    DB_MASTER_USERNAME   = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
    AWS_ACCOUNT_ID       = data.aws_caller_identity.current.account_id
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
    module.lambda_layer
  ]
}

# Database Cleanup Lambda
module "db_cleanup_lambda" {
  source = "../../modules/lambda"

  project_name = local.project_name
  environment  = local.environment
  function_name = "db-cleanup"
  
  handler = "handler.lambda_handler"
  runtime = "python3.11"
  timeout = 60
  memory_size = 256
  
  source_path = "${path.module}/../../../src/lambda/db_cleanup"
  
  role_arn = module.iam.lambda_execution_role_arn
  layers = [module.lambda_layer.layer_arn]
  
  environment_variables = {
    DB_CLUSTER_ENDPOINT  = module.aurora.cluster_endpoint
    DB_NAME              = module.aurora.database_name
    DB_MASTER_USERNAME   = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
    AWS_ACCOUNT_ID       = data.aws_caller_identity.current.account_id
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
    module.lambda_layer
  ]
}

# Database Deduplicate Chunks Lambda
module "db_deduplicate_chunks_lambda" {
  source = "../../modules/lambda"

  project_name = local.project_name
  environment  = local.environment
  function_name = "db-deduplicate-chunks"
  
  handler = "handler.lambda_handler"
  runtime = "python3.11"
  timeout = 120
  memory_size = 512
  
  source_path = "${path.module}/../../../src/lambda/db_deduplicate_chunks"
  
  role_arn = module.iam.lambda_execution_role_arn
  layers = [module.lambda_layer.layer_arn]
  
  environment_variables = {
    DB_CLUSTER_ENDPOINT  = module.aurora.cluster_endpoint
    DB_NAME              = module.aurora.database_name
    DB_MASTER_USERNAME   = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
    AWS_ACCOUNT_ID       = data.aws_caller_identity.current.account_id
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
    module.lambda_layer
  ]
}

# Database Update Book Lambda
module "db_update_book_lambda" {
  source = "../../modules/lambda"

  project_name = local.project_name
  environment  = local.environment
  function_name = "db-update-book"
  
  handler = "handler.lambda_handler"
  runtime = "python3.11"
  timeout = 30
  memory_size = 256
  
  source_path = "${path.module}/../../../src/lambda/db_update_book"
  
  role_arn = module.iam.lambda_execution_role_arn
  layers = [module.lambda_layer.layer_arn]
  
  environment_variables = {
    DB_CLUSTER_ENDPOINT  = module.aurora.cluster_endpoint
    DB_NAME              = module.aurora.database_name
    DB_MASTER_USERNAME   = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN = module.aurora.master_password_secret_arn
    AWS_ACCOUNT_ID       = data.aws_caller_identity.current.account_id
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
    module.lambda_layer
  ]
}

# AI Services Manager Lambda (for managing VPC endpoints)
module "ai_services_manager_lambda" {
  source = "../../modules/lambda"

  project_name = local.project_name
  environment  = local.environment
  function_name = "ai-services-manager"
  
  handler = "handler.lambda_handler"
  runtime = "python3.11"
  timeout = 60  # 1 minute
  memory_size = 256  # 256MB sufficient
  
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

  project_name = local.project_name
  environment  = local.environment
  function_name = "chat-handler"
  
  handler = "handler.lambda_handler"
  runtime = "python3.11"
  timeout = 300  # 5 minutes (RAG + LLM can take time)
  memory_size = 1024  # 1GB for RAG processing and LLM calls
  
  source_path = "${path.module}/../../../src/lambda/chat_handler"
  
  # Use shared Lambda execution role
  role_arn = module.iam.lambda_execution_role_arn
  
  # Attach Python dependencies layer
  layers = [module.lambda_layer.layer_arn]
  
  environment_variables = {
    DB_CLUSTER_ENDPOINT     = module.aurora.cluster_endpoint
    DB_NAME                 = module.aurora.database_name
    DB_MASTER_USERNAME      = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN  = module.aurora.master_password_secret_arn
    DYNAMODB_SESSIONS_TABLE_NAME = module.dynamodb.table_name
    AWS_ACCOUNT_ID          = data.aws_caller_identity.current.account_id
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
    module.lambda_layer
  ]
}

# API Gateway
module "api_gateway" {
  source = "../../modules/api-gateway"

  project_name = local.project_name
  environment  = local.environment
  api_name     = "${local.project_name}-${local.environment}-api"

  cors_origins = ["*"]  # TODO: Restrict to frontend domain in prod
  cors_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
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
    "multipart/form-data"
  ]

  endpoints = {
    book_upload = {
      method              = "POST"
      lambda_function_name = module.book_upload_lambda.function_name
      lambda_invoke_arn   = module.book_upload_lambda.function_invoke_arn
      path                = "books/upload"
      require_auth        = false  # TODO: Add Cognito auth in prod
    }
    ai_services_status = {
      method              = "GET"
      lambda_function_name = module.ai_services_manager_lambda.function_name
      lambda_invoke_arn   = module.ai_services_manager_lambda.function_invoke_arn
      path                = "ai-services/status"
      require_auth        = false  # TODO: Add Cognito auth in prod
    }
    ai_services_enable = {
      method              = "POST"
      lambda_function_name = module.ai_services_manager_lambda.function_name
      lambda_invoke_arn   = module.ai_services_manager_lambda.function_invoke_arn
      path                = "ai-services/enable"
      require_auth        = false  # TODO: Add Cognito auth in prod
    }
    ai_services_disable = {
      method              = "POST"
      lambda_function_name = module.ai_services_manager_lambda.function_name
      lambda_invoke_arn   = module.ai_services_manager_lambda.function_invoke_arn
      path                = "ai-services/disable"
      require_auth        = false  # TODO: Add Cognito auth in prod
    }
    chat_message = {
      method              = "POST"
      lambda_function_name = module.chat_handler_lambda.function_name
      lambda_invoke_arn   = module.chat_handler_lambda.function_invoke_arn
      path                = "chat"
      require_auth        = false  # TODO: Add Cognito auth in prod
    }
    course_request = {
      method              = "POST"
      lambda_function_name = module.course_request_handler_lambda.function_name
      lambda_invoke_arn   = module.course_request_handler_lambda.function_invoke_arn
      path                = "courses"
      require_auth        = false  # TODO: Add Cognito auth in prod
    }
  }

  tags = {
    ManagedBy = "terraform"
  }

  depends_on = [
    module.book_upload_lambda,
    module.ai_services_manager_lambda,
    module.chat_handler_lambda,
    module.course_request_handler_lambda
  ]
}

# ============================================================================
# Course Generation Lambda Functions (Event-Driven Architecture)
# ============================================================================

# Course Request Handler - Entry point (API Gateway)
module "course_request_handler_lambda" {
  source = "../../modules/lambda"

  project_name = local.project_name
  environment  = local.environment
  function_name = "course-request-handler"

  handler = "handler.lambda_handler"
  runtime = "python3.11"
  timeout = 300  # 5 minutes
  memory_size = 1024

  source_path = "${path.module}/../../../src/lambda/course_request_handler"

  role_arn = module.iam.lambda_execution_role_arn
  layers = [module.lambda_layer.layer_arn]

  environment_variables = {
    DYNAMODB_COURSE_STATE_TABLE_NAME = module.dynamodb_course_state.table_name
    EVENT_BUS_NAME                   = module.eventbridge.event_bus_name
    AWS_ACCOUNT_ID                   = data.aws_caller_identity.current.account_id
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
    module.lambda_layer
  ]
}

# Course Embedding Handler - Phase 1
module "course_embedding_handler_lambda" {
  source = "../../modules/lambda"

  project_name = local.project_name
  environment  = local.environment
  function_name = "course-embedding-handler"

  handler = "handler.lambda_handler"
  runtime = "python3.11"
  timeout = 60
  memory_size = 512

  source_path = "${path.module}/../../../src/lambda/course_embedding_handler"

  role_arn = module.iam.lambda_execution_role_arn
  layers = [module.lambda_layer.layer_arn]

  environment_variables = {
    DYNAMODB_COURSE_STATE_TABLE_NAME = module.dynamodb_course_state.table_name
    EVENT_BUS_NAME                   = module.eventbridge.event_bus_name
    AWS_ACCOUNT_ID                   = data.aws_caller_identity.current.account_id
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
    module.lambda_layer
  ]
}

# Course Book Search Handler - Phase 2
module "course_book_search_handler_lambda" {
  source = "../../modules/lambda"

  project_name = local.project_name
  environment  = local.environment
  function_name = "course-book-search-handler"

  handler = "handler.lambda_handler"
  runtime = "python3.11"
  timeout = 300  # LLM call can take time
  memory_size = 1024

  source_path = "${path.module}/../../../src/lambda/course_book_search_handler"

  role_arn = module.iam.lambda_execution_role_arn
  layers = [module.lambda_layer.layer_arn]

  environment_variables = {
    DYNAMODB_COURSE_STATE_TABLE_NAME = module.dynamodb_course_state.table_name
    EVENT_BUS_NAME                   = module.eventbridge.event_bus_name
    AWS_ACCOUNT_ID                   = data.aws_caller_identity.current.account_id
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
    module.lambda_layer
  ]
}

# Course Parts Handler - Phase 3
module "course_parts_handler_lambda" {
  source = "../../modules/lambda"

  project_name = local.project_name
  environment  = local.environment
  function_name = "course-parts-handler"

  handler = "handler.lambda_handler"
  runtime = "python3.11"
  timeout = 300  # LLM call can take time
  memory_size = 1024

  source_path = "${path.module}/../../../src/lambda/course_parts_handler"

  role_arn = module.iam.lambda_execution_role_arn
  layers = [module.lambda_layer.layer_arn]

  environment_variables = {
    DYNAMODB_COURSE_STATE_TABLE_NAME = module.dynamodb_course_state.table_name
    EVENT_BUS_NAME                   = module.eventbridge.event_bus_name
    AWS_ACCOUNT_ID                   = data.aws_caller_identity.current.account_id
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
    module.lambda_layer
  ]
}

# Course Sections Handler - Phase 4
module "course_sections_handler_lambda" {
  source = "../../modules/lambda"

  project_name = local.project_name
  environment  = local.environment
  function_name = "course-sections-handler"

  handler = "handler.lambda_handler"
  runtime = "python3.11"
  timeout = 300  # LLM call can take time
  memory_size = 1024

  source_path = "${path.module}/../../../src/lambda/course_sections_handler"

  role_arn = module.iam.lambda_execution_role_arn
  layers = [module.lambda_layer.layer_arn]

  environment_variables = {
    DYNAMODB_COURSE_STATE_TABLE_NAME = module.dynamodb_course_state.table_name
    EVENT_BUS_NAME                   = module.eventbridge.event_bus_name
    AWS_ACCOUNT_ID                   = data.aws_caller_identity.current.account_id
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
    module.lambda_layer
  ]
}

# Course Outline Reviewer Handler - Phase 5
module "course_outline_reviewer_lambda" {
  source = "../../modules/lambda"

  project_name = local.project_name
  environment  = local.environment
  function_name = "course-outline-reviewer"

  handler = "handler.lambda_handler"
  runtime = "python3.11"
  timeout = 300  # LLM call can take time
  memory_size = 1024

  source_path = "${path.module}/../../../src/lambda/course_outline_reviewer"

  role_arn = module.iam.lambda_execution_role_arn
  layers = [module.lambda_layer.layer_arn]

  environment_variables = {
    DYNAMODB_COURSE_STATE_TABLE_NAME = module.dynamodb_course_state.table_name
    EVENT_BUS_NAME                   = module.eventbridge.event_bus_name
    AWS_ACCOUNT_ID                   = data.aws_caller_identity.current.account_id
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
    module.lambda_layer
  ]
}

# Course Storage Handler - Phase 6
module "course_storage_handler_lambda" {
  source = "../../modules/lambda"

  project_name = local.project_name
  environment  = local.environment
  function_name = "course-storage-handler"

  handler = "handler.lambda_handler"
  runtime = "python3.11"
  timeout = 120
  memory_size = 512

  source_path = "${path.module}/../../../src/lambda/course_storage_handler"

  role_arn = module.iam.lambda_execution_role_arn
  layers = [module.lambda_layer.layer_arn]

  environment_variables = {
    DYNAMODB_COURSE_STATE_TABLE_NAME = module.dynamodb_course_state.table_name
    DB_CLUSTER_ENDPOINT               = module.aurora.cluster_endpoint
    DB_NAME                           = module.aurora.database_name
    DB_MASTER_USERNAME                = module.aurora.master_username
    DB_PASSWORD_SECRET_ARN            = module.aurora.master_password_secret_arn
    EVENT_BUS_NAME                   = module.eventbridge.event_bus_name
    AWS_ACCOUNT_ID                   = data.aws_caller_identity.current.account_id
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
# EventBridge Targets - Connect Rules to Lambda Functions
# ============================================================================

# EmbeddingGenerated → Embedding Handler
resource "aws_cloudwatch_event_target" "embedding_generated" {
  rule           = module.eventbridge.embedding_generated_rule_name
  event_bus_name = module.eventbridge.event_bus_name
  target_id      = "CourseEmbeddingHandler"
  arn            = module.course_embedding_handler_lambda.function_arn

  depends_on = [
    module.course_embedding_handler_lambda,
    module.eventbridge
  ]
}

# BookSummariesFound → Book Search Handler
resource "aws_cloudwatch_event_target" "book_summaries_found" {
  rule           = module.eventbridge.book_summaries_found_rule_name
  event_bus_name = module.eventbridge.event_bus_name
  target_id      = "CourseBookSearchHandler"
  arn            = module.course_book_search_handler_lambda.function_arn

  depends_on = [
    module.course_book_search_handler_lambda,
    module.eventbridge
  ]
}

# PartsGenerated → Parts Handler
resource "aws_cloudwatch_event_target" "parts_generated" {
  rule           = module.eventbridge.parts_generated_rule_name
  event_bus_name = module.eventbridge.event_bus_name
  target_id      = "CoursePartsHandler"
  arn            = module.course_parts_handler_lambda.function_arn

  depends_on = [
    module.course_parts_handler_lambda,
    module.eventbridge
  ]
}

# PartSectionsGenerated → Sections Handler
resource "aws_cloudwatch_event_target" "part_sections_generated" {
  rule           = module.eventbridge.part_sections_generated_rule_name
  event_bus_name = module.eventbridge.event_bus_name
  target_id      = "CourseSectionsHandler"
  arn            = module.course_sections_handler_lambda.function_arn

  depends_on = [
    module.course_sections_handler_lambda,
    module.eventbridge
  ]
}

# AllPartsComplete → Outline Reviewer Handler
resource "aws_cloudwatch_event_target" "all_parts_complete" {
  rule           = module.eventbridge.all_parts_complete_rule_name
  event_bus_name = module.eventbridge.event_bus_name
  target_id      = "CourseOutlineReviewer"
  arn            = module.course_outline_reviewer_lambda.function_arn

  depends_on = [
    module.course_outline_reviewer_lambda,
    module.eventbridge
  ]
}

# OutlineReview → Storage Handler
resource "aws_cloudwatch_event_target" "outline_reviewed" {
  rule           = module.eventbridge.outline_reviewed_rule_name
  event_bus_name = module.eventbridge.event_bus_name
  target_id      = "CourseStorageHandler"
  arn            = module.course_storage_handler_lambda.function_arn

  depends_on = [
    module.course_storage_handler_lambda,
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
  source_arn    = "${module.eventbridge.event_bus_arn}/*"
}

resource "aws_lambda_permission" "eventbridge_invoke_book_search" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = module.course_book_search_handler_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = "${module.eventbridge.event_bus_arn}/*"
}

resource "aws_lambda_permission" "eventbridge_invoke_parts" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = module.course_parts_handler_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = "${module.eventbridge.event_bus_arn}/*"
}

resource "aws_lambda_permission" "eventbridge_invoke_sections" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = module.course_sections_handler_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = "${module.eventbridge.event_bus_arn}/*"
}

resource "aws_lambda_permission" "eventbridge_invoke_outline_reviewer" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = module.course_outline_reviewer_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = "${module.eventbridge.event_bus_arn}/*"
}

resource "aws_lambda_permission" "eventbridge_invoke_storage" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = module.course_storage_handler_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = "${module.eventbridge.event_bus_arn}/*"
}

# Outputs will be defined in outputs.tf

