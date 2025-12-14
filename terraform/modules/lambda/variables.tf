variable "project_name" {
  description = "Project name (e.g., docprof)"
  type        = string
}

variable "environment" {
  description = "Environment name (e.g., dev)"
  type        = string
}

variable "function_name" {
  description = "Lambda function name"
  type        = string
}

variable "handler" {
  description = "Lambda handler (e.g., handler.lambda_handler)"
  type        = string
}

variable "runtime" {
  description = "Python runtime version"
  type        = string
  default     = "python3.11"
}

variable "timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 900 # 15 minutes max
}

variable "memory_size" {
  description = "Lambda memory size in MB"
  type        = number
  default     = 512
}

variable "source_path" {
  description = "Path to Lambda source code"
  type        = string
}

variable "environment_variables" {
  description = "Environment variables for Lambda"
  type        = map(string)
  default     = {}
}

variable "vpc_config" {
  description = "VPC configuration (subnet_ids, security_group_ids)"
  type = object({
    subnet_ids         = list(string)
    security_group_ids = list(string)
  })
  default = null
}

variable "layers" {
  description = "Lambda layers ARNs"
  type        = list(string)
  default     = []
}

variable "reserved_concurrent_executions" {
  description = "Reserved concurrent executions"
  type        = number
  default     = null
}

variable "tags" {
  description = "Tags to apply to Lambda"
  type        = map(string)
  default     = {}
}

variable "role_arn" {
  description = "IAM role ARN for Lambda (if provided, uses this instead of creating new role)"
  type        = string
  default     = null
}

variable "bundle_shared_code" {
  description = "Whether to bundle shared code into the function ZIP. Set to false when using shared code layer."
  type        = bool
  default     = true # Default to true for backward compatibility
}

