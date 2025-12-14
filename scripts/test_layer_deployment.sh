#!/bin/bash
# Test script to verify Lambda layer deployment
# Run after deploying Terraform changes

set -e

FUNCTION_NAME="docprof-dev-connection-test"
LAYER_NAME="docprof-dev-shared-code"

echo "🧪 Testing Lambda Layer Deployment"
echo "=================================="

# Check if AWS CLI is available
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install it first."
    exit 1
fi

# Check if layer exists
echo ""
echo "📦 Checking Lambda layer..."
LAYER_EXISTS=$(aws lambda list-layers --query "Layers[?LayerName=='${LAYER_NAME}'].LayerName" --output text 2>/dev/null || echo "")

if [ -z "$LAYER_EXISTS" ]; then
    echo "❌ Layer '${LAYER_NAME}' not found"
    echo "   Run 'terraform apply' to create the layer"
    exit 1
else
    echo "✅ Layer '${LAYER_NAME}' exists"
fi

# Get layer version
LAYER_VERSION=$(aws lambda list-layer-versions --layer-name "${LAYER_NAME}" --query "LayerVersions[0].Version" --output text 2>/dev/null)
echo "   Version: ${LAYER_VERSION}"

# Get layer details
LAYER_INFO=$(aws lambda get-layer-version --layer-name "${LAYER_NAME}" --version-number "${LAYER_VERSION}" 2>/dev/null)
LAYER_SIZE=$(echo "$LAYER_INFO" | jq -r '.Content.CodeSize // 0')
echo "   Size: $((LAYER_SIZE / 1024 / 1024))MB"

# Check if function exists and uses the layer
echo ""
echo "🔧 Checking Lambda function..."
FUNCTION_EXISTS=$(aws lambda get-function --function-name "${FUNCTION_NAME}" 2>/dev/null || echo "")

if [ -z "$FUNCTION_EXISTS" ]; then
    echo "❌ Function '${FUNCTION_NAME}' not found"
    exit 1
else
    echo "✅ Function '${FUNCTION_NAME}' exists"
    
    # Check if function uses the layer
    FUNCTION_LAYERS=$(aws lambda get-function --function-name "${FUNCTION_NAME}" --query "Configuration.Layers[*].Arn" --output text 2>/dev/null)
    if echo "$FUNCTION_LAYERS" | grep -q "${LAYER_NAME}"; then
        echo "✅ Function uses shared code layer"
    else
        echo "⚠️  Function does not appear to use shared code layer"
        echo "   Layers: ${FUNCTION_LAYERS}"
    fi
fi

# Test function invocation
echo ""
echo "🚀 Testing function invocation..."
PAYLOAD='{"test": "all"}'
RESPONSE=$(aws lambda invoke \
    --function-name "${FUNCTION_NAME}" \
    --payload "$(echo -n "$PAYLOAD" | base64)" \
    --cli-binary-format raw-in-base64-out \
    /tmp/lambda-response.json 2>&1)

if [ $? -eq 0 ]; then
    echo "✅ Function invoked successfully"
    
    # Check response for import errors
    RESPONSE_BODY=$(cat /tmp/lambda-response.json)
    if echo "$RESPONSE_BODY" | grep -qi "ImportError\|ModuleNotFoundError"; then
        echo "❌ Import error detected in response:"
        echo "$RESPONSE_BODY" | jq -r '.errorMessage // .' 2>/dev/null || echo "$RESPONSE_BODY"
        exit 1
    else
        echo "✅ No import errors in response"
        echo "   Response preview:"
        echo "$RESPONSE_BODY" | jq -r '.body // .statusCode // .' 2>/dev/null | head -5 || echo "   (Check /tmp/lambda-response.json for full response)"
    fi
else
    echo "❌ Function invocation failed:"
    echo "$RESPONSE"
    exit 1
fi

# Check CloudWatch logs for errors
echo ""
echo "📊 Checking CloudWatch logs (last 5 minutes)..."
LOG_GROUP="/aws/lambda/${FUNCTION_NAME}"
END_TIME=$(date +%s)000
START_TIME=$((END_TIME - 300000))  # 5 minutes ago

ERRORS=$(aws logs filter-log-events \
    --log-group-name "${LOG_GROUP}" \
    --start-time "${START_TIME}" \
    --end-time "${END_TIME}" \
    --filter-pattern "ImportError ModuleNotFoundError" \
    --query "events[*].message" \
    --output text 2>/dev/null || echo "")

if [ -n "$ERRORS" ]; then
    echo "⚠️  Found potential import errors in logs:"
    echo "$ERRORS"
else
    echo "✅ No import errors in recent logs"
fi

echo ""
echo "✅ Layer deployment test complete!"

