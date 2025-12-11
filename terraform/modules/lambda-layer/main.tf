# Lambda Layer for Python Dependencies
# This layer contains all Python packages needed by Lambda functions

locals {
  layer_name = "${var.project_name}-${var.environment}-python-deps"
  layer_dir  = "${path.module}/.terraform/${local.layer_name}"
  zip_path   = "${path.module}/.terraform/${local.layer_name}.zip"
}

# Build the layer ZIP using Docker (Amazon Linux 2)
# This ensures C extensions (psycopg2, pymupdf, Pillow) are compiled for Lambda runtime
# Docker is required for proper C extension compilation
data "external" "build_layer" {
  program = ["bash", "${path.module}/build_layer_docker.sh", var.requirements_path, local.layer_dir]
  
  # The build script will output JSON with output_dir and site_packages
  # If Docker is not available, the script will fail with a clear error message
}

# Create ZIP archive of the layer
data "archive_file" "layer_zip" {
  type        = "zip"
  source_dir  = local.layer_dir
  output_path = local.zip_path
  
  depends_on = [data.external.build_layer]
}

# Upload layer ZIP to S3 first (required for layers >50MB)
# Lambda layers can be up to 250MB uncompressed, but direct upload limit is ~70MB
resource "aws_s3_object" "layer_zip" {
  bucket = var.s3_bucket
  key    = "lambda-layers/${local.layer_name}/${data.archive_file.layer_zip.output_base64sha256}.zip"
  source = data.archive_file.layer_zip.output_path
  etag   = data.archive_file.layer_zip.output_md5

  tags = merge(
    var.tags,
    {
      Name        = "${local.layer_name}-zip"
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  )
}

# Lambda Layer (using S3 location for large layers)
# Note: aws_lambda_layer_version doesn't support tags directly
resource "aws_lambda_layer_version" "python_deps" {
  layer_name          = local.layer_name
  compatible_runtimes = var.compatible_runtimes
  description         = "Python dependencies for DocProf Lambda functions"

  # Use S3 location instead of filename for large layers
  s3_bucket = aws_s3_object.layer_zip.bucket
  s3_key    = aws_s3_object.layer_zip.key

  source_code_hash = data.archive_file.layer_zip.output_base64sha256

  depends_on = [aws_s3_object.layer_zip]
}

