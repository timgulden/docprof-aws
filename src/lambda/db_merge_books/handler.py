"""
Lambda function to merge chunks/figures/chapters from one book to another.
"""

import json
import logging
from typing import Dict, Any

from shared.db_utils import get_db_connection

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Merge book data from source_book_id to target_book_id."""
    
    source_book_id = event.get('source_book_id')
    target_book_id = event.get('target_book_id')
    dry_run = event.get('dry_run', True)
    
    if not source_book_id or not target_book_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'source_book_id and target_book_id are required'})
        }
    
    if source_book_id == target_book_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'source_book_id and target_book_id must be different'})
        }
    
    results = {
        'dry_run': dry_run,
        'source_book_id': source_book_id,
        'target_book_id': target_book_id,
        'chunks_moved': 0,
        'figures_moved': 0,
        'chapters_moved': 0,
        'source_book_deleted': False
    }
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Verify both books exist
                cur.execute("SELECT book_id, title FROM books WHERE book_id IN (%s, %s)", 
                           (source_book_id, target_book_id))
                books = {str(row[0]): row[1] for row in cur.fetchall()}
                
                if source_book_id not in books:
                    return {
                        'statusCode': 404,
                        'body': json.dumps({'error': f'Source book {source_book_id} not found'})
                    }
                
                if target_book_id not in books:
                    return {
                        'statusCode': 404,
                        'body': json.dumps({'error': f'Target book {target_book_id} not found'})
                    }
                
                # Count records to move
                cur.execute("SELECT COUNT(*) FROM chunks WHERE book_id = %s", (source_book_id,))
                chunk_count = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM figures WHERE book_id = %s", (source_book_id,))
                figure_count = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM chapter_documents WHERE book_id = %s", (source_book_id,))
                chapter_count = cur.fetchone()[0]
                
                results['chunks_moved'] = chunk_count
                results['figures_moved'] = figure_count
                results['chapters_moved'] = chapter_count
                
                if not dry_run:
                    # Move chunks
                    cur.execute("UPDATE chunks SET book_id = %s WHERE book_id = %s", 
                               (target_book_id, source_book_id))
                    chunks_moved = cur.rowcount
                    
                    # Move figures
                    cur.execute("UPDATE figures SET book_id = %s WHERE book_id = %s", 
                               (target_book_id, source_book_id))
                    figures_moved = cur.rowcount
                    
                    # Move chapters (delete duplicates first if they exist)
                    # Check for duplicate chapter_numbers
                    cur.execute("""
                        SELECT cd1.chapter_document_id, cd1.chapter_number
                        FROM chapter_documents cd1
                        JOIN chapter_documents cd2 ON cd1.book_id = %s 
                            AND cd2.book_id = %s 
                            AND cd1.chapter_number = cd2.chapter_number
                    """, (source_book_id, target_book_id))
                    duplicates = cur.fetchall()
                    
                    if duplicates:
                        # Delete source chapters that duplicate target
                        for dup_id, _ in duplicates:
                            cur.execute("DELETE FROM chapter_documents WHERE chapter_document_id = %s", 
                                       (dup_id,))
                    
                    # Move remaining chapters
                    cur.execute("UPDATE chapter_documents SET book_id = %s WHERE book_id = %s", 
                               (target_book_id, source_book_id))
                    chapters_moved = cur.rowcount
                    
                    # Delete source book
                    cur.execute("DELETE FROM books WHERE book_id = %s", (source_book_id,))
                    results['source_book_deleted'] = True
                    
                    conn.commit()
                    
                    logger.info(f"Merged book {source_book_id} into {target_book_id}")
                    logger.info(f"Moved {chunks_moved} chunks, {figures_moved} figures, {chapters_moved} chapters")
                else:
                    logger.info(f"DRY RUN: Would move {chunk_count} chunks, {figure_count} figures, {chapter_count} chapters")
                
                results['source_book_title'] = books.get(source_book_id, 'Unknown')
                results['target_book_title'] = books.get(target_book_id, 'Unknown')
                
                return {
                    'statusCode': 200,
                    'body': json.dumps(results, indent=2, default=str)
                }
                
    except Exception as e:
        logger.error(f"Error merging books: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Failed to merge books'
            })
        }

