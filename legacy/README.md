# Legacy MAExpert Reference

This directory contains references to the original MAExpert codebase for comparison and migration reference.

## Location

The MAExpert codebase is maintained separately at:
```
../MAExpert/
```

## Purpose

- **Reference**: Compare AWS implementation with original FastAPI implementation
- **Migration Guide**: Extract patterns and logic to reimplement in AWS-native way
- **Testing**: Use original codebase to validate functional parity

## Key Files to Reference

### Architecture & Design
- `../MAExpert/docs/architecture/functional-architecture-summary.md` - Core FP principles
- `../MAExpert/docs/architecture/interceptor-patterns.md` - Interceptor patterns
- `../MAExpert/CONTEXT_SUMMARY.md` - System overview

### Implementation Guides
- `../MAExpert/docs/implementation/fastapi-backend-guide.md` - Original API structure
- `../MAExpert/docs/implementation/course-system-implementation-guide.md` - Course logic
- `../MAExpert/docs/implementation/database-schema-and-setup.md` - Database schema

### Source Code
- `../MAExpert/src/logic/` - Pure business logic (reusable patterns)
- `../MAExpert/src/core/commands.py` - Command definitions
- `../MAExpert/src/effects/` - Side effects (reference for Lambda implementations)

## Migration Strategy

1. **Preserve Logic**: Pure functions in `src/logic/` can be reused directly
2. **Adapt Effects**: Convert `src/effects/` to Lambda-compatible implementations
3. **Maintain Contracts**: Keep API contracts consistent (see `docs/contracts/`)

## Do Not Modify

⚠️ **Never modify files in `../MAExpert/` from this repo.**  
The MAExpert codebase remains the source of truth for the local version.

