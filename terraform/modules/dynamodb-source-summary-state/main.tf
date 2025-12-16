# DynamoDB Table for Source Summary State (tracking per-book processing)

resource "aws_dynamodb_table" "source_summary_state" {
  name         = "${var.project_name}-${var.environment}-source-summary-state"
  billing_mode = "PAY_PER_REQUEST"  # On-demand billing
  hash_key     = "source_id"

  # Point-in-time recovery for data protection
  point_in_time_recovery {
    enabled = true
  }

  # Attribute definitions
  attribute {
    name = "source_id"
    type = "S"
  }

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-source-summary-state"
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  )
}
