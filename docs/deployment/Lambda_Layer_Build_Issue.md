# Lambda Layer Build Issue - C Extension Compatibility

**Date**: 2025-12-10  
**Status**: ⚠️ **Issue Identified - Solution Needed**

## Problem

The Lambda layer is being built on macOS, but Lambda runs on **Amazon Linux 2**. Packages with C extensions need to be compiled for the target platform.

**Error**: `Runtime.ImportModuleError: Unable to import module 'handler': No module named 'psycopg2._psycopg'`

This indicates that `psycopg2-binary` was installed but its C extension (`_psycopg`) isn't compatible with Lambda's runtime.

---

## Affected Packages

### Packages with C Extensions (Need Amazon Linux 2 Build)

1. **psycopg2-binary** ⚠️
   - **Issue**: PostgreSQL adapter with C extensions
   - **Error**: `No module named 'psycopg2._psycopg'`
   - **Solution**: Use Docker with Amazon Linux 2 image, or use `aws-psycopg2`

2. **pymupdf** ⚠️
   - **Issue**: PDF processing library with MuPDF C bindings
   - **Potential Error**: May fail at runtime if not built for Amazon Linux 2
   - **Solution**: Build in Docker with Amazon Linux 2

3. **Pillow** ⚠️
   - **Issue**: Image processing with C extensions
   - **Potential Error**: May fail at runtime if not built for Amazon Linux 2
   - **Solution**: Build in Docker with Amazon Linux 2

### Pure Python Packages (No Issues)

- **python-dateutil** ✅ - Pure Python, works anywhere
- **boto3** ✅ - Already included in Lambda runtime

---

## Root Cause

**Current Build Process:**
```python
# build_layer.py runs on macOS
pip install -r requirements.txt --target site_packages
```

**Problem**: Packages are compiled for macOS, not Amazon Linux 2.

**Lambda Runtime**: Amazon Linux 2 (based on RHEL/CentOS)
**Build Environment**: macOS (Darwin)

**Result**: Binary incompatibility - C extensions don't work.

---

## Solutions

### Option 1: Build Layer in Docker (Recommended) ✅

Use Docker with Amazon Linux 2 image to build the layer:

```dockerfile
# Dockerfile for Lambda layer
FROM public.ecr.aws/lambda/python:3.11

WORKDIR /build

# Copy requirements
COPY requirements.txt .

# Install packages into layer structure
RUN mkdir -p python/lib/python3.11/site-packages && \
    pip install -r requirements.txt -t python/lib/python3.11/site-packages

# Create ZIP
RUN zip -r layer.zip python/
```

**Pros:**
- Matches Lambda runtime exactly
- Works for all packages
- Reproducible builds

**Cons:**
- Requires Docker
- Slightly more complex build process

---

### Option 2: Use aws-psycopg2 (For psycopg2 Only)

Replace `psycopg2-binary` with `aws-psycopg2`:

```txt
# requirements.txt
aws-psycopg2>=2.9.9  # Pre-built for Lambda
pymupdf>=1.23.0
Pillow>=10.0.0
```

**Pros:**
- Simple fix for psycopg2
- No Docker needed

**Cons:**
- Only fixes psycopg2
- Still need Docker for pymupdf and Pillow

---

### Option 3: Use Public Lambda Layers

Use existing public layers:
- `arn:aws:lambda:us-east-1:898466741470:layer:psycopg2-py311:1` (psycopg2)
- Or build custom layer once and reuse

**Pros:**
- No build needed
- Fast deployment

**Cons:**
- May not have exact versions needed
- Less control

---

## Recommended Solution

**Use Docker to build the layer** - This ensures all packages work correctly.

### Implementation Steps

1. Create Dockerfile for layer build
2. Update `build_layer.py` to use Docker
3. Or create separate Docker-based build script
4. Update Terraform to use Docker build

---

## Current Status

- ✅ Issue identified
- ✅ Root cause understood
- ⏳ Solution implementation pending
- ⏳ Testing pending

---

## Impact

**Blocking**: Yes - Lambda functions cannot import psycopg2  
**Affected Functions**: 
- `document-processor` (needs psycopg2 for database)
- `book-upload` (needs psycopg2 for database)

**Workaround**: None - must fix layer build process

---

## Next Steps

1. Implement Docker-based layer build
2. Test layer with all packages
3. Update Terraform to use new build process
4. Deploy and verify Lambda functions work

