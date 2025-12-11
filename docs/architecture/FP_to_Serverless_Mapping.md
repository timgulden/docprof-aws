# Functional Programming to Serverless Architecture Mapping

**Purpose**: Formalize how MAExpert's FP patterns map to AWS serverless architecture  
**Goal**: Maximize code reuse and preserve architectural benefits  
**Date**: 2025-01-XX

---

## Executive Summary

**Yes, the FP paradigm maps exceptionally well to serverless!** The separation of pure logic from side effects aligns perfectly with Lambda's stateless model. This document formalizes the mapping so we can:

1. **Extract logic once** from MAExpert prototype into this codebase (`shared/logic/` and `shared/core/`)
2. **Own logic forever** - Logic becomes part of this project, version-controlled in git
3. **Adapt effects systematically** (clear transformation rules)
4. **Preserve architectural benefits** (testability, maintainability)
5. **Avoid re-learning lessons** (leverage existing patterns)

### Key Architecture Decision

**Logic is extracted from MAExpert prototype and owned by this codebase** - not copied from external source:
- Location: `src/lambda/shared/logic/` and `src/lambda/shared/core/`
- Packaging: Gets packaged with Lambda functions via `shared/` directory
- Dependencies: No external MAExpert references - logic is self-contained
- Version Control: Logic changes tracked in git with the rest of the codebase

---

## Core Mapping Principles

### 1. Logic Layer → Direct Reuse ✅

**MAExpert Pattern:**
```python
# src/logic/chat.py
def process_user_message(
    state: ApplicationState,
    message_text: str
) -> LogicResult:
    """Pure function - no side effects"""
    # ... logic ...
    return LogicResult(new_state=..., commands=[...])
```

**Serverless Mapping:**
```python
# Logic extracted into this codebase: src/lambda/shared/logic/chat.py
from shared.logic.chat import process_user_message

# Lambda handler calls pure logic
def lambda_handler(event, context):
    state = load_state_from_dynamodb(event['session_id'])
    result = process_user_message(state, event['message'])
    # Execute commands, save state
    return format_response(result)
```

**Key Insight**: Pure functions are **stateless** and **side-effect-free**, making them perfect for Lambda. Logic is **extracted into this codebase** (`shared/logic/`) and packaged with Lambda functions. No external dependencies - logic is owned by this project.

---

### 2. Effects Layer → Service Adapters

**MAExpert Pattern:**
```python
# src/effects/llm_client.py
def call_llm(api_key: str, prompt: str) -> Dict:
    client = Anthropic(api_key=api_key)
    return client.messages.create(...)

# src/effects/embeddings.py
def generate_embedding(api_key: str, text: str) -> List[float]:
    client = OpenAI(api_key=api_key)
    return client.embeddings.create(...)
```

**Serverless Mapping:**
```python
# src/lambda/shared/bedrock_client.py (ADAPTED)
def call_llm(prompt: str) -> Dict:
    """Same signature, different implementation"""
    client = boto3.client('bedrock-runtime')
    return client.invoke_model(
        modelId='anthropic.claude-3-5-sonnet',
        body=json.dumps({'prompt': prompt})
    )

def generate_embedding(text: str) -> List[float]:
    """Same signature, different implementation"""
    client = boto3.client('bedrock-runtime')
    return client.invoke_model(
        modelId='amazon.titan-embed-text-v1',
        body=json.dumps({'inputText': text})
    )
```

**Key Insight**: Effect functions have **stable signatures** but different implementations. Create adapter layer that matches MAExpert signatures but uses AWS services.

---

### 3. Command Pattern → Lambda Invocations / Step Functions

**MAExpert Pattern:**
```python
# Commands are Pydantic models
class EmbedCommand(Command):
    text: str

class VectorSearchCommand(Command):
    query_embedding: List[float]
    limit: int

# Command executor dispatches
def execute_command(command: Command) -> Any:
    if isinstance(command, EmbedCommand):
        return generate_embedding(command.text)
    elif isinstance(command, VectorSearchCommand):
        return search_vectors(command.query_embedding, command.limit)
```

**Serverless Mapping - Option A: In-Process (Simple)**
```python
# Same pattern, adapted effects
def execute_command(command: Command, effects: Dict[str, Callable]) -> Any:
    """Same dispatcher, different effect implementations"""
    if isinstance(command, EmbedCommand):
        return effects['embed'](command.text)  # Uses Bedrock Titan
    elif isinstance(command, VectorSearchCommand):
        return effects['search'](command.query_embedding, command.limit)  # Uses Aurora
```

**Serverless Mapping - Option B: Step Functions (Complex Workflows)**
```json
{
  "Comment": "Document ingestion workflow",
  "StartAt": "ExtractText",
  "States": {
    "ExtractText": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:function:extract-text",
      "Next": "ChunkDocument"
    },
    "ChunkDocument": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:function:chunk-document",
      "Next": "GenerateEmbeddings"
    },
    "GenerateEmbeddings": {
      "Type": "Map",
      "ItemsPath": "$.chunks",
      "Iterator": {
        "StartAt": "EmbedChunk",
        "States": {
          "EmbedChunk": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:...:function:generate-embedding",
            "End": true
          }
        }
      }
    }
  }
}
```

**Key Insight**: 
- **Simple commands** → Execute in-process (same Lambda)
- **Complex workflows** → Step Functions (orchestration)
- **Commands become Lambda invocations** or Step Functions tasks

---

### 4. State Management → DynamoDB / Aurora

**MAExpert Pattern:**
```python
# Immutable state updates
def add_message(state: ApplicationState, message: Message) -> ApplicationState:
    new_messages = [*state.messages, message]
    return state.model_copy(update={'messages': new_messages})
```

**Serverless Mapping:**
```python
# Same immutable pattern, different storage
def add_message(state: ApplicationState, message: Message) -> ApplicationState:
    """SAME LOGIC - no changes needed"""
    new_messages = [*state.messages, message]
    return state.model_copy(update={'messages': new_messages})

# Storage adapter
def save_state(state: ApplicationState):
    """Store in DynamoDB instead of filesystem"""
    dynamodb.put_item(
        TableName='docprof-sessions',
        Item={
            'session_id': state.session_id,
            'state': state.model_dump_json(),
            'updated_at': datetime.utcnow().isoformat()
        }
    )
```

**Key Insight**: **State update logic stays pure** (immutable updates). Only the **storage mechanism** changes (DynamoDB vs filesystem).

---

### 5. Interceptors → Lambda Layers / Middleware

**MAExpert Pattern:**
```python
# Middleware-style interceptors
def logging_interceptor(
    command: Command,
    context: Dict,
    call_next: CommandExecutor
) -> Dict:
    logger.info(f"Executing {command.command_name}")
    result = call_next(command, context)
    logger.info(f"Completed {command.command_name}")
    return result

# Applied automatically
executor = with_common_interceptors(base_executor, [
    logging_interceptor,
    performance_interceptor,
    error_handler_interceptor
])
```

**Serverless Mapping:**
```python
# Lambda middleware wrapper
def with_interceptors(handler):
    """Apply interceptors to Lambda handler"""
    def wrapped(event, context):
        # Logging interceptor
        logger.info(f"Lambda invoked: {context.function_name}")
        
        try:
            # Performance interceptor
            start_time = time.time()
            result = handler(event, context)
            duration = time.time() - start_time
            
            # Log performance
            logger.info(f"Lambda completed in {duration:.2f}s")
            return result
            
        except Exception as e:
            # Error handler interceptor
            logger.error(f"Lambda error: {e}", exc_info=True)
            return error_response(str(e))
    
    return wrapped

# Usage
@with_interceptors
def lambda_handler(event, context):
    # Handler code
    pass
```

**Key Insight**: Interceptors become **Lambda middleware/decorators**. Same cross-cutting concerns (logging, performance, errors), different mechanism.

---

## Detailed Component Mapping

### Logic Functions → Extracted into Codebase

| MAExpert Location | Serverless Location | Changes Required |
|-------------------|-------------------|------------------|
| `src/logic/chat.py` | `src/lambda/shared/logic/chat.py` | **Import paths** - update to `shared.logic` |
| `src/logic/courses.py` | `src/lambda/shared/logic/courses.py` | **Import paths** - update to `shared.logic` |
| `src/logic/ingestion.py` | `src/lambda/shared/logic/ingestion.py` | **Import paths** - update to `shared.logic` |
| `src/logic/rag_pipeline.py` | `src/lambda/shared/logic/rag_pipeline.py` | **Import paths** - update to `shared.logic` |

**Implementation:**
```python
# Logic extracted from MAExpert into this codebase
# src/lambda/shared/logic/chat.py (copied from MAExpert, imports updated)
from shared.core.chat_models import ChatMessage, ChatState
from shared.core.prompts import get_prompt

# Lambda handlers import from shared/
from shared.logic.chat import process_user_message  # Direct import!
from shared.logic.rag_pipeline import retrieve_context  # Direct import!
```

**Key**: Logic is **extracted once** from MAExpert prototype, then **owned by this codebase**. Gets packaged with Lambda functions via `shared/` directory. No external dependencies.

---

### Effects Functions → Adapter Layer

| MAExpert Effect | AWS Service | Adapter Location |
|----------------|-------------|------------------|
| `effects/llm_client.py` | Bedrock Claude | `shared/bedrock_client.py` |
| `effects/embeddings.py` | Bedrock Titan | `shared/bedrock_client.py` |
| `effects/database_client.py` | Aurora PostgreSQL | `shared/db_utils.py` |
| `effects/audio_client.py` | AWS Polly | `shared/polly_client.py` |
| `effects/pdf_extractor.py` | PyMuPDF (same) | `shared/pdf_utils.py` |

**Implementation Pattern:**
```python
# Create adapter that matches MAExpert signature
def create_bedrock_adapter():
    """Returns functions matching MAExpert effect signatures"""
    
    def call_llm(prompt: str, temperature: float = 0.7) -> Dict:
        """Matches MAExpert signature, uses Bedrock"""
        # ... Bedrock implementation ...
    
    def generate_embedding(text: str) -> List[float]:
        """Matches MAExpert signature, uses Titan"""
        # ... Titan implementation ...
    
    return {
        'call_llm': call_llm,
        'generate_embedding': generate_embedding
    }
```

---

### Command Executor → Lambda Handler

**MAExpert:**
```python
# src/effects/command_executor.py
def create_executor(deps: Dict) -> CommandExecutor:
    effects = {
        'llm': create_llm_function(deps['anthropic_api_key']),
        'embed': create_embedding_function(deps['openai_api_key']),
        'db': create_database_functions(deps['db_config'])
    }
    
    def execute(command: Command) -> Any:
        if isinstance(command, LLMCommand):
            return effects['llm'](command.prompt, command.temperature)
        elif isinstance(command, EmbedCommand):
            return effects['embed'](command.text)
        # ...
    
    return execute
```

**Serverless:**
```python
# src/lambda/chat_handler/handler.py
def lambda_handler(event, context):
    # Load state
    state = load_state_from_dynamodb(event['session_id'])
    
    # Call pure logic (from shared/logic - extracted into codebase)
    from shared.logic.chat import process_user_message
    result = process_user_message(state, event['message'])
    
    # Create effects adapter
    effects = create_aws_effects_adapter()
    
    # Execute commands
    for command in result.commands:
        execute_command(command, effects)
    
    # Save state
    save_state_to_dynamodb(result.new_state)
    
    # Return response
    return format_api_response(result)
```

---

## State Storage Mapping

### Session State → DynamoDB

**MAExpert:**
```python
# src/effects/state_storage.py
def save_session_state(state: ApplicationState, state_dir: str):
    file_path = Path(state_dir) / f"{state.session_id}.json"
    file_path.write_text(state.model_dump_json())
```

**Serverless:**
```python
# src/lambda/shared/state_storage.py
def save_session_state(state: ApplicationState):
    dynamodb.put_item(
        TableName='docprof-sessions',
        Item={
            'session_id': state.session_id,
            'state_json': state.model_dump_json(),
            'ttl': int(time.time()) + 86400  # 24 hour TTL
        }
    )
```

**Key**: State **structure** (Pydantic models) stays the same. Only **storage mechanism** changes.

---

### Persistent Data → Aurora PostgreSQL

**MAExpert:**
```python
# Same database schema, same queries
def insert_chunks(chunks: List[Dict], embeddings: List[List[float]]):
    # Uses psycopg2 directly
    execute_values(cur, "INSERT INTO chunks ...", values)
```

**Serverless:**
```python
# Same database schema, same queries, different connection method
def insert_chunks(chunks: List[Dict], embeddings: List[List[float]]):
    # Uses RDS Proxy or direct connection
    # Same SQL, same logic
    execute_values(cur, "INSERT INTO chunks ...", values)
```

**Key**: Database **schema** and **queries** stay the same. Only **connection method** changes (RDS Proxy vs direct).

---

## Workflow Mapping

### Ingestion Pipeline → Step Functions

**MAExpert:**
```python
# Stack-based interceptors for ingestion
def build_ingestion_pipeline():
    return [
        validate_pdf_interceptor,
        extract_text_interceptor,
        chunk_document_interceptor,
        generate_embeddings_interceptor,
        store_in_database_interceptor
    ]
```

**Serverless:**
```json
{
  "Comment": "Document ingestion pipeline",
  "StartAt": "ValidatePDF",
  "States": {
    "ValidatePDF": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:function:validate-pdf",
      "Next": "ExtractText"
    },
    "ExtractText": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:function:extract-text",
      "Next": "ChunkDocument"
    },
    "ChunkDocument": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:function:chunk-document",
      "Next": "GenerateEmbeddings"
    },
    "GenerateEmbeddings": {
      "Type": "Map",
      "ItemsPath": "$.chunks",
      "MaxConcurrency": 10,
      "Iterator": {
        "StartAt": "EmbedChunk",
        "States": {
          "EmbedChunk": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:...:function:generate-embedding",
            "End": true
          }
        }
      },
      "Next": "StoreInDatabase"
    },
    "StoreInDatabase": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:function:store-chunks",
      "End": true
    }
  }
}
```

**Key**: Stack-based interceptors become **Step Functions state machine**. Each interceptor becomes a **Lambda function**.

---

## Code Reuse Strategy

### Level 1: Direct Import (No Changes) ✅

**Logic functions** - Pure, stateless, side-effect-free:
```python
# Can import directly
from MAExpert.src.logic.chat import process_user_message
from MAExpert.src.logic.courses import generate_course_outline
from MAExpert.src.logic.rag_pipeline import retrieve_context
```

### Level 2: Signature Match (Adapter Pattern)

**Effect functions** - Same signature, different implementation:
```python
# Create adapter that matches MAExpert signatures
def create_aws_effects_adapter():
    return {
        'llm': lambda prompt, temp: call_bedrock_claude(prompt, temp),
        'embed': lambda text: call_bedrock_titan(text),
        'db': create_aurora_adapter(),
        'audio': lambda text: call_polly(text)
    }
```

### Level 3: Pattern Preservation (Architectural)

**State management** - Same immutable patterns:
```python
# Same immutable update patterns
new_state = state.model_copy(update={'field': new_value})

# Only storage changes
save_to_dynamodb(new_state)  # vs save_to_filesystem(new_state)
```

---

## Implementation Checklist

### Phase 1: Logic Layer Extraction ✅
- [x] Identify all pure logic functions in MAExpert
- [x] Extract logic into `src/lambda/shared/logic/` and `src/lambda/shared/core/`
- [x] Update imports from `src.*` to `shared.*`
- [x] Package logic with Lambda functions via `shared/` directory
- [x] Remove external MAExpert dependencies
- [x] Verify no side effects

### Phase 2: Effects Adapter Layer ⚠️
- [x] Create `shared/bedrock_client.py` (matches MAExpert signatures)
- [x] Create `shared/db_utils.py` (matches MAExpert signatures)
- [ ] Create `shared/polly_client.py` (matches MAExpert signatures)
- [ ] Create adapter factory function
- [ ] Test signature compatibility

### Phase 3: Command Executor Adaptation ⚠️
- [ ] Adapt command executor for Lambda
- [ ] Map commands to Lambda invocations
- [ ] Create Step Functions for complex workflows
- [ ] Test command execution

### Phase 4: State Storage Adaptation ⚠️
- [ ] Create DynamoDB state storage adapter
- [ ] Preserve immutable update patterns
- [ ] Test state persistence
- [ ] Verify state loading

### Phase 5: Interceptor Adaptation ⚠️
- [ ] Create Lambda middleware decorators
- [ ] Map interceptors to CloudWatch logging
- [ ] Add performance monitoring
- [ ] Test error handling

---

## Benefits of This Mapping

1. **Maximum Code Reuse**: Logic functions extracted once, then owned by codebase (0% rewrite)
2. **Preserved Architecture**: FP patterns maintained (testability, maintainability)
3. **Clear Adaptation Path**: Systematic transformation rules
4. **Leveraged Lessons**: All debugging/refinement preserved
5. **Incremental Migration**: Can migrate piece by piece
6. **No External Dependencies**: Logic is part of this project, not copied from external source
7. **Version Controlled**: Logic changes tracked in git with the rest of the codebase

---

## Example: Complete Chat Handler

```python
# src/lambda/chat_handler/handler.py
import sys
import os

# Import MAExpert logic directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../MAExpert/src'))
from logic.chat import process_user_message
from logic.rag_pipeline import retrieve_context

# Import AWS adapters
from shared.bedrock_client import create_bedrock_adapter
from shared.db_utils import create_db_adapter
from shared.state_storage import load_state, save_state
from shared.response import success_response, error_response

def lambda_handler(event, context):
    """Lambda handler - thin wrapper around pure logic"""
    try:
        # Parse request
        session_id = event.get('session_id')
        message = event.get('message')
        
        # Load state (from DynamoDB)
        state = load_state(session_id)
        
        # Create effects adapter (matches MAExpert signatures)
        effects = {
            **create_bedrock_adapter(),
            **create_db_adapter(),
        }
        
        # Call pure logic (REUSED FROM MAExpert - NO CHANGES)
        result = process_user_message(state, message)
        
        # Execute commands using adapted effects
        for command in result.commands:
            execute_command(command, effects)
        
        # Save state (to DynamoDB)
        save_state(result.new_state)
        
        # Return response
        return success_response({
            'message': result.ui_message,
            'session_id': result.new_state.session_id
        })
        
    except Exception as e:
        return error_response(str(e))
```

**Key**: Logic is **100% reused**. Only adapters and storage change.

---

## Architecture Summary

### Logic Extraction Strategy

**MAExpert Prototype** → **DocProf AWS (This Project)**

1. **Extract once**: Copy logic from MAExpert prototype into `src/lambda/shared/logic/` and `src/lambda/shared/core/`
2. **Update imports**: Change `from src.*` → `from shared.*` 
3. **Own forever**: Logic becomes part of this codebase, version-controlled in git
4. **Package with functions**: Lambda module packages `shared/` directory with each function
5. **No external dependencies**: Logic is self-contained, no references to MAExpert directory

### Packaging Architecture

- **Lambda Layer**: Contains only Python dependencies (psycopg2, pymupdf, etc.) - no application code
- **Lambda Functions**: Package `shared/logic/` and `shared/core/` with each function
- **Import Pattern**: `from shared.logic.chat import ...` (no sys.path manipulation needed)

## Conclusion

**Yes, formalizing this mapping is absolutely worth it!** It provides:

1. **Clear reuse strategy** - Extract logic once, then own it in this codebase
2. **Systematic transformation** - Rules for converting effects to AWS services
3. **Preserved architecture** - Maintain FP benefits in serverless
4. **Faster implementation** - Less trial and error, more systematic progress
5. **Better testing** - Pure logic tests still work, effect tests adapt
6. **No external dependencies** - Logic is part of the project, not copied from external source
7. **Version controlled** - Logic changes tracked with the rest of the codebase

**Next Steps:**
1. ✅ Extract logic from MAExpert into `shared/logic/` and `shared/core/` (COMPLETED)
2. ✅ Update imports to use `shared.*` pattern (COMPLETED)
3. ✅ Remove external MAExpert dependencies (COMPLETED)
4. Create adapter implementations following these patterns
5. Continue migrating Lambda handlers using this approach
6. Document any deviations or learnings

---

*This mapping ensures we leverage all the refinement and debugging work that went into MAExpert while adapting cleanly to AWS serverless architecture. Logic is extracted once from the prototype, then owned by this codebase - no external dependencies.*

