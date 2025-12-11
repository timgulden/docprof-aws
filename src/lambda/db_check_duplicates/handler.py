"""
Lambda function to check for duplicate chunks after merge.
"""

import json
import logging
from typing import Dict, Any

from shared.db_utils import get_db_connection
from psycopg2.extras import RealDictCursor

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Check for duplicate chunks."""
    
    book_id = event.get('book_id')
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if book_id:
                    # Check specific book
                    cur.execute("""
                        SELECT 
                            chunk_type,
                            content,
                            COUNT(*) as count,
                            array_agg(chunk_id) as chunk_ids,
                            array_agg(created_at) as created_dates
                        FROM chunks
                        WHERE book_id = %s
                        GROUP BY chunk_type, content
                        HAVING COUNT(*) > 1
                        ORDER BY count DESC
                        LIMIT 50
                    """, (book_id,))
                else:
                    # Check all books
                    cur.execute("""
                        SELECT 
                            book_id,
                            chunk_type,
                            content,
                            COUNT(*) as count,
                            array_agg(chunk_id) as chunk_ids
                        FROM chunks
                        GROUP BY book_id, chunk_type, content
                        HAVING COUNT(*) > 1
                        ORDER BY count DESC
                        LIMIT 50
                    """)
                
                duplicates = cur.fetchall()
                
                # Also check by content_hash if available
                cur.execute("""
                    SELECT 
                        book_id,
                        chunk_type,
                        metadata->>'content_hash' as content_hash,
                        COUNT(*) as count
                    FROM chunks
                    WHERE metadata ? 'content_hash'
                    GROUP BY book_id, chunk_type, metadata->>'content_hash'
                    HAVING COUNT(*) > 1
                    ORDER BY count DESC
                    LIMIT 50
                """)
                hash_duplicates = cur.fetchall()
                
                # Get total chunk counts
                if book_id:
                    cur.execute("""
                        SELECT 
                            chunk_type,
                            COUNT(*) as total,
                            COUNT(DISTINCT content) as unique_content,
                            COUNT(DISTINCT metadata->>'content_hash') FILTER (WHERE metadata ? 'content_hash') as unique_hashes
                        FROM chunks
                        WHERE book_id = %s
                        GROUP BY chunk_type
                    """, (book_id,))
                else:
                    cur.execute("""
                        SELECT 
                            chunk_type,
                            COUNT(*) as total,
                            COUNT(DISTINCT content) as unique_content,
                            COUNT(DISTINCT metadata->>'content_hash') FILTER (WHERE metadata ? 'content_hash') as unique_hashes
                        FROM chunks
                        GROUP BY chunk_type
                    """)
                totals = cur.fetchall()
                
                result = {
                    'book_id': book_id,
                    'duplicate_chunks_by_content': [dict(d) for d in duplicates],
                    'duplicate_chunks_by_hash': [dict(h) for h in hash_duplicates],
                    'totals': [dict(t) for t in totals],
                    'summary': {
                        'total_duplicates_by_content': len(duplicates),
                        'total_duplicates_by_hash': len(hash_duplicates),
                        'total_chunks': sum(t['total'] for t in totals),
                        'unique_content': sum(t['unique_content'] for t in totals),
                        'potential_waste': sum(t['total'] for t in totals) - sum(t['unique_content'] for t in totals)
                    }
                }
                
                return {
                    'statusCode': 200,
                    'body': json.dumps(result, indent=2, default=str)
                }
                
    except Exception as e:
        logger.error(f"Error checking duplicates: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Failed to check duplicates'
            })
        }

