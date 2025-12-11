# UI-Driven Ingestion Infrastructure Plan

**Goal**: Enable book ingestion through the frontend interface

## Architecture Flow

```
Frontend (React)
    ↓ (POST /api/books/upload)
API Gateway
    ↓
Book Upload Lambda
    ├─ Upload PDF to S3 (source-docs bucket)
    ├─ Create book metadata record
    └─ Return book_id
    ↓
S3 Event Notification
    ↓
Document Processor Lambda
    ├─ Extract text & figures
    ├─ Chunk content
    ├─ Generate embeddings (Bedrock Titan)
    └─ Store in Aurora
```

## Components Needed

### 1. Book Upload Lambda (`src/lambda/book_upload/`)
**Status**: ✅ Created

**Responsibilities**:
- Receive PDF upload from API Gateway
- Upload PDF to S3 source-docs bucket
- Create initial book metadata record
- Return book_id and status

**Input**: Multipart form data or base64 PDF + metadata headers

**Output**: 
```json
{
  "book_id": "uuid",
  "s3_key": "books/uuid/title_timestamp.pdf",
  "status": "uploaded",
  "message": "Book uploaded successfully. Ingestion will begin automatically."
}
```

### 2. Document Processor Lambda (`src/lambda/document_processor/`)
**Status**: ⚠️ Structure created, implementation pending

**Responsibilities**:
- Triggered by S3 event (PDF upload)
- Extract text from PDF (PyMuPDF)
- Extract figures (PyMuPDF + PIL)
- Chunk text (chapter, 2-page, figure)
- Generate embeddings (Bedrock Titan)
- Store in Aurora PostgreSQL

**Input**: S3 event notification
```json
{
  "Records": [{
    "s3": {
      "bucket": {"name": "docprof-dev-source-docs"},
      "object": {"key": "books/uuid/title.pdf"}
    }
  }]
}
```

### 3. API Gateway Configuration
**Status**: ⚠️ Pending

**Endpoints**:
- `POST /api/books/upload` → Book Upload Lambda
- `GET /api/books` → List books (future)
- `GET /api/books/{bookId}` → Get book details (future)
- `GET /api/books/{bookId}/status` → Get ingestion status (future)

**Configuration**:
- Binary media types: `application/pdf`, `multipart/form-data`
- CORS enabled for frontend
- Request size limit: 100MB (for large PDFs)

### 4. S3 Event Notification
**Status**: ⚠️ Pending (S3 bucket exists, notification not configured)

**Configuration**:
- Bucket: `docprof-dev-source-docs`
- Event: `s3:ObjectCreated:*`
- Prefix: `books/`
- Suffix: `.pdf`
- Destination: Document Processor Lambda

## Implementation Steps

### Step 1: Complete Book Upload Lambda ✅
- [x] Create handler structure
- [x] Add S3 upload logic
- [ ] Add database book record creation
- [ ] Add error handling
- [ ] Add input validation

### Step 2: Complete Document Processor Lambda ⚠️
- [x] Create structure
- [ ] Implement PDF extraction
- [ ] Implement chunking logic
- [ ] Implement embedding generation
- [ ] Implement database storage
- [ ] Add error handling and retries

### Step 3: Create API Gateway Module ⚠️
- [ ] Create Terraform module
- [ ] Configure `/api/books/upload` endpoint
- [ ] Set up Lambda integration
- [ ] Configure CORS
- [ ] Set binary media types

### Step 4: Configure S3 Event Notification ⚠️
- [ ] Add S3 event notification to Terraform
- [ ] Configure Lambda trigger
- [ ] Test event delivery

### Step 5: Deploy and Test ⚠️
- [ ] Deploy all infrastructure
- [ ] Test book upload via API
- [ ] Verify S3 event triggers Lambda
- [ ] Verify document processing completes
- [ ] Verify data in database

## Testing Strategy

### Unit Tests
- Test book upload handler with mock events
- Test document processor with sample PDFs
- Test database operations

### Integration Tests
- Upload PDF via API Gateway
- Verify S3 upload succeeds
- Verify S3 event triggers document processor
- Verify database records created

### End-to-End Test
1. Frontend uploads PDF via `/api/books/upload`
2. Verify PDF in S3
3. Verify book metadata in database
4. Wait for document processor to complete
5. Verify chunks and embeddings in database
6. Test vector search on ingested content

## Frontend Integration

The frontend will need:

```typescript
// Upload book function
async function uploadBook(file: File, metadata: BookMetadata) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('title', metadata.title);
  formData.append('author', metadata.author);
  formData.append('edition', metadata.edition);
  formData.append('isbn', metadata.isbn);
  
  const response = await fetch(`${API_BASE_URL}/api/books/upload`, {
    method: 'POST',
    body: formData,
    headers: {
      // Auth headers will be added by Amplify
    }
  });
  
  return response.json();
}

// Poll for ingestion status
async function checkIngestionStatus(bookId: string) {
  const response = await fetch(`${API_BASE_URL}/api/books/${bookId}/status`);
  return response.json();
}
```

## Next Steps

1. Complete document processor Lambda implementation
2. Create API Gateway Terraform module
3. Configure S3 event notifications
4. Deploy and test end-to-end
5. Add ingestion status polling endpoint

