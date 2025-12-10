# DocProf AWS Migration Guide

**Version:** 1.0  
**Date:** December 9, 2025  
**Purpose:** Guide for migrating DocProf from local FastAPI/PostgreSQL to AWS-native serverless architecture

---

## Executive Summary

This guide documents the migration of DocProf from a local React/FastAPI/PostgreSQL stack to a production-grade AWS serverless architecture. The goal is to demonstrate modern cloud architecture patterns while keeping costs under $100/month during development and ~$10/month when idle.

**Current Stack:**
- Frontend: React
- Backend: FastAPI (Python)
- Database: PostgreSQL + pgvector
- LLM: Anthropic API
- TTS: OpenAI API
- Deployment: Local laptop

**Target Stack:**
- Frontend: React on S3 + CloudFront
- Backend: Lambda + API Gateway
- Database: Aurora Serverless PostgreSQL + pgvector
- LLM: AWS Bedrock (Claude)
- TTS: AWS Polly Neural
- Infrastructure: Terraform (Infrastructure as Code)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  User's Browser (React SPA)                                │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  CloudFront CDN + S3 Static Hosting                        │
│  - HTTPS via ACM                                           │
│  - Global edge caching                                     │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  API Gateway                                               │
│  - REST API for requests                                   │
│  - WebSocket API for streaming                            │
│  - Cognito authorizer                                      │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  Lambda Functions (Python 3.11)                            │
│  - chat_handler                                            │
│  - course_generator                                        │
│  - lecture_generator                                       │
│  - audio_streamer                                          │
│  - document_processor                                      │
└───┬──────────┬──────────┬──────────┬───────────────────────┘
    │          │          │          │
    ▼          ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌──────┐ ┌────────┐
│ Aurora │ │Bedrock │ │  S3  │ │ Polly  │
│Servless│ │(Claude)│ │(docs)│ │ (TTS)  │
│pgvector│ │(Titan) │ │      │ │        │
└────────┘ └────────┘ └──────┘ └────────┘
```

---

## Cost Management Strategy

### Free Tier Usage (First 12 Months)
- Lambda: 1M requests/month free
- API Gateway: 1M requests/month free
- Aurora Serverless: Paused when not in use (no charges)
- S3: 5GB storage, 20K GET requests free
- CloudFront: 1TB transfer, 10M requests free
- Bedrock: No free tier (pay per use)

### Expected Costs

**Development/Active Month (~$50-100)**:
- Aurora Serverless (spinning up/down): $20-40
- Bedrock (Claude calls): $20-30
- Polly (TTS): $5-10
- Lambda (minimal): $0-5
- S3 + data transfer: $5-10
- Other services: $5

**Idle Month (~$5-15)**:
- Aurora Serverless (paused): $0
- S3 storage: $1-5
- CloudWatch logs: $2-5
- Other minimal charges: $2-5

### Cost Optimization Tactics
1. **Aurora Serverless v2**: Scales to zero when not in use
2. **RDS Proxy**: Reuse database connections across Lambda invocations
3. **S3 Intelligent Tiering**: Auto-move old documents to cheaper storage
4. **Lambda Memory Optimization**: Right-size functions (less memory = lower cost)
5. **CloudWatch Log Retention**: Set to 7 days for dev, 30 days for prod
6. **Development Schedule**: Pause/delete resources when not actively developing

---

## Phase-by-Phase Implementation Plan

## Phase 1: Infrastructure Foundation (Week 1)

**Goal**: Establish secure AWS environment with Infrastructure as Code

### 1.1 AWS Account Setup

**Actions**:
1. Create AWS account with root user
2. Enable MFA on root account
3. Create IAM admin user (never use root for day-to-day)
4. Set up billing alerts ($50, $75, $100 thresholds)
5. Install AWS CLI and configure credentials

**Cursor prompts**:
```
"Generate a bash script to configure AWS CLI with a new profile named 'docprof-dev' and test connectivity by listing S3 buckets."
```

**Validation**:
- Can authenticate via AWS CLI
- Billing alerts are working
- MFA is enabled

### 1.2 Terraform Setup

**Actions**:
1. Install Terraform (via Homebrew or download)
2. Create project structure:
```
docprof-aws/
├── terraform/
│   ├── environments/
│   │   ├── dev/
│   │   │   ├── main.tf
│   │   │   ├── terraform.tfvars
│   │   │   └── backend.tf
│   │   └── prod/  # Future
│   ├── modules/
│   │   ├── vpc/
│   │   ├── lambda/
│   │   ├── api-gateway/
│   │   ├── aurora/
│   │   └── s3/
│   └── shared/
│       └── variables.tf
├── src/
│   ├── lambda/
│   │   ├── chat_handler/
│   │   ├── course_generator/
│   │   └── ...
│   └── frontend/  # Your existing React app
└── docs/
    └── architecture/
```

**Cursor prompts**:
```
"Create a Terraform module structure for AWS infrastructure with separate modules for VPC, Lambda, API Gateway, Aurora, and S3. Include a dev environment configuration and a shared variables file."

"Generate a terraform/modules/vpc/main.tf that creates a VPC with:
- 2 public subnets in different AZs
- 2 private subnets in different AZs  
- Internet Gateway for public subnets
- NAT Gateway for private subnets
- VPC endpoints for S3 and Bedrock
- Appropriate route tables"
```

**Validation**:
- `terraform init` succeeds
- `terraform plan` shows no errors
- Terraform state is stored (local or S3 backend)

### 1.3 VPC and Networking

**Actions**:
1. Create VPC module (10.0.0.0/16)
2. Define subnets:
   - Public: 10.0.1.0/24, 10.0.2.0/24
   - Private: 10.0.10.0/24, 10.0.11.0/24
3. Create Internet Gateway and NAT Gateway
4. Set up VPC endpoints (S3, Bedrock)
5. Configure security groups:
   - `lambda-sg`: Outbound to Aurora, S3, Bedrock
   - `aurora-sg`: Inbound from Lambda only
   - `alb-sg`: Inbound HTTPS from internet (if using ALB)

**Cursor prompts**:
```
"Create terraform/modules/vpc/security_groups.tf with three security groups:
1. lambda_sg: allows outbound to Aurora (port 5432), S3, and Bedrock
2. aurora_sg: allows inbound from lambda_sg on port 5432
3. alb_sg: allows inbound HTTPS (443) from 0.0.0.0/0
Include proper descriptions and tags."
```

**Validation**:
- `terraform apply` creates VPC successfully
- Security groups have correct rules
- VPC endpoints are created

### 1.4 IAM Roles and Policies

**Actions**:
1. Create Lambda execution role with policies for:
   - CloudWatch Logs (write)
   - Aurora (connect via RDS Proxy)
   - S3 (read/write specific buckets)
   - Bedrock (invoke models)
   - Polly (synthesize speech)
2. Create RDS monitoring role
3. Create S3 bucket policies (least privilege)
4. Document all policies in `docs/iam-policies.md`

**Cursor prompts**:
```
"Create terraform/modules/iam/lambda_roles.tf with an IAM role for Lambda that includes:
- CloudWatch Logs write permission
- RDS connect via IAM authentication
- S3 read/write on buckets matching 'docprof-*'
- Bedrock InvokeModel permission for Claude and Titan
- Polly SynthesizeSpeech permission
Use least-privilege principles and inline policies where appropriate."
```

**Key Learning**: IAM is security foundation. Every service needs explicit permission to access other services.

**Validation**:
- Roles are created with correct trust relationships
- Policies are JSON-valid and minimal
- No wildcards in resource ARNs

### 1.5 Initial Deployment

**Actions**:
1. Run `terraform plan` and review output
2. Run `terraform apply` to create infrastructure
3. Verify all resources in AWS console
4. Document resource ARNs and IDs
5. Tag all resources (Environment: dev, Project: docprof)

**Validation**:
- All resources created successfully
- Can see VPC, subnets, security groups in console
- IAM roles exist
- Total cost estimate is acceptable

**Deliverables**:
- Working Terraform configuration
- VPC with proper network segmentation
- IAM roles for all services
- Documentation of architecture decisions

---

## Phase 2: Data Layer (Week 2)

**Goal**: Migrate your corpus to AWS with vector search capabilities

### 2.1 Aurora Serverless PostgreSQL Setup

**Actions**:
1. Create Aurora Serverless v2 cluster in private subnets
2. Enable pgvector extension
3. Configure RDS Proxy for Lambda connections
4. Set up automated backups (7-day retention for dev)
5. Configure parameter group for pgvector optimization

**Cursor prompts**:
```
"Create terraform/modules/aurora/main.tf for Aurora Serverless v2 PostgreSQL:
- Engine version: 15.4 or later (supports pgvector)
- Min capacity: 0.5 ACU (can scale to zero)
- Max capacity: 2 ACU (sufficient for dev)
- Private subnets only
- Security group allowing Lambda access
- Automated backups enabled
- Parameter group with shared_preload_libraries = 'vector'"

"Write a Python script scripts/enable_pgvector.py that:
- Connects to Aurora using IAM authentication
- Enables the pgvector extension (CREATE EXTENSION IF NOT EXISTS vector)
- Creates the necessary tables from my existing schema
- Verifies vector operations work with a test query"
```

**Database Schema Migration**:
```sql
-- Your existing schema should work with minimal changes
-- Just ensure pgvector extension is loaded

CREATE EXTENSION IF NOT EXISTS vector;

-- Example: chunks table with embeddings
CREATE TABLE chunks (
    chunk_id UUID PRIMARY KEY,
    book_id UUID REFERENCES books(book_id),
    chunk_type TEXT,
    content TEXT,
    embedding vector(1536),  -- Same as your local setup
    -- ... other fields
);

CREATE INDEX chunks_embedding_idx ON chunks 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

**Key Learning**: Aurora Serverless can pause after 5 minutes of inactivity, saving significant costs. RDS Proxy maintains connection pool so Lambda doesn't exhaust connections.

**Validation**:
- Can connect to Aurora from Lambda (via RDS Proxy)
- pgvector extension is loaded
- Test vector similarity query works
- Aurora auto-pauses after idle period

### 2.2 S3 Bucket Configuration

**Actions**:
1. Create S3 buckets:
   - `docprof-dev-source-docs`: Original PDFs
   - `docprof-dev-processed-chunks`: Processed text chunks
   - `docprof-dev-frontend`: Static React build
2. Enable versioning on source docs bucket
3. Configure server-side encryption (SSE-S3 or SSE-KMS)
4. Set lifecycle policies (move old docs to Glacier after 90 days)
5. Configure S3 event notifications (trigger Lambda on upload)

**Cursor prompts**:
```
"Create terraform/modules/s3/main.tf with three S3 buckets:
1. docprof-dev-source-docs:
   - Versioning enabled
   - SSE-S3 encryption
   - Lifecycle policy to move to Glacier after 90 days
   - Event notification for object creation (will trigger Lambda)
2. docprof-dev-processed-chunks:
   - No versioning needed
   - SSE-S3 encryption
3. docprof-dev-frontend:
   - Public read access (for CloudFront)
   - Website hosting enabled
Include bucket policies for least privilege access."
```

**Validation**:
- Buckets are created with encryption
- Can upload test file via AWS CLI
- Versioning works on source docs bucket
- Event notifications configured

### 2.3 Data Migration

**Actions**:
1. Export your local corpus:
   - Books metadata as JSON
   - Chunks as JSON or CSV
   - Embeddings as NumPy arrays or JSON
2. Upload to S3
3. Create migration Lambda function
4. Load data into Aurora
5. Verify vector search performance

**Cursor prompts**:
```
"Write a Python script scripts/export_corpus.py that:
- Connects to my local PostgreSQL database
- Exports all books, chunks, and embeddings to JSON files
- Uploads JSON files to S3 bucket docprof-dev-processed-chunks
- Handles large datasets in batches
- Logs progress and any errors"

"Create src/lambda/data_migrator/handler.py that:
- Reads JSON files from S3
- Connects to Aurora via RDS Proxy
- Inserts data in batches (1000 records at a time)
- Creates pgvector indexes after data load
- Returns summary of records loaded"
```

**Key Learning**: Lambda has 15-minute max execution time. For large data loads, use Step Functions or process in batches.

**Validation**:
- All books and chunks in Aurora
- Embeddings are correct (spot-check a few)
- Vector similarity search returns same results as local
- Indexes are created

### 2.4 Performance Testing

**Actions**:
1. Run benchmark queries (top-K similarity search)
2. Compare latency to local setup
3. Tune Aurora capacity settings if needed
4. Document performance characteristics

**Cursor prompts**:
```
"Write a Python script scripts/benchmark_vector_search.py that:
- Runs 100 random vector similarity queries against Aurora
- Measures query latency (p50, p95, p99)
- Compares to local PostgreSQL performance
- Outputs results as a table and chart
- Tests with different k values (5, 10, 20)"
```

**Validation**:
- Vector search latency is acceptable (<500ms p95)
- Aurora scales up when under load
- Aurora scales down/pauses when idle

**Deliverables**:
- Aurora Serverless cluster with pgvector
- S3 buckets with proper security
- Complete corpus migrated to AWS
- Performance benchmarks documented

---

## Phase 3: API Layer (Week 3)

**Goal**: Replace FastAPI with API Gateway + Lambda

### 3.1 Lambda Function Framework

**Actions**:
1. Create Lambda function template with common patterns:
   - Connection pooling for Aurora
   - Error handling and logging
   - Response formatting
   - Environment variable management
2. Set up Lambda layers for shared dependencies
3. Configure CloudWatch log groups

**Project structure for Lambda**:
```
src/lambda/
├── shared/
│   ├── __init__.py
│   ├── db_utils.py       # Aurora connection via RDS Proxy
│   ├── bedrock_client.py # Bedrock API wrapper
│   ├── s3_utils.py       # S3 operations
│   └── response.py       # Standard API responses
├── chat_handler/
│   ├── handler.py        # Lambda entry point
│   ├── requirements.txt
│   └── logic.py          # Pure business logic
├── course_generator/
│   ├── handler.py
│   ├── requirements.txt
│   └── logic.py
└── ...
```

**Cursor prompts**:
```
"Create src/lambda/shared/db_utils.py with functions for:
- Getting a database connection via RDS Proxy using IAM auth
- Connection pooling compatible with Lambda (reuse across invocations)
- Executing vector similarity queries
- Proper error handling and logging
- Include docstrings and type hints"

"Create src/lambda/shared/response.py with helper functions for:
- Success response (200) with JSON body
- Error response (400, 500) with error message
- CORS headers included
- Consistent response format"
```

**Key Learning**: Lambda functions are stateless and ephemeral. Each invocation gets a clean environment, but containers may be reused. Connection pooling is critical for database access.

### 3.2 Core Lambda Functions

**Actions**:
1. **chat_handler**: Process user messages
   - Input: User message + session context
   - Logic: Retrieve context → Call Bedrock → Format response
   - Output: Assistant message + updated session

2. **course_generator**: Create course outlines
   - Input: User query + duration + preferences
   - Logic: Semantic search → Multi-phase generation
   - Output: Course outline with parts and sections

3. **lecture_generator**: Generate lecture content
   - Input: Section ID
   - Logic: Retrieve chunks → Generate script → Format
   - Output: Lecture text

4. **audio_streamer**: Stream TTS audio
   - Input: Lecture text
   - Logic: Call Polly → Stream MP3 response
   - Output: Audio stream

**Cursor prompts**:
```
"Create src/lambda/chat_handler/handler.py that:
- Accepts POST request with {message, session_id}
- Loads session context from DynamoDB
- Performs vector search on embeddings using db_utils
- Calls Bedrock Claude with context and message
- Formats response with citations
- Updates session in DynamoDB
- Returns JSON response with assistant message
Include comprehensive error handling and logging"

"Create src/lambda/course_generator/handler.py that:
- Accepts POST request with {query, hours, preferences}
- Implements the multi-phase course generation logic:
  1. Semantic search for relevant books
  2. Generate parts outline
  3. Expand each part into sections
  4. Review and adjust for time accuracy
- Stores course outline in Aurora
- Returns JSON response with complete course structure
Use the logic from my existing course_design process"
```

**Functional Programming Note**: Keep Lambda handlers thin. Extract business logic to pure functions in `logic.py` for easier testing.

**Validation**:
- Each Lambda function works in isolation
- Can invoke via AWS CLI or console
- Logs appear in CloudWatch
- Error handling works correctly

### 3.3 API Gateway Configuration

**Actions**:
1. Create REST API in API Gateway
2. Define resources and methods:
   - `/chat` → POST → chat_handler Lambda
   - `/courses` → GET, POST → course_generator Lambda
   - `/courses/{courseId}` → GET → course_retriever Lambda
   - `/lectures/{lectureId}` → GET → lecture_generator Lambda
   - `/audio/{lectureId}` → GET → audio_streamer Lambda
3. Configure Lambda proxy integration
4. Set up CORS for browser access
5. Add request validation

**Cursor prompts**:
```
"Create terraform/modules/api-gateway/main.tf that:
- Creates REST API named 'docprof-api'
- Defines resources for /chat, /courses, /lectures, /audio
- Configures Lambda proxy integration for each endpoint
- Enables CORS with proper headers
- Sets up CloudWatch logging
- Configures stage variable for environment (dev/prod)"

"Create an OpenAPI 3.0 specification (openapi.yaml) for the DocProf API that:
- Documents all endpoints with request/response schemas
- Includes authentication requirements (to be added)
- Specifies error responses
- Can be imported into API Gateway"
```

**Key Learning**: API Gateway charges per request. Lambda proxy integration is simplest pattern - Lambda gets full request, returns full response.

### 3.4 Session Management with DynamoDB

**Actions**:
1. Create DynamoDB table for sessions
2. Design session schema:
   - Partition key: `session_id` (UUID)
   - Attributes: `user_id`, `messages`, `current_course`, `created_at`, `updated_at`
   - TTL: 7 days (auto-cleanup)
3. Create helper functions for session CRUD

**Cursor prompts**:
```
"Create terraform/modules/dynamodb/sessions.tf that:
- Creates DynamoDB table 'docprof-sessions'
- Partition key: session_id (String)
- On-demand billing mode (pay per request)
- TTL enabled on 'expires_at' attribute
- Point-in-time recovery enabled
- Tags for environment and project"

"Create src/lambda/shared/session_manager.py with functions for:
- create_session(user_id) -> session_id
- get_session(session_id) -> session_dict
- update_session(session_id, updates) -> bool
- delete_session(session_id) -> bool
- Includes proper error handling and logging
- Uses boto3 for DynamoDB operations"
```

**Schema Example**:
```json
{
  "session_id": "uuid-here",
  "user_id": "user-uuid",
  "messages": [
    {"role": "user", "content": "What is DCF?"},
    {"role": "assistant", "content": "DCF stands for..."}
  ],
  "current_course": {"course_id": "uuid", "section_index": 3},
  "created_at": "2025-12-09T10:00:00Z",
  "updated_at": "2025-12-09T10:15:00Z",
  "expires_at": 1735488000  # Unix timestamp for TTL
}
```

**Validation**:
- Can create/read/update/delete sessions
- TTL auto-deletes old sessions
- Lambda functions can access sessions

### 3.5 Integration Testing

**Actions**:
1. Test each endpoint with curl or Postman
2. Verify end-to-end flows:
   - Create session → Send message → Get response
   - Generate course → Retrieve course → Get lecture
3. Load test (simulate 10 concurrent users)
4. Monitor CloudWatch metrics

**Cursor prompts**:
```
"Create scripts/test_api.sh that:
- Tests all API Gateway endpoints
- Creates a session, sends a chat message, verifies response
- Generates a course, retrieves it, verifies structure
- Checks response times and success rates
- Uses curl or httpie for requests
- Outputs pass/fail for each test"
```

**Validation**:
- All endpoints return expected responses
- Error handling works (try invalid inputs)
- Response times are acceptable
- No Lambda errors in CloudWatch

**Deliverables**:
- Complete set of Lambda functions
- API Gateway with all endpoints
- DynamoDB table for sessions
- Integration tests passing

---

## Phase 4: AI Services (Week 4)

**Goal**: Replace external APIs with AWS Bedrock and Polly

### 4.1 Bedrock for LLM (Claude)

**Actions**:
1. Enable Bedrock model access in AWS console (Claude 3.5 Sonnet)
2. Create Bedrock client wrapper
3. Update chat and course generation to use Bedrock
4. Implement streaming for real-time responses
5. Add token usage tracking

**Cursor prompts**:
```
"Create src/lambda/shared/bedrock_client.py with:
- Function to call Bedrock Claude 3.5 Sonnet with streaming
- Handle streaming responses using boto3
- Parse and format responses
- Track token usage for cost monitoring
- Include retry logic with exponential backoff
- Type hints and docstrings throughout"

"Update src/lambda/chat_handler/logic.py to:
- Use bedrock_client instead of Anthropic API
- Handle streaming responses properly
- Format system prompt and context same as before
- Track and log token usage per request
- Return structured response with usage metadata"
```

**Bedrock API Example**:
```python
import boto3
import json

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

def invoke_claude(prompt: str, system: str = None, max_tokens: int = 4096):
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }
    if system:
        request_body["system"] = system
    
    response = bedrock.invoke_model(
        modelId="anthropic.claude-3-5-sonnet-20241022-v2:0",
        body=json.dumps(request_body)
    )
    
    response_body = json.loads(response['body'].read())
    return response_body
```

**Key Learning**: Bedrock streaming requires InvokeModelWithResponseStream. Response comes as event stream that must be parsed.

**Validation**:
- Can call Bedrock Claude successfully
- Response quality matches Anthropic API
- Streaming works correctly
- Token usage is tracked

### 4.2 Bedrock for Embeddings (Titan)

**Actions**:
1. Enable Titan Embeddings model in Bedrock
2. Create embedding generation function
3. Update document ingestion to use Titan
4. Verify embedding quality (compare to OpenAI)

**Cursor prompts**:
```
"Create src/lambda/shared/embeddings.py with:
- Function to generate embeddings using Bedrock Titan
- Batch processing (up to 25 texts at once)
- Normalize embeddings to unit length
- Handle rate limiting and retries
- Return numpy arrays or lists as needed"

"Write scripts/test_embeddings.py that:
- Generates embeddings for sample texts using both OpenAI and Titan
- Computes cosine similarity between pairs
- Compares results to verify quality is comparable
- Outputs similarity scores and correlation statistics"
```

**Titan Embeddings Example**:
```python
def generate_embeddings(texts: list[str]) -> list[list[float]]:
    bedrock = boto3.client('bedrock-runtime')
    
    embeddings = []
    for text in texts:
        request = {
            "inputText": text
        }
        response = bedrock.invoke_model(
            modelId="amazon.titan-embed-text-v1",
            body=json.dumps(request)
        )
        result = json.loads(response['body'].read())
        embeddings.append(result['embedding'])
    
    return embeddings
```

**Validation**:
- Embeddings are 1536 dimensions (same as OpenAI)
- Similarity scores are reasonable
- Vector search still works correctly

### 4.3 Polly for Text-to-Speech

**Actions**:
1. Create Polly client wrapper
2. Test Neural voices for quality (Matthew, Joanna)
3. Implement audio streaming
4. Handle long text (Polly has 3000 char limit per request)
5. Cache generated audio in S3

**Cursor prompts**:
```
"Create src/lambda/shared/polly_client.py with:
- Function to synthesize speech using Polly Neural voices
- Chunk long text into 3000-char segments
- Stream MP3 audio from Polly
- Option to save to S3 for caching
- Support for SSML (Speech Synthesis Markup Language)
- Handle rate limits and errors gracefully"

"Update src/lambda/audio_streamer/handler.py to:
- Accept lecture text (potentially long)
- Check if audio already exists in S3 cache
- If not cached, generate using Polly
- Stream audio response via API Gateway
- Save to cache for future requests
- Return proper audio/mpeg content type"
```

**Polly Streaming Example**:
```python
import boto3

def synthesize_speech(text: str, voice_id: str = "Matthew") -> bytes:
    polly = boto3.client('polly')
    
    response = polly.synthesize_speech(
        Text=text,
        OutputFormat='mp3',
        VoiceId=voice_id,
        Engine='neural'
    )
    
    # Stream audio data
    audio_stream = response['AudioStream']
    return audio_stream.read()
```

**Voice Quality Testing**: Test Matthew, Joanna, and other Neural voices to find best match for your use case. Record sample outputs for comparison.

**Validation**:
- Audio quality is acceptable (subjective)
- Long texts are handled correctly
- Streaming works from Lambda
- Cached audio reduces cost

### 4.4 Cost Monitoring and Optimization

**Actions**:
1. Set up CloudWatch custom metrics for:
   - Bedrock token usage per day
   - Bedrock cost estimate
   - Polly character count per day
   - Polly cost estimate
2. Create CloudWatch dashboard
3. Set up billing alarms
4. Document cost per operation

**Cursor prompts**:
```
"Create src/lambda/shared/cost_tracker.py with:
- Function to log custom CloudWatch metrics
- Track Bedrock input/output tokens
- Track Polly characters synthesized
- Calculate estimated costs using current pricing
- Publish metrics to CloudWatch
- Include daily aggregation logic"

"Create terraform/modules/cloudwatch/dashboards.tf with:
- CloudWatch dashboard for DocProf
- Widgets showing:
  - Lambda invocation count and errors
  - Bedrock token usage over time
  - Polly character usage over time
  - Aurora Serverless capacity units
  - Estimated daily cost
- Auto-refresh enabled"
```

**Cost Formulas** (as of Dec 2024):
- Bedrock Claude 3.5 Sonnet: $0.003/1K input tokens, $0.015/1K output tokens
- Bedrock Titan Embeddings: $0.0001/1K input tokens
- Polly Neural: $0.016/1M characters

**Validation**:
- Metrics appear in CloudWatch
- Dashboard shows current usage
- Cost estimates are reasonable
- Billing alarms trigger at thresholds

**Deliverables**:
- Bedrock integration for LLM and embeddings
- Polly integration for TTS
- Cost tracking and monitoring
- Performance comparison with previous setup

---

## Phase 5: Advanced Patterns (Week 5-6)

**Goal**: Demonstrate sophisticated AWS orchestration

### 5.1 Step Functions for Document Processing

**Actions**:
1. Design state machine for document ingestion:
   - Upload to S3 → Extract text → Chunk → Generate embeddings → Store
2. Implement parallel processing for chunks
3. Add error handling and retries
4. Create visual workflow

**Workflow Design**:
```
Start
  ↓
Extract Text (Lambda)
  ↓
Chunk Document (Lambda)
  ↓
Generate Embeddings (Parallel - one per chunk)
  ├─→ Chunk 1 Embedding (Lambda)
  ├─→ Chunk 2 Embedding (Lambda)
  └─→ ... (up to 10 parallel)
  ↓
Store in Aurora (Lambda)
  ↓
Update Search Index (Lambda)
  ↓
End
```

**Cursor prompts**:
```
"Create terraform/modules/step-functions/document_processor.tf with:
- Step Functions state machine definition
- Task states for each Lambda function
- Map state for parallel embedding generation
- Retry logic (3 attempts with exponential backoff)
- Catch blocks for error handling
- IAM role allowing Step Functions to invoke Lambdas
- CloudWatch log group for execution history"

"Create src/lambda/document_extractor/handler.py that:
- Accepts S3 event with document key
- Extracts text from PDF using PyMuPDF
- Returns extracted text and metadata
- Designed to be called by Step Functions
- Includes error handling for malformed PDFs"
```

**State Machine Example** (simplified):
```json
{
  "Comment": "Document processing pipeline",
  "StartAt": "ExtractText",
  "States": {
    "ExtractText": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:function:document-extractor",
      "Next": "ChunkDocument",
      "Retry": [{
        "ErrorEquals": ["States.TaskFailed"],
        "MaxAttempts": 3,
        "BackoffRate": 2.0
      }]
    },
    "ChunkDocument": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:function:document-chunker",
      "Next": "GenerateEmbeddings"
    },
    "GenerateEmbeddings": {
      "Type": "Map",
      "ItemsPath": "$.chunks",
      "MaxConcurrency": 10,
      "Iterator": {
        "StartAt": "EmbedChunk",
        "States": {
          "EmbedChunk": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:...:function:embedding-generator",
            "End": true
          }
        }
      },
      "Next": "StoreResults"
    },
    "StoreResults": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:function:database-writer",
      "End": true
    }
  }
}
```

**Key Learning**: Step Functions coordinate long-running workflows. They handle retries, error branching, and parallel execution without you writing coordination code.

**Validation**:
- Can trigger state machine manually
- Watch execution in Step Functions console
- Parallel processing works correctly
- Error handling catches and retries failures

### 5.2 EventBridge for Event-Driven Architecture

**Actions**:
1. Create EventBridge custom event bus
2. Define event patterns:
   - `document.uploaded` → Trigger Step Functions
   - `course.completed` → Send notification
   - `quiz.scored` → Update progress tracking
3. Add multiple consumers per event
4. Implement event replay for debugging

**Cursor prompts**:
```
"Create terraform/modules/eventbridge/main.tf with:
- Custom event bus named 'docprof-events'
- Rules for document.uploaded, course.completed, quiz.scored
- Targets for each rule (Step Functions, Lambda, SNS)
- IAM permissions for event publishing
- DLQ (Dead Letter Queue) for failed events"

"Create src/lambda/shared/event_publisher.py with:
- Function to publish events to EventBridge
- Event schema validation
- Support for custom event patterns
- Batch publishing for efficiency
- Error handling and logging"
```

**Event Schema Example**:
```json
{
  "source": "docprof.documents",
  "detail-type": "document.uploaded",
  "detail": {
    "documentId": "uuid",
    "userId": "uuid",
    "s3Key": "source-docs/document.pdf",
    "timestamp": "2025-12-09T10:00:00Z"
  }
}
```

**Architecture Benefits**:
- Decouples services (upload handler doesn't know about downstream processing)
- Easy to add new consumers (just add new rule)
- Built-in retry and DLQ
- Audit trail of all events

**Validation**:
- Events appear in EventBridge console
- Multiple consumers process same event
- DLQ catches failed events
- Event replay works

### 5.3 CloudWatch Monitoring and Alarms

**Actions**:
1. Create comprehensive dashboard
2. Set up alarms for:
   - Lambda errors (> 5 in 5 minutes)
   - High latency (p95 > 3 seconds)
   - Aurora high CPU (> 80%)
   - High Bedrock costs (> $10/day)
3. Configure SNS for alarm notifications
4. Add X-Ray tracing for distributed debugging

**Cursor prompts**:
```
"Create terraform/modules/cloudwatch/alarms.tf with:
- Alarm for Lambda errors (threshold: 5 in 5 minutes)
- Alarm for API Gateway 5xx responses (threshold: 10 in 5 minutes)
- Alarm for Aurora CPU (threshold: 80% for 10 minutes)
- Alarm for estimated daily cost (threshold: $10)
- SNS topic for alarm notifications (email subscription)
- Actions to take when alarm triggers"

"Create a comprehensive CloudWatch dashboard (JSON format) with:
- Lambda invocations and errors by function
- API Gateway request count and latency (p50, p95, p99)
- Aurora Serverless capacity and connections
- Bedrock token usage and cost estimate
- Polly character usage and cost estimate
- Step Functions execution status
- Time range: last 24 hours with auto-refresh"
```

**X-Ray Integration**:
```python
from aws_xray_sdk.core import xray_recorder

@xray_recorder.capture('process_user_message')
def process_user_message(message: str, session_id: str):
    # X-Ray will automatically trace this function
    # and all downstream calls (Aurora, Bedrock, etc.)
    ...
```

**Validation**:
- Dashboard shows real-time metrics
- Alarms trigger when thresholds exceeded
- SNS sends email notifications
- X-Ray traces show complete request path

### 5.4 Logging Best Practices

**Actions**:
1. Implement structured logging in all Lambdas
2. Set up log retention (7 days dev, 30 days prod)
3. Create CloudWatch Insights queries for:
   - Error investigation
   - Performance analysis
   - Cost attribution
4. Add correlation IDs for request tracing

**Cursor prompts**:
```
"Create src/lambda/shared/logger.py with:
- Structured JSON logging (not print statements)
- Log levels: DEBUG, INFO, WARNING, ERROR
- Automatic inclusion of: timestamp, lambda_request_id, correlation_id
- Helper functions for common log patterns
- Integration with CloudWatch Logs
- Example usage in docstrings"

"Create CloudWatch Logs Insights queries (saved in docs/cloudwatch_queries.md):
1. Find all errors in last 24 hours
2. Find slowest Lambda invocations (p99)
3. Calculate cost per user session
4. Trace a request by correlation_id
5. Identify most commonly called endpoints"
```

**Structured Logging Example**:
```python
import json
import logging

def setup_logger():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Format as JSON
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
    ))
    logger.addHandler(handler)
    return logger

logger = setup_logger()

# Usage
logger.info("Processing message", extra={
    "session_id": session_id,
    "user_id": user_id,
    "message_length": len(message)
})
```

**Validation**:
- All logs are JSON formatted
- Can query logs efficiently
- Correlation IDs work across services
- Log retention policies are set

**Deliverables**:
- Step Functions for document processing
- EventBridge event-driven architecture
- Comprehensive monitoring and alarms
- Structured logging across all services

---

## Phase 6: Frontend Integration (Week 7)

**Goal**: Connect React app to AWS backend

### 6.1 Authentication with Cognito

**Actions**:
1. Create Cognito User Pool
2. Configure password policies and MFA options
3. Add app client for React application
4. Implement authentication in React
5. Configure API Gateway to use Cognito authorizer

**Cursor prompts**:
```
"Create terraform/modules/cognito/main.tf with:
- User pool named 'docprof-users'
- Password policy (min 8 chars, require number and symbol)
- Email verification required
- MFA optional (not required for dev)
- App client for frontend (no client secret for SPA)
- Custom attributes: preferred_depth, preferred_style
- Tags for environment and project"

"Update terraform/modules/api-gateway/main.tf to:
- Add Cognito authorizer to API Gateway
- Require authorization for all endpoints except /auth/*
- Configure JWT validation
- Pass user context to Lambda in request"
```

**Frontend Integration**:
```typescript
// Install AWS Amplify
// npm install aws-amplify

import { Amplify } from 'aws-amplify';

Amplify.configure({
  Auth: {
    region: 'us-east-1',
    userPoolId: 'us-east-1_xxxxx',
    userPoolWebClientId: 'xxxxx',
  },
  API: {
    endpoints: [
      {
        name: 'docprof-api',
        endpoint: 'https://xxxxx.execute-api.us-east-1.amazonaws.com/dev',
        region: 'us-east-1',
      }
    ]
  }
});
```

**Cursor prompts for React**:
```
"Create src/frontend/src/auth/AuthProvider.tsx that:
- Uses AWS Amplify for Cognito authentication
- Provides signIn, signUp, signOut, getCurrentUser functions
- Manages authentication state with React Context
- Handles token refresh automatically
- Includes error handling and loading states
- TypeScript types for user and auth state"

"Create src/frontend/src/auth/ProtectedRoute.tsx that:
- Wraps routes requiring authentication
- Redirects to login if not authenticated
- Shows loading spinner while checking auth
- Passes user info to child components"
```

**Validation**:
- Can create new user account
- Can log in and receive JWT token
- API Gateway validates token
- Token refresh works automatically
- Can log out successfully

### 6.2 API Client Implementation

**Actions**:
1. Create API client using Amplify or fetch
2. Handle authentication headers
3. Implement retry logic
4. Add request/response interceptors
5. WebSocket client for streaming responses

**Cursor prompts**:
```
"Create src/frontend/src/api/client.ts that:
- Uses Amplify API module for authenticated requests
- Helper functions for all API endpoints:
  - sendMessage(message, sessionId)
  - generateCourse(query, hours, prefs)
  - getCourse(courseId)
  - getLecture(lectureId)
  - streamAudio(lectureId)
- Automatic retry on network errors (3 attempts)
- TypeScript types for all request/response objects
- Error handling with user-friendly messages"

"Create src/frontend/src/api/websocket.ts for streaming:
- WebSocket connection to API Gateway WebSocket API
- Subscribe to streaming responses from Bedrock
- Handle connection, message, error, close events
- Reconnection logic on disconnect
- TypeScript types for message formats"
```

**API Client Example**:
```typescript
import { API } from 'aws-amplify';

export async function sendMessage(
  message: string, 
  sessionId?: string
): Promise<ChatResponse> {
  try {
    const response = await API.post('docprof-api', '/chat', {
      body: { message, session_id: sessionId }
    });
    return response;
  } catch (error) {
    console.error('Failed to send message:', error);
    throw new Error('Failed to send message. Please try again.');
  }
}
```

**Validation**:
- Can call all API endpoints from React
- Authentication tokens are included automatically
- Errors are handled gracefully
- WebSocket streaming works

### 6.3 Update React Components

**Actions**:
1. Update ChatInterface to use new API
2. Update LecturePlayer to stream from API Gateway
3. Update CourseGenerator to use new endpoints
4. Add loading states and error handling
5. Test all user workflows

**Cursor prompts**:
```
"Update src/frontend/src/components/ChatInterface.tsx to:
- Use new sendMessage API function
- Handle authentication state
- Show loading spinner while waiting for response
- Display errors in user-friendly way
- Keep existing UI/UX intact
- Add session management (create session on first message)"

"Update src/frontend/src/components/LecturePlayer.tsx to:
- Stream audio from API Gateway instead of local server
- Use HTML5 audio element with API Gateway URL
- Handle authentication for audio endpoint
- Show loading state while audio generates
- Add error handling for Polly failures"
```

**Key Changes**:
- Replace `http://localhost:8000` with API Gateway URL
- Add authentication headers
- Handle different error responses
- Update state management if needed

**Validation**:
- All React components work with AWS backend
- Can chat, generate courses, play lectures
- No console errors
- User experience is smooth

### 6.4 Static Hosting on S3 + CloudFront

**Actions**:
1. Build React app (`npm run build`)
2. Upload build to S3 bucket
3. Configure S3 for static website hosting
4. Create CloudFront distribution
5. Configure custom domain (optional)
6. Set up HTTPS with ACM certificate

**Cursor prompts**:
```
"Create terraform/modules/frontend/main.tf with:
- S3 bucket for static website hosting
- Bucket policy allowing CloudFront access (OAI)
- CloudFront distribution with:
  - Origin pointing to S3 bucket
  - Default cache behavior (cache HTML minimally, assets aggressively)
  - HTTPS only (redirect HTTP to HTTPS)
  - Compress objects automatically
  - Custom error pages (404 -> index.html for SPA routing)
- Optional: Custom domain with Route53 and ACM certificate"

"Create scripts/deploy_frontend.sh that:
- Runs npm run build in frontend directory
- Syncs build/ to S3 bucket
- Invalidates CloudFront cache
- Outputs CloudFront URL
- Includes error handling"
```

**Deployment Process**:
```bash
# Build React app
cd src/frontend
npm run build

# Upload to S3
aws s3 sync build/ s3://docprof-dev-frontend --delete

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id EXXXXXXXXXXXXX \
  --paths "/*"
```

**Custom Domain (Optional)**:
If you want to use timgulden.com:
1. Request ACM certificate for timgulden.com (must be in us-east-1 for CloudFront)
2. Validate certificate via DNS
3. Add custom domain to CloudFront distribution
4. Create Route53 record pointing to CloudFront

**Validation**:
- Can access React app via CloudFront URL
- Authentication works from CloudFront URL
- All API calls succeed
- HTTPS works correctly
- (Optional) Custom domain resolves

**Deliverables**:
- Cognito authentication working
- React app fully integrated with AWS backend
- Static hosting on S3 + CloudFront
- All user workflows functional

---

## Phase 7: Production Readiness (Week 8)

**Goal**: Polish, document, and prepare for demonstration

### 7.1 Security Hardening

**Actions**:
1. Review all IAM policies (least privilege)
2. Enable AWS Config for compliance
3. Enable GuardDuty for threat detection
4. Implement WAF rules for API Gateway
5. Enable encryption everywhere (S3, Aurora, CloudWatch)
6. Document security architecture

**Cursor prompts**:
```
"Review all IAM policies in terraform/modules/iam/ and:
- Identify any overly permissive policies (wildcards in resources)
- Suggest specific ARNs instead of wildcards
- Remove unnecessary permissions
- Add conditions where appropriate (e.g., require MFA)
- Document the principle of least privilege in comments"

"Create terraform/modules/waf/main.tf with:
- WAF WebACL for API Gateway
- Rules to block:
  - SQL injection attempts
  - XSS attempts
  - Rate limiting (1000 requests per IP per 5 minutes)
  - Geographic restrictions (optional, block high-risk countries)
- CloudWatch metrics for WAF blocks
- Associate WebACL with API Gateway"
```

**Security Checklist**:
- [ ] All S3 buckets have encryption enabled
- [ ] Aurora uses encryption at rest
- [ ] All traffic uses HTTPS/TLS
- [ ] IAM roles follow least privilege
- [ ] No hardcoded credentials anywhere
- [ ] Secrets use AWS Secrets Manager
- [ ] CloudTrail logging enabled
- [ ] VPC Flow Logs enabled
- [ ] GuardDuty enabled
- [ ] AWS Config enabled

**Validation**:
- Run AWS Security Hub checks
- Review IAM Access Analyzer findings
- Check S3 bucket public access
- Verify encryption is enabled

### 7.2 Cost Optimization

**Actions**:
1. Analyze current costs by service
2. Identify optimization opportunities:
   - Right-size Lambda memory
   - Optimize Aurora capacity
   - Set S3 lifecycle policies
   - Use S3 Intelligent Tiering
   - Implement caching where possible
3. Set up cost allocation tags
4. Create cost report

**Cursor prompts**:
```
"Create scripts/analyze_costs.py that:
- Uses boto3 Cost Explorer API
- Gets cost breakdown by service for last 30 days
- Identifies top 5 cost drivers
- Compares to previous month
- Outputs as table and chart (matplotlib)
- Suggests optimization opportunities"

"Create a cost optimization report (docs/cost_optimization.md) that:
- Documents current monthly cost estimate
- Breaks down cost by service
- Identifies biggest opportunities:
  - Lambda memory optimization
  - Aurora auto-pause configuration
  - S3 lifecycle policies
  - CloudWatch log retention
- Provides implementation plan for each optimization
- Estimates potential savings"
```

**Cost Optimization Tactics**:
1. **Lambda Memory**: Test with different memory settings (128MB vs 512MB vs 1024MB). Lower memory = lower cost if performance is acceptable.
2. **Aurora Auto-Pause**: Configure to pause after 5 minutes of inactivity.
3. **S3 Lifecycle**: Move to Glacier after 90 days, delete after 1 year.
4. **CloudWatch Logs**: Reduce retention to 7 days for dev.
5. **Bedrock**: Cache common responses to avoid redundant calls.

**Validation**:
- Cost report shows breakdown by service
- Optimizations implemented reduce cost
- Cost stays under $100/month during dev
- Idle cost is ~$10/month

### 7.3 Testing and Quality Assurance

**Actions**:
1. Write unit tests for Lambda functions
2. Write integration tests for API endpoints
3. Load test the system (simulate 50 concurrent users)
4. Test error scenarios (network failures, invalid inputs)
5. Verify monitoring and alerts work

**Cursor prompts**:
```
"Create tests/unit/test_chat_handler.py with:
- Unit tests for chat_handler logic functions
- Mock Aurora, Bedrock, DynamoDB
- Test success cases and error cases
- Use pytest framework
- Aim for >80% code coverage
- Include fixtures for test data"

"Create tests/integration/test_api.py with:
- Integration tests for all API Gateway endpoints
- Use real AWS services (dev environment)
- Test authentication flow
- Test end-to-end user workflows
- Verify response formats and status codes
- Clean up test data after each test"

"Create tests/load/locustfile.py that:
- Uses Locust for load testing
- Simulates 50 concurrent users
- Tests chat, course generation, lecture retrieval
- Measures response times and error rates
- Outputs performance report"
```

**Testing Checklist**:
- [ ] Unit tests pass (>80% coverage)
- [ ] Integration tests pass
- [ ] Load tests show acceptable performance
- [ ] Error handling works correctly
- [ ] Monitoring captures all metrics
- [ ] Alarms trigger appropriately

**Validation**:
- All tests pass in CI/CD pipeline
- Load test shows system can handle target load
- No critical bugs remain

### 7.4 Documentation

**Actions**:
1. Create architecture diagram (use draw.io or Lucidchart)
2. Write deployment guide
3. Document API endpoints (OpenAPI spec)
4. Create runbook for operations
5. Write cost analysis report
6. Create demo script

**Cursor prompts**:
```
"Create docs/architecture.md that:
- Describes high-level architecture with diagram
- Explains each AWS service and its purpose
- Documents data flow for key user workflows
- Includes security architecture (VPC, IAM, encryption)
- Explains cost model and optimization strategies
- Provides troubleshooting guide for common issues"

"Create docs/deployment_guide.md that:
- Step-by-step instructions to deploy from scratch
- Prerequisites (AWS account, Terraform, etc.)
- Environment setup instructions
- Terraform commands to create infrastructure
- Scripts to deploy Lambda functions
- Frontend deployment steps
- How to verify deployment succeeded
- How to tear down infrastructure"
```

**Documentation Checklist**:
- [ ] Architecture diagram is clear and accurate
- [ ] Deployment guide is complete and tested
- [ ] API documentation is up-to-date
- [ ] Runbook covers common operations
- [ ] Cost analysis is documented
- [ ] Demo script is prepared

**Demo Script Outline**:
1. Show CloudFront URL (live React app)
2. Walk through authentication (Cognito)
3. Demo chat with Q&A (show Bedrock in action)
4. Generate a course outline (show multi-phase generation)
5. Play a lecture (show Polly TTS)
6. Open AWS console:
   - Show Lambda functions and logs
   - Show Step Functions workflow
   - Show CloudWatch dashboard
   - Show cost breakdown
7. Explain security architecture (VPC, IAM)
8. Discuss production readiness (monitoring, alarms)

**Deliverables**:
- Hardened security configuration
- Optimized costs
- Comprehensive test suite
- Complete documentation
- Demo-ready system

---

## Implementation Timeline

### Week 1: Infrastructure Foundation
- AWS account setup
- Terraform configuration
- VPC and networking
- IAM roles and policies
- Initial deployment

### Week 2: Data Layer
- Aurora Serverless setup
- S3 bucket configuration
- Data migration
- Performance testing

### Week 3: API Layer
- Lambda function framework
- Core Lambda functions
- API Gateway configuration
- Session management with DynamoDB

### Week 4: AI Services
- Bedrock for LLM (Claude)
- Bedrock for embeddings (Titan)
- Polly for TTS
- Cost monitoring

### Week 5-6: Advanced Patterns
- Step Functions for orchestration
- EventBridge for events
- CloudWatch monitoring
- Logging best practices

### Week 7: Frontend Integration
- Cognito authentication
- API client implementation
- React component updates
- Static hosting on S3 + CloudFront

### Week 8: Production Readiness
- Security hardening
- Cost optimization
- Testing and QA
- Documentation

---

## Key Terraform Modules

Your Terraform project will have these modules:

```
terraform/
├── environments/
│   └── dev/
│       ├── main.tf              # Orchestrates all modules
│       ├── terraform.tfvars     # Environment-specific values
│       ├── backend.tf           # S3 backend for state (optional)
│       └── outputs.tf           # Important outputs (URLs, ARNs)
├── modules/
│   ├── vpc/                     # VPC, subnets, security groups
│   ├── iam/                     # All IAM roles and policies
│   ├── aurora/                  # Aurora Serverless + RDS Proxy
│   ├── s3/                      # All S3 buckets
│   ├── lambda/                  # Lambda functions
│   ├── api-gateway/             # REST and WebSocket APIs
│   ├── cognito/                 # User pool and app client
│   ├── dynamodb/                # Session table
│   ├── step-functions/          # Document processor workflow
│   ├── eventbridge/             # Event bus and rules
│   ├── cloudwatch/              # Dashboards and alarms
│   ├── waf/                     # Web application firewall
│   └── frontend/                # S3 + CloudFront for React
└── shared/
    └── variables.tf             # Common variables
```

**Module Dependencies**:
```
VPC → Aurora, Lambda
IAM → Lambda, Aurora, Step Functions
Lambda → API Gateway, Step Functions, EventBridge
Cognito → API Gateway
S3 → Lambda, CloudFront
```

---

## Development Workflow

### Daily Development Cycle
1. Make changes to code or Terraform
2. Run `terraform plan` to see what will change
3. Run `terraform apply` to update infrastructure
4. Deploy Lambda functions: `./scripts/deploy_lambdas.sh`
5. Test changes via API Gateway
6. Check CloudWatch logs for errors
7. Commit changes to git

### Useful Scripts to Create

```bash
# scripts/deploy_lambdas.sh
# Packages and deploys all Lambda functions

# scripts/test_api.sh
# Tests all API endpoints

# scripts/tail_logs.sh [function-name]
# Streams CloudWatch logs for a function

# scripts/estimate_costs.sh
# Calculates current monthly cost estimate

# scripts/cleanup.sh
# Removes old logs, unused resources
```

### Terraform Commands
```bash
# Initialize Terraform
terraform init

# See what will change
terraform plan

# Apply changes
terraform apply

# Destroy everything (careful!)
terraform destroy

# Format Terraform files
terraform fmt -recursive

# Validate configuration
terraform validate

# Show current state
terraform show

# Get output values
terraform output
```

---

## Troubleshooting Guide

### Common Issues

**Lambda can't connect to Aurora**:
- Check security groups (Lambda SG must allow outbound to Aurora SG)
- Verify Lambda is in correct VPC and subnets
- Check RDS Proxy configuration
- Verify IAM role has RDS connect permission

**API Gateway returns 403 Forbidden**:
- Check Cognito authorizer configuration
- Verify JWT token is valid and not expired
- Check Lambda execution role has permission

**Aurora won't pause**:
- Check if there are active connections (RDS Proxy keeps connection)
- Verify auto-pause is enabled in cluster configuration
- Check if backup or maintenance is running

**High costs**:
- Check CloudWatch Logs retention (reduce to 7 days)
- Verify Aurora is auto-pausing when idle
- Check Bedrock token usage (add caching if high)
- Look for stuck Step Functions executions

**Lambda timeout**:
- Increase timeout (max 15 minutes)
- Check if waiting on slow external API
- Consider breaking into smaller functions
- Use Step Functions for long-running tasks

### Debugging Tools

**CloudWatch Logs Insights Queries**:
```sql
-- Find all errors in last hour
fields @timestamp, @message
| filter @message like /ERROR/
| sort @timestamp desc
| limit 100

-- Find slow Lambda invocations
fields @timestamp, @duration
| filter @duration > 3000
| sort @duration desc

-- Trace request by correlation ID
fields @timestamp, @message
| filter correlation_id = "xxx-xxx-xxx"
| sort @timestamp asc
```

**AWS CLI Debug Commands**:
```bash
# Get Lambda function configuration
aws lambda get-function --function-name chat-handler

# Invoke Lambda manually
aws lambda invoke \
  --function-name chat-handler \
  --payload '{"message": "test"}' \
  response.json

# Get Step Functions execution details
aws stepfunctions describe-execution \
  --execution-arn arn:aws:states:...

# Query DynamoDB
aws dynamodb get-item \
  --table-name docprof-sessions \
  --key '{"session_id": {"S": "xxx-xxx-xxx"}}'
```

---

## Cost Estimation

### Expected Costs During Development (Active Month)

| Service | Usage | Cost |
|---------|-------|------|
| Aurora Serverless | 4 hours/day active, 20 hours/day paused | $30-40 |
| Lambda | 10K invocations/day | $0-2 |
| API Gateway | 10K requests/day | $0-1 |
| Bedrock Claude | 100K tokens/day (50K in, 50K out) | $15-20 |
| Bedrock Titan | 100K tokens/day | $1-2 |
| Polly | 100K characters/day | $2-3 |
| S3 | 10GB storage, 1K requests/day | $1-2 |
| CloudFront | 100GB transfer | $0-1 |
| DynamoDB | 10K reads/writes/day | $1-2 |
| CloudWatch | Logs + metrics + dashboards | $5-10 |
| **Total** | | **~$55-85/month** |

### Expected Costs When Idle (No Usage)

| Service | Cost |
|---------|------|
| Aurora Serverless | $0 (paused) |
| S3 Storage | $1-2 |
| CloudWatch Logs | $2-5 |
| Other (minimal charges) | $2-5 |
| **Total** | **~$5-12/month** |

### Cost Optimization Checklist
- [ ] Aurora configured to auto-pause after 5 minutes
- [ ] CloudWatch log retention set to 7 days
- [ ] S3 lifecycle policies configured
- [ ] Lambda memory right-sized (test with different settings)
- [ ] Bedrock response caching implemented
- [ ] Development resources deleted when not in use

---

## Success Criteria

You'll know you've succeeded when you can demonstrate:

1. **Working System**: All features from local version work on AWS
2. **Security**: Proper IAM, VPC, encryption throughout
3. **Scalability**: Can handle 10x load without code changes
4. **Cost Efficiency**: Stays under budget
5. **Monitoring**: Comprehensive observability via CloudWatch
6. **Infrastructure as Code**: Full stack defined in Terraform
7. **Documentation**: Clear architecture and deployment docs

---

## Next Steps

### Immediate Actions (This Week)

1. **Create AWS Account**
   - Go to aws.amazon.com/console
   - Sign up with email (use tim@timgulden.com)
   - Add payment method
   - Enable MFA on root account

2. **Set Up Development Environment**
   - Install AWS CLI: `brew install awscli`
   - Install Terraform: `brew install terraform`
   - Configure AWS credentials: `aws configure`
   - Clone your existing DocProf repo

3. **Create Project Structure**
   - Create `docprof-aws/` directory
   - Set up Terraform folder structure (see above)
   - Copy existing code to `src/` directory

4. **Start with Phase 1**
   - Follow Phase 1 step by step
   - Use Cursor to generate Terraform modules
   - Deploy VPC and networking first
   - Document any issues or learnings

### Questions to Resolve

Before starting, confirm:
- AWS region to use (us-east-1 recommended for Bedrock availability)
- Do you want a custom domain for the demo? (optional)
- Cost budget approval ($50-100 during dev, $10-15 idle)
- Timeline flexibility (can adapt if needed)

### Getting Help

**Cursor Prompting Strategy**:
1. Reference this document in your prompts
2. Ask for one module at a time
3. Review generated code carefully
4. Test each component before moving on
5. Update this document with learnings

**Example Cursor Session**:
```
User: "I'm working on Phase 1 of the DocProf AWS migration. 
Please create the VPC module at terraform/modules/vpc/main.tf 
following the specifications in the migration guide. Include 
public and private subnets, NAT gateway, and VPC endpoints 
for S3 and Bedrock."

[Cursor generates code]

User: "Now create the security groups in 
terraform/modules/vpc/security_groups.tf with proper 
least-privilege rules for Lambda accessing Aurora."

[Continue iteratively]
```

**Resources**:
- AWS Documentation: docs.aws.amazon.com
- Terraform AWS Provider: registry.terraform.io/providers/hashicorp/aws
- AWS CLI Reference: docs.aws.amazon.com/cli
- This guide: `DocProf_AWS_Migration_Guide.md`

---

## Appendix A: Technology Substitutions

### Why AWS Services vs Open Source

| Function | Current | AWS Alternative | Reason for Change |
|----------|---------|----------------|-------------------|
| LLM API | Anthropic | Bedrock (Claude) | Government compliance, AWS integration |
| Embeddings | OpenAI | Bedrock (Titan) | Consistency with AWS stack |
| TTS | OpenAI | Polly Neural | AWS integration, cost |
| Compute | FastAPI server | Lambda | Serverless benefits, cost efficiency |
| Database | PostgreSQL | Aurora Serverless | Auto-scaling, managed service |
| Storage | Local/basic S3 | S3 with features | Lifecycle, events, encryption |
| Auth | Custom/JWT | Cognito | Managed service, MFA, SSO ready |

### Feature Parity Verification

| Feature | Local Version | AWS Version | Status |
|---------|--------------|-------------|--------|
| Chat Q&A | âœ" FastAPI + Anthropic | âœ" Lambda + Bedrock | Equivalent |
| Vector search | âœ" pgvector | âœ" Aurora pgvector | Equivalent |
| Course generation | âœ" Multi-phase LLM | âœ" Same logic in Lambda | Equivalent |
| Lectures | âœ" OpenAI TTS | âœ" Polly (needs voice testing) | May differ in quality |
| Figure retrieval | âœ" Local chunks | âœ" S3 + Aurora | Equivalent |
| Progress tracking | âœ" PostgreSQL | âœ" Aurora + DynamoDB | Equivalent |
| Authentication | âœ" JWT | âœ" Cognito JWT | Enhanced (MFA) |

---

## Appendix B: Terraform Module Templates

### VPC Module Structure
```
modules/vpc/
├── main.tf           # VPC, subnets, IGW, NAT
├── security_groups.tf # Security groups
├── endpoints.tf      # VPC endpoints
├── variables.tf      # Input variables
├── outputs.tf        # VPC ID, subnet IDs, etc.
└── README.md         # Module documentation
```

### Lambda Module Structure
```
modules/lambda/
├── main.tf           # Lambda function resource
├── iam.tf            # Execution role and policies
├── cloudwatch.tf     # Log group and alarms
├── variables.tf      # Function name, runtime, etc.
├── outputs.tf        # Function ARN, etc.
└── README.md
```

### Reusable Patterns

**Lambda Function Template**:
```hcl
resource "aws_lambda_function" "this" {
  function_name = var.function_name
  runtime       = "python3.11"
  handler       = "handler.lambda_handler"
  role          = aws_iam_role.lambda.arn
  
  filename         = var.zip_file
  source_code_hash = filebase64sha256(var.zip_file)
  
  timeout     = var.timeout
  memory_size = var.memory_size
  
  vpc_config {
    subnet_ids         = var.subnet_ids
    security_group_ids = var.security_group_ids
  }
  
  environment {
    variables = var.environment_variables
  }
  
  tags = var.tags
}
```

---

## Appendix C: Useful AWS CLI Commands

### Lambda
```bash
# List functions
aws lambda list-functions

# Get function details
aws lambda get-function --function-name my-function

# Update function code
aws lambda update-function-code \
  --function-name my-function \
  --zip-file fileb://function.zip

# Invoke function
aws lambda invoke \
  --function-name my-function \
  --payload '{"key":"value"}' \
  output.json
```

### CloudWatch
```bash
# Tail logs (requires AWS CLI v2)
aws logs tail /aws/lambda/my-function --follow

# Run Insights query
aws logs start-query \
  --log-group-name /aws/lambda/my-function \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, @message | filter @message like /ERROR/'
```

### S3
```bash
# List buckets
aws s3 ls

# Sync directory to bucket
aws s3 sync ./build s3://my-bucket --delete

# Copy file
aws s3 cp file.pdf s3://my-bucket/docs/
```

### RDS
```bash
# Describe Aurora cluster
aws rds describe-db-clusters --db-cluster-identifier my-cluster

# Check if cluster is paused
aws rds describe-db-clusters \
  --query 'DBClusters[0].Status'
```

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Dec 9, 2025 | Initial version - complete migration guide |

---

**End of DocProf AWS Migration Guide**

This guide should provide everything you need to work with Cursor on the AWS migration. Start with Phase 1 and work through systematically. Update this document with any learnings or changes as you go.

Good luck with the migration! The AWS experience you gain will be valuable for the Transcend role and beyond.
