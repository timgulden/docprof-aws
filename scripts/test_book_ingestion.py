#!/usr/bin/env python3
"""
End-to-end test for book ingestion via Lambda.
Tests the full flow: upload-initial -> upload PDF -> analyze -> check results.

Usage:
    export AWS_PROFILE=docprof-dev
    python scripts/test_book_ingestion.py <path_to_pdf_file>

This will:
1. Call upload-initial to get book_id
2. Upload PDF to S3
3. Call analyze endpoint to extract metadata/cover
4. Display results and check for issues
"""

import sys
import os
import json
import boto3
import uuid
from pathlib import Path
from datetime import datetime

def test_book_ingestion(pdf_path: str):
    """Test the full book ingestion flow."""
    
    # Setup
    session = boto3.Session(profile_name=os.getenv('AWS_PROFILE', 'docprof-dev'))
    lambda_client = session.client('lambda', region_name='us-east-1')
    s3_client = session.client('s3', region_name='us-east-1')
    
    function_name = 'docprof-dev-book-upload'
    bucket_name = 'docprof-dev-source-docs'
    
    print("=" * 80)
    print("BOOK INGESTION TEST")
    print("=" * 80)
    print(f"PDF: {pdf_path}")
    print(f"Lambda: {function_name}")
    print(f"S3 Bucket: {bucket_name}")
    print()
    
    # Step 1: Get book_id from upload-initial
    print("STEP 1: Getting book_id from upload-initial endpoint...")
    book_id = None
    s3_key = None
    
    event1 = {
        "path": "/books/upload-initial",
        "httpMethod": "POST",
        "headers": {"Content-Type": "application/json"},
        "pathParameters": {},
        "requestContext": {
            "path": "/books/upload-initial",
            "requestId": str(uuid.uuid4()),
        },
        "body": None
    }
    
    try:
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(event1)
        )
        result = json.loads(response['Payload'].read())
        body = json.loads(result.get('body', '{}'))
        
        if result.get('statusCode') == 200 and body.get('book_id'):
            book_id = body['book_id']
            s3_key = body.get('s3_key')
            print(f"✓ Got book_id: {book_id}")
            print(f"  S3 key: {s3_key}")
        else:
            print(f"✗ Failed: {result.get('statusCode')} - {body}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 2: Upload PDF to S3
    print(f"\nSTEP 2: Uploading PDF to S3...")
    with open(pdf_path, 'rb') as f:
        pdf_data = f.read()
    
    print(f"  PDF size: {len(pdf_data):,} bytes")
    
    # Use the s3_key from upload-initial, or construct one
    if not s3_key:
        timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
        s3_key = f"books/{book_id}/upload_{timestamp}.pdf"
    
    try:
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=pdf_data,
            ContentType='application/pdf',
            Metadata={
                'book-id': book_id,
                'x-amz-meta-book-id': book_id
            }
        )
        print(f"✓ Uploaded to s3://{bucket_name}/{s3_key}")
    except Exception as e:
        print(f"✗ Upload failed: {e}")
        return False
    
    # Step 3: Call analyze endpoint
    print(f"\nSTEP 3: Analyzing book (extracting metadata and cover)...")
    print("  This may take 30-60 seconds...")
    
    event2 = {
        "path": f"/books/analyze/{book_id}",
        "httpMethod": "POST",
        "headers": {"Content-Type": "application/json"},
        "pathParameters": {"bookId": book_id},
        "requestContext": {
            "path": f"/books/analyze/{book_id}",
            "requestId": str(uuid.uuid4()),
        },
        "body": None
    }
    
    try:
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(event2)
        )
        result = json.loads(response['Payload'].read())
        status_code = result.get('statusCode')
        body_str = result.get('body', '{}')
        
        # Debug: show raw response
        print(f"\nRaw Lambda Response:")
        print(f"  Status Code: {status_code}")
        print(f"  Body (first 500 chars): {body_str[:500]}")
        if 'errorMessage' in result:
            print(f"  Error Message: {result['errorMessage']}")
        if 'errorType' in result:
            print(f"  Error Type: {result['errorType']}")
        
        try:
            body = json.loads(body_str)
        except Exception as e:
            print(f"  ⚠️  Failed to parse body as JSON: {e}")
            body = {"raw": body_str}
        
        print(f"\nParsed Response:")
        
        if status_code == 200:
            print("✓ Analysis succeeded!")
            
            # Extract metadata from nested structure (metadata is nested in response)
            metadata = body.get('metadata', {})
            cover_url = body.get('cover_url')
            
            print("\nExtracted Metadata:")
            print(f"  Title: {metadata.get('title', '(empty)')}")
            print(f"  Author: {metadata.get('author', '(empty)')}")
            print(f"  Edition: {metadata.get('edition', '(empty)')}")
            print(f"  ISBN: {metadata.get('isbn', '(empty)')}")
            print(f"  Publisher: {metadata.get('publisher', '(empty)')}")
            print(f"  Year: {metadata.get('year', '(empty)')}")
            print(f"  Total Pages: {metadata.get('total_pages', '(empty)')}")
            
            if cover_url:
                cover_len = len(cover_url)
                print(f"  Cover: Present ({cover_len} chars, data URL)")
            else:
                print(f"  Cover: Missing")
            
            # Check confidence
            confidence = metadata.get('confidence', {})
            if confidence:
                print(f"\nExtraction Details:")
                print(f"  Method: {confidence.get('extraction_method', 'unknown')}")
                if 'error' in confidence:
                    print(f"  ⚠️  Error: {confidence.get('error')}")
                    print(f"     Message: {confidence.get('message', 'N/A')}")
                if 'isbn_source' in confidence:
                    print(f"  ISBN Source: {confidence.get('isbn_source')}")
            
            # Summary
            print("\n" + "=" * 80)
            print("RESULTS SUMMARY")
            print("=" * 80)
            
            title = metadata.get('title', '')
            has_title = bool(title and title.lower() not in ['unknown', ''])
            has_author = bool(metadata.get('author', ''))
            has_cover = bool(cover_url)
            
            print(f"✓ Book ID: {book_id}")
            print(f"{'✓' if has_title else '✗'} Title: {title if has_title else 'Missing/Unknown'}")
            print(f"{'✓' if has_author else '✗'} Author: {metadata.get('author', '') if has_author else 'Missing'}")
            print(f"{'✓' if has_cover else '✗'} Cover: {'Extracted' if has_cover else 'Missing'}")
            print(f"✓ Pages: {metadata.get('total_pages', 0)}")
            
            if not has_title and not has_author:
                print("\n⚠️  WARNING: No metadata extracted. Check CloudWatch logs for details.")
                print("   Possible causes:")
                print("   - Bedrock throttling (retry logic should handle this)")
                print("   - PDF text extraction failed")
                print("   - Claude extraction failed")
            
            return True
        else:
            print(f"✗ Analysis failed with status {status_code}")
            print(f"Response: {json.dumps(body, indent=2)}")
            
            # Check for error details
            if 'errorMessage' in result:
                print(f"Error Message: {result['errorMessage']}")
            
            return False
            
    except Exception as e:
        print(f"✗ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_book_ingestion.py <path_to_pdf_file>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)
    
    success = test_book_ingestion(pdf_path)
    sys.exit(0 if success else 1)

