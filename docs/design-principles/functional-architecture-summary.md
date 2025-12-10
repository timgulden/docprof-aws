# Functional Programming Architecture Summary

**Purpose:** Architectural patterns and principles for M&A Expert System  
**For:** Cursor implementation guidance  
**Date:** November 10, 2025

---

## Core Principles

This system uses **strict functional programming** principles:

1. **No classes for behavior** - only Pydantic models for data
2. **Pure functions** in logic layer - no side effects
3. **Immutable state** - always return new state objects
4. **Command/Effect separation** - logic decides, effects execute
5. **Interceptors** - cross-cutting concerns (middleware-style for commands, stack-based for workflows)

---

## Layer Architecture

```
┌─────────────────────────────────────────────┐
│         UI Layer (Streamlit)                │
│  - Pure presentation                        │
│  - Emit events only                         │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│      Interceptors                           │
│  - Logging, performance monitoring           │
│  - Error handling, cost tracking            │
│  - Middleware-style for commands            │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│      Logic Layer (Pure Functions)           │
│  - Business logic ONLY                      │
│  - Returns: (new_state, commands)           │
│  - NO side effects                          │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│      Command Executor                       │
│  - Dispatches commands to effects           │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│      Effects Layer (Side Effects)           │
│  - Database, API calls, I/O                 │
│  - Pure functions that DO things            │
└─────────────────────────────────────────────┘
```

---

## Pattern 1: State Management (Immutable)

### ✅ Correct - Immutable Updates

```python
from pydantic import BaseModel, Field
from typing import List
from datetime import datetime

class ApplicationState(BaseModel):
    """Immutable state"""
    session_id: str
    messages: List[Message] = Field(default_factory=list)
    user: Optional[User] = None
    updated_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        frozen = False  # Allow .model_copy()

def add_message(state: ApplicationState, message: Message) -> ApplicationState:
    """Pure function: returns NEW state"""
    new_messages = [*state.messages, message]  # Create new list
    
    return state.model_copy(update={
        'messages': new_messages,
        'updated_at': datetime.now()
    })
```

### ❌ Wrong - Mutation

```python
def add_message_bad(state: ApplicationState, message: Message) -> ApplicationState:
    """WRONG: Mutates existing state"""
    state.messages.append(message)  # ❌ Mutation!
    return state
```

---

## Pattern 2: Logic Returns Commands

### ✅ Correct - Command Pattern

```python
from pydantic import BaseModel
from typing import List

class Command(BaseModel):
    """Base command"""
    pass

class LLMCommand(Command):
    """Command to call LLM"""
    prompt: str
    temperature: float = 0.7

class VectorSearchCommand(Command):
    """Command to search database"""
    query_embedding: List[float]
    limit: int = 10

class LogicResult(BaseModel):
    """What logic functions return"""
    new_state: ApplicationState
    commands: List[Command] = Field(default_factory=list)
    ui_message: Optional[str] = None

def process_user_message(
    state: ApplicationState,
    message_text: str
) -> LogicResult:
    """
    Pure function: NO side effects.
    
    Just returns what SHOULD happen.
    """
    # Add user message to state
    user_message = Message(role='user', content=message_text)
    new_messages = [*state.messages, user_message]
    
    new_state = state.model_copy(update={
        'messages': new_messages
    })
    
    # Create commands for effects to execute
    commands = [
        EmbedCommand(text=message_text),  # What to do
        # VectorSearchCommand will be issued after embedding
    ]
    
    return LogicResult(
        new_state=new_state,
        commands=commands,
        ui_message="Searching..."
    )
```

### ❌ Wrong - Direct Side Effects

```python
def process_user_message_bad(state: ApplicationState, message: str) -> ApplicationState:
    """WRONG: Side effects in logic"""
    
    # ❌ Direct database call in logic!
    embedding = openai.embeddings.create(...)
    results = database.search(embedding)
    
    return state  # ❌ Mixed concerns
```

---

## Pattern 3: Effects Execute Commands

### ✅ Correct - Pure Effect Functions

```python
from anthropic import Anthropic
from typing import Dict

def call_llm(api_key: str, prompt: str, temperature: float) -> Dict:
    """
    Effect function: performs side effect but is still 'pure'
    in the sense that same inputs → same API call.
    """
    client = Anthropic(api_key=api_key)
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=4000
    )
    
    return {
        'text': response.content[0].text,
        'usage': {
            'input_tokens': response.usage.input_tokens,
            'output_tokens': response.usage.output_tokens
        }
    }

# Command Executor dispatches commands to effects
def execute_command(command: Command, config: Dict) -> Any:
    """Dispatch commands to appropriate effects"""
    
    if isinstance(command, LLMCommand):
        return call_llm(
            config['anthropic_api_key'],
            command.prompt,
            command.temperature
        )
    
    elif isinstance(command, VectorSearchCommand):
        return search_vectors(
            config['db_config'],
            command.query_embedding,
            command.limit
        )
    
    # ... more command types
```

---

## Pattern 4: No Classes for Behavior

### ✅ Correct - Functions + Closures

```python
from typing import Callable, Dict

# Configuration via closure
def create_llm_function(api_key: str) -> Callable:
    """
    Returns a function with captured configuration.
    
    This is functional alternative to a class.
    """
    def call(prompt: str, temperature: float = 0.7) -> Dict:
        return call_llm(api_key, prompt, temperature)
    
    return call

# Usage
llm = create_llm_function("sk-ant-...")
result = llm("What is DCF valuation?")
```

### ❌ Wrong - Classes with State

```python
class LLMClient:  # ❌ Avoid this pattern
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = Anthropic(api_key=api_key)
    
    def call(self, prompt: str) -> Dict:
        # ... instance methods
        pass
```

**Exception:** Pydantic models for DATA are fine:

```python
class User(BaseModel):  # ✅ OK - just data
    user_id: str
    username: str
    created_at: datetime
```

---

## Pattern 5: Interceptors

**Note:** The system uses two interceptor patterns. See `docs/architecture/interceptor-patterns.md` for details.

### ✅ Correct - Middleware-Style Interceptors (Command Execution)

```python
from typing import Any, Callable, Dict
from loguru import logger
from src.core.commands import Command

CommandExecutor = Callable[[Command, Dict[str, Any]], Dict[str, Any]]
CommandInterceptor = Callable[[Command, Dict[str, Any], CommandExecutor], Dict[str, Any]]

def logging_interceptor(
    command: Command,
    context: Dict[str, Any],
    call_next: CommandExecutor,
) -> Dict[str, Any]:
    """Log command execution lifecycle."""
    logger.debug("Command interceptor starting: %s", command.command_name)
    try:
        result = call_next(command, context)
        logger.debug("Command interceptor finished: %s", command.command_name)
        return result
    except Exception as e:
        logger.exception("Command interceptor error: %s", command.command_name)
        raise

def with_common_interceptors(
    executor: CommandExecutor,
    interceptors: list[CommandInterceptor],
) -> CommandExecutor:
    """Compose interceptors around a base executor."""
    def dispatch(index: int, command: Command, context: Dict[str, Any]) -> Dict[str, Any]:
        if index >= len(interceptors):
            return executor(command, context)
        
        interceptor = interceptors[index]
        
        def call_next(next_command: Command, next_context: Dict[str, Any]) -> Dict[str, Any]:
            return dispatch(index + 1, next_command, next_context)
        
        return interceptor(command, context, call_next)
    
    def wrapped(command: Command, context: Dict[str, Any]) -> Dict[str, Any]:
        return dispatch(0, command, context)
    
    return wrapped

# Usage: Automatically applied via create_executor()
executor = create_executor(deps, use_interceptors=True)
# All commands now have logging, performance monitoring, cost tracking, error handling
```

**Key Points:**
- Middleware-style pattern with `call_next` parameter
- Automatically applied to all command executors
- Common interceptors: logging, performance, cost tracking, error boundary
- See `src/interceptors/common.py` for implementation

**For stack-based interceptors (ingestion pipeline):** See `docs/architecture/interceptor101.md`

---

## Pattern 6: Functional Composition

### ✅ Correct - Compose Functions

```python
from typing import Callable, List

def compose(*functions: Callable) -> Callable:
    """Compose functions right-to-left"""
    def composed(arg):
        result = arg
        for f in reversed(functions):
            result = f(result)
        return result
    return composed

# Example: Data processing pipeline
def clean_text(text: str) -> str:
    return text.strip().lower()

def remove_stopwords(text: str) -> str:
    stopwords = {'the', 'a', 'an'}
    words = text.split()
    return ' '.join(w for w in words if w not in stopwords)

def extract_keywords(text: str) -> List[str]:
    return text.split()[:5]

# Compose into pipeline
process_text = compose(
    extract_keywords,
    remove_stopwords,
    clean_text
)

result = process_text("  The Quick BROWN Fox  ")
# ['quick', 'brown', 'fox']
```

---

## Pattern 7: Configuration via Closures

### ✅ Correct - Capture Config in Closure

```python
from typing import Dict, Callable

DatabaseConfig = Dict[str, str]

def create_database_functions(config: DatabaseConfig) -> Dict[str, Callable]:
    """
    Returns dictionary of database functions.
    
    Configuration is captured in closures.
    """
    
    def insert_user(username: str, password_hash: str) -> str:
        # config is captured from outer scope
        conn = psycopg2.connect(**config)
        # ... insert user
        return user_id
    
    def get_user(username: str) -> Optional[Dict]:
        conn = psycopg2.connect(**config)
        # ... get user
        return user_dict
    
    return {
        'insert_user': insert_user,
        'get_user': get_user
    }

# Usage
db_config = {'host': 'localhost', 'database': 'mna_expert', ...}
db = create_database_functions(db_config)

# Call without passing config again
user = db['get_user']('john_doe')
```

---

## Complete Example: Chat Flow

### 1. UI Layer (Emits Event)

```python
# src/ui/components/chat.py
import streamlit as st
from src.ui.events import UIEvent, dispatch_event

def render(state: ApplicationState):
    """Pure presentation - no logic"""
    
    user_input = st.chat_input("Ask a question...")
    
    if user_input:
        # Create event
        event = UIEvent(
            type="chat_message",
            data={"message": user_input}
        )
        
        # Dispatch event
        new_state = dispatch_event(state, event)
        
        # Update Streamlit state
        st.session_state.app_state = new_state
        st.rerun()
```

### 2. Event Router

```python
# src/ui/events.py
def dispatch_event(state: ApplicationState, event: UIEvent) -> ApplicationState:
    """Route event to logic, execute commands, return new state"""
    
    # Pure: route to logic
    result = route_event_to_logic(state, event)
    
    # Side effect: execute commands
    execute_commands(result.commands)
    
    # Return new state
    return result.new_state

def route_event_to_logic(state: ApplicationState, event: UIEvent) -> LogicResult:
    """Pure routing"""
    from src.logic import chat
    
    if event.type == "chat_message":
        return chat.process_user_message(
            state,
            event.data['message']
        )
    # ... other event types
```

### 3. Logic Layer (Pure)

```python
# src/logic/chat.py
def process_user_message(
    state: ApplicationState,
    message_text: str
) -> LogicResult:
    """
    Pure function: NO side effects.
    """
    # Update state
    user_message = Message(role='user', content=message_text)
    new_messages = [*state.messages, user_message]
    
    new_state = state.model_copy(update={
        'messages': new_messages
    })
    
    # Create commands
    commands = [
        EmbedCommand(text=message_text)
    ]
    
    return LogicResult(
        new_state=new_state,
        commands=commands,
        ui_message="Searching..."
    )
```

### 4. Command Executor

```python
# src/effects/command_executor.py
def create_command_executor():
    """Returns executor with captured config"""
    config = load_config()
    
    # Create configured functions
    llm = create_llm_function(config['anthropic_api_key'])
    embed = create_embedding_function(config['openai_api_key'])
    
    def execute(command: Command) -> Any:
        """Dispatch command to effect"""
        if isinstance(command, LLMCommand):
            return llm(command.prompt, command.temperature)
        
        elif isinstance(command, EmbedCommand):
            return embed(command.text)
        
        # ... more command types
    
    return {'execute': execute}
```

### 5. Effects Layer

```python
# src/effects/embeddings.py
from openai import OpenAI

def create_embedding_function(api_key: str) -> Callable:
    """Returns embedding function with captured API key"""
    client = OpenAI(api_key=api_key)
    
    def embed(text: str) -> List[float]:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    
    return embed
```

---

## Testing Pure Functions

Pure functions are **trivial to test**:

```python
# test_chat_logic.py
from src.logic.chat import process_user_message
from src.core.state import ApplicationState, Message

def test_process_user_message():
    """Test pure logic function"""
    
    # Arrange - create initial state
    initial_state = ApplicationState(
        session_id="test-123",
        messages=[]
    )
    
    # Act - call pure function
    result = process_user_message(initial_state, "What is DCF?")
    
    # Assert - check new state
    assert len(result.new_state.messages) == 1
    assert result.new_state.messages[0].content == "What is DCF?"
    assert len(result.commands) > 0
    assert isinstance(result.commands[0], EmbedCommand)
    
    # Original state unchanged (immutability)
    assert len(initial_state.messages) == 0
```

**No mocks needed** for logic layer!

---

## Key Takeaways for Cursor

When implementing, follow these rules:

1. **Logic functions signature:**
   ```python
   def logic_function(state: ApplicationState, ...) -> LogicResult:
       # Pure logic only
       return LogicResult(new_state=..., commands=[...])
   ```

2. **Effect functions signature:**
   ```python
   def effect_function(config: Config, ...) -> Result:
       # Side effect here
       return result
   ```

3. **Never mutate state:**
   ```python
   # ❌ Wrong
   state.messages.append(msg)
   
   # ✅ Right
   new_messages = [*state.messages, msg]
   new_state = state.model_copy(update={'messages': new_messages})
   ```

4. **Use closures for configuration:**
   ```python
   def create_api_client(api_key: str):
       def call(params):
           # api_key captured in closure
           ...
       return {'call': call}
   ```

5. **Compose decorators for cross-cutting concerns:**
   ```python
   @with_logging
   @with_state_persistence(state_dir)
   @with_error_handling()
   def my_logic_function(...):
       ...
   ```

---

## Project Structure Quick Reference

```
src/
├── core/
│   ├── state.py          # Pydantic state models (immutable data)
│   └── commands.py       # Command types
│
├── logic/               # Pure functions ONLY
│   ├── auth.py
│   ├── chat.py
│   ├── lecture.py
│   └── quiz.py
│
├── effects/             # Side effects isolated here
│   ├── database.py
│   ├── vector_search.py
│   ├── llm_client.py
│   ├── embeddings.py
│   └── audio_generator.py
│
├── interceptors/        # Interceptors for cross-cutting concerns
│   ├── common.py        # Middleware-style interceptors (commands)
│   ├── ingestion_pipeline.py  # Stack-based interceptors (ingestion)
│   └── (see interceptor-patterns.md for details)
│
└── ui/                  # Streamlit presentation
    ├── app.py
    ├── components/
    └── events.py        # Event routing
```

---

## Common Patterns Cheat Sheet

**Create new state:**
```python
new_state = state.model_copy(update={'field': new_value})
```

**Add to list immutably:**
```python
new_list = [*old_list, new_item]
```

**Update dict immutably:**
```python
new_dict = {**old_dict, 'key': new_value}
```

**Create command:**
```python
commands = [
    LLMCommand(prompt="...", temperature=0.7),
    VectorSearchCommand(query_embedding=embedding, limit=10)
]
```

**Return from logic:**
```python
return LogicResult(
    new_state=new_state,
    commands=commands,
    ui_message="Processing..."
)
```

**Create configured function:**
```python
def create_client(config):
    def call(params):
        # config captured in closure
        ...
    return call
```

---

*This document summarizes the functional programming patterns used throughout the M&A Expert System. Follow these patterns for consistent, testable, maintainable code.*
