# Shared Lambda Code

This directory contains shared code used across Lambda functions.

## Structure

```
shared/
├── core/              # Core models and utilities
│   ├── chat_models.py    # Chat state and message models (Pydantic)
│   ├── commands.py       # Command definitions
│   ├── state.py          # LogicResult and state models
│   └── prompts/          # Prompt system
│       ├── base_prompts.py      # All prompts (chat, courses, etc.)
│       ├── prompt_registry.py   # Prompt resolution with variables
│       └── __init__.py
├── logic/             # Pure business logic functions
│   └── chat.py            # Chat logic (expand_query, build_prompt, etc.)
├── bedrock_client.py  # AWS Bedrock adapters (LLM, embeddings)
├── db_utils.py        # Aurora PostgreSQL utilities
├── session_manager.py # DynamoDB session management
├── model_adapters.py  # Converters between DynamoDB dicts and Pydantic models
└── response.py        # API Gateway response helpers
```

## Architecture Principles

1. **Logic is part of this codebase** - Extracted from MAExpert prototype, now owned here
2. **Pure functions** - Logic functions have no side effects, are easily testable
3. **Packaged with functions** - Logic gets packaged with each Lambda (via shared/ directory)
4. **No external dependencies** - Logic doesn't reference MAExpert directory

## Import Pattern

From Lambda handlers:
```python
from shared.logic.chat import expand_query_for_retrieval, build_synthesis_prompt
from shared.core.chat_models import ChatMessage, ChatState
from shared.core.prompts import get_prompt
```

## Packaging

- Lambda functions include `shared/` directory in their deployment package
- Lambda layer contains only Python dependencies (not application code)
- Logic is versioned with the codebase, not copied from external source
