# Docker Build Requirements for Lambda Layer

**Date**: 2025-12-10  
**Status**: ⚠️ **Docker Required**

## Issue

The Lambda layer build requires Docker to compile C extensions for Amazon Linux 2.

**Current Status**: Docker not available in current shell environment.

## Requirements

To build the Lambda layer, you need:

1. **Docker Desktop** installed and running
2. Docker accessible from command line
3. Sufficient disk space (~2GB for build)

## Verification

Check if Docker is available:

```bash
docker --version
# Should output: Docker version 24.x.x or similar
```

If Docker is not available, you have two options:

### Option 1: Install Docker Desktop

1. Download Docker Desktop for macOS: https://www.docker.com/products/docker-desktop
2. Install and start Docker Desktop
3. Verify: `docker --version`

### Option 2: Use Alternative Build Method

If Docker is not available, we can:
1. Use `aws-psycopg2` instead of `psycopg2-binary` (pre-built for Lambda)
2. Build layer manually on EC2 instance running Amazon Linux 2
3. Use public Lambda layers (if available)

## Testing the Build

Once Docker is available:

```bash
cd terraform/modules/lambda-layer
./build_layer_docker.sh requirements.txt /tmp/test-layer
```

This will:
1. Build Docker image with Amazon Linux 2
2. Install all packages in the image
3. Extract layer.zip
4. Output JSON for Terraform

## Next Steps

1. Install Docker Desktop (if not already installed)
2. Start Docker Desktop
3. Test build script
4. Apply Terraform changes

