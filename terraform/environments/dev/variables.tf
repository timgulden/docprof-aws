variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name prefix for resources"
  type        = string
  default     = "docprof"
}

variable "environment" {
  description = "Environment name (dev, prod)"
  type        = string
  default     = "dev"
}

variable "enable_ai_endpoints" {
  description = "Enable VPC endpoints for AI services (Bedrock, Polly). Costs ~$0.04/hour when enabled. Default: false"
  type        = bool
  default     = false
}

variable "alarm_email" {
  description = "Email address for CloudWatch alarm notifications (optional). If not set, alarms will be created but no notifications will be sent."
  type        = string
  default     = null
}

# Add more variables as needed

