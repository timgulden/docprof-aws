# Reference Documentation

This directory contains reference documents from the MAExpert codebase that guide the AWS migration.

## Key Documents

### Migration Guide
- **[DocProf_AWS_Migration_Guide.md](../DocProf_AWS_Migration_Guide.md)** - Complete migration plan and implementation guide

### Context & Overview
- **[CONTEXT_SUMMARY.md](CONTEXT_SUMMARY.md)** - System overview and key documents reference
  - ⚠️ **Note**: This document references MAExpert paths. Update paths when referencing AWS implementation.

### Design Principles
See `../design-principles/` for:
- Functional programming architecture patterns
- Interceptor patterns (stack-based and middleware-style)
- Command/effect separation principles

## Using These Documents

These documents are copied from MAExpert for reference. When implementing AWS version:

1. **Follow the principles** - Functional programming patterns still apply
2. **Adapt to AWS** - Some patterns may need AWS-specific adaptations
3. **Maintain parity** - Keep same business logic, adapt side effects

## Original Location

These documents originated in:
- `../MAExpert/docs/DocProf_AWS_Migration_Guide.md`
- `../MAExpert/CONTEXT_SUMMARY.md`
- `../MAExpert/docs/architecture/`

For the most up-to-date versions, check the MAExpert repository.

