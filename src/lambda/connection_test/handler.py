"""
Connection Test Lambda Handler
Lightweight test to verify critical infrastructure connections before full ingestion.

Tests:
1. Secrets Manager access (get DB password)
2. Database connection (Aurora PostgreSQL)
3. Basic database operations (query, insert test record)
4. Optional: Bedrock connectivity (if AI endpoints enabled)
"""

import json
import os
import logging
from typing import Dict, Any

from shared.db_utils import get_db_connection_info, get_db_connection
from shared.response import success_response, error_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Test critical infrastructure connections.
    
    Expected event:
    {
        "test": "all" | "secrets" | "database" | "bedrock",
        "test_insert": true | false  # Whether to insert a test record
    }
    """
    test_type = event.get('test', 'all')
    test_insert = event.get('test_insert', False)
    
    results = {
        'secrets_manager': None,
        'database_connection': None,
        'database_query': None,
        'database_insert': None,
        'bedrock': None
    }
    
    errors = []
    
    # Test 1: Secrets Manager access
    if test_type in ['all', 'secrets']:
        try:
            logger.info("Testing Secrets Manager access...")
            conn_info = get_db_connection_info()
            results['secrets_manager'] = {
                'status': 'success',
                'host': conn_info['host'],
                'database': conn_info['database'],
                'user': conn_info['user'],
                'password_retrieved': bool(conn_info.get('password'))
            }
            logger.info("✓ Secrets Manager access successful")
        except Exception as e:
            error_msg = f"Secrets Manager test failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results['secrets_manager'] = {
                'status': 'failed',
                'error': str(e)
            }
            errors.append(error_msg)
    
    # Test 2: Database connection
    if test_type in ['all', 'database']:
        try:
            logger.info("Testing database connection...")
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Test query: Check pgvector extension
                    cur.execute("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';")
                    vector_ext = cur.fetchone()
                    
                    # Test query: Count tables
                    cur.execute("""
                        SELECT COUNT(*) 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public'
                    """)
                    table_count = cur.fetchone()[0]
                    
                    # Test query: Check if books table exists
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = 'books'
                        )
                    """)
                    books_table_exists = cur.fetchone()[0]
                    
                    results['database_connection'] = {
                        'status': 'success',
                        'pgvector_installed': bool(vector_ext),
                        'pgvector_version': vector_ext[1] if vector_ext else None,
                        'table_count': table_count,
                        'books_table_exists': books_table_exists
                    }
                    logger.info("✓ Database connection successful")
        except Exception as e:
            error_msg = f"Database connection test failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results['database_connection'] = {
                'status': 'failed',
                'error': str(e)
            }
            errors.append(error_msg)
    
    # Test 3: Database query (find_book)
    if test_type in ['all', 'database'] and results.get('database_connection', {}).get('status') == 'success':
        try:
            logger.info("Testing database query (find_book)...")
            from shared.protocol_implementations import AWSDatabaseClient
            
            database = AWSDatabaseClient()
            # Try to find a non-existent book (should return None, not error)
            result = database.find_book({
                'title': '__TEST_BOOK_THAT_DOES_NOT_EXIST__',
                'author': None,
                'isbn': None
            })
            
            results['database_query'] = {
                'status': 'success',
                'find_book_returned': result is None,  # Should be None for non-existent book
                'note': 'Query executed successfully'
            }
            logger.info("✓ Database query test successful")
        except Exception as e:
            error_msg = f"Database query test failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results['database_query'] = {
                'status': 'failed',
                'error': str(e)
            }
            errors.append(error_msg)
    
    # Test 4: Database insert (optional)
    if test_insert and test_type in ['all', 'database'] and results.get('database_query', {}).get('status') == 'success':
        try:
            logger.info("Testing database insert...")
            from shared.protocol_implementations import AWSDatabaseClient
            
            database = AWSDatabaseClient()
            # Insert a test book
            test_book_id = database.insert_book(
                metadata={
                    'title': '__CONNECTION_TEST_BOOK__',
                    'author': 'Test Author',
                    'edition': 'Test Edition',
                    'isbn': 'TEST-ISBN-12345'
                },
                total_pages=1
            )
            
            # Verify it was inserted
            found_id = database.find_book({
                'title': '__CONNECTION_TEST_BOOK__',
                'author': 'Test Author',
                'isbn': 'TEST-ISBN-12345'
            })
            
            if found_id == test_book_id:
                # Clean up: delete test book
                database.delete_book_contents(test_book_id, delete_book=True)
                results['database_insert'] = {
                    'status': 'success',
                    'test_book_id': test_book_id,
                    'note': 'Insert, query, and delete all successful'
                }
                logger.info("✓ Database insert test successful")
            else:
                results['database_insert'] = {
                    'status': 'failed',
                    'error': f'Inserted ID {test_book_id} but found {found_id}'
                }
                errors.append("Database insert verification failed")
        except Exception as e:
            error_msg = f"Database insert test failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results['database_insert'] = {
                'status': 'failed',
                'error': str(e)
            }
            errors.append(error_msg)
    
    # Test 5: Bedrock connectivity (optional, only if AI endpoints enabled)
    if test_type in ['all', 'bedrock']:
        try:
            logger.info("Testing Bedrock connectivity...")
            from shared.bedrock_client import generate_embeddings, invoke_claude
            
            # Test 5a: Titan embeddings
            test_text = "Connection test"
            embedding = generate_embeddings([test_text])
            
            embedding_success = embedding and len(embedding) > 0 and len(embedding[0]) > 0
            
            # Test 5b: Claude Sonnet 4.5 (if embeddings work)
            claude_success = False
            claude_error = None
            if embedding_success:
                try:
                    logger.info("Testing Claude Sonnet 4.5 access...")
                    response = invoke_claude(
                        messages=[{
                            "role": "user",
                            "content": "Say 'Hello, Claude Sonnet 4.5 is working!' if you can read this."
                        }],
                        max_tokens=50,
                        temperature=0.7
                    )
                    claude_response = response.get('content', '')
                    claude_success = 'working' in claude_response.lower() or len(claude_response) > 0
                    logger.info(f"✓ Claude Sonnet 4.5 test successful: {claude_response[:50]}")
                except Exception as e:
                    claude_error = str(e)
                    logger.warning(f"Claude Sonnet 4.5 test failed: {e}")
            
            if embedding_success:
                results['bedrock'] = {
                    'status': 'success' if claude_success else 'partial',
                    'embedding_dimension': len(embedding[0]) if embedding_success else None,
                    'claude_sonnet_4_5': 'working' if claude_success else 'failed',
                    'claude_error': claude_error if not claude_success else None,
                    'note': 'Bedrock Titan embeddings working' + ('; Claude Sonnet 4.5 working' if claude_success else '; Claude Sonnet 4.5 failed')
                }
                if claude_success:
                    logger.info("✓ Bedrock connectivity successful (Titan + Claude)")
                else:
                    logger.warning(f"⚠ Bedrock Titan working but Claude Sonnet 4.5 failed: {claude_error}")
            else:
                results['bedrock'] = {
                    'status': 'failed',
                    'error': 'Empty embedding returned'
                }
                errors.append("Bedrock returned empty embedding")
        except Exception as e:
            error_msg = f"Bedrock connectivity test failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results['bedrock'] = {
                'status': 'failed',
                'error': str(e)
            }
            errors.append(error_msg)
    
    # Summary
    all_passed = all(
        result.get('status') == 'success' 
        for result in results.values() 
        if result is not None
    )
    
    if errors:
        return error_response({
            'summary': 'Some tests failed',
            'results': results,
            'errors': errors
        }, 500)
    else:
        return success_response({
            'summary': 'All tests passed',
            'results': results
        })

