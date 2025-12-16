#!/usr/bin/env python3
"""
Clean up S3 books directory - keep only PDFs for books that have been ingested.

This script:
1. Gets all book_ids from the database (ingested books)
2. Lists all PDFs in S3
3. Keeps PDFs that match ingested book_ids
4. Deletes PDFs that don't match any ingested book_id
"""

import boto3
import sys
import os
from typing import Set, List, Tuple

# Set AWS profile
os.environ['AWS_PROFILE'] = 'docprof-dev'

s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda', region_name='us-east-1')

SOURCE_BUCKET = 'docprof-dev-source-docs'

def get_ingested_book_ids() -> Set[str]:
    """Get all book_ids from the database."""
    print("Fetching book_ids from database...")
    
    payload = {
        "query": "SELECT book_id FROM books"
    }
    
    try:
        response = lambda_client.invoke(
            FunctionName='docprof-dev-db-check',
            Payload=json.dumps(payload),
            InvocationType='RequestResponse'
        )
        
        result = json.loads(response['Payload'].read())
        
        if result.get('statusCode') != 200:
            print(f"Error querying database: {result}")
            return set()
        
        body = json.loads(result.get('body', '{}'))
        books = body.get('books', [])
        
        book_ids = {str(book['book_id']).lower() for book in books}
        print(f"Found {len(book_ids)} ingested book(s): {sorted(book_ids)}")
        return book_ids
        
    except Exception as e:
        print(f"Error getting book_ids from database: {e}")
        return set()

def get_s3_pdfs() -> List[Tuple[str, str]]:
    """Get all PDF paths from S3. Returns list of (s3_key, book_id) tuples."""
    print(f"\nListing PDFs in s3://{SOURCE_BUCKET}/books/...")
    
    pdfs = []
    paginator = s3_client.get_paginator('list_objects_v2')
    
    for page in paginator.paginate(Bucket=SOURCE_BUCKET, Prefix='books/'):
        if 'Contents' not in page:
            continue
            
        for obj in page['Contents']:
            key = obj['Key']
            if key.endswith('.pdf'):
                # Extract book_id from path: books/{book_id}/filename.pdf
                parts = key.split('/')
                if len(parts) >= 3:
                    book_id = parts[1].lower()  # Normalize to lowercase
                    pdfs.append((key, book_id))
    
    print(f"Found {len(pdfs)} PDF file(s) in S3")
    return pdfs

def cleanup_s3(ingested_book_ids: Set[str], dry_run: bool = True):
    """Delete PDFs that don't belong to ingested books."""
    pdfs = get_s3_pdfs()
    
    if not ingested_book_ids:
        print("\n⚠️  No ingested book_ids found. Cannot proceed safely.")
        print("   This might indicate a database connection issue.")
        return
    
    to_keep = []
    to_delete = []
    
    for s3_key, book_id in pdfs:
        if book_id in ingested_book_ids:
            to_keep.append((s3_key, book_id))
        else:
            to_delete.append((s3_key, book_id))
    
    print(f"\n📊 Summary:")
    print(f"   PDFs to KEEP: {len(to_keep)}")
    print(f"   PDFs to DELETE: {len(to_delete)}")
    
    if to_keep:
        print(f"\n✅ PDFs to keep:")
        for s3_key, book_id in sorted(to_keep):
            print(f"   {s3_key} (book_id: {book_id})")
    
    if to_delete:
        print(f"\n❌ PDFs to delete:")
        for s3_key, book_id in sorted(to_delete):
            print(f"   {s3_key} (book_id: {book_id})")
        
        if not dry_run:
            print(f"\n🗑️  Deleting {len(to_delete)} PDF(s)...")
            for s3_key, book_id in to_delete:
                try:
                    s3_client.delete_object(Bucket=SOURCE_BUCKET, Key=s3_key)
                    print(f"   ✅ Deleted: {s3_key}")
                except Exception as e:
                    print(f"   ❌ Error deleting {s3_key}: {e}")
            print(f"\n✅ Cleanup complete!")
        else:
            print(f"\n⚠️  DRY RUN - No files were deleted.")
            print(f"   Run with --execute to actually delete files.")
    else:
        print("\n✅ No files to delete - all PDFs belong to ingested books!")

if __name__ == '__main__':
    import json
    
    dry_run = '--execute' not in sys.argv
    
    if dry_run:
        print("=" * 60)
        print("S3 Books Cleanup - DRY RUN")
        print("=" * 60)
    else:
        print("=" * 60)
        print("S3 Books Cleanup - EXECUTING DELETIONS")
        print("=" * 60)
    
    ingested_book_ids = get_ingested_book_ids()
    
    if not ingested_book_ids:
        print("\n❌ Could not retrieve ingested book_ids. Exiting.")
        sys.exit(1)
    
    cleanup_s3(ingested_book_ids, dry_run=dry_run)
