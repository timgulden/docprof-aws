#!/usr/bin/env python3
"""
Check for failed chunks/fragments and optionally clean the database.
"""

import sys
import os
import json
import boto3

def check_chunks():
    """Check for chunks in database - we'll query via Lambda if available."""
    # Note: We don't have a direct chunks endpoint, but we can check via document_processor logs
    # or create a simple query. For now, let's just prepare for cleanup.
    print("Checking for chunks...")
    print("(Note: Chunks table would need direct DB access to query)")
    print()

def clean_database(dry_run=False):
    """Clean the database using db_cleanup Lambda."""
    session = boto3.Session(profile_name=os.getenv('AWS_PROFILE', 'docprof-dev'))
    lambda_client = session.client('lambda', region_name='us-east-1')
    
    print("=" * 80)
    print(f"{'DRY RUN: ' if dry_run else ''}DATABASE CLEANUP")
    print("=" * 80)
    print()
    
    payload = {
        "delete_all": True,
        "dry_run": dry_run
    }
    
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print()
    
    if not dry_run:
        response = input("⚠️  This will DELETE ALL books, chunks, and figures. Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            return
    
    try:
        print(f"{'[DRY RUN] ' if dry_run else ''}Invoking db_cleanup Lambda...")
        response = lambda_client.invoke(
            FunctionName='docprof-dev-db-cleanup',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read())
        
        if 'errorMessage' in result:
            print(f"✗ Error: {result['errorMessage']}")
            if 'errorType' in result:
                print(f"  Type: {result['errorType']}")
            if 'stackTrace' in result:
                print(f"  Stack trace: {result['stackTrace'][:500]}")
            return
        
        body = json.loads(result.get('body', '{}'))
        status_code = result.get('statusCode')
        
        print(f"Status Code: {status_code}")
        print(f"Response: {json.dumps(body, indent=2)}")
        
        if status_code == 200:
            if dry_run:
                print("\n✓ Dry run completed. Review the response above.")
            else:
                print("\n✓ Database cleaned successfully!")
        else:
            print(f"\n✗ Cleanup failed with status {status_code}")
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Check chunks and clean database')
    parser.add_argument('--clean', action='store_true', help='Clean the database')
    parser.add_argument('--dry-run', action='store_true', help='Dry run (don\'t actually delete)')
    args = parser.parse_args()
    
    if args.clean:
        clean_database(dry_run=args.dry_run)
    else:
        check_chunks()
        print("\nTo clean the database, run with --clean flag")
        print("  python scripts/check_chunks_and_clean.py --clean --dry-run  # Preview")
        print("  python scripts/check_chunks_and_clean.py --clean             # Actually clean")


