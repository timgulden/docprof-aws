#!/usr/bin/env python3
"""
Check database state for duplicate books, failed chunks, and cover status.
"""

import sys
import os
import json
import boto3
from collections import defaultdict

def check_database_state():
    """Check database for issues."""
    
    session = boto3.Session(profile_name=os.getenv('AWS_PROFILE', 'docprof-dev'))
    lambda_client = session.client('lambda', region_name='us-east-1')
    
    # Use db_cleanup Lambda to query database (it has the right permissions)
    # We'll create a simple query function, or use an existing one
    
    # Actually, let's invoke a simple query via Lambda
    print("=" * 80)
    print("DATABASE STATE CHECK")
    print("=" * 80)
    print()
    
    # Query via books_list Lambda to get all books
    print("STEP 1: Fetching all books...")
    try:
        event = {
            "path": "/books",
            "httpMethod": "GET",
            "headers": {},
            "pathParameters": {},
            "queryStringParameters": None,
            "requestContext": {"requestId": "check-state"},
            "body": None
        }
        
        response = lambda_client.invoke(
            FunctionName='docprof-dev-books-list',
            InvocationType='RequestResponse',
            Payload=json.dumps(event)
        )
        result = json.loads(response['Payload'].read())
        
        if result.get('statusCode') != 200:
            print(f"✗ Failed to fetch books: {result.get('statusCode')}")
            print(f"Response: {result.get('body', '')[:500]}")
            return
        
        body = json.loads(result.get('body', '[]'))
        books = body if isinstance(body, list) else []
        
        print(f"✓ Found {len(books)} books")
        print()
        
        # Analyze books
        print("STEP 2: Analyzing books for duplicates...")
        title_counts = defaultdict(list)
        author_title_counts = defaultdict(list)
        
        for book in books:
            title = book.get('title', '').strip()
            author = book.get('author', '').strip()
            book_id = book.get('book_id', '')
            
            if title and title.lower() not in ['unknown', '']:
                title_counts[title.lower()].append({
                    'book_id': book_id,
                    'title': title,
                    'author': author
                })
                
                # Also check by author+title
                if author:
                    key = f"{author.lower()}|{title.lower()}"
                    author_title_counts[key].append({
                        'book_id': book_id,
                        'title': title,
                        'author': author
                    })
        
        # Find duplicates
        duplicate_titles = {k: v for k, v in title_counts.items() if len(v) > 1}
        duplicate_authortitle = {k: v for k, v in author_title_counts.items() if len(v) > 1}
        
        if duplicate_titles:
            print(f"⚠️  Found {len(duplicate_titles)} titles with multiple books:")
            for title, book_list in list(duplicate_titles.items())[:10]:
                print(f"  '{book_list[0]['title']}' ({len(book_list)} instances):")
                for b in book_list:
                    print(f"    - {b['book_id']} (Author: {b['author']})")
            print()
        else:
            print("✓ No duplicate titles found")
            print()
        
        if duplicate_authortitle:
            print(f"⚠️  Found {len(duplicate_authortitle)} author+title combinations with multiple books:")
            for key, book_list in list(duplicate_authortitle.items())[:10]:
                author, title = key.split('|', 1)
                print(f"  '{title}' by '{author}' ({len(book_list)} instances):")
                for b in book_list:
                    print(f"    - {b['book_id']}")
            print()
        
        # Check covers
        print("STEP 3: Checking cover status...")
        books_with_covers = 0
        books_without_covers = 0
        valuation_books = []
        
        for book in books:
            book_id = book.get('book_id', '')
            title = book.get('title', '').strip().lower()
            
            # Check for "valuation" books
            if 'valuation' in title:
                valuation_books.append({
                    'book_id': book_id,
                    'title': book.get('title', ''),
                    'author': book.get('author', '')
                })
            
            # Test cover retrieval
            cover_event = {
                "path": f"/books/{book_id}/cover",
                "httpMethod": "GET",
                "headers": {},
                "pathParameters": {"bookId": book_id},
                "requestContext": {"requestId": f"check-cover-{book_id}"},
                "body": None
            }
            
            try:
                cover_response = lambda_client.invoke(
                    FunctionName='docprof-dev-book-cover',
                    InvocationType='RequestResponse',
                    Payload=json.dumps(cover_event)
                )
                cover_result = json.loads(cover_response['Payload'].read())
                
                if cover_result.get('statusCode') == 200:
                    books_with_covers += 1
                else:
                    books_without_covers += 1
            except Exception as e:
                books_without_covers += 1
        
        print(f"✓ Books with covers: {books_with_covers}")
        print(f"✗ Books without covers: {books_without_covers}")
        print()
        
        if valuation_books:
            print("STEP 4: Valuation book(s) found:")
            for vb in valuation_books:
                print(f"  Book ID: {vb['book_id']}")
                print(f"  Title: {vb['title']}")
                print(f"  Author: {vb['author']}")
                
                # Test cover for Valuation
                print(f"\n  Testing cover retrieval...")
                cover_event = {
                    "path": f"/books/{vb['book_id']}/cover",
                    "httpMethod": "GET",
                    "headers": {},
                    "pathParameters": {"bookId": vb['book_id']},
                    "requestContext": {"requestId": f"test-valuation-cover"},
                    "body": None
                }
                
                try:
                    cover_response = lambda_client.invoke(
                        FunctionName='docprof-dev-book-cover',
                        InvocationType='RequestResponse',
                        Payload=json.dumps(cover_event)
                    )
                    cover_result = json.loads(cover_response['Payload'].read())
                    
                    if cover_result.get('statusCode') == 200:
                        body = cover_result.get('body', '')
                        is_base64 = cover_result.get('isBase64Encoded', False)
                        print(f"    ✓ Cover found (status 200, base64={is_base64}, body length={len(body) if body else 0})")
                    else:
                        print(f"    ✗ No cover (status {cover_result.get('statusCode')})")
                        if 'body' in cover_result:
                            try:
                                error_body = json.loads(cover_result['body'])
                                print(f"      Error: {error_body.get('message', 'Unknown error')}")
                            except:
                                pass
                except Exception as e:
                    print(f"    ✗ Error testing cover: {e}")
                print()
        
        # Check for chunks (we'd need a chunks endpoint or query directly)
        # For now, just summarize
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Total books: {len(books)}")
        print(f"Books with covers: {books_with_covers}")
        print(f"Books without covers: {books_without_covers}")
        print(f"Duplicate titles: {len(duplicate_titles)}")
        print(f"Duplicate author+title: {len(duplicate_authortitle)}")
        
        if duplicate_titles or duplicate_authortitle or books_without_covers > 0:
            print()
            print("⚠️  RECOMMENDATION: Consider clearing database and re-ingesting")
            print("   Use: aws lambda invoke --function-name docprof-dev-db-cleanup")
            print("        --payload '{\"delete_all\": true, \"dry_run\": false}'")
        else:
            print()
            print("✓ Database looks clean!")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    check_database_state()

