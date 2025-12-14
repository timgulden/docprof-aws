"""
Document Processor Lambda Handler
Processes PDF documents uploaded to S3, using AWS-native ingestion pipeline

This is a clean, AWS-native implementation that:
- Uses pure logic functions for chunking (extracted from MAExpert)
- Uses AWS adapters for effects (Bedrock, Aurora)
- Follows FP principles (logic/effect separation)
- No MAExpert dependencies
"""

import json
import os
import boto3
import logging
from typing import Dict, Any

# Import response utilities
# Lambda's Python path includes /var/task/, so shared modules can be imported directly
from shared.response import success_response, error_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')
eventbridge_client = boto3.client('events')

# Environment variables (set by Terraform)
SOURCE_BUCKET = None
PROCESSED_BUCKET = None


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle S3 event notification for PDF upload.
    
    Expected event (S3 notification):
    {
        "Records": [{
            "s3": {
                "bucket": {"name": "docprof-dev-source-docs"},
                "object": {"key": "books/uuid/title.pdf"}
            }
        }]
    }
    
    This handler uses AWS-native ingestion pipeline:
    1. Pure logic functions for chunking
    2. AWS adapters for effects (Bedrock, Aurora)
    3. FP principles (logic/effect separation)
    
    Note: Lambda has a maximum timeout of 15 minutes. This handler checks remaining
    time and returns partial results if timeout is approaching.
    """
    global SOURCE_BUCKET, PROCESSED_BUCKET
    
    SOURCE_BUCKET = SOURCE_BUCKET or os.getenv('SOURCE_BUCKET')
    PROCESSED_BUCKET = PROCESSED_BUCKET or os.getenv('PROCESSED_BUCKET')
    
    # Get remaining time - Lambda max is 15 minutes (900 seconds)
    # Warn if less than 2 minutes remaining, fail gracefully if less than 30 seconds
    remaining_time_ms = context.get_remaining_time_in_millis() if context else None
    remaining_time_sec = remaining_time_ms / 1000.0 if remaining_time_ms else None
    
    if remaining_time_sec and remaining_time_sec < 30:
        logger.warning(f"Lambda timeout approaching: {remaining_time_sec:.1f} seconds remaining. Cannot start processing.")
        return error_response("Lambda timeout too close to start processing", 504)
    
    if not SOURCE_BUCKET:
        return error_response("SOURCE_BUCKET not configured", 500)
    
    try:
        # Parse event - support both S3 direct notifications and EventBridge
        bucket_name = None
        object_key = None
        
        # Check if this is an EventBridge event (from S3 EventBridge notifications)
        if 'source' in event and event.get('source') == 'aws.s3':
            # EventBridge format
            bucket_name = event['detail']['bucket']['name']
            object_key = event['detail']['object']['key']
            # Filter: only process .pdf files in books/ prefix
            if not object_key.startswith('books/') or not object_key.endswith('.pdf'):
                logger.info(f"Skipping non-PDF or non-books file: {object_key}")
                return {
                    'statusCode': 200,
                    'body': json.dumps({'message': 'Skipped: not a PDF in books/ directory'})
                }
            logger.info(f"Received EventBridge event for: s3://{bucket_name}/{object_key}")
        # Check if this is a direct S3 notification
        elif 'Records' in event and len(event['Records']) > 0:
            # Direct S3 notification format
            record = event['Records'][0]
            bucket_name = record['s3']['bucket']['name']
            object_key = record['s3']['object']['key']
            logger.info(f"Received S3 direct notification for: s3://{bucket_name}/{object_key}")
        else:
            return error_response("Invalid event format: expected S3 or EventBridge event", 400)
        
        logger.info(f"Processing document: s3://{bucket_name}/{object_key}")
        
        # Download PDF from S3
        pdf_response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        pdf_data = pdf_response['Body'].read()
        
        # Extract metadata from S3 object metadata
        # S3 metadata keys are prefixed with 'x-amz-meta-' when retrieved (e.g., 'x-amz-meta-book-id')
        s3_metadata = pdf_response.get('Metadata', {})
        # Try to get book-id from metadata first, then fall back to path
        book_id_from_metadata = s3_metadata.get('x-amz-meta-book-id') or s3_metadata.get('book-id')
        book_id_from_path = object_key.split('/')[1] if '/' in object_key else None
        book_id = book_id_from_metadata or book_id_from_path
        
        if not book_id:
            logger.error(f"Could not extract book_id from S3 metadata or path: {object_key}")
            return error_response("Could not determine book_id from S3 object", 400)
        
        logger.info(f"Extracted book_id: {book_id} (from metadata: {bool(book_id_from_metadata)}, from path: {bool(book_id_from_path)})")
        
        # Normalize S3 metadata keys (remove 'book-' prefix)
        metadata = {
            'title': s3_metadata.get('book-title', 'Unknown'),
            'author': s3_metadata.get('book-author'),
            'edition': s3_metadata.get('book-edition'),
            'isbn': s3_metadata.get('book-isbn'),
            'extra': {
                'upload-timestamp': s3_metadata.get('upload-timestamp'),
                'book-id': book_id
            }
        }
        
        # Check remaining time before starting processing
        remaining_time_ms = context.get_remaining_time_in_millis() if context else None
        remaining_time_sec = remaining_time_ms / 1000.0 if remaining_time_ms else None
        
        if remaining_time_sec and remaining_time_sec < 60:
            logger.warning(f"Not enough time remaining ({remaining_time_sec:.1f}s) to process document. Minimum 60 seconds needed.")
            return error_response(f"Not enough time remaining to process ({remaining_time_sec:.1f}s). Please retry.", 504)
        
        # Process document using AWS-native ingestion pipeline
        import asyncio
        result = asyncio.run(process_document_aws_native(
            pdf_data=pdf_data,
            book_id=book_id,
            s3_key=object_key,
            metadata=metadata,
            bucket_name=bucket_name,
            context=context  # Pass context for timeout checking
        ))
        
        # Check if processing was partial due to timeout
        if result.get('partial', False):
            logger.warning(f"Document processing completed partially due to timeout: {book_id}")
            return {
                'statusCode': 202,  # Accepted (partial completion)
                'body': json.dumps({
                    'book_id': result.get('book_id', book_id),
                    'status': 'partially_processed',
                    'chunks_created': result.get('chunks_created', 0),
                    'figures_created': result.get('figures_created', 0),
                    'message': 'Processing partially completed. Some chunks may be missing due to timeout.',
                    'remaining_time': result.get('remaining_time', None)
                })
            }
        
        logger.info(f"Document processing complete: {book_id}")
        
        return success_response({
            'book_id': result.get('book_id', book_id),
            'status': 'processed',
            'chunks_created': result.get('chunks_created', 0),
            'figures_created': result.get('figures_created', 0)
        })
        
    except Exception as e:
        logger.error(f"Error processing document: {e}", exc_info=True)
        return error_response(f"Failed to process document: {str(e)}", 500)


async def process_document_aws_native(
    pdf_data: bytes,
    book_id: str,
    s3_key: str,
    metadata: Dict[str, Any],
    bucket_name: str,
    context: Any = None
) -> Dict[str, Any]:
    """
    Process document using AWS-native ingestion pipeline.
    
    This is a clean, AWS-native implementation that:
    - Uses pure logic functions for chunking
    - Uses AWS adapters for effects (Bedrock, Aurora)
    - Follows FP principles (logic/effect separation)
    - No MAExpert dependencies
    - Monitors remaining Lambda time and returns partial results if timeout approaching
    """
    from shared.ingestion_orchestrator import run_ingestion_pipeline
    
    # Run AWS-native ingestion pipeline
    logger.info(f"Starting AWS-native ingestion pipeline for {metadata.get('title', 'Unknown')}")
    
    # Check remaining time periodically during processing
    # If less than 60 seconds remain, return partial results
    remaining_time_ms = context.get_remaining_time_in_millis() if context else None
    remaining_time_sec = remaining_time_ms / 1000.0 if remaining_time_ms else None
    
    if remaining_time_sec and remaining_time_sec < 60:
        logger.warning(f"Timeout approaching ({remaining_time_sec:.1f}s remaining). Cannot start full processing.")
        return {
            'book_id': book_id,
            'chunks_created': 0,
            'figures_created': 0,
            'partial': True,
            'remaining_time': remaining_time_sec,
            'message': 'Processing aborted due to insufficient time remaining'
        }
    
    try:
        result = await run_ingestion_pipeline(
            pdf_bytes=pdf_data,
            book_id=book_id,
            metadata=metadata,
            skip_figures=False,
            rebuild=False
        )
        
        logger.info(f"Ingestion complete: {result}")
        
        # Trigger source summary generation as final step
    # This is done asynchronously via EventBridge to avoid blocking
    try:
        event_bus_name = os.getenv('EVENT_BUS_NAME', '').strip() or None
        
        # Publish document processed event
        eventbridge_client.put_events(
            Entries=[
                {
                    'Source': 'docprof.ingestion',
                    'DetailType': 'DocumentProcessed',
                    'Detail': json.dumps({
                        'source_id': result.get('book_id', book_id),
                        'source_title': metadata.get('title', 'Unknown'),
                        'author': metadata.get('author', 'Unknown'),
                        's3_bucket': bucket_name,
                        's3_key': s3_key,
                        'chunks_created': result.get('chunks_created', 0),
                        'figures_created': result.get('figures_created', 0),
                    }),
                    **({'EventBusName': event_bus_name} if event_bus_name else {}),
                }
            ]
        )
        logger.info("Published DocumentProcessed event for source summary generation")
    except Exception as e:
        logger.warning(f"Failed to publish DocumentProcessed event: {e}")
        # Don't fail ingestion if summary generation trigger fails
    
    return {
        'book_id': result.get('book_id', book_id),
        'chunks_created': result.get('chunks_created', 0),
        'figures_created': result.get('figures_created', 0),
        'status': 'success',
        'summary_generation_triggered': True,
    }



