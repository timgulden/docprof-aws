# Lambda Shared Code Layer Module

This module creates a Lambda layer containing shared application code (utilities, database clients, etc.).

## Purpose

Instead of bundling the `shared/` directory into every Lambda function ZIP (code duplication), this layer packages it once and all functions can use it.

## Structure

The layer packages the `src/lambda/shared/` directory into the Lambda layer structure:

```
Layer ZIP:
python/
└── shared/
    ├── __init__.py
    ├── db_utils.py
    ├── bedrock_client.py
    ├── response.py
    ├── core/
    └── logic/
```

Lambda automatically adds `python/` to `sys.path`, so imports work the same:
```python
from shared.db_utils import get_db_connection  # Works the same!
```

## Usage

```hcl
module "shared_code_layer" {
  source = "../../modules/lambda-shared-code-layer"

  project_name    = "docprof"
  environment     = "dev"
  shared_code_path = "${path.module}/../../../src/lambda/shared"
  s3_bucket       = module.s3.processed_chunks_bucket_name

  tags = {
    ManagedBy = "terraform"
  }
}

# Then attach to Lambda functions
module "my_lambda" {
  source = "../../modules/lambda"
  
  layers = [
    module.lambda_layer.layer_arn,           # Python dependencies
    module.shared_code_layer.layer_arn       # Shared application code
  ]
  
  # ... other config
}
```

## Benefits

- ✅ Smaller function ZIPs (~500KB → ~10-50KB)
- ✅ Faster deployments
- ✅ True code reuse (no duplication)
- ✅ Update shared code once, all functions benefit
- ✅ Follows AWS Lambda best practices

## Outputs

- `layer_arn` - ARN of the layer (use this in function layers list)
- `layer_version` - Version number
- `layer_name` - Name of the layer

## Notes

- Layer is stored in S3 (allows for larger layers)
- Files are automatically cleaned (removes `.pyc`, `__pycache__`, etc.)
- Layer version is immutable (new version created on changes)
- Old versions remain (can be cleaned up for cost optimization)

