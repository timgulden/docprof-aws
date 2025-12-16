#!/usr/bin/env python3
"""
Check progress of Valuation book source summary generation.

Shows:
- Current completion status
- Recently completed chapters
- Any quota issues
- Estimated time remaining
"""

import boto3
import os
import sys
from datetime import datetime, timedelta

# Set up AWS session
session = boto3.Session(profile_name=os.getenv('AWS_PROFILE', 'docprof-dev'))
region = os.getenv('AWS_REGION', 'us-east-1')
dynamodb = session.resource('dynamodb', region_name=region)
logs_client = session.client('logs', region_name=region)

valuation_source_id = '45eea4fb-b509-4c99-af6b-25231163941e'

def check_progress():
    """Check Valuation processing progress."""
    print("=" * 60)
    print("VALUATION BOOK PROCESSING STATUS")
    print("=" * 60)
    
    # Check state
    state_table = dynamodb.Table('docprof-dev-source-summary-state')
    resp = state_table.scan(Limit=50)
    valuation = [i for i in resp.get('Items', []) if 'Valuation' in str(i.get('source_title', ''))]
    
    if not valuation:
        print("⚠️  No Valuation state found")
        return
    
    v = valuation[0]
    source_id = v.get('source_id')
    status = v.get('status')
    chapters_completed_state = v.get('chapters_completed', 0)
    total_chapters = v.get('total_chapters', 0)
    
    print(f"Source ID: {source_id}")
    print(f"Status: {status}")
    print(f"Total chapters: {total_chapters}")
    
    # Check actual chapter summaries
    chapters_table = dynamodb.Table('docprof-dev-chapter-summaries')
    resp2 = chapters_table.scan(
        FilterExpression='source_id = :sid',
        ExpressionAttributeValues={':sid': source_id}
    )
    chapters = resp2.get('Items', [])
    actual_completed = len(chapters)
    
    print(f"\nChapters completed (state counter): {chapters_completed_state}/{total_chapters}")
    print(f"Chapters completed (stored in DB): {actual_completed}/{total_chapters}")
    
    if total_chapters > 0:
        completion_pct = (actual_completed / total_chapters) * 100
        print(f"Progress: {completion_pct:.1f}%")
    
    # Show recent completions
    if chapters:
        sorted_chapters = sorted(chapters, key=lambda x: x.get('timestamp', ''), reverse=True)
        print("\nMost recently completed chapters:")
        for ch in sorted_chapters[:10]:
            num = ch.get('chapter_number', '?')
            idx = ch.get('chapter_index', '?')
            title = ch.get('chapter_title', 'N/A')[:50]
            timestamp = ch.get('timestamp', 'N/A')
            if timestamp != 'N/A':
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    time_str = dt.strftime('%H:%M:%S')
                except:
                    time_str = timestamp[-8:] if len(timestamp) > 8 else timestamp
            else:
                time_str = 'N/A'
            print(f"  Chapter {num} (index {idx}): {title} - {time_str}")
    
    # Check for quota issues
    print("\n" + "=" * 60)
    print("QUOTA MONITORING")
    print("=" * 60)
    
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int((datetime.now() - timedelta(minutes=30)).timestamp() * 1000)
    
    try:
        response = logs_client.filter_log_events(
            logGroupName='/aws/lambda/docprof-dev-chapter-summary-processor',
            startTime=start_time,
            endTime=end_time,
            filterPattern='DAILY TOKEN QUOTA',
            limit=10
        )
        
        quota_hits = response.get('events', [])
        if quota_hits:
            print(f"🚨 WARNING: {len(quota_hits)} daily token quota hits detected in last 30 minutes!")
            print("   CloudWatch alarm should have triggered.")
            print("   Check CloudWatch alarms and request quota increase.")
            for event in quota_hits[:3]:
                timestamp = datetime.fromtimestamp(event['timestamp'] / 1000)
                print(f"   {timestamp.strftime('%H:%M:%S')}: {event['message'][:100]}")
        else:
            print("✓ No quota issues detected")
    except Exception as e:
        print(f"⚠️  Error checking quota logs: {e}")
    
    # Check recent activity
    print("\n" + "=" * 60)
    print("RECENT ACTIVITY")
    print("=" * 60)
    
    try:
        response = logs_client.filter_log_events(
            logGroupName='/aws/lambda/docprof-dev-chapter-summary-processor',
            startTime=start_time,
            endTime=end_time,
            filterPattern='Processing chapter',
            limit=50
        )
        
        recent_events = response.get('events', [])
        print(f"Chapters started processing (last 30 min): {len(recent_events)}")
        
        if recent_events:
            latest = recent_events[-1]
            timestamp = datetime.fromtimestamp(latest['timestamp'] / 1000)
            age_minutes = (datetime.now() - timestamp.replace(tzinfo=None)).total_seconds() / 60
            print(f"Most recent: {age_minutes:.1f} minutes ago")
    except Exception as e:
        print(f"⚠️  Error checking activity: {e}")
    
    # Estimate time remaining
    if actual_completed > 0 and total_chapters > actual_completed:
        remaining = total_chapters - actual_completed
        print(f"\nRemaining chapters: {remaining}")
        print("Estimated time: ~10 minutes per chapter (with retries)")
        print(f"  Total: ~{remaining * 10 / 60:.1f} hours if processing sequentially")
        print("  (Processing happens in parallel, so actual time will be less)")

if __name__ == '__main__':
    check_progress()
