#!/usr/bin/env python3
"""
Direct RAG diagnostic test - bypasses Lambda/API to test database directly.
This will help isolate if the problem is in:
1. Embedding generation
2. Database query construction
3. Book ID filtering
4. Chunk types
"""

import os
import sys
import json
import boto3
import psycopg2
from psycopg2.extras import RealDictCursor

# Add parent to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'lambda'))

def get_db_connection():
    """Get database connection using secrets from AWS."""
    # Get secrets
    secrets_client = boto3.client('secretsmanager', region_name='us-east-1')
    
    # Get DB password
    secret_response = secrets_client.get_secret_value(
        SecretId='docprof-dev-aurora-master-password'
    )
    password = secret_response['SecretString']
    
    # Get cluster endpoint
    rds_client = boto3.client('rds', region_name='us-east-1')
    clusters = rds_client.describe_db_clusters(
        DBClusterIdentifier='docprof-dev-aurora'
    )
    endpoint = clusters['DBClusters'][0]['Endpoint']
    
    conn = psycopg2.connect(
        host=endpoint,
        port=5432,
        database='docprof',
        user='docprof_admin',
        password=password,
        connect_timeout=30
    )
    return conn


def generate_bedrock_embedding(text: str) -> list:
    """Generate embedding using Bedrock Titan."""
    client = boto3.client('bedrock-runtime', region_name='us-east-1')
    
    response = client.invoke_model(
        modelId='amazon.titan-embed-text-v1',
        contentType='application/json',
        accept='application/json',
        body=json.dumps({
            'inputText': text
        })
    )
    
    result = json.loads(response['body'].read())
    embedding = result['embedding']
    
    # Normalize (same as ingestion)
    import math
    magnitude = math.sqrt(sum(x*x for x in embedding))
    if magnitude > 0:
        embedding = [x / magnitude for x in embedding]
    
    return embedding


def test_database_contents(conn):
    """Check what's in the database."""
    print("\n" + "="*60)
    print("STEP 1: DATABASE CONTENTS")
    print("="*60)
    
    with conn.cursor() as cur:
        # Total books
        cur.execute("SELECT COUNT(*) FROM books")
        total_books = cur.fetchone()[0]
        print(f"\nTotal books: {total_books}")
        
        # List books
        cur.execute("SELECT book_id, title FROM books")
        books = cur.fetchall()
        print("\nBooks in database:")
        for book_id, title in books:
            print(f"  - {book_id}: {title[:60]}...")
        
        # Total chunks
        cur.execute("SELECT COUNT(*) FROM chunks")
        total_chunks = cur.fetchone()[0]
        print(f"\nTotal chunks: {total_chunks}")
        
        # Chunks with embeddings
        cur.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL")
        with_embeddings = cur.fetchone()[0]
        print(f"Chunks with embeddings: {with_embeddings}")
        
        # Chunk types
        cur.execute("""
            SELECT chunk_type, COUNT(*), 
                   COUNT(*) FILTER (WHERE embedding IS NOT NULL) as with_emb
            FROM chunks 
            GROUP BY chunk_type
        """)
        print("\nChunk types:")
        for chunk_type, count, with_emb in cur.fetchall():
            print(f"  - {chunk_type}: {count} chunks ({with_emb} with embeddings)")
        
        # Chunks per book
        cur.execute("""
            SELECT b.book_id, b.title, COUNT(c.chunk_id) as chunk_count,
                   COUNT(c.chunk_id) FILTER (WHERE c.embedding IS NOT NULL) as with_emb
            FROM books b
            LEFT JOIN chunks c ON b.book_id = c.book_id
            GROUP BY b.book_id, b.title
        """)
        print("\nChunks per book:")
        for book_id, title, count, with_emb in cur.fetchall():
            print(f"  - {title[:40]}: {count} chunks ({with_emb} with embeddings)")
    
    return books


def test_embedding_generation(test_query: str):
    """Test embedding generation."""
    print("\n" + "="*60)
    print("STEP 2: EMBEDDING GENERATION")
    print("="*60)
    
    print(f"\nTest query: '{test_query}'")
    print("Generating Bedrock Titan embedding...")
    
    embedding = generate_bedrock_embedding(test_query)
    print(f"Generated {len(embedding)}-dimensional embedding")
    print(f"First 5 values: {embedding[:5]}")
    print(f"Normalized: {abs(sum(x*x for x in embedding) - 1.0) < 0.001}")
    
    return embedding


def test_vector_search_no_filters(conn, embedding):
    """Test vector search with NO filters."""
    print("\n" + "="*60)
    print("STEP 3: VECTOR SEARCH - NO FILTERS")
    print("="*60)
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT 
                chunk_id, book_id, chunk_type, 
                LEFT(content, 100) as content_preview,
                1 - (embedding <=> %s::vector) as similarity
            FROM chunks
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT 10
        """, (embedding, embedding))
        
        results = cur.fetchall()
        
        print(f"\nFound {len(results)} results (no filters):")
        for i, r in enumerate(results, 1):
            print(f"\n  {i}. Similarity: {r['similarity']:.4f}")
            print(f"     Book ID: {r['book_id']}")
            print(f"     Type: {r['chunk_type']}")
            print(f"     Content: {r['content_preview']}...")
        
        return results


def test_vector_search_with_chunk_type(conn, embedding):
    """Test vector search with chunk_type filter only."""
    print("\n" + "="*60)
    print("STEP 4: VECTOR SEARCH - CHUNK_TYPE='2page' ONLY")
    print("="*60)
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT 
                chunk_id, book_id, chunk_type, 
                LEFT(content, 100) as content_preview,
                1 - (embedding <=> %s::vector) as similarity
            FROM chunks
            WHERE embedding IS NOT NULL
              AND chunk_type = '2page'
            ORDER BY embedding <=> %s::vector
            LIMIT 10
        """, (embedding, embedding))
        
        results = cur.fetchall()
        
        print(f"\nFound {len(results)} results (chunk_type='2page'):")
        for i, r in enumerate(results, 1):
            print(f"\n  {i}. Similarity: {r['similarity']:.4f}")
            print(f"     Book ID: {r['book_id']}")
            print(f"     Content: {r['content_preview']}...")
        
        return results


def test_vector_search_with_book_ids(conn, embedding, book_ids):
    """Test vector search with book_ids filter."""
    print("\n" + "="*60)
    print(f"STEP 5: VECTOR SEARCH - BOOK_IDS FILTER ({len(book_ids)} books)")
    print("="*60)
    
    print(f"\nBook IDs to filter: {book_ids}")
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # First check how many chunks exist for these books
        cur.execute("""
            SELECT COUNT(*) FROM chunks 
            WHERE book_id = ANY(%s::uuid[])
              AND embedding IS NOT NULL
        """, (book_ids,))
        total_matching = cur.fetchone()[0]
        print(f"Total chunks matching book filter (with embeddings): {total_matching}")
        
        # Now do the actual vector search
        cur.execute("""
            SELECT 
                chunk_id, book_id, chunk_type, 
                LEFT(content, 100) as content_preview,
                1 - (embedding <=> %s::vector) as similarity
            FROM chunks
            WHERE embedding IS NOT NULL
              AND book_id = ANY(%s::uuid[])
            ORDER BY embedding <=> %s::vector
            LIMIT 10
        """, (embedding, book_ids, embedding))
        
        results = cur.fetchall()
        
        print(f"\nFound {len(results)} results (book_ids filter):")
        for i, r in enumerate(results, 1):
            print(f"\n  {i}. Similarity: {r['similarity']:.4f}")
            print(f"     Book ID: {r['book_id']}")
            print(f"     Type: {r['chunk_type']}")
            print(f"     Content: {r['content_preview']}...")
        
        return results


def test_vector_search_with_both_filters(conn, embedding, book_ids):
    """Test vector search with BOTH chunk_type and book_ids filters."""
    print("\n" + "="*60)
    print(f"STEP 6: VECTOR SEARCH - BOTH FILTERS (chunk_type='2page' + book_ids)")
    print("="*60)
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # First check how many chunks exist with both filters
        cur.execute("""
            SELECT COUNT(*) FROM chunks 
            WHERE book_id = ANY(%s::uuid[])
              AND chunk_type = '2page'
              AND embedding IS NOT NULL
        """, (book_ids,))
        total_matching = cur.fetchone()[0]
        print(f"Total '2page' chunks for these books (with embeddings): {total_matching}")
        
        # Now do the actual vector search
        cur.execute("""
            SELECT 
                chunk_id, book_id, chunk_type, 
                LEFT(content, 100) as content_preview,
                1 - (embedding <=> %s::vector) as similarity
            FROM chunks
            WHERE embedding IS NOT NULL
              AND chunk_type = '2page'
              AND book_id = ANY(%s::uuid[])
            ORDER BY embedding <=> %s::vector
            LIMIT 10
        """, (embedding, book_ids, embedding))
        
        results = cur.fetchall()
        
        print(f"\nFound {len(results)} results (both filters):")
        for i, r in enumerate(results, 1):
            print(f"\n  {i}. Similarity: {r['similarity']:.4f}")
            print(f"     Book ID: {r['book_id']}")
            print(f"     Content: {r['content_preview']}...")
        
        return results


def main():
    print("="*60)
    print("DIRECT RAG DIAGNOSTIC TEST")
    print("="*60)
    print("This test bypasses Lambda/API and tests the database directly")
    
    test_query = "What is M&A?"
    
    # Connect to database
    print("\nConnecting to Aurora PostgreSQL...")
    conn = get_db_connection()
    print("Connected!")
    
    # Step 1: Check database contents
    books = test_database_contents(conn)
    book_ids = [str(b[0]) for b in books]
    
    # Step 2: Generate embedding
    embedding = test_embedding_generation(test_query)
    
    # Step 3: Vector search - no filters
    results_no_filter = test_vector_search_no_filters(conn, embedding)
    
    # Step 4: Vector search - chunk_type only
    results_chunk_type = test_vector_search_with_chunk_type(conn, embedding)
    
    # Step 5: Vector search - book_ids only
    results_book_ids = test_vector_search_with_book_ids(conn, embedding, book_ids)
    
    # Step 6: Vector search - both filters
    results_both = test_vector_search_with_both_filters(conn, embedding, book_ids)
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"\nResults count comparison:")
    print(f"  No filters:              {len(results_no_filter)} results")
    print(f"  chunk_type='2page' only: {len(results_chunk_type)} results")
    print(f"  book_ids only:           {len(results_book_ids)} results")
    print(f"  Both filters:            {len(results_both)} results")
    
    if results_no_filter:
        print(f"\nSimilarity scores (no filter):")
        print(f"  Best:  {max(r['similarity'] for r in results_no_filter):.4f}")
        print(f"  Worst: {min(r['similarity'] for r in results_no_filter):.4f}")
    
    # Check if M&A content is in results
    if results_no_filter:
        ma_mentions = sum(1 for r in results_no_filter if 'M&A' in r.get('content_preview', '') or 'merger' in r.get('content_preview', '').lower())
        print(f"\nResults mentioning M&A/merger: {ma_mentions}/10")
    
    conn.close()
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)


if __name__ == '__main__':
    main()
