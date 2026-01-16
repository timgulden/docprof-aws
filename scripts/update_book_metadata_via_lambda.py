#!/usr/bin/env python3
"""
Update book metadata via Lambda invocation.
"""

import boto3
import json
import sys

def main():
    book_id = 'a690dc56-fc0c-4eb1-ab16-26db0397ca17'
    new_title = 'Investment Valuation: Tools and Techniques for Determining the Value of Any Asset'
    new_author = 'Aswath Damodaran'
    new_edition = '3rd Edition'
    
    # Create a simple Lambda payload that updates the database
    payload = {
        'action': 'update_metadata',
        'book_id': book_id,
        'title': new_title,
        'author': new_author,
        'edition': new_edition
    }
    
    print(f"Updating book metadata via Lambda...")
    print(f"  Book ID: {book_id}")
    print(f"  Title: {new_title}")
    print(f"  Author: {new_author}")
    print(f"  Edition: {new_edition}")
    
    client = boto3.client('lambda', region_name='us-east-1')
    
    # Use books-list Lambda to update (we'll need to add this functionality)
    # For now, let's invoke with a custom payload
    response = client.invoke(
        FunctionName='docprof-dev-books-list',
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )
    
    result = json.loads(response['Payload'].read())
    print(f"\nResponse: {json.dumps(result, indent=2)}")
    
    return 0 if result.get('statusCode') == 200 else 1


if __name__ == '__main__':
    sys.exit(main())
