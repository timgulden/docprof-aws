#!/usr/bin/env python3
"""
Lambda function to check for book_summaries and source_summaries tables.
Can be invoked directly or deployed as Lambda.
"""

import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'lambda'))

from shared.db_utils import get_db_connection

def check_book_summaries():
    """Check for book summary tables and their contents."""
    
    results = {
        'book_summaries_exists': False,
        'source_summaries_exists': False,
        'book_summaries_count': 0,
        'source_summaries_count': 0,
        'book_summaries_schema': [],
        'source_summaries_schema': [],
        'recommendations': []
    }
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if book_summaries table exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'book_summaries'
                    )
                """)
                results['book_summaries_exists'] = cur.fetchone()[0]
                
                # Check if source_summaries table exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'source_summaries'
                    )
                """)
                results['source_summaries_exists'] = cur.fetchone()[0]
                
                # Get schema for book_summaries if it exists
                if results['book_summaries_exists']:
                    cur.execute("""
                        SELECT column_name, data_type, is_nullable
                        FROM information_schema.columns
                        WHERE table_name = 'book_summaries'
                        ORDER BY ordinal_position
                    """)
                    results['book_summaries_schema'] = [
                        {'name': col[0], 'type': col[1], 'nullable': col[2]}
                        for col in cur.fetchall()
                    ]
                    
                    cur.execute("SELECT COUNT(*) FROM book_summaries")
                    results['book_summaries_count'] = cur.fetchone()[0]
                
                # Get schema for source_summaries if it exists
                if results['source_summaries_exists']:
                    cur.execute("""
                        SELECT column_name, data_type, is_nullable
                        FROM information_schema.columns
                        WHERE table_name = 'source_summaries'
                        ORDER BY ordinal_position
                    """)
                    results['source_summaries_schema'] = [
                        {'name': col[0], 'type': col[1], 'nullable': col[2]}
                        for col in cur.fetchall()
                    ]
                    
                    cur.execute("SELECT COUNT(*) FROM source_summaries")
                    results['source_summaries_count'] = cur.fetchone()[0]
                
                # Generate recommendations
                if not results['book_summaries_exists'] and not results['source_summaries_exists']:
                    results['recommendations'].append(
                        "No book summary tables found. Need to create book_summaries table with embedding column."
                    )
                elif results['source_summaries_exists'] and not results['book_summaries_exists']:
                    results['recommendations'].append(
                        "source_summaries table exists but book_summaries does not. "
                        "Course generator expects book_summaries table with embedding column."
                    )
                    if results['source_summaries_count'] == 0:
                        results['recommendations'].append(
                            "source_summaries table is empty - summaries need to be generated."
                        )
                elif results['book_summaries_exists']:
                    if results['book_summaries_count'] == 0:
                        results['recommendations'].append(
                            "book_summaries table exists but is empty - summaries need to be generated."
                        )
                    else:
                        # Check if embedding column exists
                        has_embedding = any(col['name'] == 'embedding' for col in results['book_summaries_schema'])
                        if not has_embedding:
                            results['recommendations'].append(
                                "book_summaries table exists but missing embedding column - cannot do vector search."
                            )
                        else:
                            results['recommendations'].append(
                                f"book_summaries table exists with {results['book_summaries_count']} summaries. Ready for course generation."
                            )
                
                return results
                
    except Exception as e:
        return {
            'error': str(e),
            'recommendations': [f"Error checking tables: {e}"]
        }

def lambda_handler(event, context):
    """Lambda handler wrapper."""
    results = check_book_summaries()
    return {
        'statusCode': 200,
        'body': json.dumps(results, indent=2, default=str)
    }

if __name__ == '__main__':
    # Can be run directly for testing
    results = check_book_summaries()
    print(json.dumps(results, indent=2, default=str))
