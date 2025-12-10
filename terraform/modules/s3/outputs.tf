# S3 Module Outputs

output "source_docs_bucket_name" {
  description = "Name of the source documents bucket"
  value       = aws_s3_bucket.source_docs.id
}

output "source_docs_bucket_arn" {
  description = "ARN of the source documents bucket"
  value       = aws_s3_bucket.source_docs.arn
}

output "processed_chunks_bucket_name" {
  description = "Name of the processed chunks bucket"
  value       = aws_s3_bucket.processed_chunks.id
}

output "processed_chunks_bucket_arn" {
  description = "ARN of the processed chunks bucket"
  value       = aws_s3_bucket.processed_chunks.arn
}

output "frontend_bucket_name" {
  description = "Name of the frontend bucket"
  value       = aws_s3_bucket.frontend.id
}

output "frontend_bucket_arn" {
  description = "ARN of the frontend bucket"
  value       = aws_s3_bucket.frontend.arn
}

output "frontend_website_endpoint" {
  description = "Website endpoint for the frontend bucket"
  value       = aws_s3_bucket_website_configuration.frontend.website_endpoint
}

