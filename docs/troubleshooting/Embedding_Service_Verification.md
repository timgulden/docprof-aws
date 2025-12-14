# Embedding Service Verification

## Summary
✅ **Both ingestion and queries use the same embedding service**

## Embedding Service Details

### Service Used
- **Model**: `amazon.titan-embed-text-v1` (AWS Bedrock Titan)
- **Dimensions**: 1536
- **Normalization**: Yes (unit length vectors)
- **Location**: `src/lambda/shared/bedrock_client.py::generate_embeddings()`

### Ingestion Pipeline
- **Function**: `AWSEmbeddingClient.embed_texts()` → `generate_embeddings()`
- **Normalization**: `normalize=True` (default)
- **Usage**: Called during book ingestion to generate embeddings for chunks
- **File**: `src/lambda/shared/protocol_implementations.py`

### Query Pipeline
- **Function**: `generate_embeddings([expanded_query], normalize=True)`
- **Normalization**: `normalize=True` (explicit)
- **Usage**: Called in chat handler to generate query embedding
- **File**: `src/lambda/chat_handler/handler.py`

## Verification

Both paths use:
1. Same model: `amazon.titan-embed-text-v1`
2. Same normalization: `normalize=True`
3. Same dimensions: 1536

This ensures query embeddings are compatible with stored chunk embeddings.

## Differences from MAExpert

- **MAExpert**: Used OpenAI `text-embedding-ada-002` (1536 dimensions, normalized)
- **DocProf AWS**: Uses AWS Bedrock Titan `amazon.titan-embed-text-v1` (1536 dimensions, normalized)

Since the embedding models are different, similarity thresholds may need adjustment:
- OpenAI embeddings: Typically use thresholds 0.7-0.8
- Titan embeddings: May need lower thresholds (0.5-0.6) or no threshold (top K)

## Current Search Strategy

The chat handler now:
1. Tries progressively lower thresholds: 0.6 → 0.5 → 0.4 → 0.3 → 0.2 → 0.0 (no threshold)
2. Targets at least 10 results
3. Returns top K by similarity if threshold filtering doesn't yield enough results

This ensures we always get results when chunks have embeddings.
