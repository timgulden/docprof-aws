variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, prod)"
  type        = string
}

variable "user_pool_name" {
  description = "Custom name for the user pool (optional)"
  type        = string
  default     = null
}

variable "mfa_enabled" {
  description = "Enable MFA (optional for dev, recommended for prod)"
  type        = bool
  default     = false
}

variable "callback_urls" {
  description = "Allowed callback URLs for OAuth"
  type        = list(string)
  default     = ["http://localhost:5173", "http://localhost:3000"]  # Default Vite/React dev servers
}

variable "logout_urls" {
  description = "Allowed logout URLs"
  type        = list(string)
  default     = ["http://localhost:5173", "http://localhost:3000"]
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

