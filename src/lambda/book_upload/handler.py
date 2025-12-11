"""
Book Upload Lambda Handler
Handles PDF uploads from the frontend, stores in S3, and triggers ingestion
"""

import json
import os
import boto3
import uuid
import logging
from typing import Dict, Any
from datetime import datetime

# Import shared utilities
# Lambda's Python path includes /var/task/, so shared modules can be imported directly
from shared.response import success_response, error_response

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
    
    Expected event structure (API Gateway):
    {
        "body": "base64-encoded-pdf-data",
        "headers": {
            "Content-Type": "application/pdf",
            "x-book-title": "Book Title",
            "x-book-author": "Author Name",
            ...
        }
    }
    
    Or multipart/form-data:
    {
        "body": "multipart-form-data...",
        "headers": {
            "Content-Type": "multipart/form-data; boundary=..."
        }
    }
    """
    global SOURCE_BUCKET, DB_CLUSTER_ENDPOINT, DB_PASSWORD_SECRET_ARN
    
    # Initialize from environment
    SOURCE_BUCKET = SOURCE_BUCKET or os.getenv('SOURCE_BUCKET')
    DB_CLUSTER_ENDPOINT = DB_CLUSTER_ENDPOINT or os.getenv('DB_CLUSTER_ENDPOINT')
    DB_PASSWORD_SECRET_ARN = DB_PASSWORD_SECRET_ARN or os.getenv('DB_PASSWORD_SECRET_ARN')
    
    if not SOURCE_BUCKET:
        return error_response("SOURCE_BUCKET not configured", 500)
    
    try:
        # Parse request
        if event.get('isBase64Encoded'):
            # API Gateway with base64 encoding
            import base64
            pdf_data = base64.b64decode(event['body'])
        else:
            # Direct binary or multipart
            pdf_data = event['body'].encode('utf-8') if isinstance(event['body'], str) else event['body']
        
        # Extract metadata from headers
        headers = event.get('headers', {}) or {}
        book_title = headers.get('x-book-title') or headers.get('X-Book-Title', 'Unknown')
        book_author = headers.get('x-book-author') or headers.get('X-Book-Author', '')
        book_edition = headers.get('x-book-edition') or headers.get('X-Book-Edition', '')
        book_isbn = headers.get('x-book-isbn') or headers.get('X-Book-Isbn', '')
        
        # Generate unique book ID and S3 key
        book_id = str(uuid.uuid4())
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
        
        # Create book record in database (metadata only, ingestion will complete it)
        book_metadata = {
            'book_id': book_id,
            'title': book_title,
            'author': book_author,
            'edition': book_edition,
            'isbn': book_isbn,
            's3_key': s3_key,
            'status': 'uploaded',
            'uploaded_at': datetime.utcnow().isoformat()
        }
        
        # Store book metadata in database
        # Note: This will be done by document processor after ingestion completes
        # For now, we'll return success and let S3 event trigger processing
        
        logger.info(f"Book uploaded successfully: {book_id}")
        
        return success_response({
            'book_id': book_id,
            's3_key': s3_key,
            'status': 'uploaded',
            'message': 'Book uploaded successfully. Ingestion will begin automatically.',
            'metadata': book_metadata
        })
        
    except Exception as e:
        logger.error(f"Error uploading book: {e}", exc_info=True)
        return error_response(f"Failed to upload book: {str(e)}", 500)


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

