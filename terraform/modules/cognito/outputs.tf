output "user_pool_id" {
  description = "Cognito User Pool ID"
  value       = aws_cognito_user_pool.this.id
}

output "user_pool_arn" {
  description = "Cognito User Pool ARN"
  value       = aws_cognito_user_pool.this.arn
}

output "user_pool_client_id" {
  description = "Cognito User Pool Client ID (for frontend)"
  value       = aws_cognito_user_pool_client.frontend.id
  sensitive   = false
}

output "user_pool_domain" {
  description = "Cognito User Pool Domain (for hosted UI)"
  value       = aws_cognito_user_pool_domain.this.domain
}

output "cognito_domain" {
  description = "Full Cognito domain URL"
  value       = "https://${aws_cognito_user_pool_domain.this.domain}.auth.${data.aws_region.current.name}.amazoncognito.com"
}

# Data source for current region (needed for domain URL)
data "aws_region" "current" {}

