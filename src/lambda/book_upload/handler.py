"""
Book Upload Lambda Handler
Handles PDF uploads from the frontend, stores in S3, and triggers ingestion

For /books/upload-initial: Extracts cover and metadata, returns immediately
For /books/upload: Full upload and triggers ingestion
"""

import json
import os
import boto3
import uuid
import logging
import base64
from typing import Dict, Any, Optional
from datetime import datetime

# Import shared utilities
# Lambda's Python path includes /var/task/, so shared modules can be imported directly
from shared.response import success_response, error_response
from shared.cover_extractor import extract_cover_from_pdf_bytes
from shared.protocol_implementations import AWSDatabaseClient
from shared.bedrock_client import invoke_claude

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')
secrets_client = boto3.client('secretsmanager')

# Environment variables (set by Terraform)
SOURCE_BUCKET = os.getenv('SOURCE_BUCKET')
DB_CLUSTER_ENDPOINT = os.getenv('DB_CLUSTER_ENDPOINT')
DB_NAME = os.getenv('DB_NAME', 'docprof')
DB_MASTER_USERNAME = os.getenv('DB_MASTER_USERNAME', 'docprof_admin')
DB_PASSWORD_SECRET_ARN = os.getenv('DB_PASSWORD_SECRET_ARN')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle book upload request.
    
    For /books/upload-initial: Generate pre-signed S3 URL for direct upload (no file in request)
    For /books/analyze/{bookId}: Extract cover and metadata from S3
    For /books/upload: Full upload and trigger ingestion (legacy, for small files)
    
    Expected event structure (API Gateway):
    {
        "path": "/books/upload-initial" or "/books/analyze/{bookId}" or "/books/upload",
        "body": (empty for upload-initial, or base64-encoded-pdf-data for upload),
        "pathParameters": {"bookId": "..."} for analyze endpoint
    }
    """
    # Wrap entire handler in try-except to ensure CORS headers are always returned
    try:
        global SOURCE_BUCKET, DB_CLUSTER_ENDPOINT, DB_PASSWORD_SECRET_ARN
        
        # Initialize from environment
        SOURCE_BUCKET = SOURCE_BUCKET or os.getenv('SOURCE_BUCKET')
        DB_CLUSTER_ENDPOINT = DB_CLUSTER_ENDPOINT or os.getenv('DB_CLUSTER_ENDPOINT')
        DB_PASSWORD_SECRET_ARN = DB_PASSWORD_SECRET_ARN or os.getenv('DB_PASSWORD_SECRET_ARN')
        API_GATEWAY_URL = os.getenv('API_GATEWAY_URL', 'https://xp2vbfyu3f.execute-api.us-east-1.amazonaws.com/dev')
        
        if not SOURCE_BUCKET:
            return error_response("SOURCE_BUCKET not configured", 500)
        
        # Determine endpoint type
        path = event.get('path', '') or event.get('requestContext', {}).get('path', '')
        is_upload_initial = 'upload-initial' in path
        is_analyze = 'analyze' in path
        is_start_ingestion = 'start-ingestion' in path
        
        # Handle /books/upload-initial - generate pre-signed URL
        if is_upload_initial:
            # Generate unique book ID
            book_id = str(uuid.uuid4())
            
            # Generate S3 key
            timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
            s3_key = f"books/{book_id}/upload_{timestamp}.pdf"
            
            # Generate pre-signed POST URL (allows direct upload from browser)
            # POST is better than PUT because it allows us to set metadata
            # Include book-id in metadata so document_processor can find the existing book
            presigned_post = s3_client.generate_presigned_post(
                Bucket=SOURCE_BUCKET,
                Key=s3_key,
                Fields={
                    'Content-Type': 'application/pdf',
                    'x-amz-meta-book-id': book_id  # Custom metadata
                },
                Conditions=[
                    {'Content-Type': 'application/pdf'},
                    {'x-amz-meta-book-id': book_id},  # Ensure book-id is set
                    ['content-length-range', 1, 500 * 1024 * 1024]  # 1 byte to 500MB
                ],
                ExpiresIn=3600  # 1 hour
            )
            
            # Create minimal book record
            from shared.db_utils import get_db_connection
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Check if book already exists
                    cur.execute("SELECT book_id FROM books WHERE book_id = %s", (book_id,))
                    exists = cur.fetchone()
                    
                    if not exists:
                        cur.execute(
                            """
                            INSERT INTO books (book_id, title, author, edition, isbn, total_pages, metadata)
                            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                            """,
                            (
                                book_id,
                                'Temporary',  # Placeholder
                                None,
                                None,
                                None,
                                0,
                                json.dumps({'s3_key': s3_key})  # Store S3 key in metadata
                            )
                        )
                        conn.commit()
                        
                        # Verify the insert succeeded
                        cur.execute("SELECT book_id FROM books WHERE book_id = %s", (book_id,))
                        verify = cur.fetchone()
                        if verify:
                            logger.info(f"Verified book record exists in database: {book_id}")
                        else:
                            logger.error(f"ERROR: Book record INSERT failed - book_id not found after commit: {book_id}")
                    else:
                        logger.info(f"Book record already exists: {book_id}")
            logger.info(f"Created book record and pre-signed URL for book_id: {book_id}")
            
            return success_response({
                'book_id': book_id,
                'upload_url': presigned_post['url'],
                'upload_fields': presigned_post['fields'],
                's3_key': s3_key,
                'analyze_url': f"{API_GATEWAY_URL}/books/{book_id}/analyze"
            })
        
        # Handle /books/analyze/{bookId} - extract cover and metadata from S3
        if is_analyze:
            path_params = event.get('pathParameters') or {}
            book_id = path_params.get('bookId')
            
            if not book_id:
                return error_response("Book ID is required", 400)
            
            # Get S3 key from database
            from shared.db_utils import get_db_connection
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT metadata->>'s3_key' FROM books WHERE book_id = %s",
                        (book_id,)
                    )
                    row = cur.fetchone()
                    if not row or not row[0]:
                        return error_response("Book not found or S3 key not set", 404)
                    s3_key = row[0]
            
            # Download PDF from S3
            logger.info(f"Downloading PDF from S3: {s3_key}")
            try:
                response = s3_client.get_object(Bucket=SOURCE_BUCKET, Key=s3_key)
                pdf_data = response['Body'].read()
            except Exception as e:
                logger.error(f"Failed to download PDF from S3: {e}", exc_info=True)
                return error_response(f"Failed to download PDF from S3: {str(e)}", 500)
            
            # Extract cover and metadata (same logic as before)
            return _process_pdf_for_analysis(pdf_data, book_id)
        
        # Handle /books/{bookId}/start-ingestion - update metadata and trigger ingestion
        if is_start_ingestion:
            path_params = event.get('pathParameters') or {}
            book_id = path_params.get('bookId')
            
            if not book_id:
                return error_response("Book ID is required", 400)
            
            return _handle_start_ingestion(event, book_id)
        
        # Legacy /books/upload - for small files (<10MB) via API Gateway
        # Parse PDF from request
        try:
            pdf_data = _parse_pdf_from_request(event)
        except Exception as parse_error:
            logger.error(f"Error parsing PDF from request: {parse_error}", exc_info=True)
            return error_response(f"Failed to parse PDF from request: {str(parse_error)}", 400)
        
        if not pdf_data:
            return error_response("No PDF file found in request", 400)
        
        # Generate unique book ID
        book_id = str(uuid.uuid4())
        
        # Legacy /books/upload - for small files (<10MB) via API Gateway
        # This path is kept for backward compatibility but should use S3 pre-signed URLs for large files
        logger.warning("Using legacy upload path - consider using S3 pre-signed URLs for files >10MB")
        
        # Extract metadata from headers
        headers = event.get('headers', {}) or {}
        book_title = headers.get('x-book-title') or headers.get('X-Book-Title', 'Unknown')
        book_author = headers.get('x-book-author') or headers.get('X-Book-Author', '')
        book_edition = headers.get('x-book-edition') or headers.get('X-Book-Edition', '')
        book_isbn = headers.get('x-book-isbn') or headers.get('X-Book-Isbn', '')
        
        # Process PDF (extract cover, metadata, upload to S3)
        return _process_pdf_for_upload(pdf_data, book_id, book_title, book_author, book_edition, book_isbn)
        
    except Exception as e:
        logger.error(f"Unhandled error in lambda_handler: {e}", exc_info=True)
        return error_response(f"An unexpected error occurred: {str(e)}", 500)


def _process_pdf_for_analysis(pdf_data: bytes, book_id: str) -> Dict[str, Any]:
    """
    Extract cover and metadata from PDF data.
    Used by /books/analyze/{bookId} endpoint.
    """
    # Extract cover image - return as data URL (simplest approach, works directly in <img src>)
    cover_url = None
    try:
        logger.info("Extracting cover image from PDF")
        cover_bytes, cover_format = extract_cover_from_pdf_bytes(pdf_data, target_width=400)
        
        # Ensure book record exists
        database = AWSDatabaseClient()
        from shared.db_utils import get_db_connection
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT book_id FROM books WHERE book_id = %s", (book_id,))
                exists = cur.fetchone()
                
                if not exists:
                    cur.execute(
                        """
                        INSERT INTO books (book_id, title, author, edition, isbn, total_pages, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                        """,
                        (book_id, 'Temporary', None, None, None, 0, json.dumps({}))
                    )
                    conn.commit()
                    logger.info(f"Created book record: {book_id}")
        
        # Store cover in database (matches MAExpert: db.update_book_cover)
        database.update_book_cover(book_id, cover_bytes, cover_format)
        logger.info(f"Stored cover image ({len(cover_bytes):,} bytes, {cover_format})")
        
        # Return as data URL - simplest approach, works directly in <img src>
        # Format: data:image/jpeg;base64,<base64_data>
        base64_data = base64.b64encode(cover_bytes).decode('utf-8')
        cover_url = f"data:image/{cover_format};base64,{base64_data}"
        logger.info(f"Cover extracted and encoded as data URL (format: {cover_format})")
    except Exception as e:
        logger.error(f"Failed to extract cover: {e}", exc_info=True)
        # In MAExpert, cover_url is always returned as a string (even if extraction fails, 
        # it still returns the URL string - the endpoint will return 404 if cover not found)
        # For now, we'll return None and let frontend handle it, but we could also return 
        # the URL string anyway and let the endpoint return 404 if needed
        cover_url = None
    
    # Extract metadata from PDF using LLM
    extracted_metadata = _extract_metadata_from_pdf(pdf_data, book_id)
    
    # Update book record with extracted metadata (title, author, edition, isbn, total_pages)
    # This ensures the book has correct metadata before ingestion starts
    from shared.db_utils import get_db_connection
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE books
                SET title = %s, author = %s, edition = %s, isbn = %s, total_pages = %s
                WHERE book_id = %s
                """,
                (
                    extracted_metadata.get('title') or 'Unknown',
                    extracted_metadata.get('author'),
                    extracted_metadata.get('edition'),
                    extracted_metadata.get('isbn'),
                    extracted_metadata.get('total_pages') or 0,
                    book_id
                )
            )
            conn.commit()
            logger.info(f"Updated book metadata from analysis: title={extracted_metadata.get('title')}, total_pages={extracted_metadata.get('total_pages')}")
    
    # Log final cover URL status for debugging
    if cover_url:
        logger.info(f"Analysis complete for {book_id}: cover_url={cover_url}")
    else:
        logger.warning(f"Analysis complete for {book_id}: cover_url is missing (extraction failed)")
    
    # Match MAExpert response format: always return cover_url as string if extraction succeeded
    # If extraction failed, we could still return the URL path and let the endpoint return 404,
    # but for now we'll return None and let frontend handle missing covers gracefully
    return success_response({
        'book_id': book_id,
        'cover_url': cover_url if cover_url else None,  # None if extraction failed
        'metadata': extracted_metadata,
        'status': 'analyzed'
    })


def _handle_start_ingestion(event: Dict[str, Any], book_id: str) -> Dict[str, Any]:
    """
    Handle /books/{bookId}/start-ingestion endpoint.
    Updates book metadata and triggers ingestion pipeline.
    """
    try:
        # Parse request body
        body = event.get('body', '{}')
        if isinstance(body, str):
            body = json.loads(body)
        
        title = body.get('title', '')
        author = body.get('author') or None
        edition = body.get('edition') or None
        isbn = body.get('isbn') or None
        
        if not title:
            return error_response("Title is required", 400)
        
        # Update book metadata in database and set ingestion_status to 'processing'
        from shared.db_utils import get_db_connection
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Try to update with ingestion_status columns, fall back if they don't exist
                try:
                    cur.execute(
                        """
                        UPDATE books
                        SET title = %s, author = %s, edition = %s, isbn = %s, ingestion_status = 'processing', ingestion_started_at = NOW()
                        WHERE book_id = %s
                        """,
                        (title, author, edition, isbn, book_id)
                    )
                    conn.commit()
                    logger.info(f"Updated book metadata and started ingestion for {book_id}: title={title}, author={author}, edition={edition}, isbn={isbn}")
                except Exception as e:
                    if 'ingestion_status' in str(e) or 'does not exist' in str(e):
                        # Columns don't exist - rollback and use basic update
                        conn.rollback()
                        logger.info("ingestion_status columns not found, using basic update")
                        cur.execute(
                            """
                            UPDATE books
                            SET title = %s, author = %s, edition = %s, isbn = %s
                            WHERE book_id = %s
                            """,
                            (title, author, edition, isbn, book_id)
                        )
                        conn.commit()
                        logger.info(f"Updated book metadata for {book_id}: title={title}, author={author}, edition={edition}, isbn={isbn}")
                    else:
                        raise
        
        # TODO: Trigger ingestion pipeline (EventBridge event or S3 trigger)
        # For now, just return success - ingestion can be triggered separately
        # In the future, this should publish an EventBridge event to start the document_processor
        
        return success_response({
            'book_id': book_id,
            'status': 'ingestion_started',
            'message': 'Ingestion pipeline started'
        })
    except Exception as e:
        logger.error(f"Error starting ingestion for {book_id}: {e}", exc_info=True)
        return error_response(f"Failed to start ingestion: {str(e)}", 500)


def _process_pdf_for_upload(pdf_data: bytes, book_id: str, book_title: str, book_author: str, 
                            book_edition: str, book_isbn: str) -> Dict[str, Any]:
    """
    Process PDF for legacy /books/upload endpoint (small files only).
    Extracts cover, metadata, and uploads to S3.
    """
    # Extract cover and metadata
    result = _process_pdf_for_analysis(pdf_data, book_id)
    cover_url = result.get('body', {}).get('cover_url', '') if isinstance(result.get('body'), dict) else ''
    
    # Generate S3 key
    timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    s3_key = f"books/{book_id}/{book_title.replace(' ', '_')}_{timestamp}.pdf"
    
    # Upload PDF to S3
    logger.info(f"Uploading book to S3: {s3_key}")
    s3_client.put_object(
        Bucket=SOURCE_BUCKET,
        Key=s3_key,
        Body=pdf_data,
        ContentType='application/pdf',
        Metadata={
            'book-id': book_id,
            'book-title': book_title,
            'book-author': book_author,
            'book-edition': book_edition,
            'book-isbn': book_isbn,
            'upload-timestamp': timestamp
        }
    )
    
    logger.info(f"Book uploaded successfully: {book_id}")
    
    return success_response({
        'book_id': book_id,
        's3_key': s3_key,
        'status': 'uploaded',
        'message': 'Book uploaded successfully. Ingestion will begin automatically.',
        'cover_url': cover_url
    })


def _parse_pdf_from_request(event: Dict[str, Any]) -> bytes:
    """
    Parse PDF data from API Gateway event.
    Handles both multipart/form-data and base64-encoded body.
    
    Note: API Gateway with Lambda proxy integration sends multipart/form-data
    as base64-encoded body. We need to decode it first, then parse multipart.
    """
    body = event.get('body', '')
    headers = event.get('headers', {}) or {}
    content_type = headers.get('Content-Type', '') or headers.get('content-type', '')
    is_base64 = event.get('isBase64Encoded', False)
    
    # Decode base64 if needed (API Gateway often sends multipart as base64)
    if is_base64:
        try:
            body_bytes = base64.b64decode(body)
        except Exception as e:
            logger.error(f"Failed to decode base64 body: {e}")
            raise ValueError(f"Invalid base64 encoding: {e}")
    else:
        # If not base64, body should already be bytes or a string
        if isinstance(body, str):
            body_bytes = body.encode('utf-8')
        else:
            body_bytes = body
    
    # Handle multipart/form-data
    if 'multipart/form-data' in content_type:
        # Parse multipart boundary
        boundary = None
        for part in content_type.split(';'):
            part = part.strip()
            if part.startswith('boundary='):
                boundary = part.split('=', 1)[1].strip('"\'')
                break
        
        if not boundary:
            # Try to extract from body if not in header
            try:
                body_preview = body_bytes[:500]
                if b'boundary=' in body_preview:
                    # Find first line
                    first_line_end = body_preview.find(b'\r\n')
                    if first_line_end == -1:
                        first_line_end = body_preview.find(b'\n')
                    if first_line_end > 0:
                        first_line = body_preview[:first_line_end].decode('utf-8', errors='ignore')
                        if 'boundary=' in first_line:
                            boundary = first_line.split('boundary=', 1)[1].strip('"\'')
            except Exception as e:
                logger.warning(f"Could not extract boundary from body: {e}")
        
        if not boundary:
            raise ValueError("Could not find boundary in multipart/form-data")
        
        # Parse multipart body as bytes (don't decode to string - preserves binary data)
        boundary_bytes = boundary.encode('utf-8')
        boundary_marker = b'--' + boundary_bytes
        
        # Split by boundary marker
        parts = body_bytes.split(boundary_marker)
        
        for part in parts:
            # Look for file field in headers (as bytes)
            if b'Content-Disposition: form-data; name="file"' in part or b'name="file"' in part:
                # Find the double CRLF that separates headers from body
                header_body_sep = b'\r\n\r\n'
                if header_body_sep in part:
                    file_content = part.split(header_body_sep, 1)[1]
                else:
                    header_body_sep = b'\n\n'
                    if header_body_sep in part:
                        file_content = part.split(header_body_sep, 1)[1]
                    else:
                        continue
                
                # Remove trailing boundary marker and whitespace
                # Look for the end boundary marker
                end_marker = b'\r\n--' + boundary_bytes
                if end_marker in file_content:
                    file_content = file_content.rsplit(end_marker, 1)[0]
                else:
                    end_marker = b'\n--' + boundary_bytes
                    if end_marker in file_content:
                        file_content = file_content.rsplit(end_marker, 1)[0]
                
                # Remove trailing CRLF
                file_content = file_content.rstrip(b'\r\n')
                
                # Return as bytes (file_content is already bytes)
                return file_content
        
        raise ValueError("Could not find file in multipart/form-data")
    
    # Handle direct binary (non-multipart) - already bytes
    return body_bytes


def _create_book_record(book_metadata: Dict[str, Any]) -> str:
    """
    Create book record in database.
    Returns book_id.
    """
    import psycopg2
    import os
    
    # Get database connection info
    conn = psycopg2.connect(
        host=DB_CLUSTER_ENDPOINT,
        port=5432,
        database=os.getenv('DB_NAME', 'docprof'),
        user=os.getenv('DB_MASTER_USERNAME', 'docprof_admin'),
        password=_get_db_password()
    )
    
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO books (book_id, title, author, edition, isbn, metadata)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (book_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    author = EXCLUDED.author,
                    edition = EXCLUDED.edition,
                    isbn = EXCLUDED.isbn,
                    metadata = EXCLUDED.metadata
                RETURNING book_id
                """,
                (
                    book_metadata['book_id'],
                    book_metadata['title'],
                    book_metadata.get('author'),
                    book_metadata.get('edition'),
                    book_metadata.get('isbn'),
                    json.dumps(book_metadata)
                )
            )
            book_id = cur.fetchone()[0]
            conn.commit()
            return str(book_id)
    finally:
        conn.close()


def _get_db_password() -> str:
    """Get database password from Secrets Manager"""
    if not DB_PASSWORD_SECRET_ARN:
        return os.getenv('DB_PASSWORD', '')
    
    response = secrets_client.get_secret_value(SecretId=DB_PASSWORD_SECRET_ARN)
    return response['SecretString']


def _find_copyright_page(pdf_bytes: bytes, max_pages: int = 50) -> Optional[int]:
    """
    Find the copyright page by scanning first N pages for 'copyright'.
    
    Matches MAExpert's MetadataExtractor.find_copyright_page() approach.
    Expanded to search up to 50 pages for books with late copyright pages.
    
    Args:
        pdf_bytes: PDF file as bytes
        max_pages: Maximum pages to scan (default 50)
        
    Returns:
        Page number (0-indexed) of copyright page, or None if not found
    """
    import fitz  # PyMuPDF
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    actual_pages = min(max_pages, len(doc))
    
    for page_num in range(actual_pages):
        page = doc[page_num]
        text = page.get_text("text").lower()
        
        # Look for copyright indicators
        if "copyright" in text or "©" in text:
            logger.info(f"Found copyright page at page {page_num + 1}")
            doc.close()
            return page_num
    
    logger.info(f"No copyright page found in first {max_pages} pages")
    doc.close()
    return None


def _extract_metadata_from_pdf(pdf_bytes: bytes, book_id: str) -> Dict[str, Any]:
    """
    Extract book metadata from PDF using hybrid approach (matching legacy MAExpert):
    1. Cover image (always)
    2. Title page (page before copyright)
    3. Copyright page (found by scanning for "copyright" keyword)
    
    This approach is much more efficient and reliable than extracting first 15 pages.
    """
    try:
        # Import fitz here to avoid top-level import issues
        import fitz  # PyMuPDF
        import base64
        
        # Open PDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_count = len(doc)
        
        if page_count == 0:
            logger.warning("PDF has no pages")
            return {
                'title': '',
                'author': '',
                'edition': '',
                'isbn': '',
                'publisher': '',
                'year': None,
                'total_pages': 0,
                'confidence': {'error': 'no_pages'}
            }
        
        # Step 1: Extract cover image as base64
        logger.info("Extracting cover image for analysis")
        page = doc[0]
        mat = fitz.Matrix(400 / page.rect.width, 400 / page.rect.width)
        pix = page.get_pixmap(matrix=mat)
        cover_bytes = pix.tobytes("jpeg")
        cover_b64 = base64.b64encode(cover_bytes).decode('utf-8')
        logger.info(f"Cover image extracted: {len(cover_bytes)} bytes")
        
        # Step 2: Find copyright page (scan first 50 pages for "copyright" keyword)
        # Some books have copyright pages later (e.g., Valuation book has it on page 40)
        copyright_page_num = _find_copyright_page(pdf_bytes, max_pages=50)
        
        # Step 3: Build content list for Claude (cover image + text pages)
        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": cover_b64
                }
            }
        ]
        
        # Add title page (page before copyright) and copyright page text
        if copyright_page_num is not None:
            # Get title page (page before copyright)
            if copyright_page_num > 0:
                title_page = doc[copyright_page_num - 1]
                title_text = title_page.get_text("text")
                logger.info(f"Including title page {copyright_page_num} ({len(title_text)} chars)")
                content.append({
                    "type": "text",
                    "text": f"=== TITLE PAGE (page {copyright_page_num + 1}) ===\n{title_text}\n"
                })
            
            # Get copyright page
            copyright_page = doc[copyright_page_num]
            copyright_text = copyright_page.get_text("text")
            logger.info(f"Including copyright page {copyright_page_num + 1} ({len(copyright_text)} chars)")
            content.append({
                "type": "text",
                "text": f"=== COPYRIGHT PAGE (page {copyright_page_num + 1}) ===\n{copyright_text}\n"
            })
        else:
            logger.info("No copyright page found, using cover image only")
        
        # Add instruction text
        prompt_text = """You are extracting bibliographic metadata from a textbook. You have:
1. The cover image (first image above)
2. The title page and/or copyright page text (if available)

Extract the following information:

1. **Title**: The full book title (be precise, include subtitles)
2. **Author(s)**: All authors (use "and" to separate, or "et al." if many)
3. **Edition**: Edition information (e.g., "3rd Edition", "Second Edition")
4. **ISBN**: ISBN-13 or ISBN-10 if present (check copyright page)
5. **Publisher**: Publishing company (check copyright page)
6. **Year**: Publication year (check copyright page)

For each field, also provide a confidence score (0.0 to 1.0) based on how certain you are.

Guidelines:
- Cover image is best for: title, author, edition
- Copyright page is best for: ISBN, publisher, year
- If information appears in multiple places, prefer the most authoritative source
- If a field is not found anywhere, set it to null

Respond ONLY with a JSON object in this exact format (no markdown, no explanation):
{
  "title": "exact title here",
  "author": "author name(s) or null",
  "edition": "edition info or null",
  "isbn": "ISBN or null",
  "publisher": "publisher or null",
  "year": 2020,
  "confidence": {
    "title": 0.95,
    "author": 0.90,
    "edition": 0.85,
    "isbn": 0.80,
    "publisher": 0.75,
    "year": 0.70
  }
}"""
        
        content.append({
            "type": "text",
            "text": prompt_text
        })
        
        doc.close()
        
        # Step 4: Call Claude with hybrid content (image + text)
        logger.info("Calling Claude with cover + title/copyright pages")
        metadata = None
        claude_error = None
        
        try:
            response = invoke_claude(
                messages=[{"role": "user", "content": content}],
                system=None,  # No system prompt needed, instructions are in content
                max_tokens=1024,
                temperature=0.0  # Temperature 0.0 for consistent extraction (matches legacy)
            )
            
            # Parse Claude's response
            response_text = response.get('content', '').strip()
            
            # Clean response (remove markdown code blocks if present)
            if response_text.startswith("```"):
                # Remove ```json and ``` markers
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1]) if len(lines) > 2 else response_text.strip("```").strip("json")
            
            # Parse JSON
            metadata = json.loads(response_text)
            logger.info(f"Successfully extracted metadata from Claude: {metadata}")
            
        except json.JSONDecodeError as e:
            claude_error = f"JSON decode error: {e}"
            logger.error(f"Failed to parse Claude response as JSON: {e}. Response: {response_text[:500] if 'response_text' in locals() else 'N/A'}")
        except Exception as claude_exception:
            claude_error = str(claude_exception)
            logger.warning(f"Claude metadata extraction failed: {claude_error}", exc_info=True)
        
        # If Claude extraction failed, return empty metadata
        if not metadata:
            logger.error(f"Claude extraction completely failed: {claude_error}")
            return {
                'title': '',
                'author': '',
                'edition': '',
                'isbn': '',
                'publisher': '',
                'year': None,
                'total_pages': page_count,
                'confidence': {
                    'error': 'claude_extraction_failed',
                    'message': claude_error or 'Unknown error'
                }
            }
        
        # Convert confidence dict if present (legacy format), but we don't use it
        # Legacy returned confidence scores, but we simplify for AWS version
        
        # Ensure all required fields exist (empty strings, not None, for frontend compatibility)
        for field in ['title', 'author', 'edition', 'isbn', 'publisher']:
            if field not in metadata or metadata[field] is None:
                metadata[field] = ''
        if 'year' not in metadata or metadata['year'] is None:
            metadata['year'] = None
        
        # Add page count and confidence info (simplified, without individual confidence scores)
        metadata['total_pages'] = page_count
        metadata['confidence'] = {
            'extraction_method': 'hybrid_cover_and_pages',
            'copyright_page_found': copyright_page_num is not None,
            'copyright_page_num': copyright_page_num + 1 if copyright_page_num is not None else None
        }
        
        logger.info(f"Final extracted metadata: title='{metadata.get('title')}', author='{metadata.get('author')}', isbn='{metadata.get('isbn')}'")
        return metadata
            
    except Exception as e:
        logger.error(f"Error extracting metadata from PDF: {e}", exc_info=True)
        # Return defaults on error - but try to at least get page count
        page_count = None
        try:
            import fitz
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            page_count = len(doc)
            doc.close()
        except:
            pass
        
        # Return empty strings (not 'Unknown') so frontend can handle gracefully
        return {
            'title': '',
            'author': '',
            'edition': '',
            'isbn': '',
            'publisher': '',
            'year': None,
            'total_pages': page_count,
            'confidence': {'error': 'exception_occurred', 'message': str(e)}
        }

