# Course Generation: Critical Fix Required

## Problem Summary

The course generation pipeline **stops after book search** because LLM command results are not converted to events that the logic layer expects.

## Root Cause

The handler executes LLM commands but doesn't convert their results to events. The logic layer expects events (`PartsGeneratedEvent`, `PartSectionsGeneratedEvent`, etc.) but never receives them.

## Current Broken Flow

```
1. CourseRequestedEvent ✅
   → EmbedCommand ✅
   
2. EmbeddingGeneratedEvent ✅ (handler converts manually)
   → SearchBookSummariesCommand ✅
   
3. BookSummariesFoundEvent ✅ (handler converts manually)
   → LLMCommand(task="generate_course_parts") ✅
   
4. LLM Result: {'status': 'success', 'content': '...'} ❌
   → Handler doesn't convert to PartsGeneratedEvent ❌
   → Logic never receives PartsGeneratedEvent ❌
   → Pipeline stops here ❌
```

## Required Fix

The handler must convert LLM command results to events based on the `command.task` field:

```python
elif isinstance(command, LLMCommand):
    if command_result.get('status') == 'success' and 'content' in command_result:
        # Convert LLM result to event based on task
        if command.task == 'generate_course_parts':
            event = PartsGeneratedEvent(parts_text=command_result['content'])
            current_result = reduce_course_event(current_state, event)
            current_state = current_result.new_state
            
        elif command.task == 'generate_part_sections':
            # Extract part_index from prompt_variables
            part_index = command.prompt_variables.get('part_index', 0)
            event = PartSectionsGeneratedEvent(
                sections_text=command_result['content'],
                part_index=part_index
            )
            current_result = reduce_course_event(current_state, event)
            current_state = current_result.new_state
            
        elif command.task == 'review_outline':
            event = OutlineReviewEvent(
                reviewed_outline_text=command_result['content']
            )
            current_result = reduce_course_event(current_state, event)
            current_state = current_result.new_state
            
        else:
            logger.warning(f"Unknown LLM task: {command.task}")
            # Don't break - might be a different type of LLM command
```

## Complete Event Flow (After Fix)

```
1. CourseRequestedEvent
   → EmbedCommand
   
2. EmbeddingGeneratedEvent (from EmbedCommand result)
   → SearchBookSummariesCommand
   
3. BookSummariesFoundEvent (from SearchBookSummariesCommand result)
   → LLMCommand(task="generate_course_parts")
   
4. PartsGeneratedEvent (from LLMCommand result) ✅ FIX NEEDED
   → LLMCommand(task="generate_part_sections", part_index=0)
   
5. PartSectionsGeneratedEvent (from LLMCommand result) ✅ FIX NEEDED
   → LLMCommand(task="generate_part_sections", part_index=1)
   
6. PartSectionsGeneratedEvent (from LLMCommand result) ✅ FIX NEEDED
   → ... (continue for all parts)
   
7. AllPartsCompleteEvent (from logic when all parts done)
   → LLMCommand(task="review_outline")
   
8. OutlineReviewEvent (from LLMCommand result) ✅ FIX NEEDED
   → CreateCourseCommand or StoreCourseCommand
   
9. CourseStoredEvent (from CreateCourseCommand result) ✅ FIX NEEDED
   → Pipeline complete
```

## Verification Against MAExpert

After fixing, we need to verify:

1. **Same event sequence?** - Does MAExpert use the same events?
2. **Same prompts?** - Are the prompts identical?
3. **Same output format?** - Does the course JSON structure match?
4. **Same behavior?** - Test with same input, compare outputs

## Implementation Priority

**CRITICAL** - This blocks all course generation functionality.
