#!/usr/bin/env python3
"""
Check if book_summaries table exists and has data.
"""

import sys
import os

# Add parent directory to path to import shared modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'lambda'))

from shared.db_utils import get_db_connection
import json

def check_book_summaries():
    """Check for book_summaries table and its contents."""
    
    print("=" * 60)
    print("Book Summaries Check")
    print("=" * 60)
    print()
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if book_summaries table exists
                print("1. Checking if book_summaries table exists...")
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'book_summaries'
                    )
                """)
                table_exists = cur.fetchone()[0]
                
                if table_exists:
                    print("   ✅ book_summaries table exists")
                    print()
                    
                    # Check table schema
                    print("2. Checking table schema...")
                    cur.execute("""
                        SELECT column_name, data_type, is_nullable
                        FROM information_schema.columns
                        WHERE table_name = 'book_summaries'
                        ORDER BY ordinal_position
                    """)
                    columns = cur.fetchall()
                    print("   Columns:")
                    for col_name, data_type, is_nullable in columns:
                        nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
                        print(f"     • {col_name}: {data_type} ({nullable})")
                    print()
                    
                    # Check for data
                    print("3. Checking for data...")
                    cur.execute("SELECT COUNT(*) FROM book_summaries")
                    count = cur.fetchone()[0]
                    print(f"   Found {count} book summary(ies)")
                    print()
                    
                    if count > 0:
                        # Show sample data
                        print("4. Sample book summaries:")
                        cur.execute("""
                            SELECT 
                                book_id,
                                book_title,
                                LENGTH(summary_json::text) as summary_length,
                                CASE 
                                    WHEN embedding IS NOT NULL THEN 'Yes'
                                    ELSE 'No'
                                END as has_embedding
                            FROM book_summaries
                            LIMIT 5
                        """)
                        summaries = cur.fetchall()
                        for book_id, title, length, has_emb in summaries:
                            print(f"   • {title}")
                            print(f"     Book ID: {book_id}")
                            print(f"     Summary length: {length:,} chars")
                            print(f"     Has embedding: {has_emb}")
                            print()
                        
                        # Check if embeddings exist
                        cur.execute("SELECT COUNT(*) FROM book_summaries WHERE embedding IS NOT NULL")
                        with_embeddings = cur.fetchone()[0]
                        print(f"5. Summaries with embeddings: {with_embeddings} / {count}")
                        print()
                    else:
                        print("   ⚠️  No book summaries found in table")
                        print()
                    
                    # Check books table for comparison
                    print("6. Checking books table for comparison...")
                    cur.execute("SELECT COUNT(*) FROM books")
                    book_count = cur.fetchone()[0]
                    print(f"   Found {book_count} book(s) in books table")
                    print()
                    
                    if book_count > count:
                        print("   ⚠️  More books than summaries - summaries may not be generated")
                    elif book_count == count:
                        print("   ✅ Book count matches summary count")
                    else:
                        print("   ⚠️  More summaries than books (unexpected)")
                    print()
                    
                else:
                    print("   ❌ book_summaries table does NOT exist")
                    print()
                    print("   This means book summaries need to be created.")
                    print("   They are likely generated during ingestion as a separate step.")
                    print()
                    
                    # Check what tables do exist
                    print("7. Existing tables in database:")
                    cur.execute("""
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                        AND table_type = 'BASE TABLE'
                        ORDER BY table_name
                    """)
                    tables = cur.fetchall()
                    for (table_name,) in tables:
                        print(f"   • {table_name}")
                    print()
                
    except Exception as e:
        print(f"❌ Error checking book summaries: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == '__main__':
    success = check_book_summaries()
    sys.exit(0 if success else 1)
