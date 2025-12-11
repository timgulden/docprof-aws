variable "project_name" {
  description = "Project name (e.g., docprof)"
  type        = string
}

variable "environment" {
  description = "Environment name (e.g., dev)"
  type        = string
}

variable "requirements_path" {
  description = "Path to requirements.txt file"
  type        = string
}

variable "compatible_runtimes" {
  description = "List of compatible Python runtimes"
  type        = list(string)
  default     = ["python3.11"]
}

variable "tags" {
  description = "Tags to apply to the layer"
  type        = map(string)
  default     = {}
}

variable "s3_bucket" {
  description = "S3 bucket for storing large layer ZIP files (required for layers >50MB)"
  type        = string
}

