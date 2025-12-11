# Lambda Layer Module

Builds a Lambda layer containing Python dependencies, compiled for Amazon Linux 2 (Lambda runtime).

## Requirements

**Docker Desktop** must be installed and running.

- Download: https://www.docker.com/products/docker-desktop
- Verify: `docker --version` should work

## How It Works

1. Uses Docker with Amazon Linux 2 image (matches Lambda runtime)
2. Installs all Python packages in the container
3. Compiles C extensions (psycopg2, pymupdf, Pillow) for Amazon Linux 2
4. Extracts the layer ZIP file
5. Terraform packages it as a Lambda layer

**Note**: Application logic is packaged with Lambda functions (not in the layer).
The layer contains only Python dependencies. Logic lives in `src/lambda/shared/logic/` and `src/lambda/shared/core/`.

## Usage

```hcl
module "lambda_layer" {
  source = "../../modules/lambda-layer"

  project_name     = "docprof"
  environment      = "dev"
  requirements_path = "${path.module}/../../modules/lambda-layer/requirements.txt"

  tags = {
    ManagedBy = "terraform"
  }
}
```

## Build Process

The build happens automatically when Terraform runs:

1. `build_layer_docker.sh` is executed
2. Docker builds image with Amazon Linux 2
3. Packages are installed and compiled
4. Layer ZIP is extracted
5. Terraform creates Lambda layer from ZIP

## Troubleshooting

### Docker Not Found

**Error**: `docker: command not found`

**Solution**: Install Docker Desktop and ensure it's running.

### Build Fails

**Error**: `Docker build failed`

**Solution**: 
- Check Docker is running: `docker ps`
- Check disk space (need ~2GB)
- Review Docker logs

### Import Errors in Lambda

**Error**: `No module named 'psycopg2._psycopg'`

**Solution**: This shouldn't happen with Docker build. If it does:
- Verify layer is attached to Lambda function
- Check layer version matches runtime (python3.11)
- Rebuild layer with Docker


## Files

- `Dockerfile` - Amazon Linux 2 build environment
- `build_layer_docker.sh` - Build script (called by Terraform)
- `requirements.txt` - Python dependencies
- `main.tf` - Terraform module definition

