# S3 Module

This module creates S3 buckets for DocProf AWS infrastructure.

## Buckets Created

### 1. Source Documents Bucket
**Name:** `{project_name}-{environment}-source-docs`

**Features:**
- Versioning enabled
- SSE-S3 encryption
- Lifecycle policy: Move to Glacier after 90 days
- Delete old versions after 365 days
- Private (no public access)

**Purpose:** Store original PDF documents uploaded by users.

### 2. Processed Chunks Bucket
**Name:** `{project_name}-{environment}-processed-chunks`

**Features:**
- SSE-S3 encryption
- Private (no public access)

**Purpose:** Store processed text chunks and embeddings (JSON format).

### 3. Frontend Bucket
**Name:** `{project_name}-{environment}-frontend`

**Features:**
- Website hosting enabled
- SSE-S3 encryption
- Private (accessed via CloudFront OAI)

**Purpose:** Store React frontend build artifacts.

## Usage

```hcl
module "s3" {
  source = "../../modules/s3"

  project_name = "docprof"
  environment  = "dev"
  aws_region   = "us-east-1"

  tags = {
    ManagedBy = "terraform"
  }
}
```

## Security

- All buckets have encryption enabled (SSE-S3)
- Public access blocked on all buckets
- Frontend accessed via CloudFront (OAI configured separately)
- Source docs bucket has versioning for data protection

## Cost Optimization

- Source docs lifecycle policy moves old files to Glacier (cheaper storage)
- Old versions automatically deleted after 1 year
- Processed chunks bucket can use Intelligent Tiering (future enhancement)

## Outputs

- `source_docs_bucket_name` - Source documents bucket name
- `processed_chunks_bucket_name` - Processed chunks bucket name
- `frontend_bucket_name` - Frontend bucket name
- `frontend_website_endpoint` - S3 website endpoint (for testing)

