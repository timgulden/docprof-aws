# DynamoDB Table for Chat Sessions

resource "aws_dynamodb_table" "sessions" {
  name         = "${var.project_name}-${var.environment}-sessions"
  billing_mode = "PAY_PER_REQUEST"  # On-demand billing (pay per request)
  hash_key     = "session_id"

  # TTL for automatic cleanup of old sessions
  ttl {
    enabled        = true
    attribute_name = "expires_at"
  }

  # Point-in-time recovery for data protection
  point_in_time_recovery {
    enabled = true
  }

  # Attribute definitions
  attribute {
    name = "session_id"
    type = "S"
  }

  # Global secondary index for querying by user_id (if needed in future)
  # For now, we'll use session_id as the primary key
  # Can add GSI later if we need to query by user_id

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-sessions"
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  )
}
