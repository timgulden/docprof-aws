"""
Bedrock client utilities for LLM and embeddings
Uses AWS Bedrock Claude for LLM and Titan for embeddings
"""

import json
import boto3
import logging
from typing import List, Dict, Any, Optional, Iterator
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Initialize Bedrock runtime client
# Use region from environment variable (set by Lambda runtime) or default to us-east-1
import os
bedrock_region = os.getenv('AWS_REGION', 'us-east-1')
bedrock_runtime = boto3.client('bedrock-runtime', region_name=bedrock_region)


def generate_embeddings(texts: List[str], normalize: bool = True) -> List[List[float]]:
    """
    Generate embeddings using Bedrock Titan Embeddings model.
    
    Args:
        texts: List of texts to embed
        normalize: Whether to normalize embeddings to unit length (default: True)
    
    Returns:
        List of embedding vectors (1536 dimensions each)
    """
    embeddings = []
    
    for text in texts:
        try:
            # Bedrock Titan Embeddings API
            response = bedrock_runtime.invoke_model(
                modelId='amazon.titan-embed-text-v1',
                body=json.dumps({
                    'inputText': text
                })
            )
            
            response_body = json.loads(response['body'].read())
            embedding = response_body['embedding']
            
            # Normalize if requested
            if normalize:
                import math
                magnitude = math.sqrt(sum(x * x for x in embedding))
                if magnitude > 0:
                    embedding = [x / magnitude for x in embedding]
            
            embeddings.append(embedding)
            
        except ClientError as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    return embeddings


def invoke_claude(
    messages: List[Dict[str, str]],
    system: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    stream: bool = False
) -> Dict[str, Any]:
    """
    Invoke Claude Sonnet 4.5 via Bedrock (using inference profile).
    Claude Sonnet 4.5 is the newest model with best performance.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        system: Optional system prompt
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature (0-1)
        stream: Whether to stream the response
    
    Returns:
        Response dictionary with 'content' and 'usage' keys
    """
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages
    }
    
    if system:
        request_body["system"] = system
    
    # Use inference profile ARN for Claude models (required for on-demand)
    # Format: arn:aws:bedrock:region:account-id:inference-profile/profile-id
    # Use the system-defined inference profile for Claude 3 Sonnet
    region = bedrock_runtime.meta.region_name
    
    # Get account ID from environment variable (set by Terraform)
    # Avoid calling STS (would require VPC endpoint)
    import os
    account_id = os.getenv('AWS_ACCOUNT_ID')
    if not account_id:
        # Fallback: try to extract from role ARN if Lambda context available
        # This shouldn't happen if Terraform is configured correctly
        raise ValueError("AWS_ACCOUNT_ID environment variable not set. Configure in Terraform.")
    
    # Use Claude Sonnet 4.5 - Excellent quality, fast, cost-effective
    # Sonnet 4.5 provides excellent quality without the cost/speed tradeoffs of Opus
    model_id = f"arn:aws:bedrock:{region}:{account_id}:inference-profile/us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    
    if stream:
        response = bedrock_runtime.invoke_model_with_response_stream(
            modelId=model_id,
            body=json.dumps(request_body)
        )
        return _parse_streaming_response(response)
    else:
        response = bedrock_runtime.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body)
        )
        response_body = json.loads(response['body'].read())
        
        return {
            'content': response_body['content'][0]['text'],
            'usage': {
                'input_tokens': response_body.get('usage', {}).get('input_tokens', 0),
                'output_tokens': response_body.get('usage', {}).get('output_tokens', 0)
            }
        }


def _parse_streaming_response(response) -> Iterator[Dict[str, Any]]:
    """
    Parse streaming response from Bedrock.
    
    Yields:
        Dictionary chunks with 'content' and 'done' keys
    """
    stream = response.get('body')
    if not stream:
        return
    
    for event in stream:
        if 'chunk' in event:
            chunk = json.loads(event['chunk']['bytes'])
            if chunk['type'] == 'content_block_delta':
                yield {
                    'content': chunk['delta']['text'],
                    'done': False
                }
            elif chunk['type'] == 'message_stop':
                yield {'done': True}


def describe_figure(image_bytes: bytes, context: Optional[str] = None) -> str:
    """
    Describe a figure using Claude with vision capabilities.
    
    Args:
        image_bytes: Image bytes (PNG/JPEG)
        context: Optional surrounding text context
    
    Returns:
        Figure description text
    """
    import base64
    
    # Encode image as base64
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
    
    # Build message with image
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",  # Adjust based on format
                        "data": image_base64
                    }
                },
                {
                    "type": "text",
                    "text": f"""Describe this figure from a textbook. 
                    {'Context: ' + context if context else ''}
                    Provide a detailed description including:
                    - What the figure shows
                    - Key elements and labels
                    - Main takeaway or concept illustrated
                    - How it relates to the surrounding text (if context provided)
                    
                    Format as structured text suitable for embedding."""
                }
            ]
        }
    ]
    
    system = "You are an expert at analyzing and describing educational figures and diagrams from textbooks."
    
    # Use Claude Sonnet 4.5 for figure descriptions (excellent quality)
    # Temperature 0.2 for factual, consistent descriptions
    # Max tokens 2000 for detailed descriptions
    response = invoke_claude(
        messages=messages,
        system=system,
        max_tokens=2000,  # Increased for more detailed descriptions
        temperature=0.2  # Lower temperature for more factual, consistent descriptions
    )
    
    return response['content']

