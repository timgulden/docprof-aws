variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for Aurora"
  type        = list(string)
}

variable "security_group_id" {
  description = "Security group ID for Aurora (allows Lambda access)"
  type        = string
}

variable "monitoring_role_arn" {
  description = "IAM role ARN for RDS enhanced monitoring"
  type        = string
}

variable "database_name" {
  description = "Name of the default database"
  type        = string
  default     = "docprof"
}

variable "master_username" {
  description = "Master username for Aurora"
  type        = string
  default     = "docprof_admin"
}

variable "min_capacity" {
  description = "Minimum Aurora capacity units (ACU). Set to 0 to enable auto-pause, 0.5+ to disable auto-pause"
  type        = number
  default     = 0
  
  validation {
    condition     = var.min_capacity >= 0 && var.min_capacity <= 256
    error_message = "min_capacity must be between 0 and 256"
  }
}

variable "max_capacity" {
  description = "Maximum Aurora capacity units (ACU)"
  type        = number
  default     = 2.0
  
  validation {
    condition     = var.max_capacity >= 0.5 && var.max_capacity <= 256
    error_message = "max_capacity must be between 0.5 and 256"
  }
}

variable "seconds_until_auto_pause" {
  description = "Seconds of inactivity before auto-pause (300-86400). Only applies when min_capacity = 0"
  type        = number
  default     = 3600  # 60 minutes (1 hour) - balances cost savings with user experience
  
  validation {
    condition     = var.seconds_until_auto_pause >= 300 && var.seconds_until_auto_pause <= 86400
    error_message = "seconds_until_auto_pause must be between 300 (5 min) and 86400 (24 hours)"
  }
}

variable "backup_retention_period" {
  description = "Number of days to retain backups"
  type        = number
  default     = 7
}

variable "tags" {
  description = "Additional tags to apply to resources"
  type        = map(string)
  default     = {}
}

