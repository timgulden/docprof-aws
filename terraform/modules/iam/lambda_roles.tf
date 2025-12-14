# IAM Role for Lambda Functions
# This role allows Lambda functions to access AWS services needed by DocProf

resource "aws_iam_role" "lambda_execution" {
  name = "${var.project_name}-${var.environment}-lambda-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-lambda-execution-role"
    }
  )
}

# Policy for CloudWatch Logs (write logs)
resource "aws_iam_role_policy" "lambda_cloudwatch_logs" {
  name = "${var.project_name}-${var.environment}-lambda-cloudwatch-logs"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${var.account_id}:log-group:/aws/lambda/${var.project_name}-${var.environment}-*"
      }
    ]
  })
}

# Policy for VPC access (Lambda needs to be in VPC to access Aurora and VPC endpoints)
resource "aws_iam_role_policy" "lambda_vpc" {
  name = "${var.project_name}-${var.environment}-lambda-vpc"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface",
          "ec2:AssignPrivateIpAddresses",
          "ec2:UnassignPrivateIpAddresses"
        ]
        Resource = "*"
      }
    ]
  })
}

# Policy for Aurora/RDS access (via RDS Proxy with IAM authentication)
resource "aws_iam_role_policy" "lambda_rds" {
  name = "${var.project_name}-${var.environment}-lambda-rds"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "rds-db:connect"
        ]
        Resource = "arn:aws:rds-db:${var.aws_region}:${var.account_id}:dbuser:*/docprof_lambda_user"
      }
    ]
  })
}

# Policy for S3 access (read/write on DocProf buckets)
resource "aws_iam_role_policy" "lambda_s3" {
  name = "${var.project_name}-${var.environment}-lambda-s3"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:PutObjectAcl"  # Needed for pre-signed POST URLs
        ]
        Resource = [
          "arn:aws:s3:::${var.project_name}-${var.environment}-*",
          "arn:aws:s3:::${var.project_name}-${var.environment}-*/*"
        ]
      }
    ]
  })
}

# Policy for Secrets Manager access (get database password)
resource "aws_iam_role_policy" "lambda_secretsmanager" {
  name = "${var.project_name}-${var.environment}-lambda-secretsmanager"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          "arn:aws:secretsmanager:${var.aws_region}:${var.account_id}:secret:${var.project_name}-${var.environment}-*"
        ]
      }
    ]
  })
}

# Policy for Bedrock access (invoke models)
resource "aws_iam_role_policy" "lambda_bedrock" {
  name = "${var.project_name}-${var.environment}-lambda-bedrock"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          # Inference profiles (required for on-demand Claude models)
          # Claude Sonnet 4.5 (best balance, for classification and other tasks)
          "arn:aws:bedrock:us-east-1:${var.account_id}:inference-profile/us.anthropic.claude-sonnet-4-5-20250929-v1:0",
          "arn:aws:bedrock:us-east-2:${var.account_id}:inference-profile/us.anthropic.claude-sonnet-4-5-20250929-v1:0",
          "arn:aws:bedrock:us-west-2:${var.account_id}:inference-profile/us.anthropic.claude-sonnet-4-5-20250929-v1:0",
          # Foundation models (direct access) - inference profiles route to these
          "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-sonnet-4-5-20250929-v1:0",
          "arn:aws:bedrock:us-east-2::foundation-model/anthropic.claude-sonnet-4-5-20250929-v1:0",
          "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-sonnet-4-5-20250929-v1:0",
          # Embeddings
          "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-embed-text-v1",
          "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-embed-text-v2:0"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "aws-marketplace:ViewSubscriptions",
          "aws-marketplace:Subscribe"
        ]
        Resource = "*"
      }
    ]
  })
}

# Policy for Marketplace access (required for Claude Sonnet 4.5 via Marketplace)
resource "aws_iam_role_policy" "lambda_marketplace" {
  name = "${var.project_name}-${var.environment}-lambda-marketplace"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "aws-marketplace:ViewSubscriptions",
          "aws-marketplace:Subscribe"
        ]
        Resource = [
          # Inference profiles (required for on-demand Claude models)
          # Claude Opus 4.5 (highest quality, for figure descriptions)
          "arn:aws:bedrock:us-east-1:${var.account_id}:inference-profile/us.anthropic.claude-opus-4-5-20251101-v1:0",
          "arn:aws:bedrock:us-east-2:${var.account_id}:inference-profile/us.anthropic.claude-opus-4-5-20251101-v1:0",
          "arn:aws:bedrock:us-west-2:${var.account_id}:inference-profile/us.anthropic.claude-opus-4-5-20251101-v1:0",
          # Claude Sonnet 4.5 (best balance, for classification and other tasks)
          "arn:aws:bedrock:us-east-1:${var.account_id}:inference-profile/us.anthropic.claude-sonnet-4-5-20250929-v1:0",
          "arn:aws:bedrock:us-east-2:${var.account_id}:inference-profile/us.anthropic.claude-sonnet-4-5-20250929-v1:0",
          "arn:aws:bedrock:us-west-2:${var.account_id}:inference-profile/us.anthropic.claude-sonnet-4-5-20250929-v1:0",
          # Claude Sonnet 4 (backup)
          "arn:aws:bedrock:us-east-1:${var.account_id}:inference-profile/us.anthropic.claude-sonnet-4-20250514-v1:0",
          "arn:aws:bedrock:us-west-2:${var.account_id}:inference-profile/us.anthropic.claude-sonnet-4-20250514-v1:0",
          # Claude 3.7 Sonnet (backup)
          "arn:aws:bedrock:us-east-1:${var.account_id}:inference-profile/us.anthropic.claude-3-7-sonnet-20250219-v1:0",
          "arn:aws:bedrock:us-west-2:${var.account_id}:inference-profile/us.anthropic.claude-3-7-sonnet-20250219-v1:0",
          # Claude 3.5 Sonnet (backup)
          "arn:aws:bedrock:us-east-1:${var.account_id}:inference-profile/us.anthropic.claude-3-5-sonnet-20240620-v1:0",
          "arn:aws:bedrock:us-west-2:${var.account_id}:inference-profile/us.anthropic.claude-3-5-sonnet-20240620-v1:0",
          # Foundation models (direct access) - inference profiles route to these
          # Claude Opus 4.5 (highest quality, for figure descriptions)
          "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-opus-4-5-20251101-v1:0",
          "arn:aws:bedrock:us-east-2::foundation-model/anthropic.claude-opus-4-5-20251101-v1:0",
          "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-opus-4-5-20251101-v1:0",
          # Claude Sonnet 4.5 (best balance, for classification)
          "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-sonnet-4-5-20250929-v1:0",
          "arn:aws:bedrock:us-east-2::foundation-model/anthropic.claude-sonnet-4-5-20250929-v1:0",
          "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-sonnet-4-5-20250929-v1:0",
          # Claude Sonnet 4
          "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-sonnet-4-20250514-v1:0",
          "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-sonnet-4-20250514-v1:0",
          # Claude 3.7 Sonnet
          "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-7-sonnet-20250219-v1:0",
          "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-3-7-sonnet-20250219-v1:0",
          # Claude 3.5 Sonnet
          "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-20240620-v1:0",
          "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-3-5-sonnet-20240620-v1:0",
          "arn:aws:bedrock:${var.aws_region}::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0",
          "arn:aws:bedrock:${var.aws_region}::foundation-model/anthropic.claude-3-5-sonnet-*",
          # Claude 3 Sonnet (backup)
          "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0",
          "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0",
          # Embeddings
          "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-embed-text-v1",
          "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-embed-text-v2:0"
        ]
      }
    ]
  })
}

# Policy for Polly access (synthesize speech)
resource "aws_iam_role_policy" "lambda_polly" {
  name = "${var.project_name}-${var.environment}-lambda-polly"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "polly:SynthesizeSpeech"
        ]
        Resource = "*"
      }
    ]
  })
}

# Policy for DynamoDB access (session management)
resource "aws_iam_role_policy" "lambda_dynamodb" {
  name = "${var.project_name}-${var.environment}-lambda-dynamodb"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          "arn:aws:dynamodb:${var.aws_region}:${var.account_id}:table/${var.project_name}-${var.environment}-sessions",
          "arn:aws:dynamodb:${var.aws_region}:${var.account_id}:table/${var.project_name}-${var.environment}-sessions/*",
          "arn:aws:dynamodb:${var.aws_region}:${var.account_id}:table/${var.project_name}-${var.environment}-course-state",
          "arn:aws:dynamodb:${var.aws_region}:${var.account_id}:table/${var.project_name}-${var.environment}-course-state/*"
        ]
      }
    ]
  })
}

# Policy for EventBridge access (publish course generation events)
# Supports both custom bus and default bus (for migration to default bus)
resource "aws_iam_role_policy" "lambda_eventbridge" {
  name = "${var.project_name}-${var.environment}-lambda-eventbridge"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "events:PutEvents"
        ]
        Resource = [
          # Custom event bus (legacy, may be removed after migration)
          "arn:aws:events:${var.aws_region}:${var.account_id}:event-bus/${var.project_name}-${var.environment}-course-events",
          # Default event bus (current)
          "arn:aws:events:${var.aws_region}:${var.account_id}:event-bus/default"
        ]
      }
    ]
  })
}

# Policy for VPC endpoint management (AI services manager)
resource "aws_iam_role_policy" "lambda_vpc_endpoints" {
  name = "${var.project_name}-${var.environment}-lambda-vpc-endpoints"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateVpcEndpoint",
          "ec2:DeleteVpcEndpoints",
          "ec2:DescribeVpcEndpoints",
          "ec2:DescribeVpcs",
          "ec2:DescribeSubnets",
          "ec2:DescribeSecurityGroups",
          "ec2:CreateTags",
          "ec2:DeleteTags"
        ]
        Resource = "*"
      }
    ]
  })
}


