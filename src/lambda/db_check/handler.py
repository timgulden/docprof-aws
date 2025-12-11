"""
Lambda function to check database content and identify LLM-generated fields.
"""

import json
import logging
from typing import Dict, Any

from shared.db_utils import get_db_connection

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Check database for existing content and LLM-generated fields."""
    
    results = {
        'books': [],
        'chapters': [],
        'chunks': {},
        'figures': {},
        'has_llm_content': False,
        'recommendations': []
    }
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check books table
                cur.execute("""
                    SELECT 
                        book_id,
                        title,
                        author,
                        edition,
                        total_pages,
                        ingestion_date,
                        metadata
                    FROM books
                    ORDER BY ingestion_date DESC
                    LIMIT 10
                """)
                books = cur.fetchall()
                
                for book in books:
                    book_id, title, author, edition, pages, ingest_date, metadata = book
                    book_info = {
                        'book_id': str(book_id),
                        'title': title,
                        'author': author,
                        'edition': edition,
                        'total_pages': pages,
                        'ingestion_date': str(ingest_date) if ingest_date else None,
                        'metadata': metadata,
                        'has_llm_content': False
                    }
                    
                    # Check if metadata has LLM-generated fields
                    if metadata:
                        llm_fields = ['summary', 'description', 'key_points', 'overview', 'generated_summary']
                        has_llm = any(field in metadata for field in llm_fields)
                        book_info['has_llm_content'] = has_llm
                        if has_llm:
                            results['has_llm_content'] = True
                            book_info['llm_fields'] = [field for field in llm_fields if field in metadata]
                    
                    results['books'].append(book_info)
                
                # Check chapter_documents table
                cur.execute("""
                    SELECT 
                        chapter_document_id,
                        book_id,
                        chapter_number,
                        chapter_title,
                        LENGTH(content) as content_length,
                        metadata
                    FROM chapter_documents
                    ORDER BY book_id, chapter_number
                    LIMIT 50
                """)
                chapters = cur.fetchall()
                
                for chapter in chapters:
                    ch_id, book_id, ch_num, ch_title, content_len, metadata = chapter
                    chapter_info = {
                        'chapter_document_id': str(ch_id),
                        'book_id': str(book_id),
                        'chapter_number': ch_num,
                        'chapter_title': ch_title,
                        'content_length': content_len,
                        'metadata': metadata,
                        'has_llm_content': False
                    }
                    
                    # Check if metadata has LLM-generated fields
                    if metadata:
                        llm_fields = ['summary', 'description', 'key_points', 'overview', 'generated_summary']
                        has_llm = any(field in metadata for field in llm_fields)
                        chapter_info['has_llm_content'] = has_llm
                        if has_llm:
                            results['has_llm_content'] = True
                            chapter_info['llm_fields'] = [field for field in llm_fields if field in metadata]
                    
                    results['chapters'].append(chapter_info)
                
                # Check chunks table
                cur.execute("""
                    SELECT 
                        chunk_type,
                        COUNT(*) as count
                    FROM chunks
                    GROUP BY chunk_type
                """)
                chunk_stats = cur.fetchall()
                
                for chunk_type, count in chunk_stats:
                    results['chunks'][chunk_type] = count
                
                # Check figures table
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_figures,
                        COUNT(DISTINCT book_id) as books_with_figures
                    FROM figures
                """)
                figure_stats = cur.fetchone()
                
                if figure_stats:
                    results['figures'] = {
                        'total': figure_stats[0],
                        'books_with_figures': figure_stats[1]
                    }
                
                # Generate recommendations
                if results['has_llm_content']:
                    results['recommendations'].append(
                        "Database contains LLM-generated content in books or chapters. "
                        "Consider purging this content before re-ingestion to regenerate with Claude Sonnet 4.5."
                    )
                else:
                    results['recommendations'].append(
                        "Database looks clean - no LLM-generated content detected. Ready for ingestion."
                    )
                
                return {
                    'statusCode': 200,
                    'body': json.dumps(results, indent=2, default=str)
                }
                
    except Exception as e:
        logger.error(f"Error checking database: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Failed to check database content'
            })
        }

