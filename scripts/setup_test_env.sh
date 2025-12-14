#!/bin/bash
# Helper script to set up environment variables for testing RAG pipeline
# Gets values from Terraform outputs

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TERRAFORM_DIR="$PROJECT_ROOT/terraform/environments/dev"

if [ ! -d "$TERRAFORM_DIR" ]; then
    echo "Error: Terraform directory not found: $TERRAFORM_DIR"
    exit 1
fi

cd "$TERRAFORM_DIR"

echo "Getting database connection info from Terraform outputs..."
echo ""

# Get outputs
export DB_CLUSTER_ENDPOINT=$(terraform output -raw aurora_cluster_endpoint 2>/dev/null || echo "")
export DB_NAME=$(terraform output -raw aurora_database_name 2>/dev/null || echo "")
export DB_PASSWORD_SECRET_ARN=$(terraform output -raw aurora_master_password_secret_arn 2>/dev/null || echo "")

if [ -z "$DB_CLUSTER_ENDPOINT" ]; then
    echo "⚠️  Warning: Could not get DB_CLUSTER_ENDPOINT from Terraform"
    echo "   Make sure Terraform is initialized and outputs exist"
    echo "   Run: cd terraform/environments/dev && terraform init && terraform apply"
fi

if [ -z "$DB_NAME" ]; then
    echo "⚠️  Warning: Could not get DB_NAME from Terraform"
fi

if [ -z "$DB_PASSWORD_SECRET_ARN" ]; then
    echo "⚠️  Warning: Could not get DB_PASSWORD_SECRET_ARN from Terraform"
    echo "   You may need to set DB_PASSWORD manually"
else
    echo "Getting password from Secrets Manager..."
    export DB_PASSWORD=$(aws secretsmanager get-secret-value \
        --secret-id "$DB_PASSWORD_SECRET_ARN" \
        --query SecretString --output text \
        --profile docprof-dev 2>/dev/null || echo "")
    
    if [ -z "$DB_PASSWORD" ]; then
        echo "⚠️  Warning: Could not get password from Secrets Manager"
        echo "   You may need to set DB_PASSWORD manually"
    fi
fi

# Set AWS defaults
export AWS_PROFILE=${AWS_PROFILE:-docprof-dev}
export AWS_REGION=${AWS_REGION:-us-east-1}

echo ""
echo "Environment variables set:"
echo "  DB_CLUSTER_ENDPOINT=$DB_CLUSTER_ENDPOINT"
echo "  DB_NAME=$DB_NAME"
echo "  DB_PASSWORD_SECRET_ARN=$DB_PASSWORD_SECRET_ARN"
echo "  DB_PASSWORD=${DB_PASSWORD:+***hidden***}"
echo "  AWS_PROFILE=$AWS_PROFILE"
echo "  AWS_REGION=$AWS_REGION"
echo ""
echo "You can now run:"
echo "  python3 scripts/test_rag_pipeline.py \"What does M&A stand for?\""
echo ""
echo "Or source this script to set variables in your shell:"
echo "  source scripts/setup_test_env.sh"
