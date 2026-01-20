# Lambda Function

resource "aws_lambda_function" "this" {
  function_name = "${var.project_name}-${var.environment}-${var.function_name}"
  handler       = var.handler
  runtime       = var.runtime
  timeout       = var.timeout
  memory_size   = var.memory_size

  # Source code
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  # Environment variables
  environment {
    variables = var.environment_variables
  }

  # VPC configuration (if provided)
  dynamic "vpc_config" {
    for_each = var.vpc_config != null ? [1] : []
    content {
      subnet_ids         = var.vpc_config.subnet_ids
      security_group_ids = var.vpc_config.security_group_ids
    }
  }

  # Layers
  layers = var.layers

  # Reserved concurrent executions
  reserved_concurrent_executions = var.reserved_concurrent_executions

  # IAM role (use provided role or create new one)
  role = var.role_arn != null ? var.role_arn : aws_iam_role.lambda_execution[0].arn

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-${var.function_name}"
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  )
}

# Create ZIP archive that includes function code and optionally shared modules
locals {
  # Get the lambda root directory (parent of function directory)
  lambda_root  = dirname(var.source_path)
  function_dir = basename(var.source_path)
  shared_path  = "${local.lambda_root}/shared"

  staging_dir = "${path.module}/.terraform/${var.function_name}-staging"
  zip_path    = "${path.module}/.terraform/${var.function_name}.zip"

  # Get all files to include
  function_files = fileset(var.source_path, "**")

  # Only bundle shared code if bundle_shared_code is true
  # When using shared code layer, set bundle_shared_code = false
  # Get shared files only if we need to bundle them
  shared_files = (!var.bundle_shared_code || !fileexists("${local.shared_path}/__init__.py")) ? [] : fileset(local.shared_path, "**")

  # Build maps of relative path -> file content
  # Function files go to ZIP root (not in subdirectory) so handler can be "handler.lambda_handler"
  function_content = {
    for f in local.function_files :
    f => file("${var.source_path}/${f}")
  }

  # Only include shared content if we're bundling it
  shared_content = (!var.bundle_shared_code || length(local.shared_files) == 0) ? {} : {
    for f in local.shared_files :
    "shared/${f}" => file("${local.shared_path}/${f}")
  }

  all_content = merge(local.function_content, local.shared_content)
}

# Create staging directory files using local_file resources
# This creates the directory structure that archive_file can then zip
resource "local_file" "lambda_staging" {
  for_each = local.all_content

  filename = "${local.staging_dir}/${each.key}"
  content  = each.value

  # Ensure directory exists
  directory_permission = "0755"
  file_permission      = "0644"
}

# Create ZIP using archive_file with source_dir
# This avoids shell execution and works entirely within Terraform
data "archive_file" "lambda_zip" {
  type        = "zip"
  output_path = local.zip_path
  source_dir  = local.staging_dir

  depends_on = [local_file.lambda_staging]
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${aws_lambda_function.this.function_name}"
  retention_in_days = 7 # Dev: 7 days, Prod: 30 days

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-${var.function_name}-logs"
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  )
}

# IAM Role for Lambda (only create if role_arn not provided)
resource "aws_iam_role" "lambda_execution" {
  count = var.role_arn == null ? 1 : 0

  name = "${var.project_name}-${var.environment}-${var.function_name}-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-${var.function_name}-execution"
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  )
}

# Attach base Lambda execution policy (only if creating role)
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  count      = var.role_arn == null ? 1 : 0
  role       = aws_iam_role.lambda_execution[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Attach VPC execution policy if VPC configured (only if creating role)
resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  count      = var.role_arn == null && var.vpc_config != null ? 1 : 0
  role       = aws_iam_role.lambda_execution[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

