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

output "document_processor_function_name" {
  description = "Document processor Lambda function name"
  value       = module.document_processor_lambda.function_name
}

output "document_processor_function_arn" {
  description = "Document processor Lambda function ARN"
  value       = module.document_processor_lambda.function_arn
}

output "book_upload_function_name" {
  description = "Book upload Lambda function name"
  value       = module.book_upload_lambda.function_name
}

output "book_upload_function_arn" {
  description = "Book upload Lambda function ARN"
  value       = module.book_upload_lambda.function_arn
}

output "api_gateway_url" {
  description = "API Gateway base URL"
  value       = module.api_gateway.api_url
}

output "api_gateway_id" {
  description = "API Gateway ID"
  value       = module.api_gateway.api_id
}

output "book_upload_endpoint" {
  description = "Book upload endpoint URL"
  value       = "${module.api_gateway.api_url}/books/upload"
}

output "ai_services_status_endpoint" {
  description = "AI services status endpoint URL"
  value       = "${module.api_gateway.api_url}/ai-services/status"
}

output "ai_services_enable_endpoint" {
  description = "AI services enable endpoint URL"
  value       = "${module.api_gateway.api_url}/ai-services/enable"
}

output "ai_services_disable_endpoint" {
  description = "AI services disable endpoint URL"
  value       = "${module.api_gateway.api_url}/ai-services/disable"
}

output "dynamodb_sessions_table_name" {
  description = "DynamoDB sessions table name"
  value       = module.dynamodb.table_name
}

output "dynamodb_sessions_table_arn" {
  description = "DynamoDB sessions table ARN"
  value       = module.dynamodb.table_arn
}

output "dynamodb_course_state_table_name" {
  description = "DynamoDB course state table name"
  value       = module.dynamodb_course_state.table_name
}

output "eventbridge_bus_name" {
  description = "EventBridge custom bus name for course events"
  value       = module.eventbridge.event_bus_name
}

output "eventbridge_bus_arn" {
  description = "EventBridge custom bus ARN"
  value       = module.eventbridge.event_bus_arn
}

output "chat_handler_function_name" {
  description = "Chat handler Lambda function name"
  value       = module.chat_handler_lambda.function_name
}

output "chat_handler_function_arn" {
  description = "Chat handler Lambda function ARN"
  value       = module.chat_handler_lambda.function_arn
}

output "chat_endpoint" {
  description = "Chat endpoint URL"
  value       = "${module.api_gateway.api_url}/chat"
}

output "course_request_endpoint" {
  description = "Course request endpoint URL"
  value       = "${module.api_gateway.api_url}/courses"
}

output "course_request_handler_function_name" {
  description = "Course request handler Lambda function name"
  value       = module.course_request_handler_lambda.function_name
}

# TODO: Add more outputs as modules are added:
# output "cloudfront_url" {
#   description = "CloudFront distribution URL"
#   value       = module.frontend.cloudfront_url
# }

