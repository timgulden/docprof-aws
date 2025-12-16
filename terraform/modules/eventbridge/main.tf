# EventBridge Custom Bus for Course Generation Events

resource "aws_cloudwatch_event_bus" "course_events" {
  name = "${var.project_name}-${var.environment}-course-events"

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-course-events"
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  )
}

# Event Rule: CourseRequested → Embedding Generator Lambda
# Using default bus instead of custom bus (custom bus has issues with event matching)
resource "aws_cloudwatch_event_rule" "course_requested" {
  name           = "${var.project_name}-${var.environment}-course-requested"
  # event_bus_name = aws_cloudwatch_event_bus.course_events.name  # Using default bus
  description    = "Route CourseRequested events to embedding generator"

  event_pattern = jsonencode({
    source      = ["docprof.course"]
    detail-type = ["CourseRequested"]
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-course-requested-rule"
    }
  )
}

# Event Rule: EmbeddingGenerated → Book Search Lambda
resource "aws_cloudwatch_event_rule" "embedding_generated" {
  name           = "${var.project_name}-${var.environment}-embedding-generated"
  # event_bus_name = aws_cloudwatch_event_bus.course_events.name  # Using default bus
  description    = "Route EmbeddingGenerated events to book search"

  event_pattern = jsonencode({
    source      = ["docprof.course"]
    detail-type = ["EmbeddingGenerated"]
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-embedding-generated-rule"
    }
  )
}

# Event Rule: BookSummariesFound → Parts Generator Lambda
resource "aws_cloudwatch_event_rule" "book_summaries_found" {
  name           = "${var.project_name}-${var.environment}-book-summaries-found"
  # event_bus_name = aws_cloudwatch_event_bus.course_events.name  # Using default bus
  description    = "Route BookSummariesFound events to parts generator"

  event_pattern = jsonencode({
    source      = ["docprof.course"]
    detail-type = ["BookSummariesFound"]
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-book-summaries-found-rule"
    }
  )
}

# Event Rule: PartsGenerated → Sections Generator Lambda
resource "aws_cloudwatch_event_rule" "parts_generated" {
  name           = "${var.project_name}-${var.environment}-parts-generated"
  # event_bus_name = aws_cloudwatch_event_bus.course_events.name  # Using default bus
  description    = "Route PartsGenerated events to sections generator"

  event_pattern = jsonencode({
    source      = ["docprof.course"]
    detail-type = ["PartsGenerated"]
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-parts-generated-rule"
    }
  )
}

# Event Rule: PartSectionsGenerated → Next Part or Review
resource "aws_cloudwatch_event_rule" "part_sections_generated" {
  name           = "${var.project_name}-${var.environment}-part-sections-generated"
  # event_bus_name = aws_cloudwatch_event_bus.course_events.name  # Using default bus
  description    = "Route PartSectionsGenerated events (triggers next part or review)"

  event_pattern = jsonencode({
    source      = ["docprof.course"]
    detail-type = ["PartSectionsGenerated"]
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-part-sections-generated-rule"
    }
  )
}

# Event Rule: AllPartsComplete → Outline Reviewer Lambda
resource "aws_cloudwatch_event_rule" "all_parts_complete" {
  name           = "${var.project_name}-${var.environment}-all-parts-complete"
  # event_bus_name = aws_cloudwatch_event_bus.course_events.name  # Using default bus
  description    = "Route AllPartsComplete events to outline reviewer"

  event_pattern = jsonencode({
    source      = ["docprof.course"]
    detail-type = ["AllPartsComplete"]
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-all-parts-complete-rule"
    }
  )
}

# Event Rule: OutlineReviewed → Course Storage Lambda
resource "aws_cloudwatch_event_rule" "outline_reviewed" {
  name           = "${var.project_name}-${var.environment}-outline-reviewed"
  # event_bus_name = aws_cloudwatch_event_bus.course_events.name  # Using default bus
  description    = "Route OutlineReviewed events to course storage"

  event_pattern = jsonencode({
    source      = ["docprof.course"]
    detail-type = ["OutlineReviewed"]
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-outline-reviewed-rule"
    }
  )
}

# Event Rule: DocumentProcessed → Source Summary Generator Lambda
resource "aws_cloudwatch_event_rule" "document_processed" {
  name           = "${var.project_name}-${var.environment}-document-processed"
  # event_bus_name = aws_cloudwatch_event_bus.course_events.name  # Using default bus
  description    = "Route DocumentProcessed events to source summary generator"

  event_pattern = jsonencode({
    source      = ["docprof.ingestion"]
    detail-type = ["DocumentProcessed"]
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-document-processed-rule"
    }
  )
}

# Event Rule: SourceSummaryStored → Embedding Generator Lambda
resource "aws_cloudwatch_event_rule" "source_summary_stored" {
  name           = "${var.project_name}-${var.environment}-source-summary-stored"
  # event_bus_name = aws_cloudwatch_event_bus.course_events.name  # Using default bus
  description    = "Route SourceSummaryStored events to embedding generator"

  event_pattern = jsonencode({
    source      = ["docprof.ingestion"]
    detail-type = ["SourceSummaryStored"]
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-source-summary-stored-rule"
    }
  )
}

# Event Rule: ChapterSummaryRequested → Chapter Summary Processor Lambda
resource "aws_cloudwatch_event_rule" "chapter_summary_requested" {
  name           = "${var.project_name}-${var.environment}-chapter-summary-requested"
  # event_bus_name = aws_cloudwatch_event_bus.course_events.name  # Using default bus
  description    = "Route ChapterSummaryRequested events to chapter processor"

  event_pattern = jsonencode({
    source      = ["docprof.ingestion"]
    detail-type = ["ChapterSummaryRequested"]
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-chapter-summary-requested-rule"
    }
  )
}

# Event Rule: AllChaptersCompleted → Source Summary Assembler Lambda
resource "aws_cloudwatch_event_rule" "all_chapters_completed" {
  name           = "${var.project_name}-${var.environment}-all-chapters-completed"
  # event_bus_name = aws_cloudwatch_event_bus.course_events.name  # Using default bus
  description    = "Route AllChaptersCompleted events to source summary assembler"

  event_pattern = jsonencode({
    source      = ["docprof.ingestion"]
    detail-type = ["AllChaptersCompleted"]
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-all-chapters-completed-rule"
    }
  )
}

# Dead Letter Queue for failed events
resource "aws_sqs_queue" "course_events_dlq" {
  name = "${var.project_name}-${var.environment}-course-events-dlq"

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-course-events-dlq"
    }
  )
}
