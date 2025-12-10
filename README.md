# DocProf AWS Migration

This repository contains the AWS-native serverless implementation of DocProf, migrated from the local FastAPI/PostgreSQL stack.

## Project Structure

```
docprof-aws/
├── terraform/              # Infrastructure as Code
│   ├── environments/      # Environment-specific configs
│   ├── modules/          # Reusable Terraform modules
│   └── shared/           # Shared variables and configs
├── src/
│   ├── lambda/           # Lambda function code
│   └── frontend/         # React frontend (to be migrated)
├── docs/                 # Documentation
├── scripts/              # Deployment and utility scripts
├── legacy/              # Reference to MAExpert codebase
└── tests/               # Test suites
```

## Architecture

See [docs/DocProf_AWS_Migration_Guide.md](../MAExpert/docs/DocProf_AWS_Migration_Guide.md) for complete migration plan.

**Target Stack:**
- Frontend: React on S3 + CloudFront
- Backend: Lambda + API Gateway
- Database: Aurora Serverless PostgreSQL + pgvector
- LLM: AWS Bedrock (Claude)
- TTS: AWS Polly Neural
- Infrastructure: Terraform

## Getting Started

### Prerequisites
- AWS Account with billing alerts configured
- AWS CLI installed and configured
- Terraform installed
- Python 3.11+

### Development Workflow

1. **Set up environment:**
   ```bash
   cd terraform/environments/dev
   terraform init
   ```

2. **Plan infrastructure changes:**
   ```bash
   terraform plan
   ```

3. **Apply infrastructure:**
   ```bash
   terraform apply
   ```

4. **Deploy Lambda functions:**
   ```bash
   ./scripts/deploy_lambdas.sh
   ```

## Reference to MAExpert

The original MAExpert codebase is maintained separately at `../MAExpert/`. 
This repo contains AWS-native implementations that maintain functional parity.

Key differences:
- **MAExpert**: Local FastAPI + PostgreSQL + Anthropic/OpenAI APIs
- **DocProf**: AWS Lambda + Aurora + Bedrock/Polly

## Cost Management

- **Development**: ~$50-100/month (active)
- **Idle**: ~$5-15/month
- Aurora Serverless auto-pauses when not in use
- See migration guide for cost optimization strategies

## Status

🚧 **In Progress** - Following Phase 1: Infrastructure Foundation

## Documentation

- [Migration Guide](../MAExpert/docs/DocProf_AWS_Migration_Guide.md)
- [Architecture Docs](docs/architecture/)
- [API Contracts](docs/contracts/)

