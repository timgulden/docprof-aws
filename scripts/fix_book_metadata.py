#!/usr/bin/env python3
"""
Fix metadata for Investment Valuation book in Aurora PostgreSQL.
"""

import os
import sys
import boto3
import psycopg2

def get_db_connection():
    """Get database connection using AWS Secrets Manager."""
    secrets_client = boto3.client('secretsmanager', region_name='us-east-1')
    
    # Get DB password
    secret_response = secrets_client.get_secret_value(
        SecretId='docprof-dev-aurora-master-password'
    )
    password = secret_response['SecretString']
    
    # Get cluster endpoint
    rds_client = boto3.client('rds', region_name='us-east-1')
    clusters = rds_client.describe_db_clusters(
        DBClusterIdentifier='docprof-dev-aurora'
    )
    endpoint = clusters['DBClusters'][0]['Endpoint']
    
    conn = psycopg2.connect(
        host=endpoint,
        port=5432,
        database='docprof',
        user='docprof_admin',
        password=password,
        connect_timeout=30
    )
    return conn


def main():
    book_id = 'a690dc56-fc0c-4eb1-ab16-26db0397ca17'
    new_title = 'Investment Valuation: Tools and Techniques for Determining the Value of Any Asset'
    new_author = 'Aswath Damodaran'
    new_edition = '3rd Edition'
    
    print(f"Connecting to Aurora PostgreSQL...")
    conn = get_db_connection()
    
    try:
        with conn.cursor() as cur:
            # Check current metadata
            print(f"\nCurrent metadata for book {book_id}:")
            cur.execute("""
                SELECT title, author, edition, total_pages
                FROM books
                WHERE book_id = %s
            """, (book_id,))
            result = cur.fetchone()
            if result:
                print(f"  Title: {result[0]}")
                print(f"  Author: {result[1]}")
                print(f"  Edition: {result[2]}")
                print(f"  Pages: {result[3]}")
            else:
                print(f"  ERROR: Book not found!")
                return 1
            
            # Update metadata
            print(f"\nUpdating to:")
            print(f"  Title: {new_title}")
            print(f"  Author: {new_author}")
            print(f"  Edition: {new_edition}")
            
            cur.execute("""
                UPDATE books
                SET title = %s,
                    author = %s,
                    edition = %s
                WHERE book_id = %s
            """, (new_title, new_author, new_edition, book_id))
            
            conn.commit()
            
            # Verify update
            print(f"\nVerifying update:")
            cur.execute("""
                SELECT title, author, edition, total_pages
                FROM books
                WHERE book_id = %s
            """, (book_id,))
            result = cur.fetchone()
            print(f"  Title: {result[0]}")
            print(f"  Author: {result[1]}")
            print(f"  Edition: {result[2]}")
            print(f"  Pages: {result[3]}")
            
            print("\n✅ Metadata updated successfully!")
            return 0
            
    except Exception as e:
        print(f"\n❌ Error updating metadata: {e}")
        conn.rollback()
        return 1
    finally:
        conn.close()


if __name__ == '__main__':
    sys.exit(main())
