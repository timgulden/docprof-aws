# UI Setup Context Guide

**Purpose**: Essential documents for setting up the React frontend to work with the AWS backend.

## 🎯 Start Here

### 1. Project Overview
**`docs/reference/CONTEXT_SUMMARY.md`**
- What DocProf is and how it works
- Key features (chat, courses, lectures, quizzes)
- Current state of the system

### 2. Architecture Mapping
**`docs/architecture/FP_to_Serverless_Mapping.md`**
- How MAExpert's functional programming patterns map to AWS services
- Understanding the backend structure (Lambda, API Gateway, Aurora)
- How effects layer works in serverless context

### 3. Current Infrastructure State
**`docs/deployment/System_Ready.md`**
- What's deployed and working
- API Gateway endpoints available
- Database schema status

## 📡 API & Backend

### API Endpoints
- **API Gateway Base URL**: Check Terraform outputs (`terraform/environments/dev/terraform.tfstate`)
- **Endpoints Available**:
  - `POST /books/upload` - Book upload (currently direct S3 upload)
  - `POST /ai-services/enable` - Enable AI services (VPC endpoints)
  - `POST /ai-services/disable` - Disable AI services
  - `GET /ai-services/status` - Check AI services status

### Database Schema
**`src/lambda/schema_init/handler.py`** - See CREATE TABLE statements
- `books` - Book metadata
- `chunks` - Text chunks with embeddings (chapter, 2page, figure)
- `figures` - Extracted figures with images
- `chapter_documents` - Full chapter text
- `users`, `user_progress`, `quizzes`, `sessions` - User data (not yet implemented)

## 🔧 What's Working

### ✅ Completed
- **Infrastructure**: VPC, Aurora, Lambda, API Gateway, S3
- **Document Ingestion**: PDF upload → processing → database storage
- **Bedrock Integration**: Claude Sonnet 4.5 for LLM, Titan for embeddings
- **Database**: Schema initialized, ingestion working

### 🚧 In Progress
- **Ingestion**: Currently processing Valuation book (first full run)
- **Figure Extraction**: Enabled, using Bedrock for classification

### 📋 TODO (For UI)
- **Chat API**: `POST /chat` endpoint (needs Lambda handler)
- **Course API**: `GET/POST /courses` endpoints (needs Lambda handlers)
- **Retrieval API**: Vector search for chunks (needs Lambda handler)
- **Authentication**: Cognito integration (not yet implemented)

## 📚 Key Code Locations

### Backend (Lambda)
- **`src/lambda/document_processor/`** - PDF ingestion pipeline
- **`src/lambda/shared/`** - Shared utilities (DB, Bedrock, protocols)
- **`src/lambda/book_upload/`** - Book upload handler (API Gateway)

### Frontend (React)
- **`src/frontend/`** - React app (to be migrated/updated)
- Reference MAExpert frontend: `../MAExpert/mna-expert-frontend/`

### Infrastructure
- **`terraform/environments/dev/main.tf`** - Main infrastructure config
- **`terraform/modules/api-gateway/`** - API Gateway module

## 🔗 Related Documents

### Migration & Architecture
- **`docs/DocProf_AWS_Migration_Guide.md`** - Full migration plan (reference)
- **`docs/architecture/FP_to_Serverless_Mapping.md`** - Architecture patterns
- **`docs/contracts/README.md`** - API contracts (to be extracted from MAExpert)

### Deployment Status
- **`docs/deployment/System_Ready.md`** - Current system status
- **`docs/deployment/Schema_Comparison_Results.md`** - Database schema verification
- **`docs/deployment/Model_Selection.md`** - LLM model decisions

### Reference (MAExpert)
- **`../MAExpert/mna-expert-frontend/`** - Original React frontend
- **`../MAExpert/src/api/routes/`** - Original API routes (reference)

## 🎨 UI Development Priorities

1. **Connect to API Gateway** - Update API base URL
2. **Book Upload UI** - Already works (direct S3 upload)
3. **Chat Interface** - Needs `/chat` endpoint
4. **Course Generation** - Needs `/courses` endpoints
5. **Source Management** - Display ingested books/chapters

## 💡 Quick Reference

### Environment Variables (Frontend)
```bash
REACT_APP_API_URL=https://<api-id>.execute-api.us-east-1.amazonaws.com/dev
REACT_APP_REGION=us-east-1
```

### API Gateway Structure
```
/dev/
  ├── books/
  │   └── upload (POST)
  └── ai-services/
      ├── enable (POST)
      ├── disable (POST)
      └── status (GET)
```

### Database Connection
- **Endpoint**: Aurora Serverless PostgreSQL (private subnet)
- **Access**: Via Lambda functions only (no direct frontend access)
- **Schema**: See `src/lambda/schema_init/handler.py`

## 📝 Notes

- **CORS**: API Gateway has CORS enabled for frontend
- **Authentication**: Not yet implemented (will use Cognito)
- **File Upload**: Books upload directly to S3 (bypasses API Gateway 10MB limit)
- **Real-time**: Use CloudWatch logs or polling for ingestion status

---

**Last Updated**: December 11, 2025  
**Status**: Infrastructure ready, ingestion in progress, UI integration pending

