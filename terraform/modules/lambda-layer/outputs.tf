output "layer_arn" {
  description = "ARN of the Lambda layer"
  value       = aws_lambda_layer_version.python_deps.arn
}

output "layer_version" {
  description = "Version of the Lambda layer"
  value       = aws_lambda_layer_version.python_deps.version
}

