# Phase 2.3: Re-Ingestion Pipeline Implementation Plan

**Status**: In Progress  
**Date**: 2025-01-XX

## Overview

This phase implements the complete re-ingestion pipeline for processing PDF textbooks and storing them in Aurora PostgreSQL with vector embeddings. Instead of migrating existing data, we'll re-ingest the 5 books to test the full AWS-native pipeline.

## Architecture

```
PDF Upload (S3)
    ↓
S3 Event → Lambda Trigger
    ↓
Document Processor Lambda
    ├─ Extract Text (PyMuPDF)
    ├─ Extract Figures (PyMuPDF + PIL)
    ├─ Chunk Text (chapter, 2-page, figure)
    ├─ Generate Embeddings (Bedrock Titan)
    └─ Store in Aurora (PostgreSQL + pgvector)
```

## Components Created

### 1. Database Schema Setup (`scripts/setup_database_schema.py`)

**Purpose**: Initialize Aurora database with pgvector extension and all tables

**Features**:
- Enables pgvector extension
- Creates all tables (books, figures, chunks, chapter_documents, user_progress, quizzes)
- Creates vector indexes for similarity search
- Tests vector operations

**Usage**:
```bash
cd terraform/environments/dev
terraform output -json > outputs.json
python ../../scripts/setup_database_schema.py
```

### 2. Shared Utilities (`src/lambda/shared/`)

#### `db_utils.py`
- Database connection management (RDS Proxy ready)
- Vector similarity search functions
- Batch insert utilities for chunks and figures
- Book insertion utilities

#### `bedrock_client.py`
- Bedrock Titan embeddings generation
- Claude LLM invocation (for figure descriptions)
- Streaming response support

#### `response.py`
- Standard API Gateway response formatting
- Success/error response helpers

### 3. Document Processor Lambda (`src/lambda/document_processor/`)

**Status**: Structure created, implementation pending

**Planned Features**:
- S3 event handler for PDF uploads
- PDF text extraction (PyMuPDF)
- Figure extraction and description (Claude vision)
- Text chunking (chapter, 2-page with overlap)
- Embedding generation (Bedrock Titan)
- Database storage (Aurora PostgreSQL)

## Implementation Steps

### Step 1: Database Schema Setup ✅

- [x] Create `setup_database_schema.py` script
- [x] Enable pgvector extension
- [x] Create all tables
- [x] Create indexes (including vector index)
- [ ] Test script against Aurora cluster

### Step 2: Shared Utilities ✅

- [x] Database connection utilities
- [x] Bedrock client utilities
- [x] Response formatting utilities
- [ ] Unit tests

### Step 3: Document Processor Lambda (In Progress)

- [x] Create Lambda structure
- [x] Create requirements.txt
- [ ] Implement PDF extraction
- [ ] Implement text chunking
- [ ] Implement figure processing
- [ ] Implement embedding generation
- [ ] Implement database storage
- [ ] Add error handling and retries
- [ ] Add logging

### Step 4: Terraform Integration (Pending)

- [ ] Create Lambda module
- [ ] Configure S3 event trigger
- [ ] Set up IAM permissions
- [ ] Configure VPC networking
- [ ] Set environment variables
- [ ] Deploy and test

### Step 5: Testing & Validation (Pending)

- [ ] Upload test PDF to S3
- [ ] Verify Lambda execution
- [ ] Check database records
- [ ] Test vector search
- [ ] Validate embeddings quality
- [ ] Performance testing

## Key Differences from MAExpert

| Component | MAExpert | DocProf AWS |
|-----------|----------|-------------|
| **Embeddings** | OpenAI text-embedding-3-small | Bedrock Titan Embeddings |
| **LLM** | Anthropic API | Bedrock Claude |
| **Database** | Local PostgreSQL | Aurora Serverless v2 |
| **Storage** | Local filesystem | S3 |
| **Trigger** | Manual script | S3 event → Lambda |
| **Connection** | Direct psycopg2 | RDS Proxy (future) |

## Testing Strategy

1. **Unit Tests**: Test individual functions (chunking, embedding, etc.)
2. **Integration Tests**: Test Lambda with mock S3 events
3. **End-to-End Tests**: Upload real PDF, verify database records
4. **Performance Tests**: Measure ingestion time, embedding generation speed

## Next Steps

1. Complete document processor Lambda implementation
2. Create Terraform module for Lambda deployment
3. Set up S3 event notifications
4. Test with sample PDF
5. Validate data quality and vector search performance

## References

- MAExpert Database Schema: `../MAExpert/docs/implementation/database-schema-and-setup.md`
- MAExpert Ingestion Guide: `../MAExpert/docs/implementation/ingestion-pipeline-guide.md`
- Bedrock Titan Embeddings: https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html
- Aurora Serverless v2: https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.html

