# DocProf Development Environment
# This file orchestrates all infrastructure modules

terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  # TODO: Configure S3 backend for state storage
  # backend "s3" {
  #   bucket = "docprof-terraform-state"
  #   key    = "dev/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "docprof"
      Environment = "dev"
      ManagedBy   = "terraform"
    }
  }
}

# Variables will be defined in variables.tf
# For now, using locals for initial setup
locals {
  project_name = "docprof"
  environment  = "dev"
  aws_region   = "us-east-1"
}

# TODO: Add module calls as we build them
# module "vpc" {
#   source = "../../modules/vpc"
#   ...
# }

# module "iam" {
#   source = "../../modules/iam"
#   ...
# }

# Outputs will be defined in outputs.tf

