#!/bin/bash
# Test TOC extraction with LLM functionality via deployed Lambda
# This tests the full integration: Lambda -> command_executor -> LLM TOC parser

set -e

export AWS_PROFILE=docprof-dev

BOOK_ID="${1:-c0a6a1aa-afc0-43f3-8910-c8843634b7b1}"  # Valuation by default
BOOK_TITLE="${2:-Valuation: Measuring and Managing the Value of Companies}"
BOOK_AUTHOR="${3:-Tim Koller}"

echo "=========================================="
echo "Testing TOC Extraction via Lambda"
echo "=========================================="
echo ""
echo "Book ID: $BOOK_ID"
echo "Title: $BOOK_TITLE"
echo "Author: $BOOK_AUTHOR"
echo ""

# Find the PDF in S3
echo "Finding PDF in S3..."
BOOK_KEY=$(aws s3 ls "s3://docprof-dev-source-docs/books/$BOOK_ID/" --recursive | grep "\.pdf$" | head -1 | awk '{print $4}')

if [ -z "$BOOK_KEY" ]; then
    echo "❌ No PDF found for book_id: $BOOK_ID"
    exit 1
fi

echo "Found PDF: s3://docprof-dev-source-docs/$BOOK_KEY"
echo ""

# Prepare payload
PAYLOAD=$(cat <<EOF
{
  "source_id": "$BOOK_ID",
  "source_title": "$BOOK_TITLE",
  "author": "$BOOK_AUTHOR",
  "s3_bucket": "docprof-dev-source-docs",
  "s3_key": "$BOOK_KEY"
}
EOF
)

echo "Invoking source_summary_generator Lambda..."
echo "This will test:"
echo "  1. PyMuPDF TOC extraction"
echo "  2. LLM chapter level detection (if multiple levels found)"
echo "  3. LLM-based extraction (if PyMuPDF finds < 5 entries)"
echo ""

# Invoke Lambda
RESPONSE_FILE="/tmp/toc-extraction-response-$$.json"
aws lambda invoke \
  --function-name docprof-dev-source-summary-generator \
  --payload "$(echo "$PAYLOAD" | jq -c .)" \
  --cli-binary-format raw-in-base64-out \
  "$RESPONSE_FILE" > /dev/null 2>&1

echo "Lambda invocation complete!"
echo ""

# Check response
if [ -f "$RESPONSE_FILE" ]; then
    echo "Response:"
    cat "$RESPONSE_FILE" | jq '.' 2>/dev/null || cat "$RESPONSE_FILE"
    echo ""
    
    # Check for success
    if grep -q '"statusCode": 200' "$RESPONSE_FILE" 2>/dev/null || \
       grep -q '"status": "success"' "$RESPONSE_FILE" 2>/dev/null; then
        echo "✅ Lambda execution succeeded"
    else
        echo "⚠️  Response indicates potential error"
    fi
else
    echo "❌ No response file generated"
fi

echo ""
echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo ""
echo "1. Check CloudWatch logs for TOC extraction details:"
echo "   aws logs tail /aws/lambda/docprof-dev-source-summary-generator --follow --profile docprof-dev"
echo ""
echo "2. Look for these log messages:"
echo "   - 'PyMuPDF extracted TOC: X entries'"
echo "   - 'Multiple TOC levels detected: [1, 2, 3]. Using LLM to identify chapter level.'"
echo "   - 'LLM identified chapter level: 2'"
echo "   - 'LLM-based extraction found X chapters' (if PyMuPDF found < 5 entries)"
echo ""
echo "3. To view recent logs:"
echo "   aws logs tail /aws/lambda/docprof-dev-source-summary-generator --since 5m --profile docprof-dev"
echo ""
echo "4. To search for LLM-related logs:"
echo "   aws logs filter-log-events \\"
echo "     --log-group-name /aws/lambda/docprof-dev-source-summary-generator \\"
echo "     --filter-pattern 'LLM' \\"
echo "     --start-time \$(date -u -d '10 minutes ago' +%s)000 \\"
echo "     --profile docprof-dev | jq '.events[].message'"
echo ""

# Cleanup
rm -f "$RESPONSE_FILE"
