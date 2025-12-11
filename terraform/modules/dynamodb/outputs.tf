output "table_name" {
  description = "Name of the DynamoDB sessions table"
  value       = aws_dynamodb_table.sessions.name
}

output "table_arn" {
  description = "ARN of the DynamoDB sessions table"
  value       = aws_dynamodb_table.sessions.arn
}

output "table_id" {
  description = "ID of the DynamoDB sessions table"
  value       = aws_dynamodb_table.sessions.id
}
