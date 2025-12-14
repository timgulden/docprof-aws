import json
import logging
from typing import Dict, Any

from shared.response import success_response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Metrics endpoint for tracking chat metrics.
    Currently just logs the metrics - can be extended to store in CloudWatch or DynamoDB.
    """
    try:
        # Parse request body
        body = event.get('body', '{}')
        if isinstance(body, str):
            body = json.loads(body)
        
        metric = body.get('metric', 'unknown')
        data = body.get('data', {})
        timestamp = body.get('timestamp')
        
        logger.info(f"Metric received: {metric}", extra={
            'metric': metric,
            'data': data,
            'timestamp': timestamp
        })
        
        # Return success - metrics are logged to CloudWatch
        # In the future, could store in DynamoDB or send to CloudWatch Metrics
        return success_response({
            "status": "received",
            "metric": metric
        })
        
    except Exception as e:
        logger.exception("Error processing metric")
        # Still return success to avoid breaking the frontend
        return success_response({
            "status": "error",
            "message": str(e)
        })
