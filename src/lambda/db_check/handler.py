"""
Lambda function to check database content and identify LLM-generated fields.
Updated to check for embeddings in chunks.
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
                
                # Check chunks table - detailed stats including embeddings
                cur.execute("""
                    SELECT 
                        chunk_type,
                        COUNT(*) as total,
                        COUNT(embedding) as with_embedding,
                        COUNT(*) - COUNT(embedding) as without_embedding
                    FROM chunks
                    GROUP BY chunk_type
                """)
                chunk_stats = cur.fetchall()
                
                results['chunks'] = {
                    'by_type': []
                }
                total_chunks = 0
                total_with_embeddings = 0
                
                for chunk_type, total, with_emb, without_emb in chunk_stats:
                    results['chunks']['by_type'].append({
                        'chunk_type': chunk_type,
                        'total': total,
                        'with_embedding': with_emb,
                        'without_embedding': without_emb,
                        'embedding_percentage': round((with_emb / total * 100) if total > 0 else 0, 2)
                    })
                    total_chunks += total
                    total_with_embeddings += with_emb
                
                results['chunks']['summary'] = {
                    'total_chunks': total_chunks,
                    'chunks_with_embeddings': total_with_embeddings,
                    'chunks_without_embeddings': total_chunks - total_with_embeddings,
                    'embedding_percentage': round((total_with_embeddings / total_chunks * 100) if total_chunks > 0 else 0, 2)
                }
                
                # Check chunks by book
                cur.execute("""
                    SELECT 
                        b.title,
                        b.book_id,
                        COUNT(c.chunk_id) as total_chunks,
                        COUNT(c.embedding) as with_embedding
                    FROM chunks c
                    LEFT JOIN books b ON c.book_id = b.book_id
                    GROUP BY b.title, b.book_id
                    ORDER BY b.title
                """)
                chunks_by_book = cur.fetchall()
                
                results['chunks']['by_book'] = []
                for title, book_id, total, with_emb in chunks_by_book:
                    results['chunks']['by_book'].append({
                        'book_id': str(book_id) if book_id else None,
                        'title': title or 'Unknown',
                        'total_chunks': total,
                        'with_embedding': with_emb,
                        'without_embedding': total - with_emb,
                        'embedding_percentage': round((with_emb / total * 100) if total > 0 else 0, 2)
                    })
                
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
                if results['chunks']['summary']['chunks_without_embeddings'] > 0:
                    results['recommendations'].append(
                        f"⚠️  CRITICAL: {results['chunks']['summary']['chunks_without_embeddings']} chunks ({100 - results['chunks']['summary']['embedding_percentage']:.1f}%) are missing embeddings. "
                        "Vector search will not work until embeddings are generated. Re-run the book ingestion pipeline."
                    )
                elif results['chunks']['summary']['total_chunks'] == 0:
                    results['recommendations'].append(
                        "⚠️  No chunks found in database. Books may not have been ingested yet."
                    )
                else:
                    results['recommendations'].append(
                        f"✓ All {results['chunks']['summary']['total_chunks']} chunks have embeddings. Vector search should work."
                    )
                
                if results['has_llm_content']:
                    results['recommendations'].append(
                        "Database contains LLM-generated content in books or chapters. "
                        "Consider purging this content before re-ingestion to regenerate with Claude Sonnet 4.5."
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
