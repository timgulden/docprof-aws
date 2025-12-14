# RAG Pipeline Diagnosis

## Problem
Chat is working but returns "I couldn't find relevant information" even for simple questions like "What does M&A stand for?"

## Likely Causes

### 1. Chunks Don't Have Embeddings (Most Likely)
If chunks were uploaded but embeddings weren't generated, vector search will fail.

**Check:**
```sql
-- Connect to Aurora and run:
SELECT 
    COUNT(*) as total_chunks,
    COUNT(embedding) as chunks_with_embeddings
FROM chunks;

-- Check by book:
SELECT 
    b.title,
    COUNT(c.chunk_id) as total,
    COUNT(c.embedding) as with_embedding
FROM chunks c
LEFT JOIN books b ON c.book_id = b.book_id
GROUP BY b.title;
```

**Fix:** Re-run the book ingestion pipeline to generate embeddings.

### 2. Similarity Threshold Too High
The default threshold of 0.7 might be too strict.

**Fix:** Already updated in `chat_handler/handler.py` to try progressively lower thresholds (0.7 → 0.6 → 0.5 → 0.4).

### 3. Embedding Model Mismatch
If chunks were embedded with a different model than queries, similarity scores will be low.

**Check:** 
- Chunks should use `amazon.titan-embed-text-v1` (1536 dimensions)
- Queries use the same model

### 4. Database Connection Issues
Lambda might not be able to connect to Aurora.

**Check CloudWatch Logs:**
```bash
aws logs tail /aws/lambda/docprof-dev-chat-handler --follow --profile docprof-dev
```

Look for:
- Database connection errors
- "No chunks found" warnings
- Embedding generation errors

## Diagnostic Script

Run the diagnostic script to check all of the above:

```bash
# First, get database connection info from Terraform
cd terraform/environments/dev
export DB_CLUSTER_ENDPOINT=$(terraform output -raw aurora_cluster_endpoint)
export DB_NAME=$(terraform output -raw aurora_database_name)
export DB_PASSWORD_SECRET_ARN=$(terraform output -raw aurora_master_password_secret_arn)

# Get password from Secrets Manager
export DB_PASSWORD=$(aws secretsmanager get-secret-value \
  --secret-id $DB_PASSWORD_SECRET_ARN \
  --query SecretString --output text \
  --profile docprof-dev)

# Run diagnostic
cd ../../..
python3 scripts/diagnose_rag.py
```

## Quick Fixes

### Lower Similarity Threshold (Already Done)
The handler now tries multiple thresholds automatically.

### Check CloudWatch Logs
```bash
aws logs tail /aws/lambda/docprof-dev-chat-handler --follow --profile docprof-dev
```

Look for:
- "Found X results with threshold=Y"
- "No chunks found for query"
- Database connection errors

### Verify Embeddings Exist
The most common issue is that chunks were inserted without embeddings. Check the book ingestion pipeline logs to see if embeddings were generated.

## Next Steps

1. **Check CloudWatch logs** for the chat handler to see what's happening
2. **Run the diagnostic script** to verify chunks have embeddings
3. **If no embeddings:** Re-run book ingestion with embedding generation
4. **If embeddings exist but no results:** Check similarity scores in logs (should see "Found X results")
