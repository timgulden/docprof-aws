output "api_id" {
  description = "API Gateway REST API ID"
  value       = aws_api_gateway_rest_api.this.id
}

output "api_arn" {
  description = "API Gateway REST API ARN"
  value       = aws_api_gateway_rest_api.this.arn
}

output "api_execution_arn" {
  description = "API Gateway execution ARN"
  value       = aws_api_gateway_rest_api.this.execution_arn
}

output "api_url" {
  description = "API Gateway base URL"
  value       = "https://${aws_api_gateway_rest_api.this.id}.execute-api.${data.aws_region.current.name}.amazonaws.com/${var.environment}"
}

output "stage_name" {
  description = "API Gateway stage name"
  value       = aws_api_gateway_stage.this.stage_name
}

# Data source for current region
data "aws_region" "current" {}

