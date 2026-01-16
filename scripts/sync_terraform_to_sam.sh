#!/bin/bash
# Helper script to get Terraform outputs and update SAM config

set -e

echo "🔍 Fetching Terraform outputs..."

cd terraform/environments/dev

# Export AWS credentials
export AWS_PROFILE=docprof-dev
export AWS_DEFAULT_REGION=us-east-1

# Get Terraform outputs
DB_ENDPOINT=$(terraform output -raw aurora_cluster_endpoint)
DB_NAME=$(terraform output -raw aurora_database_name)
DB_USERNAME=$(terraform output -raw aurora_master_username)
DB_SECRET_ARN=$(terraform output -raw aurora_master_password_secret_arn)
DYNAMODB_TABLE=$(terraform output -raw dynamodb_course_state_table_name)
PRIVATE_SUBNETS=$(terraform output -json vpc_private_subnet_ids | jq -r 'join(",")')
LAMBDA_SG=$(terraform output -raw vpc_lambda_security_group_id)
LAMBDA_ROLE=$(terraform output -raw iam_lambda_execution_role_arn)
PYTHON_LAYER=$(terraform output -raw lambda_python_deps_layer_arn)
COGNITO_POOL=$(terraform output -raw cognito_user_pool_id)

cd ../../..

echo "✅ Terraform outputs retrieved"
echo ""
echo "📝 Updating samconfig.toml..."

# Create parameter overrides
cat > samconfig.toml << EOF
version = 0.1

[default]
[default.global.parameters]
stack_name = "docprof-dev-course-pipeline"
region = "us-east-1"
confirm_changeset = true
capabilities = "CAPABILITY_IAM"

[default.build.parameters]
parallel = true
cached = true
use_container = false

[default.deploy.parameters]
capabilities = "CAPABILITY_IAM"
parameter_overrides = [
  "DBClusterEndpoint=${DB_ENDPOINT}",
  "DBName=${DB_NAME}",
  "DBUsername=${DB_USERNAME}",
  "DBPasswordSecretArn=${DB_SECRET_ARN}",
  "DynamoDBTableName=${DYNAMODB_TABLE}",
  "PrivateSubnetIds=${PRIVATE_SUBNETS}",
  "LambdaSecurityGroupId=${LAMBDA_SG}",
  "LambdaExecutionRoleArn=${LAMBDA_ROLE}",
  "PythonDepsLayerArn=${PYTHON_LAYER}",
  "CognitoUserPoolId=${COGNITO_POOL}"
]

[default.sync.parameters]
watch = true
EOF

echo "✅ samconfig.toml updated!"
echo ""
echo "You can now run:"
echo "  sam build"
echo "  sam deploy"

