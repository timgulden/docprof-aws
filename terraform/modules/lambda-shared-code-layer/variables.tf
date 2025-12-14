variable "project_name" {
  description = "Project name (e.g., docprof)"
  type        = string
}

variable "environment" {
  description = "Environment name (e.g., dev)"
  type        = string
}

variable "shared_code_path" {
  description = "Path to the shared code directory (e.g., ../../../src/lambda/shared)"
  type        = string
}

variable "compatible_runtimes" {
  description = "List of compatible Python runtimes"
  type        = list(string)
  default     = ["python3.11"]
}

variable "s3_bucket" {
  description = "S3 bucket for storing layer ZIP files"
  type        = string
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

