#!/usr/bin/env python3
"""
Test script to process a single chapter for source summary generation.

This bypasses the full pipeline and directly invokes the chapter_summary_processor
Lambda with one chapter, useful for testing without processing all chapters.
"""

import boto3
import json
import os
import sys

# Set up AWS session
session = boto3.Session(profile_name=os.getenv('AWS_PROFILE', 'docprof-dev'))
region = os.getenv('AWS_REGION', 'us-east-1')
lambda_client = session.client('lambda', region_name=region)
s3_client = session.client('s3', region_name=region)

# Configuration
source_bucket = 'docprof-dev-source-docs'
valuation_source_id = '45eea4fb-b509-4c99-af6b-25231163941e'
s3_key = 'books/45eea4fb-b509-4c99-af6b-25231163941e/upload_20251214-162616.pdf'
lambda_function_name = 'docprof-dev-chapter-summary-processor'

def get_pdf_page_count(s3_bucket, s3_key):
    """Get total page count from PDF."""
    try:
        import fitz  # PyMuPDF
        import io
        
        # Download PDF
        response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
        pdf_data = response['Body'].read()
        
        # Open PDF
        doc = fitz.open(stream=pdf_data, filetype='pdf')
        page_count = len(doc)
        doc.close()
        
        return page_count
    except Exception as e:
        print(f"Warning: Could not get page count: {e}")
        return 1321  # Default for Valuation book

def create_test_chapter_event(chapter_index=0, chapter_number=1, chapter_title="Test Chapter", page_start=50, page_end=60):
    """Create a test event for a single chapter."""
    
    # Get total pages
    total_pages = get_pdf_page_count(source_bucket, s3_key)
    
    # Create chapter structure
    chapter = {
        "chapter_number": chapter_number,
        "chapter_title": chapter_title,
        "page_number": page_start,
        "sections": [
            {
                "section_title": "Section 1",
                "page_number": page_start,
                "level": 1
            }
        ]
    }
    
    # Create minimal TOC structure
    toc_data = {
        "chapters": [chapter],
        "total_pages": total_pages
    }
    
    # Create event payload
    event = {
        "source_id": valuation_source_id,
        "source_title": "Valuation: Measuring and Managing the Value of Companies",
        "author": "Tim Koller",
        "s3_bucket": source_bucket,
        "s3_key": s3_key,
        "chapter_index": chapter_index,
        "chapter": chapter,
        "total_pages": total_pages,
        "toc_data": toc_data
    }
    
    return event

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Test single chapter processing')
    parser.add_argument('--chapter-index', type=int, default=0, help='Chapter index (0-based)')
    parser.add_argument('--chapter-number', type=int, default=1, help='Chapter number')
    parser.add_argument('--chapter-title', type=str, default="Test Chapter", help='Chapter title')
    parser.add_argument('--page-start', type=int, default=50, help='Starting page number')
    parser.add_argument('--page-end', type=int, default=60, help='Ending page number')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("TEST SINGLE CHAPTER PROCESSING")
    print("=" * 60)
    print(f"Chapter index: {args.chapter_index}")
    print(f"Chapter number: {args.chapter_number}")
    print(f"Chapter title: {args.chapter_title}")
    print(f"Pages: {args.page_start}-{args.page_end}")
    print()
    
    # Create test event
    event = create_test_chapter_event(
        chapter_index=args.chapter_index,
        chapter_number=args.chapter_number,
        chapter_title=args.chapter_title,
        page_start=args.page_start,
        page_end=args.page_end
    )
    
    print("Invoking Lambda...")
    print(f"Function: {lambda_function_name}")
    print()
    
    try:
        response = lambda_client.invoke(
            FunctionName=lambda_function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(event)
        )
        
        # Read response
        result = json.loads(response['Payload'].read())
        
        if 'errorMessage' in result:
            print("❌ Lambda Error:")
            print(result['errorMessage'])
            if 'stackTrace' in result:
                print("\nStack trace:")
                for line in result['stackTrace']:
                    print(f"  {line}")
            sys.exit(1)
        
        # Check status code
        status_code = result.get('statusCode', 200)
        if status_code != 200:
            print(f"❌ Status code: {status_code}")
            print(f"Body: {result.get('body', 'No body')}")
            sys.exit(1)
        
        # Parse body
        body = json.loads(result.get('body', '{}'))
        
        print("✓ Lambda completed successfully!")
        print()
        print("Response:")
        print(json.dumps(body, indent=2))
        
        # Check if chapter summary was stored
        if body.get('status') == 'completed':
            print()
            print("✓ Chapter processing completed!")
            print(f"  Chapter: {body.get('chapter_number')} - {body.get('chapter_title')}")
            
            # Check DynamoDB
            print()
            print("Checking DynamoDB for stored chapter summary...")
            dynamodb = session.resource('dynamodb', region_name=region)
            chapters_table = dynamodb.Table('docprof-dev-chapter-summaries')
            
            try:
                resp = chapters_table.get_item(
                    Key={
                        'source_id': valuation_source_id,
                        'chapter_index': args.chapter_index
                    }
                )
                
                if 'Item' in resp:
                    item = resp['Item']
                    print(f"✓ Found in DynamoDB!")
                    print(f"  Status: {item.get('status')}")
                    print(f"  Timestamp: {item.get('timestamp')}")
                else:
                    print("⚠️  Not found in DynamoDB (may not have been stored)")
            except Exception as e:
                print(f"⚠️  Error checking DynamoDB: {e}")
        
    except Exception as e:
        print(f"❌ Error invoking Lambda: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
