"""
Bedrock client utilities for LLM and embeddings
Uses AWS Bedrock Claude for LLM and Titan for embeddings
"""

import json
import logging
import os
import time
from typing import Any, Dict, Iterator, List, Optional, Union

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# CloudWatch client for custom metrics
cloudwatch = boto3.client('cloudwatch', region_name=os.getenv("AWS_REGION", "us-east-1"))

# Initialize Bedrock runtime client
# Use region from environment variable (set by Lambda runtime) or default to us-east-1
bedrock_region = os.getenv("AWS_REGION", "us-east-1")
bedrock_runtime = boto3.client("bedrock-runtime", region_name=bedrock_region)

# Model configuration
# -------------------
# By default we use the Claude Sonnet 4.5 inference profile ARN constructed
# from AWS_ACCOUNT_ID and region (legacy behaviour).
#
# You can override this without code changes by setting:
#   - LLM_MODEL_ID:       primary modelId / ARN to use for all Claude calls
#   - LLM_FALLBACK_MODEL_ID: optional secondary modelId / ARN that will be
#                            automatically used if the primary model hits
#                            daily token quota limits ("Too many tokens per day").
#
# Example values:
#   LLM_MODEL_ID=arn:aws:bedrock:us-east-1:123456789012:inference-profile/us.anthropic.claude-sonnet-4-5-20250929-v1:0
#   LLM_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
#
# Recommended fallback (Claude 3.5 Sonnet - excellent quality, separate quotas):
#   LLM_FALLBACK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
#   # Or via inference profile:
#   LLM_FALLBACK_MODEL_ID=arn:aws:bedrock:us-east-1:ACCOUNT:inference-profile/us.anthropic.claude-3-5-sonnet-20241022-v2:0
#
# NOTE: Fallback is automatically triggered when hitting daily token limits.
# For other throttling (rate limits), we retry the primary model with backoff.
PRIMARY_LLM_MODEL_ID_ENV = os.getenv("LLM_MODEL_ID")
FALLBACK_LLM_MODEL_ID_ENV = os.getenv("LLM_FALLBACK_MODEL_ID")


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
    messages: List[Dict[str, Any]],
    system: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    stream: bool = False,
    model_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Invoke a Claude-family model via Bedrock (using modelId or inference profile).
    
    By default this uses the Claude Sonnet 4.5 inference profile, but you can
    override the model without code changes by setting the LLM_MODEL_ID
    environment variable, or per-call by passing model_id explicitly.
    
    Automatic fallback: If the primary model hits a daily token quota limit
    ("Too many tokens per day") and LLM_FALLBACK_MODEL_ID is configured, this
    function will automatically retry the request with the fallback model.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
                 Content can be a string or list of content blocks (text/image)
        system: Optional system prompt
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature (0-1)
        stream: Whether to stream the response
        model_id: Optional explicit modelId/ARN override (for per-call model selection)
    
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
    
    # Resolve modelId to use
    #
    # Priority:
    #   1) Explicit model_id argument
    #   2) LLM_MODEL_ID environment variable
    #   3) Legacy default: Sonnet 4.5 inference profile ARN constructed
    #      from AWS_ACCOUNT_ID and region.
    if model_id is None:
        if PRIMARY_LLM_MODEL_ID_ENV:
            model_id = PRIMARY_LLM_MODEL_ID_ENV
        else:
            region = bedrock_runtime.meta.region_name
            account_id = os.getenv("AWS_ACCOUNT_ID")
            if not account_id:
                # Fallback: try to extract from role ARN if Lambda context available
                # This shouldn't happen if Terraform is configured correctly
                raise ValueError(
                    "AWS_ACCOUNT_ID environment variable not set. Configure in Terraform "
                    "or set LLM_MODEL_ID to override the default model."
                )
            # Legacy default: Claude Sonnet 4.5 inference profile
            model_id = (
                f"arn:aws:bedrock:{region}:{account_id}:inference-profile/"
                "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
            )
    
    logger.debug(f"Invoking Bedrock model_id={model_id}")
    
    # Retry logic for throttling (fixed interval with jitter)
    max_retries = 20  # Allow many retries for throttling
    retry_interval = 30.0  # Fixed 30 second interval (20-40s with jitter)
    import random
    
    for attempt in range(max_retries + 1):
        try:
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
                # Read the response body once (it's a stream that can only be read once)
                body_bytes = response['body'].read()
                
                # Ensure we have valid JSON
                try:
                    response_body = json.loads(body_bytes.decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    # Log the raw response for debugging
                    logger.error(f"Failed to decode Bedrock response: {e}")
                    logger.error(f"Response body type: {type(body_bytes)}, length: {len(body_bytes) if body_bytes else 0}")
                    logger.error(f"Response body preview (first 500 chars): {body_bytes[:500] if body_bytes else 'None'}")
                    raise ValueError(f"Invalid response from Bedrock: {e}")
                
                return {
                    'content': response_body['content'][0]['text'],
                    'usage': {
                        'input_tokens': response_body.get('usage', {}).get('input_tokens', 0),
                        'output_tokens': response_body.get('usage', {}).get('output_tokens', 0)
                    },
                    'model_used': model_id,  # Track which model was actually used
                }
        
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_message = str(e).lower()
            
            # Check if this is a daily token quota limit (not just rate limiting)
            is_daily_token_limit = (
                error_code == 'ThrottlingException' and
                'too many tokens per day' in error_message
            )
            
            # Publish CloudWatch metric for quota hits (always, even if fallback is disabled)
            if is_daily_token_limit:
                try:
                    cloudwatch.put_metric_data(
                        Namespace='DocProf/Custom',
                        MetricData=[
                            {
                                'MetricName': 'BedrockDailyTokenQuotaHits',
                                'Value': 1,
                                'Unit': 'Count',
                                'Dimensions': [
                                    {
                                        'Name': 'ModelId',
                                        'Value': model_id.split('/')[-1] if '/' in model_id else model_id
                                    }
                                ]
                            }
                        ]
                    )
                    logger.error(
                        f"🚨 DAILY TOKEN QUOTA LIMIT HIT for {model_id}. "
                        f"CloudWatch alarm should trigger. Request quota increase immediately."
                    )
                except Exception as metric_error:
                    # Don't fail the request if metric publishing fails
                    logger.warning(f"Failed to publish quota metric: {metric_error}")
            
            # Publish metric for general throttling (rate limits)
            if error_code == 'ThrottlingException':
                try:
                    cloudwatch.put_metric_data(
                        Namespace='DocProf/Custom',
                        MetricData=[
                            {
                                'MetricName': 'BedrockThrottlingExceptions',
                                'Value': 1,
                                'Unit': 'Count',
                                'Dimensions': [
                                    {
                                        'Name': 'ModelId',
                                        'Value': model_id.split('/')[-1] if '/' in model_id else model_id
                                    },
                                    {
                                        'Name': 'QuotaType',
                                        'Value': 'daily_token_limit' if is_daily_token_limit else 'rate_limit'
                                    }
                                ]
                            }
                        ]
                    )
                except Exception as metric_error:
                    logger.warning(f"Failed to publish throttling metric: {metric_error}")
            
            # If we hit daily token limit and have a fallback model, switch to it immediately
            # NOTE: Fallback is currently disabled - we alert instead
            if is_daily_token_limit and FALLBACK_LLM_MODEL_ID_ENV and model_id != FALLBACK_LLM_MODEL_ID_ENV:
                logger.warning(
                    f"Daily token limit reached for {model_id}. "
                    f"Switching to fallback model: {FALLBACK_LLM_MODEL_ID_ENV}"
                )
                # Recursively call with fallback model (only once to avoid infinite loops)
                fallback_response = invoke_claude(
                    messages=messages,
                    system=system,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=stream,
                    model_id=FALLBACK_LLM_MODEL_ID_ENV,  # Use fallback explicitly
                )
                # Mark that we switched models
                fallback_response['model_switched'] = True
                fallback_response['primary_model'] = model_id
                fallback_response['fallback_model'] = FALLBACK_LLM_MODEL_ID_ENV
                return fallback_response
            
            # Handle throttling with fixed interval + jitter to spread out retries
            if error_code == 'ThrottlingException' and attempt < max_retries:
                # Add jitter (±10 seconds) to prevent synchronized retries and spread out load
                # This gives 20-40 second delays between retries to avoid tight loops
                jitter = random.uniform(-10.0, 10.0)
                delay = max(1.0, retry_interval + jitter)  # Ensure at least 1 second
                logger.warning(f"Bedrock throttling (attempt {attempt + 1}/{max_retries + 1}), retrying in {delay:.1f}s...")
                time.sleep(delay)
                continue
            
            # For other errors or final attempt, raise the exception
            logger.error(f"Bedrock API error: {error_code} - {e}")
            raise
        
        except Exception as e:
            # Non-ClientError exceptions should be raised immediately
            logger.error(f"Unexpected error calling Bedrock: {e}")
            raise


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

