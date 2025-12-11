# UI-Driven Ingestion Setup Complete ✅

**Status**: Ready for deployment  
**Date**: 2025-01-XX

## What's Been Set Up

### 1. API Gateway Module ✅
- **Location**: `terraform/modules/api-gateway/`
- **Features**:
  - REST API with CORS support
  - Binary media type support (PDF uploads)
  - CloudWatch logging
  - Lambda proxy integration

### 2. Book Upload Lambda ✅
- **Function**: `docprof-dev-book-upload`
- **Handler**: `handler.lambda_handler`
- **Runtime**: Python 3.11
- **Memory**: 256 MB
- **Timeout**: 60 seconds
- **Permissions**: S3 write access, Secrets Manager read

### 3. Document Processor Lambda ✅
- **Function**: `docprof-dev-document-processor`
- **Handler**: `handler.lambda_handler`
- **Runtime**: Python 3.11
- **Memory**: 1024 MB
- **Timeout**: 900 seconds (15 minutes)
- **Trigger**: S3 event notification

### 4. S3 Event Notification ✅
- **Bucket**: `docprof-dev-source-docs`
- **Event**: `s3:ObjectCreated:*`
- **Filter**: Prefix `books/`, Suffix `.pdf`
- **Target**: Document Processor Lambda

## Architecture Flow

```
Frontend UI
    ↓
POST /books/upload (with PDF + metadata)
    ↓
API Gateway
    ↓
Book Upload Lambda
    ├─ Upload PDF to S3 (books/{book_id}/title.pdf)
    ├─ Store metadata in S3 object metadata
    └─ Return book_id
    ↓
S3 Event Notification (automatic)
    ↓
Document Processor Lambda
    ├─ Extract text & figures (PyMuPDF)
    ├─ Chunk content
    ├─ Generate embeddings (Bedrock Titan)
    ├─ Describe figures (Bedrock Claude)
    └─ Store in Aurora PostgreSQL
```

## API Endpoint

**URL**: `https://{api-id}.execute-api.{region}.amazonaws.com/dev/books/upload`

**Method**: `POST`

**Headers**:
- `Content-Type`: `application/pdf` or `multipart/form-data`
- `X-Book-Title`: Book title (required)
- `X-Book-Author`: Author name (optional)
- `X-Book-Edition`: Edition (optional)
- `X-Book-Isbn`: ISBN (optional)

**Body**: PDF file (base64 encoded or binary)

**Response**:
```json
{
  "statusCode": 200,
  "body": {
    "book_id": "uuid",
    "s3_key": "books/uuid/title_timestamp.pdf",
    "status": "uploaded",
    "message": "Book uploaded successfully. Ingestion will begin automatically.",
    "metadata": {
      "book_id": "uuid",
      "title": "Book Title",
      "author": "Author Name",
      "edition": "1st",
      "isbn": "1234567890",
      "s3_key": "books/uuid/title_timestamp.pdf",
      "status": "uploaded",
      "uploaded_at": "2025-01-XXT..."
    }
  }
}
```

## Frontend Integration

### React/TypeScript Example

```typescript
async function uploadBook(file: File, metadata: BookMetadata): Promise<UploadResponse> {
  const apiUrl = process.env.REACT_APP_API_URL; // From Terraform output
  
  // Read file as base64
  const base64 = await fileToBase64(file);
  
  const response = await fetch(`${apiUrl}/books/upload`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/pdf',
      'X-Book-Title': metadata.title,
      'X-Book-Author': metadata.author || '',
      'X-Book-Edition': metadata.edition || '',
      'X-Book-Isbn': metadata.isbn || '',
    },
    body: base64,
  });
  
  if (!response.ok) {
    throw new Error(`Upload failed: ${response.statusText}`);
  }
  
  return response.json();
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => {
      const base64 = (reader.result as string).split(',')[1];
      resolve(base64);
    };
    reader.onerror = error => reject(error);
  });
}

interface BookMetadata {
  title: string;
  author?: string;
  edition?: string;
  isbn?: string;
}

interface UploadResponse {
  book_id: string;
  s3_key: string;
  status: string;
  message: string;
  metadata: {
    book_id: string;
    title: string;
    author?: string;
    edition?: string;
    isbn?: string;
    s3_key: string;
    status: string;
    uploaded_at: string;
  };
}
```

### Alternative: Multipart Form Data

```typescript
async function uploadBookMultipart(file: File, metadata: BookMetadata): Promise<UploadResponse> {
  const apiUrl = process.env.REACT_APP_API_URL;
  
  const formData = new FormData();
  formData.append('file', file);
  formData.append('title', metadata.title);
  formData.append('author', metadata.author || '');
  formData.append('edition', metadata.edition || '');
  formData.append('isbn', metadata.isbn || '');
  
  const response = await fetch(`${apiUrl}/books/upload`, {
    method: 'POST',
    body: formData,
    // Don't set Content-Type header - browser will set it with boundary
  });
  
  if (!response.ok) {
    throw new Error(`Upload failed: ${response.statusText}`);
  }
  
  return response.json();
}
```

## Deployment Steps

### 1. Deploy Infrastructure

```bash
cd terraform/environments/dev
terraform apply -var="enable_ai_endpoints=false"
```

**Note**: Enable AI endpoints when ready to process books:
```bash
./scripts/enable-ai-services.sh
```

### 2. Get API Gateway URL

```bash
terraform output book_upload_endpoint
# Output: https://{api-id}.execute-api.{region}.amazonaws.com/dev/books/upload
```

### 3. Configure Frontend

Add to your `.env` file:
```
REACT_APP_API_URL=https://{api-id}.execute-api.{region}.amazonaws.com/dev
```

### 4. Upload Books via UI

1. Navigate to book upload page in frontend
2. Select PDF file
3. Enter book metadata (title required, others optional)
4. Click "Upload"
5. Wait for confirmation message
6. Ingestion will begin automatically

## Monitoring

### Check Upload Status

```bash
# Check CloudWatch logs for book upload Lambda
aws logs tail /aws/lambda/docprof-dev-book-upload --follow

# Check CloudWatch logs for document processor Lambda
aws logs tail /aws/lambda/docprof-dev-document-processor --follow
```

### Check S3 Upload

```bash
# List uploaded books
aws s3 ls s3://docprof-dev-source-docs/books/ --recursive

# Check specific book metadata
aws s3api head-object \
  --bucket docprof-dev-source-docs \
  --key books/{book_id}/title.pdf
```

### Check Database

```bash
# Connect to Aurora and check books table
psql -h {cluster-endpoint} -U docprof_admin -d docprof
SELECT book_id, title, author, created_at FROM books ORDER BY created_at DESC;
```

## Troubleshooting

### Upload Fails

1. **Check API Gateway logs**: CloudWatch → Log Groups → `/aws/apigateway/docprof-dev-api`
2. **Check Lambda logs**: CloudWatch → Log Groups → `/aws/lambda/docprof-dev-book-upload`
3. **Verify CORS**: Check browser console for CORS errors
4. **Verify file size**: API Gateway has 10MB limit by default (can be increased)

### Ingestion Doesn't Start

1. **Check S3 event notification**: Verify Lambda trigger is configured
2. **Check Lambda permissions**: Verify S3 can invoke document processor
3. **Check document processor logs**: CloudWatch → Log Groups → `/aws/lambda/docprof-dev-document-processor`
4. **Verify file format**: Must be `.pdf` in `books/` prefix

### Processing Fails

1. **Check AI endpoints**: Must be enabled for Bedrock access
2. **Check VPC**: Document processor needs VPC access
3. **Check database**: Verify Aurora is accessible from Lambda
4. **Check memory/timeout**: Large books may need more resources

## Next Steps

1. **Deploy infrastructure** (see above)
2. **Test upload** with a small PDF first
3. **Monitor ingestion** via CloudWatch logs
4. **Verify database** records are created
5. **Test vector search** on ingested content

## Cost Estimate

**Per Book Upload**:
- API Gateway: $0.00 (first 1M requests/month free)
- Lambda (upload): ~$0.0000002 per request
- Lambda (processing): ~$0.01-0.10 per book (depending on size)
- S3 storage: ~$0.023 per GB/month
- Bedrock: ~$0.0001 per 1K tokens (embeddings + figure descriptions)

**Total per book**: ~$0.01-0.15 depending on book size

## Security Notes

⚠️ **Current Configuration**:
- API Gateway has no authentication (open to public)
- CORS allows all origins (`*`)

🔒 **Production Recommendations**:
- Add Cognito authentication to API Gateway
- Restrict CORS to specific frontend domain
- Add API key or rate limiting
- Enable WAF for DDoS protection

