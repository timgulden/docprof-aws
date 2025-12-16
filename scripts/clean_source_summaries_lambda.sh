#!/bin/bash
# Clean source_summaries using Lambda function
# This avoids VPC connection issues

set -e

export AWS_PROFILE=docprof-dev

BOOK_ID="${1:-c0a6a1aa-afc0-43f3-8910-c8843634b7b1}"

echo "=========================================="
echo "Cleaning Source Summaries via Lambda"
echo "=========================================="
echo ""
echo "Book ID: $BOOK_ID"
echo ""

# Check if db_cleanup Lambda exists
if aws lambda get-function --function-name docprof-dev-db-cleanup --profile docprof-dev > /dev/null 2>&1; then
    echo "Using db_cleanup Lambda..."
    
    PAYLOAD=$(cat <<EOF
{
  "action": "clean_source_summaries",
  "book_id": "$BOOK_ID"
}
EOF
)
    
    aws lambda invoke \
      --function-name docprof-dev-db-cleanup \
      --payload "$(echo "$PAYLOAD" | jq -c .)" \
      --cli-binary-format raw-in-base64-out \
      /tmp/cleanup-response.json \
      --profile docprof-dev > /dev/null 2>&1
    
    if [ -f /tmp/cleanup-response.json ]; then
        echo "Response:"
        cat /tmp/cleanup-response.json | jq '.' 2>/dev/null || cat /tmp/cleanup-response.json
        rm -f /tmp/cleanup-response.json
    fi
else
    echo "❌ db_cleanup Lambda not found"
    echo ""
    echo "Alternative: Use SQL directly if you have database access:"
    echo ""
    echo "DELETE FROM source_summaries WHERE source_id = '$BOOK_ID';"
    echo "DELETE FROM source_summary_embeddings WHERE source_id = '$BOOK_ID';"
    echo ""
    echo "Or create a simple Lambda function to do this cleanup."
fi
