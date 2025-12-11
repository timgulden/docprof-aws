"""
AI Services Manager Lambda Handler
Manages VPC endpoints for Bedrock and Polly (enable/disable on-demand)
"""

import json
import os
import boto3
import logging
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ec2_client = boto3.client('ec2')

# Environment variables (set by Terraform)
VPC_ID = os.getenv('VPC_ID')
PROJECT_NAME = os.getenv('PROJECT_NAME', 'docprof')
ENVIRONMENT = os.getenv('ENVIRONMENT', 'dev')
# AWS_REGION is automatically set by Lambda runtime
import boto3
_region_session = boto3.Session()
AWS_REGION = _region_session.region_name or 'us-east-1'


class ServiceStatus(str, Enum):
    """Service status enumeration"""
    ONLINE = "online"
    OFFLINE = "offline"
    WORKING = "working"  # Transitioning state


def get_bedrock_endpoint_id() -> Optional[str]:
    """Get Bedrock VPC endpoint ID if it exists"""
    try:
        response = ec2_client.describe_vpc_endpoints(
            Filters=[
                {'Name': 'vpc-id', 'Values': [VPC_ID]},
                {'Name': 'service-name', 'Values': [f'com.amazonaws.{AWS_REGION}.bedrock-runtime']},
                {'Name': 'tag:OnDemand', 'Values': ['true']},
            ]
        )
        
        if response['VpcEndpoints']:
            endpoint = response['VpcEndpoints'][0]
            state = endpoint['State']
            
            # Check if endpoint is in a transitional state
            if state in ['pending', 'pending-acceptance', 'modifying']:
                return endpoint['VpcEndpointId'], ServiceStatus.WORKING
            
            if state == 'available':
                return endpoint['VpcEndpointId'], ServiceStatus.ONLINE
        
        return None, ServiceStatus.OFFLINE
    except Exception as e:
        logger.error(f"Error checking Bedrock endpoint: {e}", exc_info=True)
        return None, ServiceStatus.OFFLINE


def get_polly_endpoint_id() -> Optional[str]:
    """Get Polly VPC endpoint ID if it exists"""
    try:
        response = ec2_client.describe_vpc_endpoints(
            Filters=[
                {'Name': 'vpc-id', 'Values': [VPC_ID]},
                {'Name': 'service-name', 'Values': [f'com.amazonaws.{AWS_REGION}.polly']},
                {'Name': 'tag:OnDemand', 'Values': ['true']},
            ]
        )
        
        if response['VpcEndpoints']:
            endpoint = response['VpcEndpoints'][0]
            state = endpoint['State']
            
            # Check if endpoint is in a transitional state
            if state in ['pending', 'pending-acceptance', 'modifying']:
                return endpoint['VpcEndpointId'], ServiceStatus.WORKING
            
            if state == 'available':
                return endpoint['VpcEndpointId'], ServiceStatus.ONLINE
        
        return None, ServiceStatus.OFFLINE
    except Exception as e:
        logger.error(f"Error checking Polly endpoint: {e}", exc_info=True)
        return None, ServiceStatus.OFFLINE


def get_security_group_id() -> str:
    """Get VPC endpoints security group ID"""
    try:
        response = ec2_client.describe_security_groups(
            Filters=[
                {'Name': 'vpc-id', 'Values': [VPC_ID]},
                {'Name': 'group-name', 'Values': [f'{PROJECT_NAME}-{ENVIRONMENT}-vpc-endpoints-sg']},
            ]
        )
        
        if response['SecurityGroups']:
            return response['SecurityGroups'][0]['GroupId']
        
        raise Exception(f"Security group not found: {PROJECT_NAME}-{ENVIRONMENT}-vpc-endpoints-sg")
    except Exception as e:
        logger.error(f"Error getting security group: {e}", exc_info=True)
        raise


def get_private_subnet_ids() -> list[str]:
    """Get private subnet IDs"""
    try:
        response = ec2_client.describe_subnets(
            Filters=[
                {'Name': 'vpc-id', 'Values': [VPC_ID]},
                {'Name': 'tag:Type', 'Values': ['private']},
            ]
        )
        
        return [subnet['SubnetId'] for subnet in response['Subnets']]
    except Exception as e:
        logger.error(f"Error getting private subnets: {e}", exc_info=True)
        raise


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle AI services management requests.
    
    Routes:
    - GET /ai-services/status -> Check current status
    - POST /ai-services/enable -> Enable AI services (create VPC endpoints)
    - POST /ai-services/disable -> Disable AI services (delete VPC endpoints)
    """
    
    if not VPC_ID:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({
                'error': 'VPC_ID not configured',
                'enabled': False,
                'status': 'error'
            })
        }
    
    try:
        # Parse request
        http_method = event.get('httpMethod', event.get('requestContext', {}).get('http', {}).get('method', 'GET'))
        path = event.get('path', event.get('requestContext', {}).get('path', ''))
        
        # Route handling
        if http_method == 'GET' and '/status' in path:
            return handle_status()
        elif http_method == 'POST' and '/enable' in path:
            return handle_enable()
        elif http_method == 'POST' and '/disable' in path:
            return handle_disable()
        else:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps({'error': 'Not found'})
            }
    
    except Exception as e:
        logger.error(f"Error handling request: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({
                'error': str(e),
                'enabled': False,
                'status': 'error'
            })
        }


def handle_status() -> Dict[str, Any]:
    """Check current status of AI services"""
    bedrock_id, bedrock_status = get_bedrock_endpoint_id()
    polly_id, polly_status = get_polly_endpoint_id()
    
    # Overall status: if either is working, overall is working
    # If both are online, overall is online
    # Otherwise offline
    if bedrock_status == ServiceStatus.WORKING or polly_status == ServiceStatus.WORKING:
        overall_status = ServiceStatus.WORKING
        enabled = True  # In progress
    elif bedrock_status == ServiceStatus.ONLINE and polly_status == ServiceStatus.ONLINE:
        overall_status = ServiceStatus.ONLINE
        enabled = True
    else:
        overall_status = ServiceStatus.OFFLINE
        enabled = False
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps({
            'enabled': enabled,
            'status': overall_status.value,
            'bedrock': {
                'endpoint_id': bedrock_id,
                'status': bedrock_status.value,
            },
            'polly': {
                'endpoint_id': polly_id,
                'status': polly_status.value,
            },
            'message': _get_status_message(overall_status)
        })
    }


def handle_enable() -> Dict[str, Any]:
    """Enable AI services by creating VPC endpoints"""
    try:
        # Check if already enabled
        bedrock_id, bedrock_status = get_bedrock_endpoint_id()
        polly_id, polly_status = get_polly_endpoint_id()
        
        if bedrock_status == ServiceStatus.ONLINE and polly_status == ServiceStatus.ONLINE:
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps({
                    'enabled': True,
                    'status': 'online',
                    'message': 'AI services are already enabled'
                })
            }
        
        # Get required resources
        security_group_id = get_security_group_id()
        subnet_ids = get_private_subnet_ids()
        
        # Create Bedrock endpoint if needed
        if not bedrock_id or bedrock_status == ServiceStatus.OFFLINE:
            logger.info("Creating Bedrock VPC endpoint...")
            bedrock_response = ec2_client.create_vpc_endpoint(
                VpcId=VPC_ID,
                ServiceName=f'com.amazonaws.{AWS_REGION}.bedrock-runtime',
                VpcEndpointType='Interface',
                SubnetIds=subnet_ids,
                SecurityGroupIds=[security_group_id],
                PrivateDnsEnabled=True,
                TagSpecifications=[
                    {
                        'ResourceType': 'vpc-endpoint',
                        'Tags': [
                            {'Key': 'Name', 'Value': f'{PROJECT_NAME}-{ENVIRONMENT}-bedrock-runtime-endpoint'},
                            {'Key': 'Service', 'Value': 'bedrock-runtime'},
                            {'Key': 'OnDemand', 'Value': 'true'},
                            {'Key': 'Project', 'Value': PROJECT_NAME},
                            {'Key': 'Environment', 'Value': ENVIRONMENT},
                            {'Key': 'ManagedBy', 'Value': 'lambda'},
                        ]
                    }
                ]
            )
            bedrock_id = bedrock_response['VpcEndpoint']['VpcEndpointId']
            logger.info(f"Created Bedrock endpoint: {bedrock_id}")
        
        # Create Polly endpoint if needed
        if not polly_id or polly_status == ServiceStatus.OFFLINE:
            logger.info("Creating Polly VPC endpoint...")
            polly_response = ec2_client.create_vpc_endpoint(
                VpcId=VPC_ID,
                ServiceName=f'com.amazonaws.{AWS_REGION}.polly',
                VpcEndpointType='Interface',
                SubnetIds=subnet_ids,
                SecurityGroupIds=[security_group_id],
                PrivateDnsEnabled=True,
                TagSpecifications=[
                    {
                        'ResourceType': 'vpc-endpoint',
                        'Tags': [
                            {'Key': 'Name', 'Value': f'{PROJECT_NAME}-{ENVIRONMENT}-polly-endpoint'},
                            {'Key': 'Service', 'Value': 'polly'},
                            {'Key': 'OnDemand', 'Value': 'true'},
                            {'Key': 'Project', 'Value': PROJECT_NAME},
                            {'Key': 'Environment', 'Value': ENVIRONMENT},
                            {'Key': 'ManagedBy', 'Value': 'lambda'},
                        ]
                    }
                ]
            )
            polly_id = polly_response['VpcEndpoint']['VpcEndpointId']
            logger.info(f"Created Polly endpoint: {polly_id}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({
                'enabled': True,
                'status': 'working',
                'bedrock': {'endpoint_id': bedrock_id, 'status': 'working'},
                'polly': {'endpoint_id': polly_id, 'status': 'working'},
                'message': 'AI services are being enabled. This may take 3-5 minutes.'
            })
        }
    
    except Exception as e:
        logger.error(f"Error enabling AI services: {e}", exc_info=True)
        raise


def handle_disable() -> Dict[str, Any]:
    """Disable AI services by deleting VPC endpoints"""
    try:
        # Get endpoint IDs
        bedrock_id, _ = get_bedrock_endpoint_id()
        polly_id, _ = get_polly_endpoint_id()
        
        deleted_endpoints = []
        
        # Delete Bedrock endpoint if it exists
        if bedrock_id:
            try:
                logger.info(f"Deleting Bedrock endpoint: {bedrock_id}")
                ec2_client.delete_vpc_endpoints(VpcEndpointIds=[bedrock_id])
                deleted_endpoints.append('bedrock')
            except Exception as e:
                logger.error(f"Error deleting Bedrock endpoint: {e}", exc_info=True)
        
        # Delete Polly endpoint if it exists
        if polly_id:
            try:
                logger.info(f"Deleting Polly endpoint: {polly_id}")
                ec2_client.delete_vpc_endpoints(VpcEndpointIds=[polly_id])
                deleted_endpoints.append('polly')
            except Exception as e:
                logger.error(f"Error deleting Polly endpoint: {e}", exc_info=True)
        
        if not deleted_endpoints:
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps({
                    'enabled': False,
                    'status': 'offline',
                    'message': 'AI services are already disabled'
                })
            }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({
                'enabled': False,
                'status': 'offline',
                'deleted': deleted_endpoints,
                'message': 'AI services are being disabled. This may take a few minutes.'
            })
        }
    
    except Exception as e:
        logger.error(f"Error disabling AI services: {e}", exc_info=True)
        raise


def _get_status_message(status: ServiceStatus) -> str:
    """Get user-friendly status message"""
    messages = {
        ServiceStatus.ONLINE: 'AI services are online and ready to use',
        ServiceStatus.OFFLINE: 'AI services are offline. Enable to use AI features.',
        ServiceStatus.WORKING: 'AI services are being configured. Please wait...',
    }
    return messages.get(status, 'Unknown status')

