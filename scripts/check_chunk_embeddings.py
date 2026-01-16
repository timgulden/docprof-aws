#!/usr/bin/env python3
"""Check if chunks have embeddings in the database."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'lambda'))

from shared.db_utils import get_db_connection

with get_db_connection() as conn:
    with conn.cursor() as cur:
        # Check if chunks have embeddings
        cur.execute('SELECT COUNT(*) as total, COUNT(embedding) as with_embedding FROM chunks')
        row = cur.fetchone()
        print(f'Total chunks: {row[0]}, With embeddings: {row[1]}')
        
        # Check embeddings per book
        cur.execute('''
            SELECT b.title, COUNT(c.chunk_id) as total_chunks, COUNT(c.embedding) as chunks_with_embedding
            FROM books b
            LEFT JOIN chunks c ON b.book_id = c.book_id
            GROUP BY b.book_id, b.title
            ORDER BY b.title
        ''')
        print('\nChunks per book:')
        for row in cur.fetchall():
            print(f'  {row[0]}: {row[1]} total, {row[2]} with embeddings')
