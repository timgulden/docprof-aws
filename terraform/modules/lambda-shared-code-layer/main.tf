# Lambda Layer for Shared Application Code
# This layer contains shared utility modules (db_utils, bedrock_client, etc.)

locals {
  layer_name = "${var.project_name}-${var.environment}-shared-code"
  layer_dir  = "${path.module}/.terraform/${local.layer_name}"
  zip_path   = "${path.module}/.terraform/${local.layer_name}.zip"

  # Lambda layers use python/ prefix - Lambda automatically adds this to sys.path
  python_dir = "${local.layer_dir}/python"
  shared_dir = "${local.python_dir}/shared"

  # Get all files from shared code directory (excluding some patterns)
  shared_files = fileset(var.shared_code_path, "**")
}

# Create the python/shared directory structure
resource "null_resource" "prepare_layer_structure" {
  triggers = {
    shared_code_hash = sha256(jsonencode([
      for f in local.shared_files : {
        path = f
        hash = fileexists("${var.shared_code_path}/${f}") ? filesha256("${var.shared_code_path}/${f}") : ""
      }
    ]))
  }

  # Create directory structure
  provisioner "local-exec" {
    command = <<-EOT
      mkdir -p "${local.shared_dir}"
    EOT
  }

  # Copy all shared code files to python/shared/
  provisioner "local-exec" {
    command = <<-EOT
      cp -r "${var.shared_code_path}"/* "${local.shared_dir}/"
    EOT
  }

  # Remove unwanted files (similar to package_lambda.py exclusions)
  provisioner "local-exec" {
    command = <<-EOT
      find "${local.shared_dir}" -type f -name "*.pyc" -delete
      find "${local.shared_dir}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
      find "${local.shared_dir}" -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
      find "${local.shared_dir}" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
      find "${local.shared_dir}" -type f -name "*.md" -delete
    EOT
  }
}

# Create ZIP archive of the layer
data "archive_file" "layer_zip" {
  type        = "zip"
  source_dir  = local.layer_dir
  output_path = local.zip_path

  depends_on = [null_resource.prepare_layer_structure]

  # Exclude hidden files and directories
  excludes = [
    ".terraform",
    ".git",
    ".DS_Store"
  ]
}

# Upload layer ZIP to S3 (consistent with deps layer pattern)
# Note: base64sha256 can contain '/' characters, so we use md5 for the key
resource "aws_s3_object" "layer_zip" {
  bucket  = var.s3_bucket
  key     = "lambda-layers/${local.layer_name}/${data.archive_file.layer_zip.output_md5}.zip"
  source  = data.archive_file.layer_zip.output_path
  etag    = data.archive_file.layer_zip.output_md5

  tags = merge(
    var.tags,
    {
      Name        = "${local.layer_name}-zip"
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  )
  
  depends_on = [data.archive_file.layer_zip]
}

# Lambda Layer for shared application code
resource "aws_lambda_layer_version" "shared_code" {
  layer_name          = local.layer_name
  compatible_runtimes = var.compatible_runtimes
  description         = "Shared application code for DocProf Lambda functions (db_utils, bedrock_client, etc.)"

  # Use S3 location (consistent with deps layer, allows for larger layers)
  s3_bucket = aws_s3_object.layer_zip.bucket
  s3_key    = aws_s3_object.layer_zip.key

  source_code_hash = data.archive_file.layer_zip.output_base64sha256

  depends_on = [aws_s3_object.layer_zip]
}

