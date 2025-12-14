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
    aws_api_gateway_method.options,
    aws_api_gateway_integration.options,
    aws_api_gateway_method_response.options,
    aws_api_gateway_integration_response.options,
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
resource "aws_api_gateway_gateway_response" "cors_4xx" {
  rest_api_id   = aws_api_gateway_rest_api.this.id
  response_type = "DEFAULT_4XX"

  response_templates = {
    "application/json" = jsonencode({
      message = "$context.error.messageString"
    })
  }

  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = length(var.cors_origins) > 0 && var.cors_origins[0] == "*" ? "'*'" : "'${var.cors_origins[0]}'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'${join(",", var.cors_headers)}'"
    "gatewayresponse.header.Access-Control-Allow-Methods" = "'${join(",", var.cors_methods)}'"
  }
}

resource "aws_api_gateway_gateway_response" "cors_5xx" {
  rest_api_id   = aws_api_gateway_rest_api.this.id
  response_type = "DEFAULT_5XX"

  response_templates = {
    "application/json" = jsonencode({
      message = "$context.error.messageString"
    })
  }

  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = length(var.cors_origins) > 0 && var.cors_origins[0] == "*" ? "'*'" : "'${var.cors_origins[0]}'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'${join(",", var.cors_headers)}'"
    "gatewayresponse.header.Access-Control-Allow-Methods" = "'${join(",", var.cors_methods)}'"
  }
}

resource "aws_api_gateway_gateway_response" "cors_401" {
  rest_api_id   = aws_api_gateway_rest_api.this.id
  response_type = "UNAUTHORIZED"

  response_templates = {
    "application/json" = jsonencode({
      message = "$context.error.messageString"
    })
  }

  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = length(var.cors_origins) > 0 && var.cors_origins[0] == "*" ? "'*'" : "'${var.cors_origins[0]}'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'${join(",", var.cors_headers)}'"
    "gatewayresponse.header.Access-Control-Allow-Methods" = "'${join(",", var.cors_methods)}'"
  }
}

resource "aws_api_gateway_gateway_response" "cors_403" {
  rest_api_id   = aws_api_gateway_rest_api.this.id
  response_type = "ACCESS_DENIED"

  response_templates = {
    "application/json" = jsonencode({
      message = "$context.error.messageString"
    })
  }

  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = length(var.cors_origins) > 0 && var.cors_origins[0] == "*" ? "'*'" : "'${var.cors_origins[0]}'"
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
# Special handling: if path is single segment and matches a parent, use that parent directly
locals {
  # Endpoints that should use existing parent resources (single segment matching a parent)
  endpoints_using_parent = {
    for k, v in var.endpoints :
    k => contains(local.parent_segments, local.endpoint_paths[k][0])
    if length(local.endpoint_paths[k]) == 1
  }
  
  # Endpoints that need new resources created
  endpoints_needing_resources = {
    for k, v in var.endpoints :
    k => v
    if length(local.endpoint_paths[k]) > 1 || !contains(local.parent_segments, local.endpoint_paths[k][0])
  }
}

# Create intermediate resources for paths with 3+ segments (e.g., "books/{bookId}/cover")
# This creates resources for all intermediate path segments
locals {
  # Find all intermediate path segments that need to be created
  # For "books/{bookId}/cover" -> need to create "{bookId}" under "books"
  # Use path string (not resource ID) for deduplication to avoid dependency issues
  intermediate_resources_raw = {
    for k, v in local.endpoints_needing_resources :
    "${k}-intermediate" => {
      endpoint_key = k
      parent_segment = local.endpoint_paths[k][0]  # e.g., "books"
      path_part    = local.endpoint_paths[k][1]    # e.g., "{bookId}"
      key          = "${local.endpoint_paths[k][0]}:${local.endpoint_paths[k][1]}"  # Use string, not resource ID
    }
    if length(local.endpoint_paths[k]) > 2  # Only for paths with 3+ segments
  }
  
  # Deduplicate intermediate resources by parent_segment:path_part (using strings, not IDs)
  # If multiple endpoints need the same intermediate resource, we only create it once
  intermediate_resources = {
    for key in toset([for k, v in local.intermediate_resources_raw : v.key]) :
    key => [for k, v in local.intermediate_resources_raw : v if v.key == key][0]
  }
}

# Create intermediate resources (e.g., "{bookId}" in "books/{bookId}/cover")
resource "aws_api_gateway_resource" "intermediate" {
  for_each = local.intermediate_resources

  rest_api_id = aws_api_gateway_rest_api.this.id
  parent_id   = aws_api_gateway_resource.parent[each.value.parent_segment].id
  path_part   = each.value.path_part
}

# Map endpoint keys to their intermediate resource IDs (for paths with 3+ segments)
locals {
  endpoint_to_intermediate = {
    for k, v in local.intermediate_resources_raw :
    v.endpoint_key => aws_api_gateway_resource.intermediate[v.key].id
  }
  
  # Map intermediate resources by their path_part and parent (to detect duplicates)
  # This allows endpoints with 2 segments to reuse intermediate resources created for 3+ segment paths
  # Use string key (parent_segment:path_part) instead of resource ID
  intermediate_by_path = {
    for k, v in local.intermediate_resources :
    k => aws_api_gateway_resource.intermediate[k].id
  }
  
  # Also create a lookup by parent resource ID for endpoints that need to check
  intermediate_by_parent_id = {
    for k, v in local.intermediate_resources :
    "${aws_api_gateway_resource.parent[v.parent_segment].id}:${v.path_part}" => aws_api_gateway_resource.intermediate[k].id
  }
  
  # Compute parent_id for each endpoint
  endpoint_parent_ids = {
    for k in keys(local.endpoints_needing_resources) :
    k => length(local.endpoint_paths[k]) > 2
      ? (contains(keys(local.endpoint_to_intermediate), k) ? local.endpoint_to_intermediate[k] : aws_api_gateway_resource.parent[local.endpoint_paths[k][0]].id)
      : (length(local.endpoint_paths[k]) > 1
        ? (
          # Check if an intermediate resource already exists for this path segment
          # For "books/{bookId}", check if "{bookId}" intermediate resource exists under "books"
          # Use string-based lookup first, then fall back to parent resource ID lookup
          length(local.endpoint_paths[k]) >= 2 && contains(keys(local.intermediate_by_path), "${local.endpoint_paths[k][0]}:${local.endpoint_paths[k][1]}")
          ? local.intermediate_by_parent_id["${aws_api_gateway_resource.parent[local.endpoint_paths[k][0]].id}:${local.endpoint_paths[k][1]}"]
          : aws_api_gateway_resource.parent[local.endpoint_paths[k][0]].id
        )
        : aws_api_gateway_rest_api.this.root_resource_id)
  }
}

# Only create resources for endpoints that don't already have an intermediate resource
# Endpoints with 2 segments that match an existing intermediate resource will use that resource directly
# Use string-based check (parent_segment:path_part) instead of resource ID to avoid dependency issues
locals {
  intermediate_path_keys = toset([for k, v in local.intermediate_resources : k])
  
  endpoints_needing_new_resources = {
    for k, v in local.endpoints_needing_resources :
    k => v
    if length(local.endpoint_paths[k]) != 2 || !(length(local.endpoint_paths[k]) >= 2 && try(contains(local.intermediate_path_keys, "${local.endpoint_paths[k][0]}:${local.endpoint_paths[k][1]}"), false))
  }
}

resource "aws_api_gateway_resource" "this" {
  for_each = local.endpoints_needing_new_resources

  rest_api_id = aws_api_gateway_rest_api.this.id
  parent_id   = local.endpoint_parent_ids[each.key]
  path_part   = local.endpoint_paths[each.key][length(local.endpoint_paths[each.key]) - 1]
}

# Local value to get resource ID (either new resource, intermediate resource, or existing parent)
locals {
  endpoint_resource_ids = merge(
    {
      for k, v in aws_api_gateway_resource.this : k => v.id
    },
    {
      # Endpoints that reuse existing intermediate resources (2-segment paths that match 3+ segment intermediate)
      for k in keys(local.endpoints_needing_resources) :
      k => local.endpoint_parent_ids[k]
      if length(local.endpoint_paths[k]) == 2 && try(contains(local.intermediate_path_keys, "${local.endpoint_paths[k][0]}:${local.endpoint_paths[k][1]}"), false)
    },
    {
      for k in keys(local.endpoints_using_parent) :
      k => aws_api_gateway_resource.parent[local.endpoint_paths[k][0]].id
      if contains(local.parent_segments, local.endpoint_paths[k][0])
    }
  )
}

# Cognito Authorizer (if Cognito is configured)
# Use for_each with a conditional map to avoid count issues
resource "aws_api_gateway_authorizer" "cognito" {
  for_each = var.cognito_user_pool_arn != null ? { enabled = true } : {}

  name                   = "${var.project_name}-${var.environment}-cognito-authorizer"
  rest_api_id            = aws_api_gateway_rest_api.this.id
  type                   = "COGNITO_USER_POOLS"
  provider_arns          = [var.cognito_user_pool_arn]
  authorizer_credentials = null
}

# API Gateway Method
resource "aws_api_gateway_method" "this" {
  for_each = var.endpoints

  rest_api_id   = aws_api_gateway_rest_api.this.id
  resource_id   = local.endpoint_resource_ids[each.key]
  http_method   = each.value.method
  authorization = each.value.require_auth && var.cognito_user_pool_arn != null ? "COGNITO_USER_POOLS" : "NONE"
  authorizer_id = each.value.require_auth && var.cognito_user_pool_arn != null ? aws_api_gateway_authorizer.cognito["enabled"].id : null
  api_key_required = false  # Explicitly disable API key requirement

  request_parameters = {
    "method.request.header.Content-Type" = false
  }

  # Force recreation if configuration changes to avoid orphaned methods
  lifecycle {
    replace_triggered_by = [
      aws_api_gateway_rest_api.this
    ]
  }
}

# API Gateway Integration
resource "aws_api_gateway_integration" "this" {
  for_each = var.endpoints

  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = local.endpoint_resource_ids[each.key]
  http_method = aws_api_gateway_method.this[each.key].http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = each.value.lambda_invoke_arn

  # For AWS_PROXY integration, content_handling is not used - API Gateway handles base64 decoding automatically
  # based on isBase64Encoded flag and binary_media_types configuration
  content_handling = null

  # Force recreation if configuration changes
  lifecycle {
    replace_triggered_by = [
      aws_api_gateway_method.this[each.key]
    ]
  }
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
  resource_id = local.endpoint_resource_ids[each.key]
  http_method = aws_api_gateway_method.this[each.key].http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = true
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Credentials" = true
    "method.response.header.Content-Type" = true  # Allow Content-Type to be passed through
  }

  # With AWS_PROXY, response_models are ignored - Lambda response is passed through directly
  # But we still need to define it for API Gateway validation
  # Empty model allows any content type (Lambda sets the actual Content-Type)
  response_models = {}
}

# Integration Response
resource "aws_api_gateway_integration_response" "this" {
  for_each = var.endpoints

  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = local.endpoint_resource_ids[each.key]
  http_method = aws_api_gateway_method.this[each.key].http_method
  status_code = aws_api_gateway_method_response.this[each.key].status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = length(var.cors_origins) > 0 && var.cors_origins[0] == "*" ? "'*'" : "'${var.cors_origins[0]}'"
    "method.response.header.Access-Control-Allow-Headers" = "'${join(",", var.cors_headers)}'"
    "method.response.header.Access-Control-Allow-Methods" = "'${join(",", var.cors_methods)}'"
    "method.response.header.Access-Control-Allow-Credentials" = "'true'"
    # Pass through Content-Type from Lambda response (AWS_PROXY passes through headers directly)
    "method.response.header.Content-Type" = "integration.response.header.Content-Type"
  }

  depends_on = [aws_api_gateway_integration.this]
}

# OPTIONS method for CORS preflight
resource "aws_api_gateway_method" "options" {
  for_each = var.endpoints

  rest_api_id   = aws_api_gateway_rest_api.this.id
  resource_id   = local.endpoint_resource_ids[each.key]
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options" {
  for_each = var.endpoints

  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = local.endpoint_resource_ids[each.key]
  http_method = aws_api_gateway_method.options[each.key].http_method

  type = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options" {
  for_each = var.endpoints

  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = local.endpoint_resource_ids[each.key]
  http_method = aws_api_gateway_method.options[each.key].http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = true
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods"  = true
    "method.response.header.Access-Control-Allow-Credentials" = true
  }
}

resource "aws_api_gateway_integration_response" "options" {
  for_each = var.endpoints

  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = local.endpoint_resource_ids[each.key]
  http_method = aws_api_gateway_method.options[each.key].http_method
  status_code = "200"

  # Use the first origin (or * if present) - API Gateway doesn't support multiple origins dynamically
  # For production, consider using a Lambda integration to return the request origin dynamically
  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = length(var.cors_origins) > 0 && var.cors_origins[0] == "*" ? "'*'" : "'${var.cors_origins[0]}'"
    "method.response.header.Access-Control-Allow-Headers" = "'${join(",", var.cors_headers)}'"
    "method.response.header.Access-Control-Allow-Methods"  = "'${join(",", var.cors_methods)}'"
    "method.response.header.Access-Control-Allow-Credentials" = "'true'"
  }

  depends_on = [aws_api_gateway_integration.options]
}

