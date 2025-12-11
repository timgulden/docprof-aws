#!/bin/bash
# Upload a book PDF directly to S3 (bypasses API Gateway 10MB limit)
# EventBridge will automatically trigger the document processor Lambda
# Usage: ./upload_book.sh <pdf_path> [book_title] [book_author] [book_edition] [book_isbn]

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get S3 bucket name from Terraform output
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="$SCRIPT_DIR/../terraform/environments/dev"

if [ ! -f "$TERRAFORM_DIR/terraform.tfstate" ]; then
    echo "Error: Terraform state not found. Please deploy infrastructure first."
    exit 1
fi

# Get S3 bucket name from Terraform output
S3_BUCKET=$(cd "$TERRAFORM_DIR" && AWS_PROFILE=docprof-dev terraform output -raw source_docs_bucket_name 2>/dev/null || echo "")

if [ -z "$S3_BUCKET" ]; then
    echo "Error: Could not get S3 bucket name from Terraform outputs."
    echo "Please ensure infrastructure is deployed: cd terraform/environments/dev && terraform apply"
    exit 1
fi

# Parse arguments
PDF_PATH="$1"
BOOK_TITLE="${2:-}"
BOOK_AUTHOR="${3:-}"
BOOK_EDITION="${4:-}"
BOOK_ISBN="${5:-}"

if [ -z "$PDF_PATH" ]; then
    echo "Usage: $0 <pdf_path> [book_title] [book_author] [book_edition] [book_isbn]"
    echo ""
    echo "Example:"
    echo "  $0 ../MAExpert/source-docs/Valuation8thEd.pdf \\"
    echo "      \"Valuation: Measuring and Managing the Value of Companies\" \\"
    echo "      \"Tim Koller, Marc Goedhart, David Wessels\" \\"
    echo "      \"8th Edition\" \\"
    echo "      \"978-1119610886\""
    exit 1
fi

if [ ! -f "$PDF_PATH" ]; then
    echo "Error: PDF file not found: $PDF_PATH"
    exit 1
fi

# Generate book ID and S3 key
BOOK_ID=$(uuidgen 2>/dev/null || python3 -c "import uuid; print(uuid.uuid4())")
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
FILENAME=$(basename "$PDF_PATH")
S3_KEY="books/${BOOK_ID}/${FILENAME}"

# Extract filename if title not provided
if [ -z "$BOOK_TITLE" ]; then
    BOOK_TITLE=$(basename "$PDF_PATH" .pdf)
    echo -e "${YELLOW}Warning: No book title provided. Using filename: $BOOK_TITLE${NC}"
fi

echo -e "${BLUE}Uploading book to S3 (EventBridge will trigger processing)...${NC}"
echo "  PDF: $PDF_PATH"
echo "  Title: $BOOK_TITLE"
echo "  Author: $BOOK_AUTHOR"
echo "  Edition: $BOOK_EDITION"
echo "  ISBN: $BOOK_ISBN"
echo "  Book ID: $BOOK_ID"
echo "  S3 Bucket: $S3_BUCKET"
echo "  S3 Key: $S3_KEY"
echo ""

# Upload to S3 with metadata
# Note: Metadata values are URL-encoded, so commas/spaces are handled correctly
echo -e "${BLUE}Uploading to S3...${NC}"
aws s3 cp "$PDF_PATH" "s3://${S3_BUCKET}/${S3_KEY}" \
    --content-type "application/pdf" \
    --metadata "book-id=${BOOK_ID}" \
    --metadata "book-title=${BOOK_TITLE}" \
    --metadata "book-author=${BOOK_AUTHOR}" \
    --metadata "book-edition=${BOOK_EDITION}" \
    --metadata "book-isbn=${BOOK_ISBN}" \
    --metadata "upload-timestamp=${TIMESTAMP}" \
    --profile docprof-dev

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Upload successful!${NC}"
    echo ""
    echo -e "${BLUE}EventBridge will automatically trigger document processing.${NC}"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo "  1. Check CloudWatch logs for document processor:"
    echo "     aws logs tail /aws/lambda/docprof-dev-document-processor --follow --profile docprof-dev"
    echo ""
    echo "  2. Verify file in S3:"
    echo "     aws s3 ls s3://${S3_BUCKET}/books/${BOOK_ID}/ --profile docprof-dev"
    echo ""
    echo "  3. Check EventBridge rule:"
    echo "     aws events describe-rule --name docprof-dev-s3-document-upload --profile docprof-dev"
    echo ""
    echo -e "${YELLOW}Note: Processing may take several minutes for large PDFs.${NC}"
else
    echo -e "${YELLOW}✗ Upload failed${NC}"
    exit 1
fi

