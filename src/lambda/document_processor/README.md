# Document Processor Lambda

Processes PDF documents uploaded to S3, extracts text and figures, chunks content, generates embeddings, and stores in Aurora PostgreSQL.

## Architecture

```
S3 Upload (PDF)
    ↓
Lambda Trigger (S3 Event)
    ↓
1. Extract Text & Figures (PyMuPDF)
    ↓
2. Chunk Text (chapter, 2-page, figure)
    ↓
3. Generate Embeddings (Bedrock Titan)
    ↓
4. Store in Aurora (PostgreSQL + pgvector)
```

## Input

S3 Event Notification:
```json
{
  "Records": [{
    "s3": {
      "bucket": {"name": "docprof-dev-source-docs"},
      "object": {"key": "Valuation8thEd.pdf"}
    }
  }]
}
```

## Output

- Books table: Book metadata
- Figures table: Extracted images
- Chunks table: Text chunks with embeddings
- Chapter documents table: Full chapter text

## Environment Variables

- `DB_CLUSTER_ENDPOINT`: Aurora cluster endpoint
- `DB_NAME`: Database name (default: docprof)
- `DB_MASTER_USERNAME`: Database username
- `DB_PASSWORD_SECRET_ARN`: Secrets Manager ARN for password
- `SOURCE_BUCKET`: S3 bucket name for source documents
- `PROCESSED_BUCKET`: S3 bucket name for processed chunks

## Dependencies

See `requirements.txt` for Python dependencies.

## Deployment

This Lambda will be deployed via Terraform in Phase 3 (Compute Layer).

## Testing

Test locally with:
```bash
python -m pytest tests/unit/document_processor/
```

Test with S3 event:
```bash
aws lambda invoke \
  --function-name docprof-dev-document-processor \
  --payload file://test-event.json \
  response.json
```

