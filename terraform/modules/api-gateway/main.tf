# API Gateway REST API

resource "aws_api_gateway_rest_api" "this" {
  name        = var.api_name != null ? var.api_name : "${var.project_name}-${var.environment}-api"
  description = "DocProf API Gateway"

  binary_media_types = var.binary_media_types

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-api"
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  )
}

# API Gateway Deployment
resource "aws_api_gateway_deployment" "this" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  stage_name  = var.environment

  depends_on = [
    aws_api_gateway_method.this,
    aws_api_gateway_integration.this,
    aws_api_gateway_method_response.this,
    aws_api_gateway_integration_response.this,
  ]

  lifecycle {
    create_before_destroy = true
  }
}

# API Gateway Stage
resource "aws_api_gateway_stage" "this" {
  deployment_id = aws_api_gateway_deployment.this.id
  rest_api_id  = aws_api_gateway_rest_api.this.id
  stage_name   = var.environment
  
  lifecycle {
    ignore_changes = [deployment_id]
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      caller         = "$context.identity.caller"
      user           = "$context.identity.user"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      resourcePath   = "$context.resourcePath"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
    })
  }

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-api-stage"
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  )
}

# CloudWatch Log Group for API Gateway
resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${var.project_name}-${var.environment}-api"
  retention_in_days = 7  # Dev: 7 days, Prod: 30 days

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-api-logs"
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  )
}

# API Gateway Account Settings (for CloudWatch Logs)
resource "aws_api_gateway_account" "this" {
  cloudwatch_role_arn = aws_iam_role.api_gateway_cloudwatch.arn
}

# IAM Role for API Gateway CloudWatch Logs
resource "aws_iam_role" "api_gateway_cloudwatch" {
  name = "${var.project_name}-${var.environment}-api-gateway-cloudwatch-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "apigateway.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-api-gateway-cloudwatch-role"
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  )
}

resource "aws_iam_role_policy_attachment" "api_gateway_cloudwatch" {
  role       = aws_iam_role.api_gateway_cloudwatch.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
}

# CORS Configuration
resource "aws_api_gateway_gateway_response" "cors" {
  rest_api_id   = aws_api_gateway_rest_api.this.id
  response_type = "DEFAULT_4XX"

  response_templates = {
    "application/json" = jsonencode({
      message = "$context.error.messageString"
    })
  }

  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'${join(",", var.cors_origins)}'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'${join(",", var.cors_headers)}'"
    "gatewayresponse.header.Access-Control-Allow-Methods" = "'${join(",", var.cors_methods)}'"
  }
}

# Create resources and methods for each endpoint
# Handle nested paths dynamically (e.g., "ai-services/status" -> create "ai-services" resource, then "status" resource)
locals {
  # Build resource map: key -> list of path parts
  endpoint_paths = {
    for k, v in var.endpoints : k => split("/", trimprefix(v.path, "/"))
  }
  
  # Extract all unique parent path segments
  # For "ai-services/status" -> ["ai-services"]
  # For "books/upload" -> ["books"]
  parent_segments = toset([
    for k, v in local.endpoint_paths :
      v[0] if length(v) > 1
  ])
  
  # Map of parent segment -> endpoint keys that use it
  parent_to_endpoints = {
    for parent in local.parent_segments :
    parent => [
      for k, v in local.endpoint_paths :
      k if length(v) > 1 && v[0] == parent
    ]
  }
}

# Create parent resources dynamically (e.g., "ai-services", "books")
resource "aws_api_gateway_resource" "parent" {
  for_each = local.parent_segments

  rest_api_id = aws_api_gateway_rest_api.this.id
  parent_id   = aws_api_gateway_rest_api.this.root_resource_id
  path_part   = each.value
}

# Create final resource for each endpoint
resource "aws_api_gateway_resource" "this" {
  for_each = var.endpoints

  rest_api_id = aws_api_gateway_rest_api.this.id
  # If path has multiple parts, use parent resource; otherwise use root
  parent_id = length(local.endpoint_paths[each.key]) > 1 ? aws_api_gateway_resource.parent[local.endpoint_paths[each.key][0]].id : aws_api_gateway_rest_api.this.root_resource_id
  path_part   = local.endpoint_paths[each.key][length(local.endpoint_paths[each.key]) - 1]
}

# API Gateway Method
resource "aws_api_gateway_method" "this" {
  for_each = var.endpoints

  rest_api_id   = aws_api_gateway_rest_api.this.id
  resource_id   = aws_api_gateway_resource.this[each.key].id
  http_method   = each.value.method
  authorization = "NONE"  # Can be updated to use Cognito later

  request_parameters = {
    "method.request.header.Content-Type" = false
  }
}

# API Gateway Integration
resource "aws_api_gateway_integration" "this" {
  for_each = var.endpoints

  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.this[each.key].id
  http_method = aws_api_gateway_method.this[each.key].http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = each.value.lambda_invoke_arn

  content_handling = contains(var.binary_media_types, "application/pdf") ? "CONVERT_TO_BINARY" : null
}

# Lambda Permission for API Gateway
resource "aws_lambda_permission" "api_gateway" {
  for_each = var.endpoints

  statement_id  = "AllowExecutionFromAPIGateway-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = each.value.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.this.execution_arn}/*/*"
}

# Method Response
resource "aws_api_gateway_method_response" "this" {
  for_each = var.endpoints

  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.this[each.key].id
  http_method = aws_api_gateway_method.this[each.key].http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = true
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
  }

  response_models = {
    "application/json" = "Empty"
  }
}

# Integration Response
resource "aws_api_gateway_integration_response" "this" {
  for_each = var.endpoints

  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.this[each.key].id
  http_method = aws_api_gateway_method.this[each.key].http_method
  status_code = aws_api_gateway_method_response.this[each.key].status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = "'${join(",", var.cors_origins)}'"
    "method.response.header.Access-Control-Allow-Headers" = "'${join(",", var.cors_headers)}'"
    "method.response.header.Access-Control-Allow-Methods" = "'${join(",", var.cors_methods)}'"
  }

  depends_on = [aws_api_gateway_integration.this]
}

# OPTIONS method for CORS preflight
resource "aws_api_gateway_method" "options" {
  for_each = var.endpoints

  rest_api_id   = aws_api_gateway_rest_api.this.id
  resource_id   = aws_api_gateway_resource.this[each.key].id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options" {
  for_each = var.endpoints

  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.this[each.key].id
  http_method = aws_api_gateway_method.options[each.key].http_method

  type = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options" {
  for_each = var.endpoints

  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.this[each.key].id
  http_method = aws_api_gateway_method.options[each.key].http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = true
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods"  = true
  }
}

resource "aws_api_gateway_integration_response" "options" {
  for_each = var.endpoints

  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.this[each.key].id
  http_method = aws_api_gateway_method.options[each.key].http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = "'${join(",", var.cors_origins)}'"
    "method.response.header.Access-Control-Allow-Headers" = "'${join(",", var.cors_headers)}'"
    "method.response.header.Access-Control-Allow-Methods"  = "'${join(",", var.cors_methods)}'"
  }

  depends_on = [aws_api_gateway_integration.options]
}

