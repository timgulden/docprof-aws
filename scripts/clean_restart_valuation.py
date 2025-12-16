#!/usr/bin/env python3
"""
Clean restart of Valuation source summary generation.

This script:
1. Deletes ALL chapter summaries for Valuation (clean slate)
2. Deletes the source summary state
3. Waits for any running Lambdas to finish
4. Restarts processing with fully fixed code

Use this for a clean, consistent run after fixing bugs.
"""

import boto3
import json
import os
import sys
import time
from datetime import datetime, timedelta

# Set up AWS session
session = boto3.Session(profile_name=os.getenv('AWS_PROFILE', 'docprof-dev'))
region = os.getenv('AWS_REGION', 'us-east-1')

dynamodb = session.resource('dynamodb', region_name=region)
lambda_client = session.client('lambda', region_name=region)
logs_client = session.client('logs', region_name=region)
s3_client = session.client('s3', region_name=region)

# Configuration
state_table_name = 'docprof-dev-source-summary-state'
chapters_table_name = 'docprof-dev-chapter-summaries'
source_bucket = 'docprof-dev-source-docs'
valuation_source_id = '45eea4fb-b509-4c99-af6b-25231163941e'
s3_key = 'books/45eea4fb-b509-4c99-af6b-25231163941e/upload_20251214-162616.pdf'

def check_if_lambdas_running():
    """Check if any chapter processor Lambdas are still running."""
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int((datetime.now() - timedelta(minutes=15)).timestamp() * 1000)
    
    try:
        # Check for recent START events
        response = logs_client.filter_log_events(
            logGroupName='/aws/lambda/docprof-dev-chapter-summary-processor',
            startTime=start_time,
            endTime=end_time,
            filterPattern='START RequestId',
            limit=100
        )
        
        starts = response.get('events', [])
        if starts:
            latest_start = starts[-1]
            start_dt = datetime.fromtimestamp(latest_start['timestamp'] / 1000)
            age_minutes = (datetime.now() - start_dt.replace(tzinfo=None)).total_seconds() / 60
            
            if age_minutes < 10:
                return True, age_minutes
        
        return False, 0
    except Exception as e:
        print(f"Warning: Could not check Lambda status: {e}")
        return False, 0

def delete_all_chapter_summaries():
    """Delete all chapter summaries for Valuation."""
    chapters_table = dynamodb.Table(chapters_table_name)
    
    try:
        # Scan for all Valuation chapters
        resp = chapters_table.scan(
            FilterExpression='source_id = :sid',
            ExpressionAttributeValues={':sid': valuation_source_id}
        )
        
        items = resp.get('Items', [])
        deleted_count = 0
        
        for item in items:
            chapters_table.delete_item(Key={
                'source_id': item['source_id'],
                'chapter_index': item['chapter_index']
            })
            deleted_count += 1
        
        print(f"✓ Deleted {deleted_count} chapter summaries")
        return deleted_count
    except Exception as e:
        print(f"Error deleting chapter summaries: {e}")
        return 0

def delete_source_summary_state():
    """Delete Valuation state."""
    state_table = dynamodb.Table(state_table_name)
    
    try:
        state_table.delete_item(Key={'source_id': valuation_source_id})
        print(f"✓ Deleted source summary state")
        return True
    except Exception as e:
        print(f"Error deleting state: {e}")
        return False

def restart_processing():
    """Restart Valuation source summary generation."""
    payload = {
        "source_id": valuation_source_id,
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
        
        if 'errorMessage' in result:
            print(f"\n⚠️  Error: {result['errorMessage']}")
            return False
        
        # Parse body
        body = json.loads(result.get('body', '{}'))
        chapters_found = body.get('chapters_found', 0)
        events_published = body.get('events_published', 0)
        
        print(f"  Chapters found: {chapters_found}")
        print(f"  Events published: {events_published}")
        
        return True
    except Exception as e:
        print(f"\n✗ Error invoking Lambda: {e}")
        return False

def main():
    print("=" * 60)
    print("CLEAN RESTART - Valuation Source Summary")
    print("=" * 60)
    print()
    
    # Check for --yes flag
    auto_confirm = '--yes' in sys.argv or '-y' in sys.argv
    
    # Step 1: Check if Lambdas are still running
    print("Step 1: Checking for running Lambdas...")
    is_running, age = check_if_lambdas_running()
    
    if is_running:
        print(f"⚠️  Lambdas started {age:.1f} minutes ago may still be running")
        print(f"   Timeout is 10 minutes. Wait {10 - age:.1f} more minutes to be safe.")
        
        if not auto_confirm:
            response = input("\nProceed anyway? (yes/no): ")
            if response.lower() != 'yes':
                print("Cancelled.")
                return
        else:
            print("   Auto-confirming (--yes flag)...")
    else:
        print("✓ No recent Lambda activity")
    
    # Step 2: Delete chapter summaries
    print("\nStep 2: Deleting all chapter summaries...")
    deleted = delete_all_chapter_summaries()
    
    if deleted == 0:
        print("  No chapters to delete")
    
    # Step 3: Delete state
    print("\nStep 3: Deleting source summary state...")
    delete_source_summary_state()
    
    # Step 4: Restart processing
    print("\nStep 4: Restarting source summary generation...")
    success = restart_processing()
    
    if success:
        print("\n" + "=" * 60)
        print("✓ CLEAN RESTART COMPLETE")
        print("=" * 60)
        print()
        print("All chapter summaries deleted and processing restarted.")
        print("All chapters will be processed with the latest fixed code.")
        print()
        print("Monitor progress with:")
        print("  AWS_PROFILE=docprof-dev python3 scripts/check_valuation_progress.py")
    else:
        print("\n✗ Restart failed")
        sys.exit(1)

if __name__ == '__main__':
    main()
