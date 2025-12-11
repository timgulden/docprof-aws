#!/bin/bash
# Build Lambda Layer using Docker (Amazon Linux 2)
# This ensures C extensions are compiled for Lambda runtime
# Outputs JSON for Terraform external data source

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIREMENTS_FILE="${1:-${SCRIPT_DIR}/requirements.txt}"
OUTPUT_DIR="${2:-${SCRIPT_DIR}/.terraform/layer-build}"

if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo "{\"error\": \"Requirements file not found: $REQUIREMENTS_FILE\"}" >&2
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Copy requirements to script directory for Docker build (if different)
# Use || true to avoid failing if files are identical
if [ "$REQUIREMENTS_FILE" != "${SCRIPT_DIR}/requirements.txt" ]; then
    cp "$REQUIREMENTS_FILE" "${SCRIPT_DIR}/requirements.txt" || true
fi

# Build Docker image for x86_64 (Lambda default architecture)
# Suppress warnings and output except errors
docker build \
    --platform linux/amd64 \
    -f "${SCRIPT_DIR}/Dockerfile" \
    -t lambda-layer-builder:latest \
    "${SCRIPT_DIR}" 2>&1 | grep -v "FromPlatformFlagConstDisallowed" >&2 || {
    echo "{\"error\": \"Docker build failed\"}" >&2
    exit 1
}

# Create a temporary container to extract the layer.zip
CONTAINER_ID=$(docker create --platform linux/amd64 lambda-layer-builder:latest 2>&1 | grep -v "WARNING" | head -1) || {
    echo "{\"error\": \"Failed to create Docker container\"}" >&2
    exit 1
}

# Copy layer.zip from container
docker cp "$CONTAINER_ID:/build/layer.zip" "$OUTPUT_DIR/layer.zip" >&2 || {
    docker rm "$CONTAINER_ID" > /dev/null 2>&1
    echo "{\"error\": \"Failed to copy layer.zip from container\"}" >&2
    exit 1
}

# Extract layer.zip to output directory
cd "$OUTPUT_DIR"
unzip -q -o layer.zip -d . >&2 || {
    docker rm "$CONTAINER_ID" > /dev/null 2>&1
    echo "{\"error\": \"Failed to extract layer.zip\"}" >&2
    exit 1
}
rm -f layer.zip

# Clean up container
docker rm "$CONTAINER_ID" > /dev/null 2>&1

# Output JSON for Terraform external data source (must be ONLY stdout)
echo "{\"output_dir\": \"$OUTPUT_DIR\", \"site_packages\": \"$OUTPUT_DIR/python/lib/python3.11/site-packages\"}"
