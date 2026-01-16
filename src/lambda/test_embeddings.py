"""
Test script to compare OpenAI vs Bedrock Titan embeddings against database.

This will prove whether the database has OpenAI or Bedrock embeddings by:
1. Generating embeddings for "What is M&A?" with both models
2. Searching the database with each embedding
3. Comparing similarity scores

Run as a Lambda or locally with proper AWS credentials.
"""

import json
import logging
from typing import List, Dict, Any

# Bedrock imports
import boto3
from shared.bedrock_client import generate_embeddings as generate_bedrock_embeddings
from shared.db_utils import get_db_connection

# OpenAI imports (need to install: pip install openai)
try:
    import openai
    import os
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("OpenAI not available - install with: pip install openai")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_openai_embedding(text: str) -> List[float]:
    """Generate embedding using OpenAI text-embedding-ada-002."""
    if not OPENAI_AVAILABLE:
        raise ImportError("OpenAI library not installed")
    
    # Get API key from environment
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    client = openai.OpenAI(api_key=api_key)
    
    response = client.embeddings.create(
        model="text-embedding-ada-002",
        input=text
    )
    
    return response.data[0].embedding


def search_with_embedding(embedding: List[float], model_name: str, limit: int = 10) -> Dict[str, Any]:
    """Search database with given embedding and return results."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing with {model_name} embedding")
    logger.info(f"{'='*60}")
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Search chunks with no threshold (get top K by similarity)
            query = """
                SELECT 
                    chunk_id,
                    book_id,
                    chunk_type,
                    content,
                    1 - (embedding <=> %s::vector) as similarity
                FROM chunks
                WHERE embedding IS NOT NULL
                  AND chunk_type = '2page'
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """
            
            cur.execute(query, (embedding, embedding, limit))
            results = cur.fetchall()
            
            logger.info(f"\nFound {len(results)} results")
            logger.info(f"Similarity scores:")
            
            for i, (chunk_id, book_id, chunk_type, content, similarity) in enumerate(results, 1):
                logger.info(f"  {i}. Similarity: {similarity:.4f} - {content[:100]}...")
            
            if results:
                best_similarity = results[0][4]
                avg_similarity = sum(r[4] for r in results) / len(results)
                worst_similarity = results[-1][4]
                
                summary = {
                    'model': model_name,
                    'count': len(results),
                    'best_similarity': best_similarity,
                    'avg_similarity': avg_similarity,
                    'worst_similarity': worst_similarity,
                    'top_3_content': [r[3][:200] for r in results[:3]]
                }
                
                logger.info(f"\nSummary for {model_name}:")
                logger.info(f"  Best similarity: {best_similarity:.4f}")
                logger.info(f"  Avg similarity:  {avg_similarity:.4f}")
                logger.info(f"  Worst similarity: {worst_similarity:.4f}")
                
                return summary
            else:
                logger.warning(f"No results found for {model_name}")
                return {'model': model_name, 'count': 0}


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler for testing embeddings."""
    return run_embedding_test()


def run_embedding_test() -> Dict[str, Any]:
    """Run the embedding comparison test."""
    test_query = "What is M&A?"
    
    logger.info(f"\n{'='*60}")
    logger.info(f"EMBEDDING MODEL TEST")
    logger.info(f"{'='*60}")
    logger.info(f"Test query: '{test_query}'")
    
    results = {}
    
    # Test 1: Bedrock Titan (current system)
    logger.info("\n[1/2] Generating Bedrock Titan embedding...")
    bedrock_embedding = generate_bedrock_embeddings([test_query], normalize=True)[0]
    logger.info(f"  Generated {len(bedrock_embedding)}-dimensional embedding")
    results['bedrock'] = search_with_embedding(bedrock_embedding, "Bedrock Titan", limit=10)
    
    # Test 2: OpenAI (if available)
    if OPENAI_AVAILABLE and os.getenv('OPENAI_API_KEY'):
        logger.info("\n[2/2] Generating OpenAI embedding...")
        try:
            openai_embedding = generate_openai_embedding(test_query)
            logger.info(f"  Generated {len(openai_embedding)}-dimensional embedding")
            results['openai'] = search_with_embedding(openai_embedding, "OpenAI Ada-002", limit=10)
        except Exception as e:
            logger.error(f"Failed to test OpenAI: {e}")
            results['openai'] = {'error': str(e)}
    else:
        logger.warning("\n[2/2] OpenAI not available - skipping")
        logger.warning("  To test OpenAI, set OPENAI_API_KEY environment variable")
        results['openai'] = {'error': 'OpenAI not available'}
    
    # Compare results
    logger.info(f"\n{'='*60}")
    logger.info("COMPARISON")
    logger.info(f"{'='*60}")
    
    if 'best_similarity' in results.get('bedrock', {}):
        bedrock_best = results['bedrock']['best_similarity']
        logger.info(f"Bedrock Titan best similarity: {bedrock_best:.4f}")
    
    if 'best_similarity' in results.get('openai', {}):
        openai_best = results['openai']['best_similarity']
        logger.info(f"OpenAI Ada-002 best similarity: {openai_best:.4f}")
    
    # Conclusion
    logger.info(f"\n{'='*60}")
    logger.info("CONCLUSION")
    logger.info(f"{'='*60}")
    
    bedrock_best = results.get('bedrock', {}).get('best_similarity', 0)
    openai_best = results.get('openai', {}).get('best_similarity', 0)
    
    if bedrock_best > 0.4:
        logger.info("✅ Database chunks appear to have BEDROCK TITAN embeddings")
        logger.info(f"   (Bedrock similarity: {bedrock_best:.4f} is good)")
    elif openai_best > 0.4:
        logger.info("✅ Database chunks appear to have OPENAI embeddings")
        logger.info(f"   (OpenAI similarity: {openai_best:.4f} is good, Bedrock: {bedrock_best:.4f} is poor)")
    elif bedrock_best < 0.3 and openai_best < 0.3:
        logger.info("⚠️  Low similarity with BOTH models - possible issues:")
        logger.info("   - Chunks don't contain M&A content")
        logger.info("   - Embeddings are corrupted")
        logger.info("   - Different embedding model entirely")
    else:
        logger.info(f"🤔 Unclear - similarities: Bedrock={bedrock_best:.4f}, OpenAI={openai_best:.4f}")
    
    return {
        'statusCode': 200,
        'body': json.dumps(results, indent=2)
    }


if __name__ == "__main__":
    # For local testing
    run_embedding_test()
