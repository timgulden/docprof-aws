output "event_bus_name" {
  description = "Name of the EventBridge custom bus"
  value       = aws_cloudwatch_event_bus.course_events.name
}

output "event_bus_arn" {
  description = "ARN of the EventBridge custom bus"
  value       = aws_cloudwatch_event_bus.course_events.arn
}

output "embedding_generated_rule_name" {
  description = "Name of the EmbeddingGenerated event rule"
  value       = aws_cloudwatch_event_rule.embedding_generated.name
}

output "book_summaries_found_rule_name" {
  description = "Name of the BookSummariesFound event rule"
  value       = aws_cloudwatch_event_rule.book_summaries_found.name
}

output "parts_generated_rule_name" {
  description = "Name of the PartsGenerated event rule"
  value       = aws_cloudwatch_event_rule.parts_generated.name
}

output "part_sections_generated_rule_name" {
  description = "Name of the PartSectionsGenerated event rule"
  value       = aws_cloudwatch_event_rule.part_sections_generated.name
}

output "all_parts_complete_rule_name" {
  description = "Name of the AllPartsComplete event rule"
  value       = aws_cloudwatch_event_rule.all_parts_complete.name
}

output "outline_reviewed_rule_name" {
  description = "Name of the OutlineReview event rule"
  value       = aws_cloudwatch_event_rule.outline_reviewed.name
}

output "document_processed_rule_name" {
  description = "Name of the document processed event rule"
  value       = aws_cloudwatch_event_rule.document_processed.name
}

output "source_summary_stored_rule_name" {
  description = "Name of the source summary stored event rule"
  value       = aws_cloudwatch_event_rule.source_summary_stored.name
}

output "chapter_summary_requested_rule_name" {
  description = "Name of the chapter_summary_requested event rule"
  value       = aws_cloudwatch_event_rule.chapter_summary_requested.name
}

output "all_chapters_completed_rule_name" {
  description = "Name of the all_chapters_completed event rule"
  value       = aws_cloudwatch_event_rule.all_chapters_completed.name
}

output "dlq_arn" {
  description = "ARN of the dead letter queue for failed events"
  value       = aws_sqs_queue.course_events_dlq.arn
}
