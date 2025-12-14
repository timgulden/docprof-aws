#!/usr/bin/env python3
"""
Diagnostic script to check RAG pipeline issues.
Checks:
1. If chunks exist with embeddings
2. If vector search is working
3. If embeddings are being generated correctly
4. Tests similarity thresholds
"""

import os
import sys
import json
from pathlib import Path

# Add src/lambda/shared to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "lambda"))

from shared.db_utils import get_db_connection, vector_similarity_search
from shared.bedrock_client import generate_embeddings

# Set up environment variables (adjust as needed)
os.environ.setdefault('AWS_PROFILE', 'docprof-dev')
os.environ.setdefault('AWS_REGION', 'us-east-1')

# These should be set by Terraform, but for local testing we might need them
# Check if they're set, otherwise we'll need to get them from Terraform state
if not os.getenv('DB_CLUSTER_ENDPOINT'):
    print("ERROR: DB_CLUSTER_ENDPOINT not set. Run this from Lambda or set environment variables.")
    print("You may need to get these from Terraform outputs or AWS console.")
    sys.exit(1)


def check_chunks_with_embeddings():
    """Check if chunks exist and have embeddings."""
    print("\n=== Checking Chunks with Embeddings ===")
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Count total chunks
            cur.execute("SELECT COUNT(*) FROM chunks")
            total_chunks = cur.fetchone()[0]
            print(f"Total chunks: {total_chunks}")
            
            # Count chunks with embeddings
            cur.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL")
            chunks_with_embeddings = cur.fetchone()[0]
            print(f"Chunks with embeddings: {chunks_with_embeddings}")
            
            # Count chunks without embeddings
            chunks_without = total_chunks - chunks_with_embeddings
            print(f"Chunks without embeddings: {chunks_without}")
            
            # Check by chunk type
            cur.execute("""
                SELECT chunk_type, 
                       COUNT(*) as total,
                       COUNT(embedding) as with_embedding
                FROM chunks
                GROUP BY chunk_type
                ORDER BY chunk_type
            """)
            print("\nBy chunk type:")
            for row in cur.fetchall():
                print(f"  {row[0]}: {row[1]} total, {row[2]} with embeddings")
            
            # Check by book
            cur.execute("""
                SELECT b.title, 
                       COUNT(c.chunk_id) as total_chunks,
                       COUNT(c.embedding) as with_embedding
                FROM chunks c
                LEFT JOIN books b ON c.book_id = b.book_id
                GROUP BY b.title
                ORDER BY b.title
            """)
            print("\nBy book:")
            for row in cur.fetchall():
                title = row[0] or "Unknown"
                print(f"  {title}: {row[1]} total chunks, {row[2]} with embeddings")
            
            return chunks_with_embeddings > 0


def test_embedding_generation():
    """Test if embeddings can be generated."""
    print("\n=== Testing Embedding Generation ===")
    
    test_query = "What does M&A stand for?"
    print(f"Test query: '{test_query}'")
    
    try:
        embeddings = generate_embeddings([test_query])
        embedding = embeddings[0]
        print(f"✓ Embedding generated: {len(embedding)} dimensions")
        print(f"  First 5 values: {embedding[:5]}")
        return embedding
    except Exception as e:
        print(f"✗ Failed to generate embedding: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_vector_search(query_embedding, threshold=0.7):
    """Test vector search with different thresholds."""
    print(f"\n=== Testing Vector Search (threshold={threshold}) ===")
    
    if not query_embedding:
        print("Skipping - no query embedding")
        return []
    
    try:
        results = vector_similarity_search(
            query_embedding=query_embedding,
            chunk_types=["2page"],
            limit=10,
            similarity_threshold=threshold
        )
        
        print(f"Found {len(results)} results")
        
        if results:
            print("\nTop results:")
            for i, result in enumerate(results[:5], 1):
                similarity = result.get('similarity', 0)
                chunk_id = result.get('chunk_id', 'unknown')
                book_id = result.get('book_id', 'unknown')
                chapter = result.get('chapter_title', 'Unknown')
                page_start = result.get('page_start', '?')
                content_preview = result.get('content', '')[:100]
                
                print(f"\n  [{i}] Similarity: {similarity:.4f}")
                print(f"      Chunk ID: {chunk_id}")
                print(f"      Book ID: {book_id}")
                print(f"      Chapter: {chapter}, Page: {page_start}")
                print(f"      Preview: {content_preview}...")
        
        return results
    except Exception as e:
        print(f"✗ Vector search failed: {e}")
        import traceback
        traceback.print_exc()
        return []


def test_different_thresholds(query_embedding):
    """Test with different similarity thresholds."""
    print("\n=== Testing Different Similarity Thresholds ===")
    
    thresholds = [0.5, 0.6, 0.7, 0.8, 0.9]
    
    for threshold in thresholds:
        results = test_vector_search(query_embedding, threshold=threshold)
        print(f"  Threshold {threshold}: {len(results)} results")


def main():
    print("RAG Pipeline Diagnostic")
    print("=" * 50)
    
    # Step 1: Check chunks
    has_embeddings = check_chunks_with_embeddings()
    
    if not has_embeddings:
        print("\n⚠️  WARNING: No chunks have embeddings!")
        print("   This is likely the problem. Chunks need to be processed with embeddings.")
        print("   Check the book ingestion pipeline.")
        return
    
    # Step 2: Test embedding generation
    query_embedding = test_embedding_generation()
    
    if not query_embedding:
        print("\n⚠️  WARNING: Cannot generate embeddings!")
        print("   Check Bedrock access and configuration.")
        return
    
    # Step 3: Test vector search with default threshold
    results = test_vector_search(query_embedding, threshold=0.7)
    
    if not results:
        print("\n⚠️  WARNING: No results with threshold 0.7")
        print("   Trying lower thresholds...")
        test_different_thresholds(query_embedding)
    else:
        print("\n✓ Vector search is working!")
        print("   If chat still doesn't work, check:")
        print("   1. Query expansion logic")
        print("   2. Lambda logs for errors")
        print("   3. Bedrock access permissions")


if __name__ == "__main__":
    main()
