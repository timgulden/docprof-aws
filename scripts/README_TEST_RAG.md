# Testing RAG Pipeline

## Quick Start

### Option 1: Using the setup script (Recommended)

```bash
# Set up environment variables from Terraform
source scripts/setup_test_env.sh

# Run the test
python3 scripts/test_rag_pipeline.py "What does M&A stand for?"
```

### Option 2: Manual setup

```bash
# Get database info from Terraform
cd terraform/environments/dev
export DB_CLUSTER_ENDPOINT=$(terraform output -raw aurora_cluster_endpoint)
export DB_NAME=$(terraform output -raw aurora_database_name)
export DB_PASSWORD_SECRET_ARN=$(terraform output -raw aurora_master_password_secret_arn)

# Get password from Secrets Manager
export DB_PASSWORD=$(aws secretsmanager get-secret-value \
  --secret-id $DB_PASSWORD_SECRET_ARN \
  --query SecretString --output text \
  --profile docprof-dev)

# Set AWS defaults
export AWS_PROFILE=docprof-dev
export AWS_REGION=us-east-1

# Run the test
cd ../../..
python3 scripts/test_rag_pipeline.py "What does M&A stand for?"
```

## What the Script Does

The test script runs the complete RAG pipeline:

1. **Session Management** - Gets or creates a chat session
2. **Query Expansion** - Expands the query using MAExpert logic
3. **Embedding Generation** - Generates embedding using Bedrock Titan
4. **Vector Search** - Searches for similar chunks (tries multiple thresholds)
5. **Prompt Building** - Builds synthesis prompt with chunks and history
6. **LLM Synthesis** - Calls Claude to generate response
7. **Citation Building** - Builds source citations from search results

## Output

The script shows detailed output at each step:

- ✓ Success indicators
- ✗ Error messages with stack traces
- Search results with similarity scores
- Prompt preview
- Final response with citations

## Troubleshooting

### "Missing required environment variables"
- Run `source scripts/setup_test_env.sh` first
- Or set variables manually (see Option 2 above)

### "No chunks found"
- Most likely: Chunks don't have embeddings
- Check: Run `scripts/diagnose_rag.py` to verify embeddings exist
- Fix: Re-run book ingestion pipeline to generate embeddings

### "Failed to generate embedding"
- Check: Bedrock access permissions
- Check: AWS credentials (`aws sts get-caller-identity`)
- Check: VPC endpoints if Lambda is in VPC

### "Database connection error"
- Check: Database is running (Aurora might be paused)
- Check: Security groups allow connection
- Check: Database credentials are correct

## Example Output

```
======================================================================
  RAG Pipeline Test
======================================================================
User Message: 'What does M&A stand for?'

======================================================================
  Step 1: Session Management
======================================================================
✓ Created new session: abc-123-def-456

======================================================================
  Step 2: Convert Session to ChatState
======================================================================
✓ Converted to ChatState
  - Session context: None
  - Conversation history: 0 messages

======================================================================
  Step 3: Query Expansion
======================================================================
Original query: 'What does M&A stand for?'
Expanded query: 'what does m&a stand for?'
✓ Query expanded (28 chars)

======================================================================
  Step 4: Generate Embedding
======================================================================
✓ Embedding generated: 1536 dimensions
  First 5 values: [0.0123, -0.0456, 0.0789, ...]

======================================================================
  Step 5: Vector Search
======================================================================
✓ Found 5 chunks with threshold=0.6

  Top 3 results:
    [1] Similarity: 0.7234
        Chunk: abc12345... | Chapter 1: Introduction (p15)
        Preview: Mergers and acquisitions (M&A) refer to...

======================================================================
  Step 6: Build Synthesis Prompt
======================================================================
✓ Prompt built: 4523 characters

======================================================================
  Step 7: LLM Synthesis
======================================================================
✓ Claude response received
  Input tokens: 1234
  Output tokens: 567

Response (234 chars):
----------------------------------------------------------------------
M&A stands for "Mergers and Acquisitions." This refers to...
----------------------------------------------------------------------

======================================================================
  Pipeline Summary
======================================================================
✓ All steps completed successfully!
```
