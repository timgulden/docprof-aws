#!/usr/bin/env python3
"""
Quick test script to verify Bedrock Claude Sonnet 4.5 access.
Tests model access without running full ingestion pipeline.
"""

import json
import boto3
import os
import sys
from botocore.exceptions import ClientError

def test_bedrock_access():
    """Test Bedrock Claude Sonnet 4.5 access."""
    
    # Get AWS credentials from environment or default profile
    aws_profile = os.getenv('AWS_PROFILE', 'docprof-dev')
    region = os.getenv('AWS_REGION', 'us-east-1')
    
    # Get account ID from environment or try to get it
    account_id = os.getenv('AWS_ACCOUNT_ID')
    if not account_id:
        try:
            sts = boto3.client('sts', region_name=region)
            account_id = sts.get_caller_identity()['Account']
        except Exception as e:
            print(f"⚠️  Could not get account ID: {e}")
            print("   Set AWS_ACCOUNT_ID environment variable or configure AWS credentials")
            return False
    
    print(f"🧪 Testing Bedrock access...")
    print(f"   Region: {region}")
    print(f"   Account ID: {account_id}")
    print(f"   Model: Claude Sonnet 4.5")
    print()
    
    # Initialize Bedrock runtime client
    try:
        bedrock = boto3.client('bedrock-runtime', region_name=region)
    except Exception as e:
        print(f"❌ Failed to create Bedrock client: {e}")
        return False
    
    # Construct inference profile ARN
    model_id = f"arn:aws:bedrock:{region}:{account_id}:inference-profile/us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    
    print(f"📡 Invoking model: {model_id}")
    print()
    
    # Test request
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 100,
        "temperature": 0.7,
        "messages": [
            {
                "role": "user",
                "content": "Say 'Hello, Bedrock is working!' if you can read this."
            }
        ]
    }
    
    try:
        print("⏳ Sending test request...")
        response = bedrock.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body)
        )
        
        response_body = json.loads(response['body'].read())
        content = response_body['content'][0]['text']
        usage = response_body.get('usage', {})
        
        print("✅ SUCCESS! Bedrock access is working!")
        print()
        print(f"📝 Response: {content}")
        print()
        print(f"📊 Token Usage:")
        print(f"   Input tokens: {usage.get('input_tokens', 'N/A')}")
        print(f"   Output tokens: {usage.get('output_tokens', 'N/A')}")
        print()
        print("🎉 Claude Sonnet 4.5 is ready to use!")
        return True
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        
        print(f"❌ FAILED: {error_code}")
        print(f"   {error_message}")
        print()
        
        if 'AccessDeniedException' in error_code:
            if 'Marketplace' in error_message:
                print("💡 This looks like a Marketplace subscription issue.")
                print("   Claude Sonnet 4.5 shouldn't require Marketplace.")
                print("   Check if the use case form was approved.")
            else:
                print("💡 Check IAM permissions for Bedrock InvokeModel")
        elif 'ResourceNotFoundException' in error_code:
            if 'use case' in error_message.lower():
                print("💡 Use case form may not be approved yet.")
                print("   Wait a few more minutes and try again.")
            else:
                print("💡 Model may not be available in this region.")
        
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


if __name__ == '__main__':
    print("=" * 60)
    print("Bedrock Access Test - Claude Sonnet 4.5")
    print("=" * 60)
    print()
    
    success = test_bedrock_access()
    
    print()
    print("=" * 60)
    if success:
        print("✅ Test passed! Bedrock is ready for ingestion.")
        sys.exit(0)
    else:
        print("❌ Test failed. Check errors above.")
        sys.exit(1)

