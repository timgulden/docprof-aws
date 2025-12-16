"""
Lambda function to clean up broken book records before re-ingestion.
"""

import json
import logging
from typing import Dict, Any

from shared.db_utils import get_db_connection

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Clean up broken book records or delete all data."""
    
    delete_all = event.get('delete_all', False)
    book_id = event.get('book_id')
    delete_all_broken = event.get('delete_all_broken', False)
    clean_source_summaries = event.get('clean_source_summaries', False)
    dry_run = event.get('dry_run', True)
    
    results = {
        'dry_run': dry_run,
        'books_found': [],
        'books_deleted': [],
        'chunks_deleted': 0,
        'figures_deleted': 0,
        'chapters_deleted': 0,
        'source_summaries_deleted': 0,
        'source_summary_embeddings_deleted': 0
    }
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Handle clean_source_summaries option
                if clean_source_summaries and book_id:
                    if not dry_run:
                        # Count before deletion (source_summaries uses book_id, not source_id)
                        cur.execute("SELECT COUNT(*) FROM source_summaries WHERE book_id = %s", (book_id,))
                        summary_count = cur.fetchone()[0]
                        # Check if source_summary_embeddings table exists
                        cur.execute("""
                            SELECT EXISTS (
                                SELECT FROM information_schema.tables 
                                WHERE table_name = 'source_summary_embeddings'
                            )
                        """)
                        embeddings_table_exists = cur.fetchone()[0]
                        embedding_count = 0
                        if embeddings_table_exists:
                            cur.execute("SELECT COUNT(*) FROM source_summary_embeddings WHERE book_id = %s", (book_id,))
                            embedding_count = cur.fetchone()[0]
                        
                        # Delete source_summaries and embeddings
                        cur.execute("DELETE FROM source_summaries WHERE book_id = %s", (book_id,))
                        if embeddings_table_exists:
                            cur.execute("DELETE FROM source_summary_embeddings WHERE book_id = %s", (book_id,))
                        
                        conn.commit()
                        
                        results['source_summaries_deleted'] = summary_count
                        results['source_summary_embeddings_deleted'] = embedding_count
                        
                        return {
                            'statusCode': 200,
                            'body': json.dumps({
                                **results,
                                'message': f'Deleted {summary_count} source_summaries and {embedding_count} embeddings for book_id: {book_id}'
                            }, indent=2, default=str)
                        }
                    else:
                        # Dry run
                        cur.execute("SELECT COUNT(*) FROM source_summaries WHERE book_id = %s", (book_id,))
                        summary_count = cur.fetchone()[0]
                        cur.execute("""
                            SELECT EXISTS (
                                SELECT FROM information_schema.tables 
                                WHERE table_name = 'source_summary_embeddings'
                            )
                        """)
                        embeddings_table_exists = cur.fetchone()[0]
                        embedding_count = 0
                        if embeddings_table_exists:
                            cur.execute("SELECT COUNT(*) FROM source_summary_embeddings WHERE book_id = %s", (book_id,))
                            embedding_count = cur.fetchone()[0]
                        
                        return {
                            'statusCode': 200,
                            'body': json.dumps({
                                **results,
                                'message': f'DRY RUN: Would delete {summary_count} source_summaries and {embedding_count} embeddings for book_id: {book_id}'
                            }, indent=2, default=str)
                        }
                
                # Handle delete_all option
                if delete_all:
                    if not dry_run:
                        # Count records before deletion
                        cur.execute("SELECT COUNT(*) FROM books")
                        book_count = cur.fetchone()[0]
                        cur.execute("SELECT COUNT(*) FROM chunks")
                        chunk_count = cur.fetchone()[0]
                        cur.execute("SELECT COUNT(*) FROM chapter_documents")
                        chapter_count = cur.fetchone()[0]
                        
                        # Delete everything
                        cur.execute("DELETE FROM chunks")
                        cur.execute("DELETE FROM chapter_documents")
                        cur.execute("UPDATE books SET metadata = metadata - 'figures' - 'cover' WHERE metadata IS NOT NULL")
                        cur.execute("DELETE FROM books")
                        
                        conn.commit()
                        
                        results['books_deleted'] = [f"deleted_all_{book_count}_books"]
                        results['chunks_deleted'] = chunk_count
                        results['chapters_deleted'] = chapter_count
                        
                        return {
                            'statusCode': 200,
                            'body': json.dumps({
                                **results,
                                'message': f'Deleted all data: {book_count} books, {chunk_count} chunks, {chapter_count} chapters'
                            }, indent=2, default=str)
                        }
                    else:
                        # Dry run - just count
                        cur.execute("SELECT COUNT(*) FROM books")
                        book_count = cur.fetchone()[0]
                        cur.execute("SELECT COUNT(*) FROM chunks")
                        chunk_count = cur.fetchone()[0]
                        
                        return {
                            'statusCode': 200,
                            'body': json.dumps({
                                **results,
                                'message': f'DRY RUN: Would delete all data: {book_count} books, {chunk_count} chunks'
                            }, indent=2, default=str)
                        }
                
                # Find broken books (title is NULL, empty, or "Unknown")
                if book_id:
                    cur.execute("""
                        SELECT book_id, title, author, total_pages, ingestion_date
                        FROM books
                        WHERE book_id = %s
                    """, (book_id,))
                elif delete_all_broken:
                    cur.execute("""
                        SELECT book_id, title, author, total_pages, ingestion_date
                        FROM books
                        WHERE title IS NULL 
                           OR title = '' 
                           OR LOWER(title) = 'unknown'
                    """)
                else:
                    cur.execute("""
                        SELECT book_id, title, author, total_pages, ingestion_date
                        FROM books
                        WHERE title IS NULL 
                           OR title = '' 
                           OR LOWER(title) = 'unknown'
                    """)
                
                broken_books = cur.fetchall()
                
                if not broken_books:
                    return {
                        'statusCode': 200,
                        'body': json.dumps({
                            **results,
                            'message': 'No broken books found'
                        }, indent=2, default=str)
                    }
                
                for book in broken_books:
                    bid, title, author, pages, ingest_date = book
                    results['books_found'].append({
                        'book_id': str(bid),
                        'title': title,
                        'author': author,
                        'total_pages': pages,
                        'ingestion_date': str(ingest_date) if ingest_date else None
                    })
                    
                    if not dry_run:
                        # Count related records
                        cur.execute("SELECT COUNT(*) FROM chunks WHERE book_id = %s", (bid,))
                        chunk_count = cur.fetchone()[0]
                        
                        cur.execute("SELECT COUNT(*) FROM figures WHERE book_id = %s", (bid,))
                        figure_count = cur.fetchone()[0]
                        
                        cur.execute("SELECT COUNT(*) FROM chapter_documents WHERE book_id = %s", (bid,))
                        chapter_count = cur.fetchone()[0]
                        
                        # Delete related records (CASCADE should handle this, but being explicit)
                        cur.execute("DELETE FROM chunks WHERE book_id = %s", (bid,))
                        cur.execute("DELETE FROM figures WHERE book_id = %s", (bid,))
                        cur.execute("DELETE FROM chapter_documents WHERE book_id = %s", (bid,))
                        cur.execute("DELETE FROM books WHERE book_id = %s", (bid,))
                        
                        results['books_deleted'].append(str(bid))
                        results['chunks_deleted'] += chunk_count
                        results['figures_deleted'] += figure_count
                        results['chapters_deleted'] += chapter_count
                
                if not dry_run:
                    conn.commit()
                    logger.info(f"Deleted {len(results['books_deleted'])} broken book(s)")
                else:
                    logger.info(f"DRY RUN: Would delete {len(results['books_found'])} broken book(s)")
                
                return {
                    'statusCode': 200,
                    'body': json.dumps(results, indent=2, default=str)
                }
                
    except Exception as e:
        logger.error(f"Error cleaning up books: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Failed to clean up books'
            })
        }

