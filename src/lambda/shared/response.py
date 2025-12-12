"""
Standard API response utilities for Lambda functions
"""

from typing import Dict, Any, Optional
import json
from datetime import datetime, date

def _json_serializer(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def success_response(
    body: Dict[str, Any],
    status_code: int = 200,
    headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Create a successful API Gateway response.
    
    Args:
        body: Response body dictionary
        status_code: HTTP status code (default: 200)
        headers: Optional custom headers
    
    Returns:
        API Gateway response dictionary
    """
    default_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
    }
    
    if headers:
        default_headers.update(headers)
    
    return {
        'statusCode': status_code,
        'headers': default_headers,
        'body': json.dumps(body, default=_json_serializer)
    }


def error_response(
    message: str,
    status_code: int = 500,
    error_code: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Create an error API Gateway response.
    
    Args:
        message: Error message
        status_code: HTTP status code (default: 500)
        error_code: Optional error code
        headers: Optional custom headers
    
    Returns:
        API Gateway response dictionary
    """
    body = {
        'error': message
    }
    
    if error_code:
        body['error_code'] = error_code
    
    default_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
    }
    
    if headers:
        default_headers.update(headers)
    
    return {
        'statusCode': status_code,
        'headers': default_headers,
        'body': json.dumps(body)
    }

