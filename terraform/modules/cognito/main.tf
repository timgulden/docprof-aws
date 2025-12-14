# Cognito User Pool for DocProf Authentication

resource "aws_cognito_user_pool" "this" {
  name = var.user_pool_name != null ? var.user_pool_name : "${var.project_name}-${var.environment}-users"

  # Password policy
  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_uppercase = true
    require_numbers   = true
    require_symbols   = true
  }

  # Email verification
  auto_verified_attributes = ["email"]

  # MFA configuration (optional for dev, can enable in prod)
  mfa_configuration = var.mfa_enabled ? "OPTIONAL" : "OFF"

  # Account recovery
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  # User attributes
  # Note: Email is a standard attribute, automatically included
  # Custom attributes can be added later if needed, but require User Pool recreation

  # Email configuration (use Cognito default for dev)
  email_configuration {
    email_sending_account = "COGNITO_DEFAULT"
  }

  # Lifecycle: Ignore schema changes (schema can't be modified after creation)
  lifecycle {
    ignore_changes = [schema]
  }

  # User pool tags
  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-user-pool"
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  )
}

# Cognito User Pool Client (for frontend SPA)
resource "aws_cognito_user_pool_client" "frontend" {
  name         = "${var.project_name}-${var.environment}-frontend-client"
  user_pool_id = aws_cognito_user_pool.this.id

  # No client secret for SPA (public client)
  generate_secret = false

  # Allowed OAuth flows
  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_SRP_AUTH"
  ]

  # OAuth scopes (required if OAuth flows are enabled)
  allowed_oauth_scopes = [
    "email",
    "openid",
    "profile"
  ]

  # OAuth flows (required if OAuth scopes are set)
  allowed_oauth_flows = [
    "code",
    "implicit"
  ]

  # OAuth flows user pool client
  allowed_oauth_flows_user_pool_client = true

  # Callback URLs (will be updated when CloudFront is deployed)
  callback_urls = var.callback_urls
  logout_urls   = var.logout_urls

  # Prevent user existence errors (security best practice)
  prevent_user_existence_errors = "ENABLED"

  # Token validity (in hours)
  access_token_validity  = 1   # 1 hour
  id_token_validity      = 1   # 1 hour
  refresh_token_validity = 30  # 30 days

  # Supported identity providers
  supported_identity_providers = ["COGNITO"]

  # Note: User Pool Client doesn't support tags
}

# Cognito User Pool Domain (for hosted UI)
resource "aws_cognito_user_pool_domain" "this" {
  domain       = "${var.project_name}-${var.environment}-auth"
  user_pool_id = aws_cognito_user_pool.this.id
}

