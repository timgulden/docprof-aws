output "function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.this.function_name
}

output "function_arn" {
  description = "Lambda function ARN"
  value       = aws_lambda_function.this.arn
}

output "function_invoke_arn" {
  description = "Lambda function invoke ARN"
  value       = aws_lambda_function.this.invoke_arn
}

output "role_arn" {
  description = "Lambda execution role ARN"
  value       = var.role_arn != null ? var.role_arn : (length(aws_iam_role.lambda_execution) > 0 ? aws_iam_role.lambda_execution[0].arn : null)
}

output "role_name" {
  description = "Lambda execution role name"
  value       = var.role_arn != null ? split("/", var.role_arn)[1] : (length(aws_iam_role.lambda_execution) > 0 ? aws_iam_role.lambda_execution[0].name : null)
}

