# DocProf AWS Documentation

## Quick Start

1. **[Migration Guide](DocProf_AWS_Migration_Guide.md)** - Start here for the complete migration plan
2. **[Reference Docs](reference/)** - Context and overview from MAExpert
3. **[Design Principles](design-principles/)** - Core architectural patterns to maintain

## Directory Structure

```
docs/
├── DocProf_AWS_Migration_Guide.md  # Main migration guide
├── reference/                       # Reference docs from MAExpert
│   ├── CONTEXT_SUMMARY.md          # System overview
│   └── README.md
├── design-principles/              # Core design patterns
│   ├── functional-architecture-summary.md
│   ├── interceptor-patterns.md
│   ├── interceptor101.md
│   └── README.md
├── architecture/                   # AWS architecture docs (to be created)
├── contracts/                      # API contracts (to be created)
└── deployment/                     # Deployment guides (to be created)
```

## Key Principles

**Maintain functional programming patterns** from MAExpert:
- Pure logic layer
- Command/effect separation  
- Immutable state
- Interceptor patterns

**Adapt to AWS**:
- Lambda functions (instead of FastAPI)
- Aurora Serverless (instead of local PostgreSQL)
- Bedrock/Polly (instead of Anthropic/OpenAI)
- DynamoDB (for sessions)

## Reference to MAExpert

Original codebase at `../MAExpert/`:
- Source code: `../MAExpert/src/`
- Documentation: `../MAExpert/docs/`
- Design principles: `../MAExpert/docs/architecture/`

Use MAExpert as reference, but implement AWS-native solutions in this repo.

