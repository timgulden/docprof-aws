#!/usr/bin/env python3
"""
Clean source_summaries for a specific book (or all books).

This is useful when:
- TOC parsing was incorrect (e.g., 330 entries instead of 43 chapters)
- Need to regenerate summaries with corrected chapter structure
- Testing TOC extraction improvements
"""

import sys
import os
import boto3
import json
import subprocess
import psycopg2

def get_db_connection_info():
    """Get database connection info from Terraform outputs"""
    try:
        result = subprocess.run(
            ['terraform', 'output', '-json'],
            cwd=os.path.join(os.path.dirname(__file__), '..', 'terraform', 'environments', 'dev'),
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            outputs = json.loads(result.stdout)
            cluster_endpoint = outputs.get('aurora_cluster_endpoint', {}).get('value', '')
            secret_arn = outputs.get('aurora_master_password_secret_arn', {}).get('value', '')
            
            if cluster_endpoint and secret_arn:
                # Get password from Secrets Manager
                secrets_client = boto3.Session(profile_name='docprof-dev').client('secretsmanager')
                secret_response = secrets_client.get_secret_value(SecretId=secret_arn)
                password = secret_response['SecretString']
                
                return {
                    'host': cluster_endpoint,
                    'port': 5432,
                    'database': 'docprof',
                    'user': 'docprof_admin',
                    'password': password
                }
    except Exception as e:
        print(f"Error getting database connection info: {e}")
        sys.exit(1)
    
    print("Failed to get database connection info from Terraform outputs")
    sys.exit(1)

def clean_source_summaries(book_id=None, skip_confirmation=False):
    """Delete source_summaries for a specific book or all books."""
    
    if book_id:
        print(f"⚠️  WARNING: This will delete ALL source_summaries for book_id: {book_id}")
    else:
        print("⚠️  WARNING: This will delete ALL source_summaries for ALL books!")
    
    if not skip_confirmation:
        response = input("\nAre you sure you want to proceed? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return
    else:
        print("\nProceeding with cleanup (--yes flag provided)...")
    
    print("\nChecking source_summaries...")
    
    # Get connection info
    db_info = get_db_connection_info()
    
    # Connect to database
    conn = psycopg2.connect(
        host=db_info['host'],
        port=db_info['port'],
        database=db_info['database'],
        user=db_info['user'],
        password=db_info['password']
    )
    
    try:
        with conn.cursor() as cur:
            # Count records before deletion
            if book_id:
                cur.execute("SELECT COUNT(*) FROM source_summaries WHERE source_id = %s", (book_id,))
                count_before = cur.fetchone()[0]
                
                # Show what we're about to delete
                cur.execute("""
                    SELECT chapter_number, chapter_title, page_number
                    FROM source_summaries 
                    WHERE source_id = %s
                    ORDER BY chapter_number
                    LIMIT 10
                """, (book_id,))
                chapters = cur.fetchall()
                
                if chapters:
                    print(f"\nFound {count_before} source_summary entries for book_id: {book_id}")
                    print(f"\nFirst 10 chapters that will be deleted:")
                    for ch_num, ch_title, page in chapters:
                        print(f"  {ch_num}: {ch_title[:60]} (page {page})")
                    
                    cur.execute("SELECT MAX(chapter_number) FROM source_summaries WHERE source_id = %s", (book_id,))
                    max_ch = cur.fetchone()[0]
                    if max_ch:
                        print(f"\nMax chapter number: {max_ch}")
                        if max_ch > 50:
                            print(f"⚠️  This looks like it might be from an incorrect TOC parse (expected ~43 chapters)")
                else:
                    print(f"No source_summaries found for book_id: {book_id}")
                    return
            else:
                cur.execute("SELECT COUNT(*) FROM source_summaries")
                count_before = cur.fetchone()[0]
                print(f"Found {count_before} total source_summary entries")
            
            # Delete
            if book_id:
                print(f"\nDeleting source_summaries for book_id: {book_id}...")
                cur.execute("DELETE FROM source_summaries WHERE source_id = %s", (book_id,))
            else:
                print("\nDeleting ALL source_summaries...")
                cur.execute("DELETE FROM source_summaries")
            
            deleted_count = cur.rowcount
            print(f"  Deleted {deleted_count} source_summary entries")
            
            # Also delete embeddings if they exist
            if book_id:
                print(f"\nDeleting source_summary_embeddings for book_id: {book_id}...")
                cur.execute("""
                    DELETE FROM source_summary_embeddings 
                    WHERE source_id = %s
                """, (book_id,))
                embeddings_deleted = cur.rowcount
                if embeddings_deleted > 0:
                    print(f"  Deleted {embeddings_deleted} embedding entries")
            else:
                print("\nDeleting ALL source_summary_embeddings...")
                cur.execute("DELETE FROM source_summary_embeddings")
                embeddings_deleted = cur.rowcount
                if embeddings_deleted > 0:
                    print(f"  Deleted {embeddings_deleted} embedding entries")
            
            # Commit all deletions
            conn.commit()
            print("\n✅ Cleanup completed successfully!")
            
            # Verify
            if book_id:
                cur.execute("SELECT COUNT(*) FROM source_summaries WHERE source_id = %s", (book_id,))
                remaining = cur.fetchone()[0]
                if remaining == 0:
                    print(f"\n✅ Verification: All source_summaries deleted for book_id: {book_id}")
                else:
                    print(f"\n⚠️  Warning: {remaining} entries still remain")
            else:
                cur.execute("SELECT COUNT(*) FROM source_summaries")
                remaining = cur.fetchone()[0]
                if remaining == 0:
                    print(f"\n✅ Verification: All source_summaries deleted")
                else:
                    print(f"\n⚠️  Warning: {remaining} entries still remain")
                    
    finally:
        conn.close()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Clean source_summaries for a book or all books')
    parser.add_argument('--book-id', help='Book ID to clean (if not provided, cleans all)')
    parser.add_argument('--yes', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()
    clean_source_summaries(book_id=args.book_id, skip_confirmation=args.yes)
