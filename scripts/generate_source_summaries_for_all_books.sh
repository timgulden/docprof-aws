#!/bin/bash
# Generate source summaries for all existing books that don't have them
# This is a one-time backfill script for books uploaded before EventBridge rules were set up

set -e

export AWS_PROFILE=docprof-dev

echo "=========================================="
echo "Generating Source Summaries for All Books"
echo "=========================================="
echo ""

# Get all books from S3
echo "Finding books in S3..."
BOOK_PATHS=$(aws s3 ls s3://docprof-dev-source-docs/books/ --recursive | grep "\.pdf$" | awk '{print $4}')

if [ -z "$BOOK_PATHS" ]; then
    echo "❌ No PDF files found in s3://docprof-dev-source-docs/books/"
    exit 1
fi

BOOK_COUNT=$(echo "$BOOK_PATHS" | wc -l | tr -d ' ')
echo "Found $BOOK_COUNT book(s)"
echo ""

# Process each book
SUCCESS_COUNT=0
FAIL_COUNT=0

for BOOK_PATH in $BOOK_PATHS; do
    BOOK_ID=$(echo "$BOOK_PATH" | cut -d'/' -f2)
    
    echo "Processing book ID: $BOOK_ID"
    echo "  S3 Key: $BOOK_PATH"
    
    # Try to get metadata from S3 object
    S3_METADATA=$(aws s3api head-object --bucket docprof-dev-source-docs --key "$BOOK_PATH" --query 'Metadata' --output json 2>/dev/null || echo "{}")
    BOOK_TITLE=$(echo "$S3_METADATA" | jq -r '.["book-title"] // .["x-amz-meta-book-title"] // empty' 2>/dev/null || echo "")
    BOOK_AUTHOR=$(echo "$S3_METADATA" | jq -r '.["book-author"] // .["x-amz-meta-book-author"] // empty' 2>/dev/null || echo "")
    
    # Fallback: extract from filename
    if [ -z "$BOOK_TITLE" ]; then
        BOOK_TITLE=$(echo "$BOOK_PATH" | cut -d'/' -f3 | sed 's/\.pdf$//' | sed 's/_/ /g')
    fi
    
    # Final fallback
    if [ -z "$BOOK_TITLE" ] || [ "$BOOK_TITLE" == "$BOOK_ID" ]; then
        BOOK_TITLE="Book $BOOK_ID"
    fi
    
    if [ -z "$BOOK_AUTHOR" ]; then
        BOOK_AUTHOR="Unknown"
    fi
    
    echo "  Title: $BOOK_TITLE"
    echo "  Author: $BOOK_AUTHOR"
    
    # Invoke source summary generator
    PAYLOAD=$(cat <<EOF
{
  "source_id": "$BOOK_ID",
  "source_title": "$BOOK_TITLE",
  "author": "Unknown",
  "s3_bucket": "docprof-dev-source-docs",
  "s3_key": "$BOOK_PATH"
}
EOF
)
    
    echo "  Invoking source_summary_generator..."
    if aws lambda invoke \
      --function-name docprof-dev-source-summary-generator \
      --payload "$(echo "$PAYLOAD" | jq -c .)" \
      --cli-binary-format raw-in-base64-out \
      /tmp/source-summary-response.json > /dev/null 2>&1; then
        
        # Check response
        if grep -q '"statusCode": 200' /tmp/source-summary-response.json 2>/dev/null || \
           grep -q '"status": "success"' /tmp/source-summary-response.json 2>/dev/null; then
            echo "  ✅ Success"
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        else
            echo "  ⚠️  Response indicates error:"
            cat /tmp/source-summary-response.json | jq '.' 2>/dev/null | head -5 || cat /tmp/source-summary-response.json | head -5
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
    else
        echo "  ❌ Lambda invocation failed"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
    
    echo ""
done

echo "=========================================="
echo "Summary:"
echo "  ✅ Success: $SUCCESS_COUNT"
echo "  ❌ Failed: $FAIL_COUNT"
echo "=========================================="
echo ""
echo "Note: Summary generation is asynchronous."
echo "Embeddings will be generated automatically via EventBridge."
echo "Check CloudWatch logs for progress:"
echo "  - /aws/lambda/docprof-dev-source-summary-generator"
echo "  - /aws/lambda/docprof-dev-source-summary-embedding-generator"
