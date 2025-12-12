"""
Source Summary Embedding Generator Lambda Handler
Generates embeddings for source summaries stored in database.

Triggered after source summary is stored, or can be run manually to retrofit embeddings.
"""

import json
import logging
from typing import Dict, Any, List

from shared.db_utils import get_db_connection
from shared.bedrock_client import generate_embeddings
from shared.response import success_response, error_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def generate_embedding_for_summary(summary_json: dict) -> List[float]:
    """
    Generate embedding for a source summary.
    
    Converts the full JSON summary to text for embedding.
    Same logic as MAExpert generate_book_summary_embeddings.py
    """
    # Convert JSON to a readable text representation
    # Include source title, author, source summary, and chapter summaries
    text_parts = []
    
    if summary_json.get("source_title"):
        text_parts.append(f"Source: {summary_json['source_title']}")
    
    if summary_json.get("author"):
        text_parts.append(f"Author: {summary_json['author']}")
    
    if summary_json.get("source_summary"):
        text_parts.append(f"Overview: {summary_json['source_summary']}")
    
    # Add chapter summaries
    for chapter in summary_json.get("chapters", []):
        chapter_text = f"Chapter {chapter.get('chapter_number', '?')}: {chapter.get('chapter_title', 'Unknown')}"
        if chapter.get("summary"):
            chapter_text += f" - {chapter['summary']}"
        text_parts.append(chapter_text)
        
        # Add section topics and key concepts
        for section in chapter.get("sections", []):
            if section.get("topics"):
                text_parts.append(f"  Topics: {', '.join(section['topics'])}")
            if section.get("key_concepts"):
                text_parts.append(f"  Concepts: {', '.join(section['key_concepts'])}")
    
    # Combine into single text
    summary_text = "\n".join(text_parts)
    
    # Generate embedding using Bedrock Titan
    embeddings = generate_embeddings([summary_text])
    return embeddings[0] if embeddings else [0.0] * 1536


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle source summary embedding generation request.
    
    Expected event format:
    {
        "source_id": "uuid"  # Optional - if not provided, processes all summaries without embeddings
    }
    
    Or from EventBridge (source summary stored):
    {
        "source": "docprof.ingestion",
        "detail-type": "SourceSummaryStored",
        "detail": {
            "source_id": "uuid",
            "summary_id": "uuid"
        }
    }
    """
    try:
        # Parse event
        if event.get('source') == 'docprof.ingestion':
            # EventBridge format
            detail = event.get('detail', {})
            source_id = detail.get('source_id')
        else:
            # Direct invocation format
            source_id = event.get('source_id')
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                if source_id:
                    # Process specific source
                    logger.info(f"Generating embedding for source_id: {source_id}")
                    cur.execute("""
                        SELECT book_id, summary_json
                        FROM source_summaries
                        WHERE book_id = %s
                        AND embedding IS NULL
                        ORDER BY version DESC
                        LIMIT 1
                    """, (source_id,))
                    summaries = cur.fetchall()
                else:
                    # Process all summaries without embeddings
                    logger.info("Generating embeddings for all summaries without embeddings")
                    cur.execute("""
                        SELECT book_id, summary_json
                        FROM source_summaries
                        WHERE embedding IS NULL
                        ORDER BY generated_at DESC
                    """)
                    summaries = cur.fetchall()
                
                if not summaries:
                    return success_response({
                        'message': 'No summaries found without embeddings',
                        'processed': 0,
                    })
                
                processed = 0
                errors = []
                
                for book_id, summary_json in summaries:
                    try:
                        logger.info(f"Processing source_id: {book_id}")
                        
                        # Parse JSON if needed
                        if isinstance(summary_json, str):
                            summary_data = json.loads(summary_json)
                        else:
                            summary_data = summary_json
                        
                        # Generate embedding
                        embedding = generate_embedding_for_summary(summary_data)
                        
                        # Update database
                        cur.execute("""
                            UPDATE source_summaries
                            SET embedding = %s::vector
                            WHERE book_id = %s
                            AND version = (
                                SELECT MAX(version) 
                                FROM source_summaries 
                                WHERE book_id = %s
                            )
                        """, (embedding, book_id, book_id))
                        conn.commit()
                        
                        processed += 1
                        logger.info(f"✓ Generated and stored embedding for source_id: {book_id}")
                        
                    except Exception as e:
                        logger.error(f"✗ Failed to generate embedding for source_id {book_id}: {e}", exc_info=True)
                        errors.append({'source_id': str(book_id), 'error': str(e)})
                        continue
                
                return success_response({
                    'processed': processed,
                    'errors': errors if errors else None,
                    'message': f'Processed {processed} summary embedding(s)',
                })
        
    except Exception as e:
        logger.error(f"Error in source summary embedding generator: {e}", exc_info=True)
        return error_response(f"Internal server error: {str(e)}", status_code=500)
