"""
Book PDF Lambda Handler
Returns presigned S3 URLs for PDF files (for large files that exceed Lambda response limits).
PDFs are stored in S3 at books/{book_id}/{title}.pdf, with s3_key in metadata.
For large PDFs (>6MB), we return a presigned URL instead of the file itself.
"""

import logging
import json
import boto3
import os
from typing import Dict, Any, Optional
from datetime import timedelta

from shared.response import error_response, success_response
from shared.db_utils import get_db_connection

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# S3 client
s3_client = boto3.client('s3')

# Get S3 bucket name from environment variable (set by Terraform)
SOURCE_BUCKET = os.getenv('SOURCE_BUCKET', 'docprof-dev-source-docs')

# Presigned URL expiration (1 hour)
PRESIGNED_URL_EXPIRATION = 3600

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle GET /books/{bookId}/pdf request.
    
    Returns a presigned S3 URL for the PDF file.
    This avoids Lambda's 6MB response payload limit for large PDFs.
    """
    # Extract book_id from path parameters
    path_params = event.get('pathParameters') or {}
    book_id = path_params.get('bookId')
    
    if not book_id:
        return error_response("Book ID is required", 400)
    
    logger.info(f"PDF URL requested for book_id: {book_id}")
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if book exists and get S3 key
                cur.execute(
                    """
                    SELECT 
                        metadata->>'s3_key' as s3_key
                    FROM books
                    WHERE book_id = %s
                    """,
                    (book_id,)
                )
                row = cur.fetchone()
                
                if not row:
                    logger.warning(f"Book not found in database: {book_id}")
                    return error_response("Book not found", 404)
                
                s3_key = row[0] if row[0] else None
                
                if not s3_key:
                    logger.warning(f"S3 key not found for book_id: {book_id}")
                    return error_response("PDF not available for this book", 404)
                
                # Generate presigned URL for S3 object
                try:
                    logger.info(f"Generating presigned URL for s3://{SOURCE_BUCKET}/{s3_key}")
                    presigned_url = s3_client.generate_presigned_url(
                        'get_object',
                        Params={
                            'Bucket': SOURCE_BUCKET,
                            'Key': s3_key,
                            'ResponseContentType': 'application/pdf',
                            'ResponseContentDisposition': f'inline; filename="book_{book_id}.pdf"'
                        },
                        ExpiresIn=PRESIGNED_URL_EXPIRATION
                    )
                    
                    logger.info(f"Generated presigned URL for book_id: {book_id}")
                    
                    return success_response({
                        'pdf_url': presigned_url,
                        'expires_in': PRESIGNED_URL_EXPIRATION
                    })
                    
                except Exception as s3_error:
                    logger.error(f"Failed to generate presigned URL for {s3_key}: {s3_error}", exc_info=True)
                    return error_response("Failed to generate PDF URL", 500)
                    
    except Exception as e:
        logger.error(f"Error retrieving PDF URL: {e}", exc_info=True)
        return error_response("Failed to retrieve PDF URL", 500)

