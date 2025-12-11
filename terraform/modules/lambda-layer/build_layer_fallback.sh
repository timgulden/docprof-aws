#!/bin/bash
# Fallback Lambda Layer build (without Docker)
# Uses aws-psycopg2 instead of psycopg2-binary
# Note: pymupdf and Pillow may still have issues without Docker build

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIREMENTS_FILE="${1:-${SCRIPT_DIR}/requirements-alternative.txt}"
OUTPUT_DIR="${2:-${SCRIPT_DIR}/.terraform/layer-build}"

if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo "{\"error\": \"Requirements file not found: $REQUIREMENTS_FILE\"}" >&2
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Lambda layer structure: python/lib/python3.11/site-packages/
SITE_PACKAGES="$OUTPUT_DIR/python/lib/python3.11/site-packages"
mkdir -p "$SITE_PACKAGES"

echo "Building Lambda layer (fallback method - Docker recommended for C extensions)..." >&2

# Install packages using pip with --target
# WARNING: This builds for current platform (macOS), not Amazon Linux 2
# C extensions (pymupdf, Pillow) may not work correctly
python3 -m pip install \
    -r "$REQUIREMENTS_FILE" \
    --target "$SITE_PACKAGES" \
    --upgrade \
    --quiet >&2 || {
    echo "{\"error\": \"pip install failed\"}" >&2
    exit 1
}

# Output JSON for Terraform external data source (must be ONLY stdout)
echo "{\"output_dir\": \"$OUTPUT_DIR\", \"site_packages\": \"$SITE_PACKAGES\"}"

