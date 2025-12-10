# Quick Start Guide

## Essential Documents

When you open this workspace, start here:

### 1. Migration Guide
**`docs/DocProf_AWS_Migration_Guide.md`**
- Complete step-by-step migration plan
- Phase-by-phase implementation guide
- Cost estimates and optimization strategies
- **This is your primary roadmap**

### 2. Design Principles
**`docs/design-principles/`**
- **functional-architecture-summary.md** - Core FP patterns (pure logic, commands, effects)
- **interceptor-patterns.md** - Two interceptor patterns to maintain
- **interceptor101.md** - Stack-based interceptor details

**Why these matter**: These principles have proven valuable. We'll adapt them to AWS, not abandon them.

### 3. Reference Context
**`docs/reference/CONTEXT_SUMMARY.md`**
- System overview from MAExpert
- Key documents reference
- Architecture at a glance

## Key Differences: MAExpert vs DocProf AWS

| Aspect | MAExpert (Local) | DocProf AWS |
|--------|------------------|-------------|
| **Backend** | FastAPI server | Lambda + API Gateway |
| **Database** | Local PostgreSQL | Aurora Serverless |
| **LLM** | Anthropic API | AWS Bedrock (Claude) |
| **Embeddings** | OpenAI | AWS Bedrock (Titan) |
| **TTS** | OpenAI TTS | AWS Polly |
| **Sessions** | File system | DynamoDB |
| **Storage** | Local files | S3 |

## What Stays the Same

✅ **Pure logic functions** - Can be reused directly  
✅ **Command/effect separation** - Commands become Lambda invocations  
✅ **Immutable state** - Pydantic models still work  
✅ **Interceptor patterns** - Adapted for Lambda/Step Functions  

## What Changes

⚠️ **Effects layer** - Rewrite for AWS services (boto3, RDS Proxy)  
⚠️ **State storage** - DynamoDB instead of file system  
⚠️ **API structure** - API Gateway instead of FastAPI routes  

## Reference to MAExpert

Original codebase is at `../MAExpert/`:
- **Logic**: `../MAExpert/src/logic/` - Pure functions (reusable)
- **Effects**: `../MAExpert/src/effects/` - Side effects (reference for AWS adaptation)
- **Commands**: `../MAExpert/src/core/commands.py` - Command definitions
- **Architecture**: `../MAExpert/docs/architecture/` - Design patterns

## Next Steps

1. **Review migration guide**: `docs/DocProf_AWS_Migration_Guide.md`
2. **Start Phase 1**: Infrastructure Foundation (VPC, IAM)
3. **Reference MAExpert**: When implementing Lambda functions, look at `../MAExpert/src/logic/` for patterns

## Important Notes

- **MAExpert stays untouched** - It's your reference and working local version
- **Design principles preserved** - We adapt them to AWS, not abandon them
- **Functional parity** - AWS version should behave identically to MAExpert

