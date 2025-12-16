#!/usr/bin/env python3
"""
Clean up stuck Valuation source summary and re-trigger processing.

This script:
1. Deletes the stuck Valuation entry from source-summary-state DynamoDB table
2. Deletes any partial chapter summaries for Valuation
3. Re-invokes the source_summary_generator Lambda to restart processing
"""

import boto3
import json
import os
import sys
from uuid import uuid4

# Set up AWS session
session = boto3.Session(profile_name=os.getenv('AWS_PROFILE', 'docprof-dev'))
region = os.getenv('AWS_REGION', 'us-east-1')

dynamodb = session.resource('dynamodb', region_name=region)
lambda_client = session.client('lambda', region_name=region)
s3_client = session.client('s3', region_name=region)

# Table names
state_table_name = 'docprof-dev-source-summary-state'
chapters_table_name = 'docprof-dev-chapter-summaries'
source_bucket = 'docprof-dev-source-docs'

def find_valuation_source_id():
    """Find the Valuation source_id from DynamoDB."""
    state_table = dynamodb.Table(state_table_name)
    resp = state_table.scan(Limit=50)
    
    for item in resp.get('Items', []):
        if item.get('source_title') == 'Valuation':
            return item.get('source_id')
    
    return None

def find_valuation_s3_key():
    """Find the Valuation book S3 key."""
    try:
        # List books in S3 - Valuation source_id is 45eea4fb-b509-4c99-af6b-25231163941e
        valuation_source_id = '45eea4fb-b509-4c99-af6b-25231163941e'
        prefix = f'books/{valuation_source_id}/'
        
        response = s3_client.list_objects_v2(
            Bucket=source_bucket,
            Prefix=prefix
        )
        
        for obj in response.get('Contents', []):
            key = obj['Key']
            if key.endswith('.pdf'):
                return key
        
        # Fallback: try to get from DynamoDB state
        state_table = dynamodb.Table(state_table_name)
        resp = state_table.scan(Limit=50)
        for item in resp.get('Items', []):
            if item.get('source_title') == 'Valuation':
                return item.get('s3_key')
        
        return None
    except Exception as e:
        print(f"Error finding S3 key: {e}")
        return None

def cleanup_valuation_state(source_id):
    """Delete Valuation state and chapter summaries."""
    print(f"Cleaning up source_id: {source_id}")
    
    # Delete from source-summary-state
    state_table = dynamodb.Table(state_table_name)
    try:
        state_table.delete_item(Key={'source_id': source_id})
        print(f"✓ Deleted from {state_table_name}")
    except Exception as e:
        print(f"Error deleting state: {e}")
    
    # Delete chapter summaries
    chapters_table = dynamodb.Table(chapters_table_name)
    try:
        # Scan and delete all chapters for this source_id
        resp = chapters_table.scan(
            FilterExpression='source_id = :sid',
            ExpressionAttributeValues={':sid': source_id}
        )
        
        deleted_count = 0
        for item in resp.get('Items', []):
            chapters_table.delete_item(Key={
                'source_id': item['source_id'],
                'chapter_index': item['chapter_index']
            })
            deleted_count += 1
        
        print(f"✓ Deleted {deleted_count} chapter summaries from {chapters_table_name}")
    except Exception as e:
        print(f"Error deleting chapter summaries: {e}")

def restart_valuation_processing(s3_key):
    """Re-invoke source_summary_generator Lambda for Valuation."""
    print(f"\nRe-triggering source summary generation...")
    print(f"S3 Key: {s3_key}")
    
    # Extract source_id from S3 key (assuming format: books/{source_id}/filename.pdf)
    source_id = s3_key.split('/')[1] if '/' in s3_key else str(uuid4())
    
    payload = {
        "source_id": source_id,
        "source_title": "Valuation: Measuring and Managing the Value of Companies",
        "author": "Tim Koller",
        "s3_bucket": source_bucket,
        "s3_key": s3_key
    }
    
    try:
        response = lambda_client.invoke(
            FunctionName='docprof-dev-source-summary-generator',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read())
        print(f"\n✓ Lambda invoked")
        print(f"Response: {json.dumps(result, indent=2)}")
        
        if 'errorMessage' in result:
            print(f"\n⚠️  Error: {result['errorMessage']}")
            return False
        
        return True
    except Exception as e:
        print(f"\n✗ Error invoking Lambda: {e}")
        return False

def main():
    import sys
    
    print("=" * 60)
    print("Restart Valuation Source Summary Processing")
    print("=" * 60)
    print()
    
    # Check for --yes flag for non-interactive mode
    auto_confirm = '--yes' in sys.argv or '-y' in sys.argv
    
    # Find Valuation source_id
    source_id = find_valuation_source_id()
    
    # Get S3 key BEFORE cleanup (from state if available)
    s3_key = None
    if source_id:
        # Get S3 key from state before we delete it
        state_table = dynamodb.Table(state_table_name)
        try:
            resp = state_table.get_item(Key={'source_id': source_id})
            if 'Item' in resp:
                s3_key = resp['Item'].get('s3_key')
                print(f"Found Valuation source_id: {source_id}")
                print(f"Found S3 key: {s3_key}")
        except Exception as e:
            print(f"Error reading state: {e}")
    
    # If still not found, try S3 search
    if not s3_key:
        s3_key = find_valuation_s3_key()
    
    if not source_id:
        print("⚠️  No Valuation entry found in source-summary-state")
        print("   Proceeding to re-trigger anyway...")
    else:
        # Confirm cleanup (unless auto-confirm)
        if not auto_confirm:
            response = input("\nDelete existing Valuation state and chapter summaries? (yes/no): ")
            if response.lower() != 'yes':
                print("Cancelled.")
                return
        else:
            print("\nAuto-confirming cleanup (--yes flag)...")
        
        # Cleanup
        cleanup_valuation_state(source_id)
    
    if not s3_key:
        print("\n⚠️  Could not find Valuation book in S3")
        if not auto_confirm:
            s3_key = input("S3 key (e.g., books/45eea4fb-b509-4c99-af6b-25231163941e/Valuation.pdf): ").strip()
            if not s3_key:
                print("Cancelled.")
                return
        else:
            print("   Cannot proceed without S3 key in non-interactive mode.")
            sys.exit(1)
    
    # Restart processing
    print()
    success = restart_valuation_processing(s3_key)
    
    if success:
        print("\n✓ Valuation processing restarted!")
        print("   Monitor progress in CloudWatch logs:")
        print("   - /aws/lambda/docprof-dev-source-summary-generator")
        print("   - /aws/lambda/docprof-dev-chapter-summary-processor")
    else:
        print("\n✗ Failed to restart processing")
        sys.exit(1)

if __name__ == '__main__':
    main()
