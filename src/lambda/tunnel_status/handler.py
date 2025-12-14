import logging
from typing import Dict, Any

from shared.response import success_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Stub tunnel status endpoint for AWS deployment.
    Tunnel feature is not needed in AWS-native architecture.
    """
    logger.info(f"Tunnel status requested: {event}")
    
    # Return disabled status - tunnel feature not used in AWS
    # Note: success_response expects a dict, so we wrap the response data
    return success_response({
        "enabled": False,
        "backend_url": None,
        "frontend_url": None,
    })

