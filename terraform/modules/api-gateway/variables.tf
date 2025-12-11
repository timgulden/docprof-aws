variable "project_name" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, prod)"
  type        = string
}

variable "api_name" {
  description = "API Gateway name"
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

variable "cors_origins" {
  description = "Allowed CORS origins"
  type        = list(string)
  default     = ["*"]
}

variable "cors_methods" {
  description = "Allowed CORS methods"
  type        = list(string)
  default     = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
}

variable "cors_headers" {
  description = "Allowed CORS headers"
  type        = list(string)
  default     = ["Content-Type", "Authorization", "X-Amz-Date", "X-Api-Key", "X-Book-Title", "X-Book-Author", "X-Book-Edition", "X-Book-Isbn"]
}

variable "binary_media_types" {
  description = "Binary media types for API Gateway"
  type        = list(string)
  default     = ["application/pdf", "multipart/form-data"]
}

variable "endpoints" {
  description = "API Gateway endpoints configuration"
  type = map(object({
    method           = string
    lambda_function_name = string
    lambda_invoke_arn = string
    path             = string
    require_auth     = bool
  }))
  default = {}
}

