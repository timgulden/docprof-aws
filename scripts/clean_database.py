#!/usr/bin/env python3
"""
Clean all data from the database for fresh ingestion testing.

This script:
1. Deletes all chunks
2. Deletes all figures
3. Deletes all chapter documents
4. Deletes all books
5. Confirms database is clean

Use with caution! This is destructive.
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
                secrets_client = boto3.client('secretsmanager')
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

def clean_database(skip_confirmation=False):
    """Delete all data from the database."""
    print("⚠️  WARNING: This will delete ALL data from the database!")
    print("This includes:")
    print("  - All books")
    print("  - All chunks")
    print("  - All figures")
    print("  - All chapter documents")
    
    if not skip_confirmation:
        response = input("\nAre you sure you want to proceed? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return
    else:
        print("\nProceeding with cleanup (--yes flag provided)...")
    
    print("\nCleaning database...")
    
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
            cur.execute("SELECT COUNT(*) FROM books")
            book_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM document_chunks")
            chunk_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM books WHERE metadata->'figures' IS NOT NULL")
            figure_count = cur.fetchone()[0]
            
            print(f"  Found {book_count} books, {chunk_count} chunks, {figure_count} books with figures")
            
            # Delete in correct order (respecting foreign keys)
            print("\nDeleting chunks...")
            cur.execute("DELETE FROM document_chunks")
            chunks_deleted = cur.rowcount
            print(f"  Deleted {chunks_deleted} chunks")
            
            print("Deleting chapter documents...")
            cur.execute("DELETE FROM chapter_documents")
            chapters_deleted = cur.rowcount
            print(f"  Deleted {chapters_deleted} chapter documents")
            
            # Note: Figures are stored in books.metadata, so we'll clear that
            print("Clearing figure metadata from books...")
            cur.execute("UPDATE books SET metadata = metadata - 'figures' WHERE metadata->'figures' IS NOT NULL")
            figures_cleared = cur.rowcount
            print(f"  Cleared figures from {figures_cleared} books")
            
            # Clear cover metadata too
            print("Clearing cover metadata from books...")
            cur.execute("UPDATE books SET metadata = metadata - 'cover' WHERE metadata->'cover' IS NOT NULL")
            covers_cleared = cur.rowcount
            print(f"  Cleared covers from {covers_cleared} books")
            
            print("Deleting all books...")
            cur.execute("DELETE FROM books")
            books_deleted = cur.rowcount
            print(f"  Deleted {books_deleted} books")
            
            # Commit all deletions
            conn.commit()
            print("\n✅ Database cleaned successfully!")
            
            # Verify
            cur.execute("SELECT COUNT(*) FROM books")
            remaining_books = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM document_chunks")
            remaining_chunks = cur.fetchone()[0]
            
            if remaining_books == 0 and remaining_chunks == 0:
                print(f"\n✅ Verification: Database is clean (0 books, 0 chunks)")
            else:
                print(f"\n⚠️  Warning: Some data remains ({remaining_books} books, {remaining_chunks} chunks)")
    finally:
        conn.close()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Clean all data from the database')
    parser.add_argument('--yes', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()
    clean_database(skip_confirmation=args.yes)

