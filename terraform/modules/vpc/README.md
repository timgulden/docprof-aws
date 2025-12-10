# VPC Module

This module creates a VPC with public and private subnets, networking components, and security groups for the DocProf AWS infrastructure.

## Resources Created

- VPC (10.0.0.0/16 by default)
- 2 Public subnets (10.0.1.0/24, 10.0.2.0/24) in different AZs
- 2 Private subnets (10.0.10.0/24, 10.0.11.0/24) in different AZs
- Internet Gateway
- NAT Gateway (in first public subnet)
- Route tables for public and private subnets
- Security groups:
  - Lambda security group (outbound to all)
  - Aurora security group (inbound from Lambda on port 5432)
  - ALB security group (inbound HTTPS from internet)
- VPC Endpoints:
  - S3 Gateway endpoint (free)
  - Bedrock Interface endpoint (for private access)

## Usage

```hcl
module "vpc" {
  source = "../../modules/vpc"

  project_name     = "docprof"
  environment      = "dev"
  vpc_cidr         = "10.0.0.0/16"
  availability_zones = ["us-east-1a", "us-east-1b"]

  tags = {
    ManagedBy = "terraform"
  }
}
```

## Outputs

- `vpc_id` - VPC ID
- `public_subnet_ids` - List of public subnet IDs
- `private_subnet_ids` - List of private subnet IDs
- `lambda_security_group_id` - Lambda security group ID
- `aurora_security_group_id` - Aurora security group ID
- `alb_security_group_id` - ALB security group ID

