# Ingestion Pipeline Migration Plan

**Purpose**: Migrate from MAExpert's ingestion pipeline to a fully AWS-native implementation  
**Goal**: Create a clean showcase of AWS serverless tools while preserving FP architecture  
**Date**: 2025-12-12

---

## Executive Summary

This plan migrates the document ingestion pipeline from MAExpert's `run_ingestion_pipeline` to a fully AWS-native implementation that:

1. **Extracts pure logic** from MAExpert into `shared/logic/ingestion.py`
2. **Uses AWS-native orchestration** (Step Functions or Lambda orchestration)
3. **Leverages existing AWS adapters** (`AWSDatabaseClient`, `AWSEmbeddingClient`, etc.)
4. **Follows FP principles** from `FP_to_Serverless_Mapping.md`
5. **Eliminates MAExpert dependencies** - fully self-contained

---

## Current State Analysis

### What MAExpert's Pipeline Does

The `run_ingestion_pipeline` function in `MAExpert/src/effects/ingestion_effects.py` performs:

1. **Load PDF** - Read PDF from file system
2. **Extract Text** - Extract text from all pages using PyMuPDF
3. **Extract Figures** - Extract images from PDF pages
4. **Classify Figures** - Use LLM to classify figure types (Figure, Table, Exhibit, etc.)
5. **Build Chunks** - Split text into semantic chunks with overlap
6. **Generate Embeddings** - Create vector embeddings for chunks
7. **Store in Database** - Insert chunks, figures, and embeddings
8. **Extract Cover** - Extract first page as cover image
9. **Update Metrics** - Track ingestion progress

### Current AWS Implementation

- ✅ **Protocol Adapters**: `AWSDatabaseClient`, `AWSEmbeddingClient`, `AWSFigureDescriptionClient` exist
- ✅ **Cover Extraction**: `shared/cover_extractor.py` exists
- ✅ **Database Utilities**: `shared/db_utils.py` has chunk/figure insertion
- ⚠️ **Orchestration**: Still uses MAExpert's `run_ingestion_pipeline` function
- ⚠️ **Logic**: Not extracted - still importing from MAExpert

---

## Migration Strategy

### Principle 1: Extract Logic, Own It Forever

**From FP_to_Serverless_Mapping.md:**
> Logic is extracted from MAExpert prototype and owned by this codebase - not copied from external source

**Action**: Extract ingestion logic from MAExpert into `shared/logic/ingestion.py`

### Principle 2: Pure Functions → Direct Reuse

**From FP_to_Serverless_Mapping.md:**
> Pure functions are stateless and side-effect-free, making them perfect for Lambda

**Action**: Identify pure logic functions (chunking, text processing) and extract them

### Principle 3: Effects → Service Adapters

**From FP_to_Serverless_Mapping.md:**
> Effect functions have stable signatures but different implementations

**Action**: Use existing AWS adapters (`AWSDatabaseClient`, `AWSEmbeddingClient`)

### Principle 4: Complex Workflows → Step Functions

**From FP_to_Serverless_Mapping.md:**
> Stack-based interceptors become Step Functions state machine

**Action**: Design Step Functions workflow for ingestion pipeline

---

## Architecture Design

### Option A: Step Functions Orchestration (Recommended for Showcase)

**Why**: Best showcases AWS orchestration capabilities, handles long-running workflows, built-in retries

```
S3 Event → Step Functions State Machine
  ├─→ Extract Text (Lambda)
  ├─→ Extract Figures (Lambda) 
  ├─→ Extract Cover (Lambda)
  ├─→ Build Chunks (Lambda) - Pure logic
  ├─→ Generate Embeddings (Map State - Parallel)
  │    ├─→ Embed Chunk 1 (Lambda)
  │    ├─→ Embed Chunk 2 (Lambda)
  │    └─→ ... (up to 10 parallel)
  ├─→ Store Chunks (Lambda)
  ├─→ Classify Figures (Map State - Parallel)
  │    ├─→ Classify Figure 1 (Lambda)
  │    └─→ ... (parallel)
  └─→ Store Figures (Lambda)
```

**Benefits**:
- Visual workflow in AWS Console
- Built-in retry logic
- Parallel processing for embeddings/figures
- Error handling and dead-letter queues
- Cost-effective (pay per state transition)

### Option B: Lambda Orchestration (Simpler, Still Clean)

**Why**: Simpler to implement, still showcases AWS, easier to debug

```
S3 Event → Document Processor Lambda
  ├─→ Extract text (in-process)
  ├─→ Extract figures (in-process)
  ├─→ Extract cover (in-process)
  ├─→ Build chunks (pure logic - in-process)
  ├─→ Generate embeddings (parallel Lambda invocations)
  ├─→ Store chunks (in-process)
  ├─→ Classify figures (parallel Lambda invocations)
  └─→ Store figures (in-process)
```

**Benefits**:
- Simpler architecture
- Easier debugging (single Lambda)
- Still uses AWS services (Bedrock, Aurora)
- Can migrate to Step Functions later

---

## Implementation Plan

### Phase 1: Extract Pure Logic Functions

**Goal**: Identify and extract pure logic from MAExpert

**Tasks**:
1. **Extract chunking logic**
   - Location: `MAExpert/src/effects/chunk_builder.py`
   - Extract to: `shared/logic/chunking.py`
   - Function: `build_chunks(text: str, chunk_size: int, overlap: int) -> List[Chunk]`
   - Status: Pure function - no side effects

2. **Extract text extraction logic** (if any pure parts)
   - Most text extraction is effectful (file I/O)
   - Keep as effect, but ensure clean interface

3. **Extract figure extraction logic** (if any pure parts)
   - Most figure extraction is effectful (PDF parsing)
   - Keep as effect, but ensure clean interface

**Deliverable**: `shared/logic/chunking.py` with pure chunking functions

---

### Phase 2: Create Ingestion Orchestrator

**Goal**: Create clean orchestration that uses pure logic + AWS adapters

**Option A - Step Functions** (Recommended):

**Tasks**:
1. **Create Lambda functions for each step**:
   - `text_extractor` - Extract text from PDF
   - `figure_extractor` - Extract figures from PDF
   - `cover_extractor` - Extract cover (already exists)
   - `chunk_builder` - Build chunks (pure logic)
   - `embedding_generator` - Generate single embedding
   - `chunk_storer` - Store chunks in database
   - `figure_classifier` - Classify single figure
   - `figure_storer` - Store figures in database

2. **Create Step Functions state machine**:
   - Define workflow in Terraform
   - Use Map states for parallel processing
   - Add retry logic and error handling

3. **Update document_processor Lambda**:
   - Remove MAExpert imports
   - Trigger Step Functions instead of calling MAExpert pipeline

**Option B - Lambda Orchestration**:

**Tasks**:
1. **Create `shared/logic/ingestion.py`**:
   - Pure orchestration logic
   - Returns commands to execute
   - No side effects

2. **Create `shared/ingestion_orchestrator.py`**:
   - Orchestrates ingestion using pure logic
   - Executes commands using AWS adapters
   - Handles parallel processing (async/await)

3. **Update document_processor Lambda**:
   - Remove MAExpert imports
   - Use native orchestrator

---

### Phase 3: Implement Individual Steps

**Goal**: Implement each ingestion step as clean, testable functions

**Steps to Implement**:

1. **Text Extraction**
   - Input: PDF bytes from S3
   - Logic: Use PyMuPDF to extract text
   - Output: Structured text with page numbers
   - Location: `shared/pdf_utils.py` (may already exist)

2. **Figure Extraction**
   - Input: PDF bytes
   - Logic: Extract images from PDF pages
   - Output: List of figure images with metadata
   - Location: `shared/figure_extractor.py`

3. **Cover Extraction**
   - ✅ Already implemented: `shared/cover_extractor.py`

4. **Chunk Building**
   - Input: Text, chunk_size, overlap
   - Logic: Pure function - split text into chunks
   - Output: List of chunks
   - Location: `shared/logic/chunking.py`

5. **Embedding Generation**
   - Input: Text chunk
   - Logic: Call Bedrock Titan
   - Output: Vector embedding
   - Location: `shared/bedrock_client.py` (already exists)

6. **Figure Classification**
   - Input: Figure image + context
   - Logic: Call Bedrock Claude to classify
   - Output: Figure type and description
   - Location: `shared/bedrock_client.py` (already exists)

7. **Database Storage**
   - Input: Chunks/figures with embeddings
   - Logic: Insert into Aurora
   - Output: IDs of inserted records
   - Location: `shared/db_utils.py` (already exists)

---

### Phase 4: Remove MAExpert Dependencies

**Goal**: Eliminate all MAExpert imports from document_processor

**Tasks**:
1. Remove `from src.effects.ingestion_effects import run_ingestion_pipeline`
2. Remove `from src.effects.chunk_builder import ChunkBuilder`
3. Remove all sys.path manipulation for MAExpert
4. Remove monkey-patching code
5. Update imports to use `shared.*` modules

**Deliverable**: `document_processor/handler.py` with zero MAExpert dependencies

---

## Detailed Implementation: Option A (Step Functions)

### Step Functions State Machine

```json
{
  "Comment": "Document ingestion pipeline - AWS-native implementation",
  "StartAt": "ExtractText",
  "States": {
    "ExtractText": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:function:text-extractor",
      "Next": "ExtractFigures",
      "Retry": [{
        "ErrorEquals": ["States.TaskFailed"],
        "MaxAttempts": 3,
        "BackoffRate": 2.0
      }]
    },
    "ExtractFigures": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:function:figure-extractor",
      "Next": "ExtractCover"
    },
    "ExtractCover": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:function:cover-extractor",
      "Next": "BuildChunks"
    },
    "BuildChunks": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:function:chunk-builder",
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
            "Resource": "arn:aws:lambda:...:function:embedding-generator",
            "End": true
          }
        }
      },
      "Next": "StoreChunks"
    },
    "StoreChunks": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:function:chunk-storer",
      "Next": "ClassifyFigures"
    },
    "ClassifyFigures": {
      "Type": "Map",
      "ItemsPath": "$.figures",
      "MaxConcurrency": 5,
      "Iterator": {
        "StartAt": "ClassifyFigure",
        "States": {
          "ClassifyFigure": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:...:function:figure-classifier",
            "End": true
          }
        }
      },
      "Next": "StoreFigures"
    },
    "StoreFigures": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:function:figure-storer",
      "End": true
    }
  }
}
```

### Lambda Functions

Each Lambda function follows the pattern:

```python
# src/lambda/text_extractor/handler.py
from shared.pdf_utils import extract_text_from_pdf
from shared.response import success_response, error_response

def lambda_handler(event, context):
    """Extract text from PDF."""
    try:
        # Get PDF from S3
        s3_key = event['s3_key']
        pdf_bytes = download_from_s3(s3_key)
        
        # Extract text (pure logic or effect)
        text_data = extract_text_from_pdf(pdf_bytes)
        
        return success_response(text_data)
    except Exception as e:
        return error_response(str(e))
```

---

## Detailed Implementation: Option B (Lambda Orchestration)

### Pure Orchestration Logic

```python
# shared/logic/ingestion.py
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class IngestionState:
    """Immutable ingestion state"""
    book_id: str
    pdf_bytes: bytes
    text_data: Optional[Dict] = None
    figures: List[Dict] = None
    chunks: List[Dict] = None
    embeddings: List[List[float]] = None

def plan_ingestion_steps(state: IngestionState) -> List[str]:
    """Pure function - returns list of steps to execute"""
    steps = ['extract_text', 'extract_figures', 'extract_cover']
    
    if state.text_data:
        steps.append('build_chunks')
    
    if state.chunks:
        steps.append('generate_embeddings')
        steps.append('store_chunks')
    
    if state.figures:
        steps.append('classify_figures')
        steps.append('store_figures')
    
    return steps
```

### Orchestrator

```python
# shared/ingestion_orchestrator.py
from shared.logic.ingestion import plan_ingestion_steps, IngestionState
from shared.pdf_utils import extract_text_from_pdf
from shared.figure_extractor import extract_figures_from_pdf
from shared.cover_extractor import extract_cover_from_pdf_bytes
from shared.logic.chunking import build_chunks
from shared.bedrock_client import generate_embeddings
from shared.db_utils import insert_chunks_batch, insert_figures_batch
from shared.protocol_implementations import AWSDatabaseClient

async def run_ingestion_pipeline(
    book_id: str,
    pdf_bytes: bytes,
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """AWS-native ingestion pipeline orchestrator"""
    
    state = IngestionState(book_id=book_id, pdf_bytes=pdf_bytes)
    database = AWSDatabaseClient()
    
    # Step 1: Extract text
    state.text_data = extract_text_from_pdf(pdf_bytes)
    
    # Step 2: Extract figures
    state.figures = extract_figures_from_pdf(pdf_bytes, book_id)
    
    # Step 3: Extract cover
    cover_bytes, cover_format = extract_cover_from_pdf_bytes(pdf_bytes)
    database.update_book_cover(book_id, cover_bytes, cover_format)
    
    # Step 4: Build chunks (pure logic)
    state.chunks = build_chunks(
        text=state.text_data['text'],
        chunk_size=1000,
        overlap=200
    )
    
    # Step 5: Generate embeddings (parallel)
    chunk_texts = [chunk['content'] for chunk in state.chunks]
    state.embeddings = await generate_embeddings_parallel(chunk_texts)
    
    # Step 6: Store chunks
    insert_chunks_batch(book_id, state.chunks, state.embeddings)
    
    # Step 7: Classify figures (parallel)
    classified_figures = await classify_figures_parallel(state.figures)
    
    # Step 8: Store figures
    insert_figures_batch(book_id, classified_figures)
    
    return {
        'book_id': book_id,
        'chunks_created': len(state.chunks),
        'figures_created': len(state.figures)
    }
```

---

## Recommendation: Option B (Lambda Orchestration)

**Why Option B for this showcase:**

1. **Simpler to understand** - Single Lambda, clear flow
2. **Easier to debug** - All code in one place
3. **Still showcases AWS** - Uses Bedrock, Aurora, S3
4. **Follows FP principles** - Pure logic separated from effects
5. **Can migrate to Step Functions later** - If needed for scale

**Step Functions can be added later** if we need:
- Visual workflow monitoring
- Complex retry logic
- Very long-running workflows (>15 minutes)

---

## Implementation Checklist

### Phase 1: Extract Logic ✅
- [ ] Extract chunking logic to `shared/logic/chunking.py`
- [ ] Extract any other pure logic functions
- [ ] Create `shared/logic/ingestion.py` for orchestration logic

### Phase 2: Create Effect Functions
- [ ] Create `shared/pdf_utils.py` for text extraction
- [ ] Create `shared/figure_extractor.py` for figure extraction
- [ ] Verify `shared/cover_extractor.py` is complete
- [ ] Verify `shared/bedrock_client.py` has embedding/classification
- [ ] Verify `shared/db_utils.py` has storage functions

### Phase 3: Create Orchestrator
- [ ] Create `shared/ingestion_orchestrator.py`
- [ ] Implement async parallel processing for embeddings
- [ ] Implement async parallel processing for figure classification
- [ ] Add error handling and logging

### Phase 4: Update Document Processor
- [ ] Remove MAExpert imports
- [ ] Remove sys.path manipulation
- [ ] Remove monkey-patching code
- [ ] Use native orchestrator
- [ ] Test end-to-end

### Phase 5: Testing & Validation
- [ ] Test with sample PDF
- [ ] Verify chunks are created correctly
- [ ] Verify figures are extracted and classified
- [ ] Verify cover is extracted
- [ ] Verify embeddings are generated
- [ ] Verify data is stored in database

---

## Benefits of This Approach

1. **Clean Architecture** - Follows FP principles, no monkey-patching
2. **AWS Showcase** - Demonstrates Bedrock, Aurora, Lambda, S3
3. **Maintainable** - All code owned by this project
4. **Testable** - Pure logic functions easy to test
5. **Scalable** - Can migrate to Step Functions if needed
6. **Self-Contained** - No external MAExpert dependencies

---

## Next Steps

1. **Review this plan** - Confirm approach (Option A vs B)
2. **Start with Phase 1** - Extract chunking logic
3. **Iterate** - Build incrementally, test as we go
4. **Document** - Update architecture docs as we implement

---

*This plan ensures we create a clean, maintainable, AWS-native ingestion pipeline that showcases best practices while preserving the valuable FP architecture patterns.*

