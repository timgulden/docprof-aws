# Outputs for DocProf development environment

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "public_subnet_ids" {
  description = "List of public subnet IDs"
  value       = module.vpc.public_subnet_ids
}

output "private_subnet_ids" {
  description = "List of private subnet IDs"
  value       = module.vpc.private_subnet_ids
}

output "lambda_security_group_id" {
  description = "Lambda security group ID"
  value       = module.vpc.lambda_security_group_id
}

output "aurora_security_group_id" {
  description = "Aurora security group ID"
  value       = module.vpc.aurora_security_group_id
}

output "ai_endpoints_enabled" {
  description = "Whether AI endpoints are currently enabled"
  value       = module.vpc.ai_endpoints_enabled
}

output "bedrock_endpoint_id" {
  description = "Bedrock endpoint ID (null if disabled)"
  value       = module.vpc.bedrock_endpoint_id
}

output "polly_endpoint_id" {
  description = "Polly endpoint ID (null if disabled)"
  value       = module.vpc.polly_endpoint_id
}

output "lambda_execution_role_arn" {
  description = "ARN of Lambda execution role"
  value       = module.iam.lambda_execution_role_arn
}

output "lambda_execution_role_name" {
  description = "Name of Lambda execution role"
  value       = module.iam.lambda_execution_role_name
}

output "rds_monitoring_role_arn" {
  description = "ARN of RDS monitoring role"
  value       = module.iam.rds_monitoring_role_arn
}

output "aurora_cluster_id" {
  description = "Aurora cluster identifier"
  value       = module.aurora.cluster_id
}

output "aurora_cluster_endpoint" {
  description = "Aurora cluster writer endpoint"
  value       = module.aurora.cluster_endpoint
  sensitive   = false
}

output "aurora_master_password_secret_arn" {
  description = "ARN of Secrets Manager secret containing master password"
  value       = module.aurora.master_password_secret_arn
}

output "source_docs_bucket_name" {
  description = "Name of source documents S3 bucket"
  value       = module.s3.source_docs_bucket_name
}

output "processed_chunks_bucket_name" {
  description = "Name of processed chunks S3 bucket"
  value       = module.s3.processed_chunks_bucket_name
}

output "frontend_bucket_name" {
  description = "Name of frontend S3 bucket"
  value       = module.s3.frontend_bucket_name
}

# TODO: Add more outputs as modules are added:
# output "api_gateway_url" {
#   description = "API Gateway endpoint URL"
#   value       = module.api_gateway.api_url
# }
#
# output "cloudfront_url" {
#   description = "CloudFront distribution URL"
#   value       = module.frontend.cloudfront_url
# }

