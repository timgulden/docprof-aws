#!/usr/bin/env python3
"""
Script to fix all OPTIONS methods in API Gateway that are missing integrations.
"""

import boto3
import json

# Configuration
API_ID = "evjgcsghvi"
STAGE_NAME = "dev"
CORS_ORIGIN = "http://localhost:5173"
CORS_HEADERS = "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Book-Title,X-Book-Author,X-Book-Edition,X-Book-Isbn"
CORS_METHODS = "GET,POST,PUT,DELETE,OPTIONS,PATCH"

# Create boto3 client
session = boto3.Session(profile_name='docprof-dev')
client = session.client('apigateway')

def fix_options_method(resource_id, path):
    """Fix the OPTIONS method for a resource."""
    print(f"\nFixing OPTIONS for {path} ({resource_id})...")
    
    try:
        # Check if OPTIONS method exists
        try:
            client.get_method(
                restApiId=API_ID,
                resourceId=resource_id,
                httpMethod='OPTIONS'
            )
            # If it exists, delete it first
            print(f"  Deleting existing OPTIONS method...")
            client.delete_method(
                restApiId=API_ID,
                resourceId=resource_id,
                httpMethod='OPTIONS'
            )
        except client.exceptions.NotFoundException:
            print(f"  No existing OPTIONS method to delete")
        
        # Create OPTIONS method
        print(f"  Creating OPTIONS method...")
        client.put_method(
            restApiId=API_ID,
            resourceId=resource_id,
            httpMethod='OPTIONS',
            authorizationType='NONE',
            apiKeyRequired=False
        )
        
        # Add MOCK integration
        print(f"  Adding MOCK integration...")
        client.put_integration(
            restApiId=API_ID,
            resourceId=resource_id,
            httpMethod='OPTIONS',
            type='MOCK',
            requestTemplates={
                'application/json': '{"statusCode": 200}'
            }
        )
        
        # Add method response
        print(f"  Adding method response...")
        client.put_method_response(
            restApiId=API_ID,
            resourceId=resource_id,
            httpMethod='OPTIONS',
            statusCode='200',
            responseParameters={
                'method.response.header.Access-Control-Allow-Origin': True,
                'method.response.header.Access-Control-Allow-Headers': True,
                'method.response.header.Access-Control-Allow-Methods': True,
                'method.response.header.Access-Control-Allow-Credentials': True
            }
        )
        
        # Add integration response
        print(f"  Adding integration response...")
        client.put_integration_response(
            restApiId=API_ID,
            resourceId=resource_id,
            httpMethod='OPTIONS',
            statusCode='200',
            responseParameters={
                'method.response.header.Access-Control-Allow-Origin': f"'{CORS_ORIGIN}'",
                'method.response.header.Access-Control-Allow-Headers': f"'{CORS_HEADERS}'",
                'method.response.header.Access-Control-Allow-Methods': f"'{CORS_METHODS}'",
                'method.response.header.Access-Control-Allow-Credentials': "'true'"
            }
        )
        
        print(f"  ✓ Fixed!")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def main():
    print("=" * 60)
    print("Fixing all OPTIONS methods in API Gateway")
    print("=" * 60)
    
    # Get all resources
    print("\nGetting all resources...")
    resources = client.get_resources(restApiId=API_ID, limit=500)
    
    fixed_count = 0
    error_count = 0
    skipped_count = 0
    
    for resource in resources['items']:
        resource_id = resource['id']
        path = resource['path']
        
        # Skip root
        if path == '/':
            continue
        
        # Check if this resource needs an OPTIONS method
        # Resources that are just parent paths (like /chat, /books, /ai-services) don't need OPTIONS
        # Only endpoints that have actual methods need OPTIONS
        methods = resource.get('resourceMethods', {})
        if not methods:
            print(f"\nSkipping {path} - no methods defined")
            skipped_count += 1
            continue
        
        # Check if OPTIONS integration exists and is correct
        try:
            integration = client.get_integration(
                restApiId=API_ID,
                resourceId=resource_id,
                httpMethod='OPTIONS'
            )
            # Check if request templates are correct
            templates = integration.get('requestTemplates', {})
            if templates and templates.get('application/json') == '{"statusCode": 200}':
                print(f"\nSkipping {path} - OPTIONS already configured correctly")
                skipped_count += 1
                continue
            else:
                print(f"\n{path} has broken OPTIONS (empty requestTemplates)")
        except client.exceptions.NotFoundException:
            print(f"\n{path} is missing OPTIONS integration")
        
        # Fix the OPTIONS method
        if fix_options_method(resource_id, path):
            fixed_count += 1
        else:
            error_count += 1
    
    print("\n" + "=" * 60)
    print(f"Summary: Fixed {fixed_count}, Errors {error_count}, Skipped {skipped_count}")
    print("=" * 60)
    
    if fixed_count > 0 or error_count == 0:
        # Create deployment
        print("\nCreating deployment...")
        try:
            response = client.create_deployment(
                restApiId=API_ID,
                stageName=STAGE_NAME,
                description='Fix all OPTIONS methods'
            )
            print(f"Deployment created: {response['id']}")
        except Exception as e:
            print(f"Error creating deployment: {e}")
    
    print("\nDone!")

if __name__ == '__main__':
    main()
