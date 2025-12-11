"""
Document Processor Lambda Handler
Processes PDF documents uploaded to S3, using MAExpert logic + AWS-adapted effects

This demonstrates the FP-to-Serverless mapping:
- Imports MAExpert logic directly (no changes)
- Uses AWS-adapted effects (matching MAExpert signatures)
- Preserves FP architecture benefits
"""

import json
import os
import sys
import boto3
import logging
from pathlib import Path
from typing import Dict, Any

# Import response utilities
# Lambda's Python path includes /var/task/, so shared modules can be imported directly
from shared.response import success_response, error_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')

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
    
    This handler demonstrates:
    1. Importing MAExpert logic directly
    2. Using AWS-adapted effects
    3. Preserving FP architecture
    """
    global SOURCE_BUCKET, PROCESSED_BUCKET
    
    SOURCE_BUCKET = SOURCE_BUCKET or os.getenv('SOURCE_BUCKET')
    PROCESSED_BUCKET = PROCESSED_BUCKET or os.getenv('PROCESSED_BUCKET')
    
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
        # S3 metadata keys are prefixed with 'book-' (e.g., 'book-title', 'book-author')
        s3_metadata = pdf_response.get('Metadata', {})
        book_id = s3_metadata.get('book-id', object_key.split('/')[1])  # Extract from path if not in metadata
        
        # Normalize S3 metadata keys (remove 'book-' prefix) for MAExpert compatibility
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
        
        # Process document using MAExpert ingestion pipeline
        result = process_document_with_maexpert_logic(
            pdf_data=pdf_data,
            book_id=book_id,
            s3_key=object_key,
            metadata=metadata
        )
        
        logger.info(f"Document processing complete: {book_id}")
        
        return success_response({
            'book_id': book_id,
            'status': 'processed',
            'chunks_created': result.get('chunks_created', 0),
            'figures_created': result.get('figures_created', 0)
        })
        
    except Exception as e:
        logger.error(f"Error processing document: {e}", exc_info=True)
        return error_response(f"Failed to process document: {str(e)}", 500)


def process_document_with_maexpert_logic(
    pdf_data: bytes,
    book_id: str,
    s3_key: str,
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Process document using MAExpert ingestion pipeline + AWS Protocol implementations.
    
    This demonstrates the FP-to-Serverless mapping:
    - Uses MAExpert run_ingestion_pipeline function (reused as-is)
    - Uses AWS Protocol implementations (matching MAExpert interfaces)
    """
    import tempfile
    from dataclasses import dataclass
    
    # Import MAExpert ingestion effects
    # MAExpert code is packaged in maexpert/ directory in Lambda deployment
    try:
        # Add src directory to Python path (MAExpert code is packaged as src/)
        # MAExpert code uses "from src.core" imports, so we need src/ in the path
        src_path = Path(__file__).parent / "src"
        if src_path.exists():
            # Add parent directory so "src" module can be imported
            parent_path = src_path.parent
            sys.path.insert(0, str(parent_path))
        else:
            # Fallback: try parent directory structure (for local testing)
            sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "MAExpert" / "src"))
        
        # Import MAExpert ingestion pipeline (reusing existing chunking logic!)
        # MAExpert uses "from src.core" imports
        from src.effects.ingestion_effects import run_ingestion_pipeline, FigureProcessingConfig
        from src.effects.chunk_builder import ChunkBuilder
        from src.core.commands import RunIngestionPipelineCommand
        from src.core.state import IngestionState
        from src.logic.ingestion import BookMetadata
        
        # Replace MAExpert's caption classifier with AWS Bedrock version
        # This allows MAExpert code to use AWS services without modification
        # Must import the module first, then replace the function
        import src.effects.caption_classifier as caption_classifier_module
        from shared.maexpert_caption_classifier_adapter import classify_caption_types_for_figures as aws_classify_caption_types
        # Monkey-patch: replace the function in the module
        caption_classifier_module.classify_caption_types_for_figures = aws_classify_caption_types
        
        # Also patch ingestion_effects to always use classifier (skip API key check)
        # The ingestion code checks for anthropic_api_key before calling classifier
        # We need to make it always call our Bedrock version
        import src.effects.ingestion_effects as ingestion_effects_module
        
        # Store original function
        original_run_ingestion_pipeline = ingestion_effects_module.run_ingestion_pipeline
        
        def patched_run_ingestion_pipeline(*args, **kwargs):
            """Wrapper that forces caption classification to use Bedrock"""
            # Temporarily patch the get_settings to return a mock with anthropic_api_key
            # This tricks the code into thinking it has an API key, so it calls our classifier
            original_get_settings = None
            try:
                from src.utils.config import get_settings as original_get_settings_func
                class MockSettings:
                    anthropic_api_key = "bedrock"  # Fake key to trigger classifier call
                
                def mock_get_settings():
                    return MockSettings()
                
                # Replace get_settings temporarily
                import src.utils.config as config_module
                config_module.get_settings = mock_get_settings
                
                # Run the pipeline
                result = original_run_ingestion_pipeline(*args, **kwargs)
                
                # Restore original
                if original_get_settings_func:
                    config_module.get_settings = original_get_settings_func
                
                return result
            except Exception as e:
                logger.warning(f"Failed to patch settings, falling back to original: {e}")
                # Restore original if we have it
                if original_get_settings:
                    import src.utils.config as config_module
                    config_module.get_settings = original_get_settings
                return original_run_ingestion_pipeline(*args, **kwargs)
        
        # Replace the function
        ingestion_effects_module.run_ingestion_pipeline = patched_run_ingestion_pipeline
        
        logger.info("Successfully imported MAExpert ingestion pipeline - reusing existing chunking logic")
        logger.info("Replaced caption classifier with AWS Bedrock version")
        logger.info("Patched ingestion pipeline to always use Bedrock classifier")
    except ImportError as e:
        logger.error(f"Failed to import MAExpert modules: {e}")
        logger.error(f"Python path: {sys.path}")
        raise
    
    # Create temporary file for PDF (MAExpert expects Path)
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        tmp_file.write(pdf_data)
        pdf_path = Path(tmp_file.name)
    
    try:
        # Create book metadata
        book_metadata = BookMetadata(
            title=metadata.get('title', 'Unknown'),
            author=metadata.get('author'),
            edition=metadata.get('edition'),
            isbn=metadata.get('isbn'),
            extra=metadata.get('extra', {})
        )
        
        # Create ingestion command
        command = RunIngestionPipelineCommand(
            pdf_path=pdf_path,
            book_metadata={
                'title': book_metadata.title,
                'author': book_metadata.author,
                'edition': book_metadata.edition,
                'isbn': book_metadata.isbn,
                'extra': book_metadata.extra
            },
            run_id=book_id,  # Use book_id as run_id
            rebuild=False,
            skip_figures=False
        )
        
        # Create AWS Protocol implementations
        from shared.protocol_implementations import (
            AWSDatabaseClient,
            AWSPDFExtractor,
            AWSEmbeddingClient,
            AWSFigureDescriptionClient
        )
        
        database = AWSDatabaseClient()
        pdf_extractor = AWSPDFExtractor()
        embeddings = AWSEmbeddingClient()
        figure_client = AWSFigureDescriptionClient()
        chunk_builder = ChunkBuilder()  # Import from MAExpert
        
        # Patch ingestion flow to check for existing figures early (optimization)
        # This skips expensive extraction/classification if figures already exist
        from shared.ingestion_flow_optimizer import patch_ingestion_flow_for_early_exit
        optimized_run_ingestion_pipeline = patch_ingestion_flow_for_early_exit(
            run_ingestion_pipeline,
            database,
            book_id
        )
        
        # Figure processing config
        figure_config = FigureProcessingConfig(
            caption_tokens=['Figure', 'Table', 'Exhibit', 'Diagram'],
            context_window=5  # 5 pages of context
        )
        
        # Run ingestion pipeline (MAExpert function, reused as-is, with optimizations!)
        logger.info(f"Starting MAExpert ingestion pipeline for {book_metadata.title}")
        result = optimized_run_ingestion_pipeline(
            command=command,
            pdf_extractor=pdf_extractor,
            figure_client=figure_client,
            chunk_builder=chunk_builder,
            embeddings=embeddings,
            database=database,
            figure_config=figure_config,
            progress_callback=None  # Could add progress reporting later
        )
        
        logger.info(f"Ingestion complete: {result}")
        
        return {
            'book_id': result.get('book_id', book_id),
            'chunks_created': result.get('total_chunks', 0),
            'figures_created': result.get('total_figures', 0),
            'status': 'success'
        }
        
    finally:
        # Clean up temporary file
        if pdf_path.exists():
            pdf_path.unlink()


def process_document_local(
    pdf_data: bytes,
    book_id: str,
    s3_key: str
) -> Dict[str, Any]:
    """
    Fallback local implementation if MAExpert not available.
    This would be a simplified version for testing.
    """
    logger.warning("Using local fallback implementation (MAExpert not available)")
    
    # Basic processing without MAExpert logic
    # This is just a placeholder - actual implementation would extract, chunk, embed, store
    
    return {
        'chunks_created': 0,
        'figures_created': 0,
        'note': 'Local fallback - MAExpert logic not available'
    }

