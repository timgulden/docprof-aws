# Design Principles

This directory contains the core design principles that guide DocProf development. These principles have proven valuable in previous projects and should be maintained in the AWS implementation.

## Core Principles

### Functional Programming Architecture
- **[functional-architecture-summary.md](functional-architecture-summary.md)** - Pure logic layer, command/effect separation, immutable state
  - **Key**: Logic returns `(new_state, commands)`, effects execute commands
  - **Still applies**: Lambda handlers should be thin, delegate to pure logic functions

### Interceptor Patterns
- **[interceptor-patterns.md](interceptor-patterns.md)** - Two interceptor patterns used in the system
  - **Stack-based**: For ingestion pipelines (enter/leave/error)
  - **Middleware-style**: For command execution (call_next pattern)
  - **AWS adaptation**: Lambda middleware can use similar patterns

- **[interceptor101.md](interceptor101.md)** - Detailed explanation of stack-based interceptors
  - Useful for Step Functions workflows
  - Can be adapted for Lambda function composition

## AWS Adaptations

### What Stays the Same
- ✅ Pure logic functions (can be reused directly)
- ✅ Command/effect separation (commands become Lambda invocations)
- ✅ Immutable state (Pydantic models still work)
- ✅ Interceptor patterns (Lambda middleware, Step Functions)

### What Needs Adaptation
- ⚠️ **Effects layer**: Convert to Lambda-compatible implementations
  - Database connections via RDS Proxy
  - API calls via boto3 (Bedrock, Polly)
  - File operations via S3 SDK
- ⚠️ **State management**: Serverless-friendly storage
  - Sessions in DynamoDB (not file system)
  - State snapshots in S3 or DynamoDB
- ⚠️ **Interceptors**: Lambda middleware instead of decorators
  - Use Lambda layers for shared code
  - Use Step Functions for complex workflows

## Implementation Strategy

1. **Preserve Logic**: Copy pure functions from `../MAExpert/src/logic/` directly
2. **Adapt Effects**: Rewrite `../MAExpert/src/effects/` for AWS services
3. **Maintain Patterns**: Keep interceptor patterns, adapt to AWS primitives
4. **Test Parity**: Ensure AWS version behaves identically to MAExpert

## Why These Principles Matter

These functional programming principles provide:
- **Testability**: Pure functions are easy to test
- **Maintainability**: Clear separation of concerns
- **Scalability**: Stateless functions scale naturally
- **Reliability**: Immutable state prevents bugs

**Don't abandon these principles** - adapt them to AWS serverless architecture.

