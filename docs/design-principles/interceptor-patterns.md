# Interceptor Patterns in M&A Expert

**Last Updated:** 2025-12-02

This document explains the two interceptor patterns used in the M&A Expert system and when to use each.

---

## Overview

The M&A Expert system uses **two interceptor patterns** for different use cases:

1. **Stack-Based Pattern** (`enter`/`leave`/`error`) - Used for ingestion pipeline
2. **Middleware-Style Pattern** (`call_next`) - Used for command execution

Both patterns are valid and serve different purposes. This document explains each pattern and when to use them.

---

## Pattern 1: Stack-Based Interceptors

**Reference:** `docs/architecture/interceptor101.md` and `docs/architecture/interceptor.py`

**Used For:** Ingestion pipeline, complex multi-step workflows

**Characteristics:**
- Three functions: `enter`, `leave`, `error`
- Context passed through stack
- Automatic error handling via `error` function
- Bidirectional execution (enter → leave)

**Example:**
```python
# src/interceptors/ingestion_pipeline.py
def _validate_pdf(ctx: Context) -> Context:
    command: RunIngestionPipelineCommand = ctx["command"]
    pdf_path: Path = Path(command.pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found at {pdf_path}")
    return ctx

def build_interceptor_stack() -> List[Interceptor]:
    return [
        _validate_pdf,
        _execute_pipeline,
        _mark_success,
    ]
```

**When to Use:**
- Complex workflows with multiple phases
- Need bidirectional execution (setup/teardown)
- Need explicit error handling per interceptor
- Ingestion pipelines, batch processing

**Implementation:** `docs/architecture/interceptor.py` provides the stack executor.

---

## Pattern 2: Middleware-Style Interceptors

**Reference:** `src/interceptors/common.py`

**Used For:** Command execution, cross-cutting concerns (logging, performance, cost tracking)

**Characteristics:**
- Single function with `call_next` parameter
- Unidirectional execution (top to bottom)
- Simpler API for common use cases
- Automatic composition via `with_common_interceptors()`

**Example:**
```python
# src/interceptors/common.py
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

# Usage
executor = with_common_interceptors(base_executor, [
    logging_interceptor,
    performance_monitoring_interceptor,
    cost_tracking_interceptor,
    error_boundary_interceptor,
])
```

**When to Use:**
- Command execution wrapping
- Cross-cutting concerns (logging, monitoring, cost tracking)
- Simple unidirectional processing
- Most common use case in the system

**Implementation:** `src/interceptors/common.py` provides the middleware-style composition.

---

## Common Interceptors

The system includes several pre-built middleware-style interceptors in `src/interceptors/common.py`:

1. **`logging_interceptor`** - Logs command execution lifecycle
2. **`performance_monitoring_interceptor`** - Tracks execution time
3. **`cost_tracking_interceptor`** - Tracks LLM token usage
4. **`error_boundary_interceptor`** - Catches and logs errors

These are automatically applied to all command executors via `create_executor()` in `src/effects/command_executor.py`.

---

## Integration

### Command Executor Integration

All command executors created via `create_executor()` automatically use common interceptors:

```python
# src/effects/command_executor.py
def create_executor(
    deps: EffectDependencies,
    use_interceptors: bool = True,
) -> CommandExecutor:
    """Create a command executor with optional interceptors."""
    base_executor = _create_base_executor(deps)
    
    if use_interceptors:
        interceptors = get_default_common_interceptors()
        return with_common_interceptors(base_executor, interceptors)
    
    return base_executor
```

### Usage in API Routes

```python
# src/api/routes/chat.py
deps = EffectDependencies(...)
executor = create_executor(deps, use_interceptors=True)  # Interceptors enabled by default
```

---

## Pattern Comparison

| Feature | Stack-Based | Middleware-Style |
|--------|-------------|------------------|
| **Complexity** | Higher | Lower |
| **Execution** | Bidirectional (enter/leave) | Unidirectional |
| **Error Handling** | Explicit `error` function | Try/catch in interceptor |
| **Use Case** | Complex workflows | Command wrapping |
| **Composition** | Manual stack building | Automatic via `with_common_interceptors()` |
| **Current Usage** | Ingestion pipeline | Command execution |

---

## Best Practices

### When to Use Stack-Based Pattern

- ✅ Multi-phase workflows (setup → execute → teardown)
- ✅ Need bidirectional execution
- ✅ Complex error recovery
- ✅ Ingestion pipelines

### When to Use Middleware-Style Pattern

- ✅ Command execution wrapping
- ✅ Cross-cutting concerns (logging, monitoring)
- ✅ Simple unidirectional processing
- ✅ Most command execution use cases

### General Principles

1. **One interceptor, one concern** - Each interceptor should do one thing
2. **Keep interceptors simple** - Prefer multiple simple interceptors over one complex one
3. **Don't handle errors unless necessary** - Let errors propagate naturally
4. **Use common interceptors** - Leverage `get_default_common_interceptors()` for standard concerns

---

## Migration Notes

The system originally documented only the stack-based pattern (`interceptor101.md`). The middleware-style pattern was introduced for command execution to simplify common use cases. Both patterns are now officially supported.

**For new code:**
- Use middleware-style for command execution (default)
- Use stack-based for complex workflows (ingestion, batch processing)

---

## References

- **Stack-Based Pattern:** `docs/architecture/interceptor101.md`, `docs/architecture/interceptor.py`
- **Middleware-Style Pattern:** `src/interceptors/common.py`
- **Ingestion Example:** `src/interceptors/ingestion_pipeline.py`
- **Command Executor:** `src/effects/command_executor.py`

---

*Last Updated: 2025-12-02*

