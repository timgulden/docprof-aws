# DynamoDB Table for Chapter Summaries (per-chapter processing)

resource "aws_dynamodb_table" "chapter_summaries" {
  name         = "${var.project_name}-${var.environment}-chapter-summaries"
  billing_mode = "PAY_PER_REQUEST"  # On-demand billing
  hash_key     = "source_id"
  range_key    = "chapter_index"

  # Point-in-time recovery for data protection
  point_in_time_recovery {
    enabled = true
  }

  # Attribute definitions
  attribute {
    name = "source_id"
    type = "S"
  }

  attribute {
    name = "chapter_index"
    type = "N"
  }

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-chapter-summaries"
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  )
}
