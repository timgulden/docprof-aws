# Terraform backend configuration
# Currently using local backend for initial development
# TODO: Migrate to S3 backend for team collaboration

# Uncomment and configure when ready:
# terraform {
#   backend "s3" {
#     bucket         = "docprof-terraform-state-dev"
#     key            = "terraform.tfstate"
#     region         = "us-east-1"
#     encrypt        = true
#     dynamodb_table = "terraform-state-lock"
#   }
# }

# For now, state is stored locally
# Remember to add terraform.tfstate to .gitignore (already done)

