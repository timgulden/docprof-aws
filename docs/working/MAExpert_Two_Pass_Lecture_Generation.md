# MAExpert Two-Pass Lecture Generation Implementation

**Date:** December 26, 2025  
**Status:** ✅ Implemented and deployed

## Overview

Successfully replicated MAExpert's two-pass objective-by-objective lecture generation approach in the AWS serverless architecture.

## Architecture Decision

### **Chosen Approach: Synchronous in Lambda** ✅

**Why Synchronous:**
- User is actively waiting for the lecture (immediate need)
- Most sections have 3-5 objectives = ~2-3 minutes generation time
- Simpler to implement and debug
- Avoids complexity of async EventBridge orchestration
- **Timeout:** Increased from 120s to 600s (10 minutes) to accommodate multi-objective generation

**Alternative Considered:**
- Async with EventBridge (like course creation pipeline)
- Would be needed for sections with 10+ objectives or if we add more sophisticated processing
- Can be migrated later if needed without changing the logic layer

## Implementation Details

### **Pass 1: Objective-by-Objective Generation**

For each learning objective in the section:

1. **Search for objective-specific chunks** using `SearchCorpusCommand`
   - Query: the objective text itself
   - Retrieves 5 chapters + 2 summaries per objective
   - Chunk types: `["chapter", "source_summary"]`

2. **Combine chunks with deduplication**
   - Section-level chunks (already retrieved once)
   - Objective-specific chunks (just retrieved)
   - Deduplicate by `chunk_id`
   - Track all chunks used across objectives

3. **Generate content** using `generate_objective_content()`
   - Pure logic function from MAExpert
   - Takes `state`, `objective_index`, and `chunks`
   - Returns `LLMCommand` to generate content for that objective
   - Execute command and collect the generated content

4. **Accumulate objective contents**
   - Store each objective's generated content
   - Track: objective text, generated content, index

### **Pass 2: Refinement and Integration**

1. **Combine all objective contents** into a draft lecture
   - Format: `## Learning Objective {idx}: {objective}\n\n{content}`
   - All objectives concatenated with clear section headers

2. **Update state with draft**
   - Set `state.current_section_draft` to the combined draft
   - This allows `refine_section_lecture` to access the draft

3. **Refine the complete lecture** using `refine_section_lecture()`
   - Pure logic function from MAExpert
   - Takes only `state` (reads draft from `state.current_section_draft`)
   - Returns `LLMCommand` to refine and integrate all objectives
   - Ensures flow, style consistency, and pedagogical quality
   - Matches the style of previous lectures

4. **Store the final lecture**
   - Execute storage command
   - Return lecture script and delivery ID to the frontend

## Files Modified

### 1. `/src/lambda/section_lecture_handler/handler.py`

**Changes:**
- Replaced single-pass generation with two-pass approach
- Updated function signature: returns `tuple[str, str, str]` (added `model_switch_notification`)
- Added imports: `generate_objective_content`, `refine_section_lecture`
- Implemented Pass 1 loop: objective search → generate → accumulate
- Implemented Pass 2: combine draft → update state → refine
- Added detailed logging for each pass

**Key Logic:**
```python
# Pass 1: Loop through objectives
for idx, objective in enumerate(section.learning_objectives, 1):
    # Search for objective-specific chunks
    search_cmd = SearchCorpusCommand(...)
    objective_chunks = execute_command(search_cmd)
    
    # Combine + deduplicate with section chunks
    unique_chunks = deduplicate(section_chunks + objective_chunks)
    
    # Generate content for this objective
    result = generate_objective_content(state, idx - 1, unique_chunks)
    llm_cmd = result.commands[0]
    content = execute_command(llm_cmd)
    
    objective_contents.append(content)

# Pass 2: Refine complete draft
draft_lecture = combine_objectives(objective_contents)
state = state.model_copy(update={"current_section_draft": draft_lecture})
result = refine_section_lecture(state)
lecture_script = execute_command(result.commands[0])
```

### 2. `/terraform/environments/dev/main.tf`

**Changes:**
- Increased `section-lecture-handler` timeout from 120s to 600s (10 minutes)
- Updated comment to reflect two-pass generation

### 3. Deployment

**Method:** Direct Lambda code update (bypassing Terraform to avoid Docker issue)

```bash
# Package and deploy handler
cd src/lambda/section_lecture_handler
zip -r /tmp/section-lecture-handler.zip . -x "*.pyc" "__pycache__/*"
aws lambda update-function-code \
  --function-name docprof-dev-section-lecture-handler \
  --zip-file fileb:///tmp/section-lecture-handler.zip

# Update timeout
aws lambda update-function-configuration \
  --function-name docprof-dev-section-lecture-handler \
  --timeout 600
```

**Status:** ✅ Deployed successfully
- Timeout: 600s
- CodeSize: 5762 bytes
- LastUpdateStatus: Successful

## Benefits of Two-Pass Approach

### **Compared to Single-Pass:**

1. **More comprehensive source coverage**
   - Each objective gets its own targeted chunk retrieval
   - Section-level chunks provide broad context
   - Objective-level chunks provide specific details
   - Deduplication ensures efficiency without redundancy

2. **Better content quality**
   - Each objective addressed individually with focused prompting
   - LLM can concentrate on one learning goal at a time
   - Refinement pass ensures consistency and flow
   - Style and pedagogical quality maintained across objectives

3. **Matches proven MAExpert approach**
   - Same logic functions used (`generate_objective_content`, `refine_section_lecture`)
   - Proven effectiveness in production
   - Easier to maintain parity with legacy system

4. **More observable and debuggable**
   - Clear logging for each objective
   - Can see exactly which chunks were used for which objective
   - Pass 1 and Pass 2 clearly separated in logs

## Testing Status

- ✅ Lambda deployed
- ✅ Timeout increased to 600s
- ✅ Function signature corrected (`objective_index` is 0-based, pass `idx - 1`)
- ✅ State update for refinement (`current_section_draft` set before `refine_section_lecture`)
- ✅ No linter errors

**Next:** User testing via frontend UI

## Future Enhancements (if needed)

1. **Async EventBridge approach**
   - If sections with 10+ objectives become common
   - If we add more sophisticated processing (e.g., multimedia generation per objective)
   - Would require: state machine in DynamoDB, events per objective, aggregation event

2. **Parallel objective generation**
   - Could use AWS Step Functions to generate objectives in parallel
   - Would speed up generation for sections with many objectives
   - Trade-off: more complex orchestration, higher concurrency costs

3. **Caching**
   - Cache objective-specific chunks for reuse
   - Cache refined lectures for similar sections
   - Would reduce Bedrock API calls and costs

