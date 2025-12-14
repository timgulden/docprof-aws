# S3 Buckets for DocProf
# Creates buckets for source documents, processed chunks, and frontend assets

# S3 Bucket for Source Documents (PDFs)
resource "aws_s3_bucket" "source_docs" {
  bucket = "${var.project_name}-${var.environment}-source-docs"

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-source-docs"
      Purpose = "source-documents"
    }
  )
}

# Versioning for source docs bucket
resource "aws_s3_bucket_versioning" "source_docs" {
  bucket = aws_s3_bucket.source_docs.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Encryption for source docs bucket
resource "aws_s3_bucket_server_side_encryption_configuration" "source_docs" {
  bucket = aws_s3_bucket.source_docs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Lifecycle policy for source docs (move to Glacier after 90 days)
resource "aws_s3_bucket_lifecycle_configuration" "source_docs" {
  bucket = aws_s3_bucket.source_docs.id

  rule {
    id     = "transition-to-glacier"
    status = "Enabled"

    filter {}

    transition {
      days          = 90
      storage_class = "GLACIER"
    }
  }

  rule {
    id     = "delete-old-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 365
    }
  }
}

# Block public access for source docs
resource "aws_s3_bucket_public_access_block" "source_docs" {
  bucket = aws_s3_bucket.source_docs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets  = true
}

# CORS configuration for source docs bucket
# Allows direct uploads from frontend using pre-signed POST URLs
resource "aws_s3_bucket_cors_configuration" "source_docs" {
  bucket = aws_s3_bucket.source_docs.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["POST", "PUT"]
    allowed_origins = [
      "http://localhost:5173",  # Vite dev server
      "http://localhost:3000",  # Alternative dev port
      "https://*.cloudfront.net",  # Production CloudFront distribution
    ]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# S3 Bucket for Processed Chunks
resource "aws_s3_bucket" "processed_chunks" {
  bucket = "${var.project_name}-${var.environment}-processed-chunks"

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-processed-chunks"
      Purpose = "processed-chunks"
    }
  )
}

# Encryption for processed chunks bucket
resource "aws_s3_bucket_server_side_encryption_configuration" "processed_chunks" {
  bucket = aws_s3_bucket.processed_chunks.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Block public access for processed chunks
resource "aws_s3_bucket_public_access_block" "processed_chunks" {
  bucket = aws_s3_bucket.processed_chunks.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets  = true
}

# S3 Bucket for Frontend (React build)
resource "aws_s3_bucket" "frontend" {
  bucket = "${var.project_name}-${var.environment}-frontend"

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-frontend"
      Purpose = "frontend-static"
    }
  )
}

# Website hosting for frontend bucket
resource "aws_s3_bucket_website_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "index.html"
  }
}

# Encryption for frontend bucket
resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Public read access for frontend (via CloudFront OAI, not direct)
# We'll configure bucket policy separately when CloudFront is created
resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets  = true
}

# TODO: Add bucket policy for CloudFront OAI access (when CloudFront module is created)

