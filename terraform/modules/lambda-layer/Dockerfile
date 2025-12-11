# Dockerfile for building Lambda Layer
# Uses Amazon Linux 2 to match Lambda runtime environment
# Note: Build with --platform linux/amd64 flag for x86_64 Lambda

FROM public.ecr.aws/lambda/python:3.11

WORKDIR /build

# Install system dependencies needed for building C extensions
# Install devtoolset for newer compiler (supports C++20)
RUN yum update -y && \
    yum install -y \
    gcc \
    gcc-c++ \
    make \
    cmake \
    postgresql-devel \
    zip \
    python3-devel \
    openssl-devel \
    libjpeg-devel \
    zlib-devel \
    freetype-devel \
    lcms2-devel \
    openjpeg2-devel \
    tesseract-devel \
    leptonica-devel \
    && yum clean all

# Try to use pre-built wheels where possible to avoid compilation issues
# Set environment to prefer binary wheels
ENV PIP_ONLY_BINARY=:all:
ENV PIP_PREFER_BINARY=1

# Copy requirements file
COPY requirements.txt .

# Create Lambda layer directory structure
RUN mkdir -p python/lib/python3.11/site-packages

# Upgrade pip first
RUN pip install --upgrade pip setuptools wheel

# Install packages one at a time to identify issues
# Start with pure Python packages
RUN pip install --no-cache-dir python-dateutil -t python/lib/python3.11/site-packages/

# loguru (used by MAExpert for logging)
RUN pip install --no-cache-dir loguru -t python/lib/python3.11/site-packages/

# pydantic (used by MAExpert for data validation)
RUN pip install --no-cache-dir pydantic pydantic-settings -t python/lib/python3.11/site-packages/

# anthropic (MAExpert imports it, but we use Bedrock instead)
RUN pip install --no-cache-dir anthropic -t python/lib/python3.11/site-packages/

# tenacity (retry logic used by MAExpert)
RUN pip install --no-cache-dir tenacity -t python/lib/python3.11/site-packages/

# Install packages with C extensions
# psycopg2-binary has pre-built wheels
RUN pip install --no-cache-dir psycopg2-binary -t python/lib/python3.11/site-packages/

# Pillow has pre-built wheels
RUN pip install --no-cache-dir Pillow -t python/lib/python3.11/site-packages/

# pymupdf - try to use pre-built wheel, fall back to source if needed
# Unset PIP_ONLY_BINARY for pymupdf to allow source build if wheel unavailable
ENV PIP_ONLY_BINARY=
RUN pip install --no-cache-dir --prefer-binary pymupdf -t python/lib/python3.11/site-packages/ || \
    (echo "Warning: pymupdf wheel not available, trying source build..." && \
     pip install --no-cache-dir pymupdf -t python/lib/python3.11/site-packages/)

# Verify critical packages are installed (fail build if critical packages don't work)
# Add site-packages to Python path for verification
RUN PYTHONPATH=python/lib/python3.11/site-packages python -c "import psycopg2; print('✓ psycopg2 OK')" || (echo "ERROR: psycopg2 import failed" && exit 1)
RUN PYTHONPATH=python/lib/python3.11/site-packages python -c "import fitz; print('✓ pymupdf OK')" || (echo "ERROR: pymupdf import failed" && exit 1)
RUN PYTHONPATH=python/lib/python3.11/site-packages python -c "from PIL import Image; print('✓ Pillow OK')" || (echo "ERROR: Pillow import failed" && exit 1)

# Create ZIP archive
RUN zip -r layer.zip python/

# The layer.zip will be in /build/layer.zip

