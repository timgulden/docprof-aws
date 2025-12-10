# Aurora Module

This module creates an Aurora Serverless v2 PostgreSQL cluster with pgvector extension support.

## Resources Created

- Aurora Serverless v2 PostgreSQL cluster (engine version 15.4+)
- DB parameter group with pgvector preloaded
- DB cluster parameter group
- DB subnet group (private subnets)
- Aurora instance (db.serverless)
- Secrets Manager secret for master password
- Random password generation

## Features

- **Serverless v2**: Auto-scales from 0.5 ACU to 2 ACU
- **pgvector**: Pre-configured for vector similarity search
- **Backups**: 7-day retention (configurable)
- **Monitoring**: Enhanced CloudWatch monitoring enabled
- **Security**: Master password stored in Secrets Manager
- **Network**: Deployed in private subnets only

## Usage

```hcl
module "aurora" {
  source = "../../modules/aurora"

  project_name      = "docprof"
  environment       = "dev"
  aws_region        = "us-east-1"
  private_subnet_ids = module.vpc.private_subnet_ids
  security_group_id  = module.vpc.aurora_security_group_id
  monitoring_role_arn = module.iam.rds_monitoring_role_arn

  min_capacity = 0.5
  max_capacity = 2.0

  tags = {
    ManagedBy = "terraform"
  }
}
```

## Cost Considerations

- **Min capacity (0.5 ACU)**: ~$43/month if always running
- **Auto-pause**: Aurora Serverless v2 can scale to zero when idle
- **Dev environment**: Consider using smaller max capacity (2 ACU)
- **Backups**: 7-day retention for dev (configurable)

## Outputs

- `cluster_id` - Cluster identifier
- `cluster_endpoint` - Writer endpoint
- `cluster_reader_endpoint` - Reader endpoint
- `master_password_secret_arn` - Secrets Manager ARN for password

## Next Steps

After deployment:
1. Enable pgvector extension: `CREATE EXTENSION IF NOT EXISTS vector;`
2. Create database schema
3. Set up RDS Proxy for Lambda connections (optional but recommended)

