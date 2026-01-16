#!/usr/bin/env python3
"""
RAG diagnostic test via Lambda - invokes chat_handler with diagnostic mode.
"""

import os
import sys
import json
import boto3
import base64

def main():
    print("="*60)
    print("RAG DIAGNOSTIC TEST VIA LAMBDA")
    print("="*60)
    
    client = boto3.client('lambda', region_name='us-east-1')
    logs_client = boto3.client('logs', region_name='us-east-1')
    
    # Test 1: Run the embedded diagnostic (test_embeddings mode)
    print("\n" + "-"*60)
    print("TEST 1: Embedding model test (test_embeddings mode)")
    print("This tests DIRECT embedding search with original query")
    print("-"*60)
    
    response = client.invoke(
        FunctionName='docprof-dev-chat-handler',
        InvocationType='RequestResponse',
        Payload=json.dumps({
            'test_embeddings': True,
            'test_query': 'What is M&A?'
        })
    )
    
    result = json.loads(response['Payload'].read())
    print(f"\nResponse status: {result.get('statusCode')}")
    
    if result.get('body'):
        body = json.loads(result['body']) if isinstance(result['body'], str) else result['body']
        print(f"\nTest results:")
        print(json.dumps(body, indent=2))
    
    # NEW TEST: Direct embedding test with lowercase query
    print("\n" + "-"*60)
    print("TEST 1b: Embedding model test with LOWERCASE query")
    print("This tests if case affects embeddings")
    print("-"*60)
    
    response = client.invoke(
        FunctionName='docprof-dev-chat-handler',
        InvocationType='RequestResponse',
        Payload=json.dumps({
            'test_embeddings': True,
            'test_query': 'what is m&a?'  # Lowercase like expand_query_for_retrieval does
        })
    )
    
    result = json.loads(response['Payload'].read())
    print(f"\nResponse status: {result.get('statusCode')}")
    
    if result.get('body'):
        body = json.loads(result['body']) if isinstance(result['body'], str) else result['body']
        print(f"\nTest results:")
        print(json.dumps(body, indent=2))
    
    # Test 2: Run actual chat query (no book filter)
    print("\n" + "-"*60)
    print("TEST 2: Chat query - NO book filter")
    print("-"*60)
    
    response = client.invoke(
        FunctionName='docprof-dev-chat-handler',
        InvocationType='RequestResponse',
        Payload=json.dumps({
            'body': json.dumps({
                'message': 'What is M&A?',
                'book_ids': []  # Empty = search all books
            })
        })
    )
    
    result = json.loads(response['Payload'].read())
    print(f"\nResponse status: {result.get('statusCode')}")
    
    if result.get('body'):
        body = json.loads(result['body']) if isinstance(result['body'], str) else result['body']
        if 'messages' in body and body['messages']:
            msg = body['messages'][0]
            print(f"\nAnswer preview: {msg.get('content', '')[:500]}...")
            print(f"\nSources count: {len(msg.get('sources', []))}")
            if msg.get('sources'):
                print("Source scores:")
                for s in msg['sources'][:5]:
                    print(f"  - [{s.get('citation_id')}] {s.get('book_title', 'Unknown')[:30]}: score={s.get('score', 'N/A')}")
        else:
            print(f"Full response: {json.dumps(body, indent=2)}")
    
    # Test 3: Run actual chat query WITH book filter (all 5 books)
    print("\n" + "-"*60)
    print("TEST 3: Chat query - WITH book filter (all 5 books)")
    print("-"*60)
    
    # First get the book IDs
    books_response = client.invoke(
        FunctionName='docprof-dev-books-list',
        InvocationType='RequestResponse',
        Payload=json.dumps({})
    )
    books_result = json.loads(books_response['Payload'].read())
    
    if books_result.get('body'):
        books_body = json.loads(books_result['body']) if isinstance(books_result['body'], str) else books_result['body']
        book_ids = [b['book_id'] for b in books_body]
        print(f"Found {len(book_ids)} books: {book_ids}")
        
        response = client.invoke(
            FunctionName='docprof-dev-chat-handler',
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'body': json.dumps({
                    'message': 'What is M&A?',
                    'book_ids': book_ids
                })
            })
        )
        
        result = json.loads(response['Payload'].read())
        print(f"\nResponse status: {result.get('statusCode')}")
        
        if result.get('body'):
            body = json.loads(result['body']) if isinstance(result['body'], str) else result['body']
            if 'messages' in body and body['messages']:
                msg = body['messages'][0]
                print(f"\nAnswer preview: {msg.get('content', '')[:500]}...")
                print(f"\nSources count: {len(msg.get('sources', []))}")
                if msg.get('sources'):
                    print("Source scores:")
                    for s in msg['sources'][:5]:
                        print(f"  - [{s.get('citation_id')}] {s.get('book_title', 'Unknown')[:30]}: score={s.get('score', 'N/A')}")
            else:
                print(f"Full response: {json.dumps(body, indent=2)}")
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)


if __name__ == '__main__':
    main()
