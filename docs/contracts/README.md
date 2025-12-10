# API Contracts

This directory contains API contracts and data models extracted from MAExpert to ensure functional parity in the AWS implementation.

## Purpose

- **API Contracts**: Request/response schemas for all endpoints
- **Data Models**: Database schemas and Pydantic models
- **Behavioral Contracts**: Expected behavior and side effects

## Files to Create

### API Contracts
- `chat_api.md` - Chat/Q&A endpoint contracts
- `course_api.md` - Course generation and management contracts
- `lecture_api.md` - Lecture generation and delivery contracts
- `retrieval_api.md` - Vector search and retrieval contracts

### Data Models
- `database_schema.sql` - PostgreSQL schema (for Aurora migration)
- `pydantic_models.md` - Core data models (State, Commands, etc.)

### Behavioral Contracts
- `course_generation_flow.md` - Multi-phase course generation logic
- `chat_flow.md` - Chat message processing flow
- `lecture_qa_flow.md` - Q&A during lecture delivery

## Extraction Process

1. Review MAExpert source code
2. Extract contracts and document here
3. Use as reference when implementing AWS version
4. Verify parity through integration tests

These contracts ensure the AWS implementation maintains the same functionality and user experience as the original MAExpert system.

