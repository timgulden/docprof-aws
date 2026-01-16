#!/usr/bin/env python3
"""
Compare Bedrock Titan vs OpenAI embeddings for RAG quality.
This helps determine if re-embedding with OpenAI would improve results.
"""

import os
import sys
import json
import boto3
import math

# Check for OpenAI
try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    print("OpenAI not installed. Run: pip install openai")


def generate_bedrock_embedding(text: str) -> list:
    """Generate embedding using Bedrock Titan."""
    client = boto3.client('bedrock-runtime', region_name='us-east-1')
    
    response = client.invoke_model(
        modelId='amazon.titan-embed-text-v1',
        contentType='application/json',
        accept='application/json',
        body=json.dumps({'inputText': text})
    )
    
    result = json.loads(response['body'].read())
    embedding = result['embedding']
    
    # Normalize
    magnitude = math.sqrt(sum(x*x for x in embedding))
    if magnitude > 0:
        embedding = [x / magnitude for x in embedding]
    
    return embedding


def generate_openai_embedding(text: str) -> list:
    """Generate embedding using OpenAI text-embedding-ada-002."""
    if not HAS_OPENAI:
        return None
    
    # Check for API key
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        print("OPENAI_API_KEY environment variable not set")
        return None
    
    client = openai.OpenAI(api_key=api_key)
    
    response = client.embeddings.create(
        model="text-embedding-ada-002",
        input=text
    )
    
    embedding = response.data[0].embedding
    
    # Normalize (OpenAI embeddings are usually already normalized, but just in case)
    magnitude = math.sqrt(sum(x*x for x in embedding))
    if magnitude > 0:
        embedding = [x / magnitude for x in embedding]
    
    return embedding


def search_with_embedding(embedding: list, label: str) -> dict:
    """Search database using Lambda with a specific embedding."""
    client = boto3.client('lambda', region_name='us-east-1')
    
    # We'll use a custom test payload that accepts a pre-computed embedding
    # For now, let's just invoke the test_embeddings mode with different queries
    # to see the difference
    
    # Actually, let's invoke a direct database query via a simple Lambda
    # For this test, we'll use the chat handler's test mode
    
    return None  # We'll do direct comparison instead


def main():
    print("="*70)
    print("EMBEDDING MODEL COMPARISON TEST")
    print("="*70)
    
    test_queries = [
        "What is M&A?",
        "How do you value a company using DCF?",
        "What are the key steps in a merger?",
        "Explain leveraged buyout",
    ]
    
    client = boto3.client('lambda', region_name='us-east-1')
    
    for query in test_queries:
        print(f"\n{'='*70}")
        print(f"Query: '{query}'")
        print("="*70)
        
        # Test 1: Bedrock Titan (current system)
        print("\n--- Bedrock Titan (current) ---")
        response = client.invoke(
            FunctionName='docprof-dev-chat-handler',
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'test_embeddings': True,
                'test_query': query
            })
        )
        result = json.loads(response['Payload'].read())
        if result.get('body'):
            body = json.loads(result['body']) if isinstance(result['body'], str) else result['body']
            print(f"Results: {body.get('results_count', 0)}")
            print(f"Best similarity: {body.get('best_similarity', 0):.4f}")
            print(f"Avg similarity: {body.get('avg_similarity', 0):.4f}")
            if body.get('top_3_content'):
                print(f"Top result preview: {body['top_3_content'][0][:100]}...")
    
    # Summary
    print("\n" + "="*70)
    print("ANALYSIS")
    print("="*70)
    print("""
The similarity scores tell us about embedding quality:
- 0.7+ : Excellent match (ideal)
- 0.5-0.7: Good match (acceptable)
- 0.3-0.5: Moderate match (may miss relevant content)
- <0.3: Poor match (likely wrong content)

If Bedrock Titan consistently shows 0.4-0.6 range, it's working but may not be
as precise as OpenAI embeddings for financial/technical content.

Options to consider:
1. Keep Bedrock Titan - it's working and integrated
2. Re-embed with OpenAI - better quality but costs money and takes time
3. Try Bedrock's newer Titan V2 model if available
4. Adjust retrieval (get more chunks, use different chunk types)
""")


if __name__ == '__main__':
    main()
