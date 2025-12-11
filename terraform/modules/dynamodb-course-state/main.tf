# DynamoDB Table for Course State

resource "aws_dynamodb_table" "course_state" {
  name         = "${var.project_name}-${var.environment}-course-state"
  billing_mode = "PAY_PER_REQUEST"  # On-demand billing
  hash_key     = "course_id"

  # TTL for automatic cleanup of old course states
  ttl {
    enabled        = true
    attribute_name = "ttl"
  }

  # Point-in-time recovery for data protection
  point_in_time_recovery {
    enabled = true
  }

  # Attribute definitions
  attribute {
    name = "course_id"
    type = "S"
  }

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-course-state"
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  )
}
