#!/usr/bin/env python3
"""
Check if chunks exist with embeddings for course search to work.
"""

import os
import sys
import boto3
from psycopg2.extras import RealDictCursor

# Add parent directory to path to import shared modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'lambda'))

from shared.db_utils import get_db_connection

def check_chunks():
    """Check if chunks exist with embeddings."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Check total chunks
                cur.execute("SELECT COUNT(*) as total FROM chunks")
                total = cur.fetchone()['total']
                print(f"Total chunks: {total}")
                
                # Check chunks with embeddings
                cur.execute("SELECT COUNT(*) as total FROM chunks WHERE embedding IS NOT NULL")
                with_embeddings = cur.fetchone()['total']
                print(f"Chunks with embeddings: {with_embeddings}")
                
                # Check chunks without embeddings
                cur.execute("SELECT COUNT(*) as total FROM chunks WHERE embedding IS NULL")
                without_embeddings = cur.fetchone()['total']
                print(f"Chunks without embeddings: {without_embeddings}")
                
                # Check books that have chunks
                cur.execute("""
                    SELECT DISTINCT b.book_id, b.title, COUNT(c.chunk_id) as chunk_count
                    FROM books b
                    INNER JOIN chunks c ON b.book_id = c.book_id
                    WHERE c.embedding IS NOT NULL
                    GROUP BY b.book_id, b.title
                    ORDER BY chunk_count DESC
                """)
                books_with_chunks = cur.fetchall()
                print(f"\nBooks with embedded chunks: {len(books_with_chunks)}")
                for book in books_with_chunks:
                    print(f"  - {book['title']}: {book['chunk_count']} chunks")
                
                # Test a sample query to see if search would work
                if with_embeddings > 0:
                    print("\nTesting sample search query...")
                    # Get a random embedding to use as query
                    cur.execute("""
                        SELECT embedding
                        FROM chunks
                        WHERE embedding IS NOT NULL
                        LIMIT 1
                    """)
                    sample = cur.fetchone()
                    if sample:
                        query_embedding = sample['embedding']
                        # Try the actual search query
                        cur.execute("""
                            WITH relevant_chunks AS (
                                SELECT 
                                    book_id,
                                    1 - (embedding <=> %s::vector) as similarity
                                FROM chunks
                                WHERE embedding IS NOT NULL
                                  AND 1 - (embedding <=> %s::vector) >= 0.5
                                ORDER BY embedding <=> %s::vector
                                LIMIT 50
                            ),
                            book_relevance AS (
                                SELECT 
                                    book_id,
                                    MAX(similarity) as max_similarity,
                                    COUNT(*) as matching_chunks
                                FROM relevant_chunks
                                GROUP BY book_id
                            )
                            SELECT 
                                br.book_id,
                                b.title as book_title,
                                br.max_similarity as similarity,
                                br.matching_chunks
                            FROM book_relevance br
                            INNER JOIN books b ON br.book_id = b.book_id
                            ORDER BY br.max_similarity DESC
                            LIMIT 5
                        """, (query_embedding, query_embedding, query_embedding))
                        results = cur.fetchall()
                        print(f"Sample search returned {len(results)} books:")
                        for book in results:
                            print(f"  - {book['book_title']}: similarity={book['similarity']:.3f}, chunks={book['matching_chunks']}")
                
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    check_chunks()
