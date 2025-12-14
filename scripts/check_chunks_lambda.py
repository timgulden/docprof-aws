#!/usr/bin/env python3
"""
Quick script to check if chunks have embeddings by querying the database.
This can be run as a Lambda function or locally if you have VPC access.
"""

import json
import sys
from pathlib import Path

# Add src/lambda to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "lambda"))

from shared.db_utils import get_db_connection

def check_chunks():
    """Check if chunks have embeddings."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Count total chunks
                cur.execute("SELECT COUNT(*) FROM chunks")
                total = cur.fetchone()[0]
                
                # Count chunks with embeddings
                cur.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL")
                with_embeddings = cur.fetchone()[0]
                
                # Count by chunk type
                cur.execute("""
                    SELECT chunk_type, 
                           COUNT(*) as total,
                           COUNT(embedding) as with_embedding
                    FROM chunks
                    GROUP BY chunk_type
                    ORDER BY chunk_type
                """)
                by_type = cur.fetchall()
                
                # Count by book
                cur.execute("""
                    SELECT b.title, 
                           COUNT(c.chunk_id) as total_chunks,
                           COUNT(c.embedding) as with_embedding
                    FROM chunks c
                    LEFT JOIN books b ON c.book_id = b.book_id
                    GROUP BY b.title
                    ORDER BY b.title
                """)
                by_book = cur.fetchall()
                
                result = {
                    'total_chunks': total,
                    'chunks_with_embeddings': with_embeddings,
                    'chunks_without_embeddings': total - with_embeddings,
                    'by_type': [{'type': row[0], 'total': row[1], 'with_embedding': row[2]} for row in by_type],
                    'by_book': [{'title': row[0] or 'Unknown', 'total': row[1], 'with_embedding': row[2]} for row in by_book]
                }
                
                return result
    except Exception as e:
        return {'error': str(e)}

if __name__ == "__main__":
    result = check_chunks()
    print(json.dumps(result, indent=2))
