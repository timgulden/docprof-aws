# DocProf Development Environment
# This file orchestrates all infrastructure modules

terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.1"
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
  project_name = var.project_name
  environment  = var.environment
  aws_region   = var.aws_region
}

# Get availability zones for the region
data "aws_availability_zones" "available" {
  state = "available"
}

# Get AWS account ID
data "aws_caller_identity" "current" {}

# VPC Module
module "vpc" {
  source = "../../modules/vpc"

  project_name       = local.project_name
  environment        = local.environment
  aws_region         = local.aws_region
  vpc_cidr           = "10.0.0.0/16"
  availability_zones = slice(data.aws_availability_zones.available.names, 0, 2)
  
  # Enable AI endpoints on-demand (default: false to save costs)
  enable_ai_endpoints = var.enable_ai_endpoints

  tags = {
    ManagedBy = "terraform"
  }
}

# IAM Module
module "iam" {
  source = "../../modules/iam"

  project_name = local.project_name
  environment  = local.environment
  aws_region   = local.aws_region
  account_id   = data.aws_caller_identity.current.account_id

  tags = {
    ManagedBy = "terraform"
  }
}

# Aurora Module
module "aurora" {
  source = "../../modules/aurora"

  project_name       = local.project_name
  environment        = local.environment
  aws_region         = local.aws_region
  private_subnet_ids = module.vpc.private_subnet_ids
  security_group_id  = module.vpc.aurora_security_group_id
  monitoring_role_arn = module.iam.rds_monitoring_role_arn

  min_capacity             = 0      # Enable auto-pause (pauses after 60 min idle)
  max_capacity             = 2.0
  seconds_until_auto_pause = 3600   # 60 minutes (1 hour) - smoother UX, still saves costs

  tags = {
    ManagedBy = "terraform"
  }
}

# S3 Module
module "s3" {
  source = "../../modules/s3"

  project_name = local.project_name
  environment  = local.environment
  aws_region   = local.aws_region

  tags = {
    ManagedBy = "terraform"
  }
}

# Outputs will be defined in outputs.tf

