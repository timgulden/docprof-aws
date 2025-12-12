#!/bin/bash
# Test source summary generation

set -e

# Get book details from S3
BOOK_PATH=$(aws s3 ls s3://docprof-dev-source-docs/books/ --recursive | head -1 | awk '{print $4}')
BOOK_ID=$(echo "$BOOK_PATH" | cut -d'/' -f2)
BOOK_KEY="$BOOK_PATH"

echo "Testing source summary generation for book: $BOOK_ID"
echo "S3 Key: $BOOK_KEY"

# Invoke source summary generator Lambda
aws lambda invoke \
  --function-name docprof-dev-source-summary-generator \
  --payload "{\"source_id\": \"$BOOK_ID\", \"source_title\": \"Valuation: Measuring and Managing the Value of Companies\", \"author\": \"Tim Koller\", \"s3_bucket\": \"docprof-dev-source-docs\", \"s3_key\": \"$BOOK_KEY\"}" \
  --cli-binary-format raw-in-base64-out \
  /tmp/source-summary-response.json

echo ""
echo "Response:"
cat /tmp/source-summary-response.json | python3 -m json.tool
