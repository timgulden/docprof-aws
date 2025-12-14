output "layer_arn" {
  description = "ARN of the Lambda layer for shared code"
  value       = aws_lambda_layer_version.shared_code.arn
}

output "layer_version" {
  description = "Version number of the Lambda layer"
  value       = aws_lambda_layer_version.shared_code.version
}

output "layer_name" {
  description = "Name of the Lambda layer"
  value       = aws_lambda_layer_version.shared_code.layer_name
}

