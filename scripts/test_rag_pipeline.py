#!/usr/bin/env python3
"""
Test script to run the full RAG pipeline outside of Lambda/UI.
Uses the same code as the Lambda handler to test the complete flow.

Usage:
    # Set environment variables first (see below)
    python3 scripts/test_rag_pipeline.py "What does M&A stand for?"
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from uuid import uuid4

# Add src/lambda to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "lambda"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import Lambda code
from shared.session_manager import get_session, create_session
from shared.bedrock_client import invoke_claude, generate_embeddings
from shared.db_utils import vector_similarity_search, get_db_connection
from shared.model_adapters import (
    dict_to_chat_state,
    get_expand_query,
    get_build_prompt,
    get_system_prompt
)


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_rag_pipeline(user_message: str, session_id: str = None):
    """
    Test the complete RAG pipeline.
    
    Args:
        user_message: The user's question
        session_id: Optional existing session ID
    """
    print_section("RAG Pipeline Test")
    print(f"User Message: '{user_message}'")
    if session_id:
        print(f"Session ID: {session_id}")
    
    try:
        # Step 1: Get or create session
        print_section("Step 1: Session Management")
        if session_id:
            session = get_session(session_id)
            if not session:
                print(f"⚠️  Session not found: {session_id}, creating new session")
                session = create_session()
                session_id = session['session_id']
            else:
                print(f"✓ Found existing session: {session_id}")
        else:
            session = create_session()
            session_id = session['session_id']
            print(f"✓ Created new session: {session_id}")
        
        print(f"Session has {len(session.get('messages', []))} messages")
        
        # Step 2: Convert to ChatState
        print_section("Step 2: Convert Session to ChatState")
        chat_state = dict_to_chat_state(session)
        conversation_history = chat_state.messages
        print(f"✓ Converted to ChatState")
        print(f"  - Session context: {chat_state.session_context or 'None'}")
        print(f"  - Conversation history: {len(conversation_history)} messages")
        
        # Step 3: Expand query
        print_section("Step 3: Query Expansion")
        expand_query_fn = get_expand_query()
        expanded_query = expand_query_fn(
            user_message,
            session_context=chat_state.session_context,
            conversation_history=conversation_history
        )
        print(f"Original query: '{user_message}'")
        print(f"Expanded query: '{expanded_query}'")
        print(f"✓ Query expanded ({len(expanded_query)} chars)")
        
        # Step 4: Generate embedding
        print_section("Step 4: Generate Embedding")
        print(f"Generating embedding for: '{expanded_query[:100]}...'")
        try:
            embeddings = generate_embeddings([expanded_query])
            query_embedding = embeddings[0]
            print(f"✓ Embedding generated: {len(query_embedding)} dimensions")
            print(f"  First 5 values: {query_embedding[:5]}")
            print(f"  Embedding magnitude: {sum(x*x for x in query_embedding)**0.5:.4f}")
        except Exception as e:
            print(f"✗ Failed to generate embedding: {e}")
            import traceback
            traceback.print_exc()
            return None
        
        # Step 5: Vector search
        print_section("Step 5: Vector Search")
        chunk_types = ["2page"]
        print(f"Searching for chunk types: {chunk_types}")
        
        # Try multiple thresholds
        search_results = None
        thresholds = [0.7, 0.6, 0.5, 0.4, 0.3]
        
        for threshold in thresholds:
            print(f"\n  Trying threshold={threshold}...")
            try:
                results = vector_similarity_search(
                    query_embedding=query_embedding,
                    chunk_types=chunk_types,
                    book_id=None,  # Search all books
                    limit=12,
                    similarity_threshold=threshold
                )
                print(f"  → Found {len(results)} results")
                
                if results:
                    search_results = results
                    print(f"✓ Found {len(results)} chunks with threshold={threshold}")
                    
                    # Show top results
                    print("\n  Top 3 results:")
                    for i, result in enumerate(results[:3], 1):
                        similarity = result.get('similarity', 0)
                        chunk_id = result.get('chunk_id', 'unknown')[:8]
                        chapter = result.get('chapter_title', 'Unknown')
                        page_start = result.get('page_start', '?')
                        content_preview = result.get('content', '')[:80].replace('\n', ' ')
                        
                        print(f"    [{i}] Similarity: {similarity:.4f}")
                        print(f"        Chunk: {chunk_id}... | {chapter} (p{page_start})")
                        print(f"        Preview: {content_preview}...")
                    break
                else:
                    print(f"  → No results")
            except Exception as e:
                print(f"  ✗ Search failed: {e}")
                import traceback
                traceback.print_exc()
                return None
        
        if not search_results:
            print(f"\n✗ No chunks found after trying all thresholds: {thresholds}")
            print("\nPossible issues:")
            print("  1. Chunks don't have embeddings (most likely)")
            print("  2. Query embedding doesn't match chunk embeddings")
            print("  3. Similarity threshold too high (tried down to 0.3)")
            print("\nNext steps:")
            print("  - Check if chunks have embeddings in database")
            print("  - Verify embedding model matches (should be amazon.titan-embed-text-v1)")
            print("  - Check database connection and query syntax")
            return None
        
        # Step 6: Build synthesis prompt
        print_section("Step 6: Build Synthesis Prompt")
        chunks = []
        for chunk in search_results:
            chunks.append({
                'chunk_type': chunk.get('chunk_type', '2page'),
                'chapter_title': chunk.get('chapter_title'),
                'chapter_number': chunk.get('chapter_number'),
                'page_start': chunk.get('page_start'),
                'page_end': chunk.get('page_end'),
                'content': chunk.get('content', '')[:8000]
            })
        
        history_for_prompt = conversation_history[-5:] if len(conversation_history) >= 5 else conversation_history
        print(f"Using {len(chunks)} chunks and {len(history_for_prompt)} history messages")
        
        build_prompt_fn = get_build_prompt()
        prompt = build_prompt_fn(
            user_message=user_message,
            conversation_history=history_for_prompt,
            chunks=chunks,
            session_context=chat_state.session_context
        )
        
        print(f"✓ Prompt built: {len(prompt)} characters")
        print(f"\nPrompt preview (first 500 chars):")
        print("-" * 70)
        print(prompt[:500] + "...")
        print("-" * 70)
        
        # Step 7: Call Claude for synthesis
        print_section("Step 7: LLM Synthesis")
        system_prompt = get_system_prompt()
        print(f"System prompt length: {len(system_prompt)} chars")
        print(f"User prompt length: {len(prompt)} chars")
        print("\nCalling Claude...")
        
        try:
            llm_response = invoke_claude(
                messages=[{"role": "user", "content": prompt}],
                system=system_prompt,
                max_tokens=8000,
                temperature=0.3,
                stream=False
            )
            
            synthesized_text = llm_response['content']
            usage = llm_response.get('usage', {})
            
            print(f"✓ Claude response received")
            print(f"  Input tokens: {usage.get('input_tokens', 0)}")
            print(f"  Output tokens: {usage.get('output_tokens', 0)}")
            print(f"\nResponse ({len(synthesized_text)} chars):")
            print("-" * 70)
            print(synthesized_text)
            print("-" * 70)
            
        except Exception as e:
            print(f"✗ Failed to call Claude: {e}")
            import traceback
            traceback.print_exc()
            return None
        
        # Step 8: Build source citations
        print_section("Step 8: Build Source Citations")
        source_citations = []
        book_title_cache = {}
        
        for i, chunk in enumerate(search_results, 1):
            book_id = chunk.get('book_id')
            
            # Get book title
            if book_id and book_id not in book_title_cache:
                try:
                    with get_db_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("SELECT title FROM books WHERE book_id = %s", (book_id,))
                            result = cur.fetchone()
                            if result:
                                book_title_cache[book_id] = result[0]
                            else:
                                book_title_cache[book_id] = "Unknown Book"
                except Exception as e:
                    logger.warning(f"Failed to get book title for {book_id}: {e}")
                    book_title_cache[book_id] = "Unknown Book"
            
            citation = {
                'citation_id': f"[{i}]",
                'chunk_id': chunk.get('chunk_id', ''),
                'chunk_type': chunk.get('chunk_type', '2page'),
                'book_id': book_id or '',
                'book_title': book_title_cache.get(book_id, 'Unknown Book'),
                'chapter_number': chunk.get('chapter_number'),
                'chapter_title': chunk.get('chapter_title'),
                'page_start': chunk.get('page_start'),
                'page_end': chunk.get('page_end'),
                'target_page': chunk.get('page_start'),
                'content': chunk.get('content', '')[:1000],
                'score': chunk.get('similarity')
            }
            source_citations.append(citation)
        
        print(f"✓ Built {len(source_citations)} citations")
        print("\nCitations:")
        for citation in source_citations[:3]:
            print(f"  {citation['citation_id']} {citation['book_title']} - {citation['chapter_title']} (p{citation['page_start']}) - Score: {citation['score']:.4f}")
        
        # Summary
        print_section("Pipeline Summary")
        print("✓ All steps completed successfully!")
        print(f"\nFinal Response:")
        print(f"  Message: {synthesized_text[:200]}...")
        print(f"  Sources: {len(source_citations)} citations")
        print(f"  Session ID: {session_id}")
        
        return {
            'session_id': session_id,
            'response': synthesized_text,
            'sources': source_citations,
            'chunks_found': len(search_results),
            'threshold_used': threshold
        }
        
    except Exception as e:
        print_section("Error")
        print(f"✗ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/test_rag_pipeline.py '<your question>' [session_id]")
        print("\nExample:")
        print('  python3 scripts/test_rag_pipeline.py "What does M&A stand for?"')
        print("\nEnvironment variables needed:")
        print("  - DB_CLUSTER_ENDPOINT")
        print("  - DB_NAME")
        print("  - DB_PASSWORD_SECRET_ARN (or DB_PASSWORD)")
        print("  - AWS_PROFILE (default: docprof-dev)")
        print("  - AWS_REGION (default: us-east-1)")
        print("\nTo get database info from Terraform:")
        print("  cd terraform/environments/dev")
        print("  export DB_CLUSTER_ENDPOINT=$(terraform output -raw aurora_cluster_endpoint)")
        print("  export DB_NAME=$(terraform output -raw aurora_database_name)")
        print("  export DB_PASSWORD_SECRET_ARN=$(terraform output -raw aurora_master_password_secret_arn)")
        sys.exit(1)
    
    user_message = sys.argv[1]
    session_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Check environment variables
    required_vars = ['DB_CLUSTER_ENDPOINT', 'DB_NAME']
    missing = [v for v in required_vars if not os.getenv(v)]
    
    if missing:
        print(f"✗ Missing required environment variables: {', '.join(missing)}")
        print("\nGet them from Terraform outputs:")
        print("  cd terraform/environments/dev")
        print("  terraform output")
        sys.exit(1)
    
    # Set defaults
    os.environ.setdefault('AWS_PROFILE', 'docprof-dev')
    os.environ.setdefault('AWS_REGION', 'us-east-1')
    
    # Run the pipeline
    result = test_rag_pipeline(user_message, session_id)
    
    if result:
        print("\n" + "=" * 70)
        print("✓ Test completed successfully!")
        print("=" * 70)
        sys.exit(0)
    else:
        print("\n" + "=" * 70)
        print("✗ Test failed - check output above for details")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    main()
