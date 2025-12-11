"""
Lambda function to deduplicate chunks by content_hash.
Keeps the oldest chunk for each duplicate group.
"""

import json
import logging
from typing import Dict, Any

from shared.db_utils import get_db_connection

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Deduplicate chunks by content_hash."""
    
    book_id = event.get('book_id')
    dry_run = event.get('dry_run', True)
    
    if not book_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'book_id is required'})
        }
    
    results = {
        'dry_run': dry_run,
        'book_id': book_id,
        'duplicates_found': 0,
        'chunks_deleted': 0,
        'chunks_kept': 0
    }
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Find duplicate chunks by content_hash
                cur.execute("""
                    SELECT 
                        metadata->>'content_hash' as content_hash,
                        chunk_type,
                        COUNT(*) as count,
                        array_agg(chunk_id::text ORDER BY created_at) as chunk_ids
                    FROM chunks
                    WHERE book_id = %s
                      AND metadata ? 'content_hash'
                    GROUP BY metadata->>'content_hash', chunk_type
                    HAVING COUNT(*) > 1
                    ORDER BY count DESC
                """, (book_id,))
                
                duplicates = cur.fetchall()
                results['duplicates_found'] = len(duplicates)
                
                total_to_delete = 0
                total_to_keep = 0
                
                for content_hash, chunk_type, count, chunk_ids_array in duplicates:
                    # Convert PostgreSQL array to Python list
                    # chunk_ids_array is a string like "{uuid1,uuid2,uuid3}"
                    if isinstance(chunk_ids_array, str):
                        chunk_ids = [cid.strip() for cid in chunk_ids_array.strip('{}').split(',')]
                    else:
                        chunk_ids = list(chunk_ids_array) if chunk_ids_array else []
                    
                    # Keep the first (oldest) chunk, delete the rest
                    keep_id = chunk_ids[0] if chunk_ids else None
                    delete_ids = chunk_ids[1:] if len(chunk_ids) > 1 else []
                    
                    total_to_keep += 1
                    total_to_delete += len(delete_ids)
                    
                    if not dry_run and delete_ids:
                        # Delete duplicate chunks (use tuple for IN clause)
                        placeholders = ','.join(['%s'] * len(delete_ids))
                        cur.execute(f"""
                            DELETE FROM chunks
                            WHERE chunk_id::text IN ({placeholders})
                        """, delete_ids)
                        
                        logger.info(
                            f"Deleted {len(delete_ids)} duplicate {chunk_type} chunks "
                            f"(hash: {content_hash[:16]}...), kept {keep_id}"
                        )
                
                if not dry_run:
                    conn.commit()
                    results['chunks_deleted'] = total_to_delete
                    results['chunks_kept'] = total_to_keep
                    logger.info(f"Deduplication complete: deleted {total_to_delete} duplicates, kept {total_to_keep} unique chunks")
                else:
                    results['chunks_deleted'] = total_to_delete
                    results['chunks_kept'] = total_to_keep
                    logger.info(f"DRY RUN: Would delete {total_to_delete} duplicates, keep {total_to_keep} unique chunks")
                
                return {
                    'statusCode': 200,
                    'body': json.dumps(results, indent=2, default=str)
                }
                
    except Exception as e:
        logger.error(f"Error deduplicating chunks: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Failed to deduplicate chunks'
            })
        }

