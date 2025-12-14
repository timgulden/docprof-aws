#!/usr/bin/env python3
"""
Test book_upload Lambda function programmatically.
Invokes the actual deployed Lambda to test the full flow including retry logic.

Usage:
    export AWS_PROFILE=docprof-dev
    python scripts/test_book_upload_lambda.py <path_to_pdf_file>

This script will:
1. Upload a PDF to S3 (simulating frontend upload)
2. Invoke the analyze endpoint to extract metadata and cover
3. Show results including any throttling/retry behavior
"""

import sys
import os
import json
import boto3
import uuid
import base64
from pathlib import Path
from datetime import datetime

def create_api_gateway_event(path: str, body: str = None, path_params: dict = None, http_method: str = "POST") -> dict:
    """Create an API Gateway proxy event structure for testing."""
    event = {
        "resource": path,
        "path": path,
        "httpMethod": http_method,
        "headers": {
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        "multiValueHeaders": {},
        "queryStringParameters": None,
        "multiValueQueryStringParameters": None,
        "pathParameters": path_params or {},
        "stageVariables": None,
        "requestContext": {
            "resourceId": "test",
            "resourcePath": path,
            "httpMethod": http_method,
            "requestId": str(uuid.uuid4()),
            "path": path,
            "accountId": "176520790264",
            "protocol": "HTTP/1.1",
            "stage": "dev",
            "domainPrefix": "test",
            "requestTime": datetime.utcnow().isoformat(),
            "requestTimeEpoch": int(datetime.utcnow().timestamp()),
            "identity": {
                "cognitoIdentityPoolId": None,
                "accountId": None,
                "cognitoIdentityId": None,
                "caller": None,
                "sourceIp": "127.0.0.1",
                "principalOrgId": None,
                "accessKey": None,
                "cognitoAuthenticationType": None,
                "cognitoAuthenticationProvider": None,
                "userArn": None,
                "userAgent": "test-script",
                "user": None
            },
            "domainName": "test.execute-api.us-east-1.amazonaws.com",
            "apiId": "test"
        },
        "body": body,
        "isBase64Encoded": False
    }
    return event


def test_upload_initial(lambda_client, function_name: str):
    """Test the /books/upload-initial endpoint - generates pre-signed URL."""
    print("=" * 80)
    print("TEST 1: Upload Initial (Generate Pre-signed URL)")
    print("=" * 80)
    
    event = create_api_gateway_event("/books/upload-initial")
    
    print(f"\nInvoking Lambda: {function_name}")
    print(f"Path: {event['path']}")
    
    try:
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(event)
        )
        
        payload = json.loads(response['Payload'].read())
        status_code = payload.get('statusCode', 500)
        body = json.loads(payload.get('body', '{}'))
        
        print(f"\nStatus Code: {status_code}")
        print(f"\nResponse Body:")
        print(json.dumps(body, indent=2))
        
        if status_code == 200 and 'book_id' in body:
            book_id = body['book_id']
            print(f"\n✓ Success! Book ID: {book_id}")
            return book_id, body.get('upload_url')
        else:
            print(f"\n✗ Failed with status {status_code}")
            return None, None
            
    except Exception as e:
        print(f"\n✗ Error invoking Lambda: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def test_analyze_book(lambda_client, function_name: str, book_id: str, pdf_path: str):
    """Test the /books/analyze/{bookId} endpoint - extracts metadata and cover."""
    print("\n" + "=" * 80)
    print("TEST 2: Analyze Book (Extract Metadata and Cover)")
    print("=" * 80)
    
    print(f"\nBook ID: {book_id}")
    print(f"PDF Path: {pdf_path}")
    
    # First, we need to upload the PDF to S3
    # Get the bucket name from environment or Lambda configuration
    s3_client = boto3.client('s3')
    
    # Read PDF
    with open(pdf_path, 'rb') as f:
        pdf_data = f.read()
    
    print(f"PDF size: {len(pdf_data):,} bytes")
    
    # Get bucket name - we'll need to check Lambda environment or use a default
    # For now, let's try to get it from the Lambda configuration
    try:
        lambda_config = lambda_client.get_function_configuration(FunctionName=function_name)
        env_vars = lambda_config.get('Environment', {}).get('Variables', {})
        bucket_name = env_vars.get('SOURCE_BUCKET')
        
        if not bucket_name:
            print("⚠️  Could not determine SOURCE_BUCKET from Lambda config")
            print("   Please set SOURCE_BUCKET environment variable")
            return None
    except Exception as e:
        print(f"⚠️  Could not get Lambda config: {e}")
        bucket_name = os.getenv('SOURCE_BUCKET')
    
    if not bucket_name:
        print("✗ SOURCE_BUCKET not found. Cannot upload PDF to S3.")
        print("   Either set SOURCE_BUCKET env var or ensure Lambda has it configured.")
        return None
    
    # Upload PDF to S3 with book_id metadata
    timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    s3_key = f"books/{book_id}/upload_{timestamp}.pdf"
    
    print(f"\nUploading PDF to S3...")
    print(f"  Bucket: {bucket_name}")
    print(f"  Key: {s3_key}")
    
    try:
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=pdf_data,
            ContentType='application/pdf',
            Metadata={
                'book-id': book_id,  # Important for document_processor
                'x-amz-meta-book-id': book_id  # Also set this for compatibility
            }
        )
        print(f"✓ PDF uploaded to S3")
    except Exception as e:
        print(f"✗ Failed to upload PDF to S3: {e}")
        return None
    
    # Now invoke the analyze endpoint
    event = create_api_gateway_event(
        f"/books/analyze/{book_id}",
        path_params={"bookId": book_id}
    )
    
    print(f"\nInvoking Lambda: {function_name}")
    print(f"Path: {event['path']}")
    
    try:
        print("\n⏳ Invoking analyze endpoint (this may take 30-60 seconds)...")
        print("   (Watch for retry messages if throttling occurs)")
        
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(event)
        )
        
        payload = json.loads(response['Payload'].read())
        status_code = payload.get('statusCode', 500)
        body_str = payload.get('body', '{}')
        
        # Try to parse body as JSON
        try:
            body = json.loads(body_str)
        except json.JSONDecodeError:
            body = {"raw": body_str}
        
        print(f"\nStatus Code: {status_code}")
        print(f"\nResponse Body:")
        print(json.dumps(body, indent=2))
        
        if status_code == 200:
            print("\n✓ Analyze succeeded!")
            
            # Check metadata
            if body.get('title'):
                print(f"  ✓ Title: {body.get('title')}")
            else:
                print(f"  ✗ Title: Missing")
            
            if body.get('author'):
                print(f"  ✓ Author: {body.get('author')}")
            else:
                print(f"  ✗ Author: Missing")
            
            if body.get('isbn'):
                print(f"  ✓ ISBN: {body.get('isbn')}")
            else:
                print(f"  - ISBN: Not found")
            
            if body.get('cover_url'):
                print(f"  ✓ Cover: {body.get('cover_url')[:50]}... (data URL)")
            else:
                print(f"  ✗ Cover: Missing")
            
            if body.get('total_pages'):
                print(f"  ✓ Pages: {body.get('total_pages')}")
            
            return body
        else:
            print(f"\n✗ Failed with status {status_code}")
            if 'errorMessage' in payload:
                print(f"  Error: {payload['errorMessage']}")
            return None
            
    except Exception as e:
        print(f"\n✗ Error invoking Lambda: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_book_upload_lambda.py <path_to_pdf_file>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)
    
    # Set up AWS clients
    session = boto3.Session(profile_name=os.getenv('AWS_PROFILE', 'docprof-dev'))
    lambda_client = session.client('lambda', region_name='us-east-1')
    
    # Lambda function name (set by Terraform)
    function_name = os.getenv('BOOK_UPLOAD_LAMBDA_NAME', 'docprof-dev-book-upload')
    
    print("=" * 80)
    print("BOOK UPLOAD LAMBDA TEST")
    print("=" * 80)
    print(f"\nLambda Function: {function_name}")
    print(f"PDF File: {pdf_path}")
    print(f"AWS Profile: {os.getenv('AWS_PROFILE', 'docprof-dev')}")
    print()
    
    # Test 1: Upload Initial
    book_id, upload_url = test_upload_initial(lambda_client, function_name)
    
    if not book_id:
        print("\n✗ Failed to get book_id. Cannot continue.")
        sys.exit(1)
    
    # Test 2: Analyze Book
    result = test_analyze_book(lambda_client, function_name, book_id, pdf_path)
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if result:
        print("✓ Book analysis completed successfully")
        print(f"\nBook ID: {book_id}")
        if result.get('title'):
            print(f"Title: {result.get('title')}")
        if result.get('author'):
            print(f"Author: {result.get('author')}")
        if result.get('isbn'):
            print(f"ISBN: {result.get('isbn')}")
        if result.get('total_pages'):
            print(f"Pages: {result.get('total_pages')}")
    else:
        print("✗ Book analysis failed")
        sys.exit(1)


if __name__ == "__main__":
    main()

