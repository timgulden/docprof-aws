output "table_name" {
  description = "Name of the DynamoDB course state table"
  value       = aws_dynamodb_table.course_state.name
}

output "table_arn" {
  description = "ARN of the DynamoDB course state table"
  value       = aws_dynamodb_table.course_state.arn
}

output "table_id" {
  description = "ID of the DynamoDB course state table"
  value       = aws_dynamodb_table.course_state.id
}
