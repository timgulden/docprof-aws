# Bedrock Model Selection

## Current Configuration

We're using **Claude Sonnet 4.5** (September 2025) as our standard model:
- Model: `anthropic.claude-sonnet-4-5-20250929-v1:0`
- Inference Profile: `us.anthropic.claude-sonnet-4-5-20250929-v1:0`
- Status: ACTIVE
- Rationale: Excellent quality (5/5), fast, cost-effective, no Marketplace required

## Available Models

### ACTIVE Models (Recommended)
- **Claude Sonnet 4** (`anthropic.claude-sonnet-4-20250514-v1:0`) - NEWEST, but may require use case form
- **Claude Sonnet 4.5** (`anthropic.claude-sonnet-4-5-20250929-v1:0`) - NEWEST, but may require use case form
- **Claude 3.7 Sonnet** (`anthropic.claude-3-7-sonnet-20250219-v1:0`) - ACTIVE, but requires inference profile

### LEGACY Models (Not Recommended)
- **Claude 3 Sonnet** (`anthropic.claude-3-sonnet-20240229-v1:0`) - LEGACY (what we were using)
- **Claude 3.5 Sonnet v2** (`anthropic.claude-3-5-sonnet-20241022-v2:0`) - LEGACY

## Why Claude Sonnet 4.5?

1. **Newest Model**: Claude Sonnet 4.5 is the latest and most capable model (September 2025)
2. **Best Performance**: Significantly better than Claude 3.x models
3. **Has Inference Profile**: System-defined inference profile available (no custom setup needed)
4. **ACTIVE Status**: Not marked as LEGACY
5. **Vision Support**: Full vision capabilities for figure description
6. **Future-Proof**: Latest model ensures we're using best available technology

## Future Upgrades

When Claude Sonnet 4/4.5 inference profiles become available, we can upgrade to:
- Better performance
- Newer capabilities
- Still ACTIVE status

## Embeddings

We're using **Amazon Titan Embeddings v1** (`amazon.titan-embed-text-v1`):
- 1536 dimensions
- Fast and reliable
- No inference profile needed

## Model Usage

- **Figure Descriptions**: Claude 3.5 Sonnet (vision)
- **Caption Classification**: Claude 3.5 Sonnet (vision)
- **Text Embeddings**: Amazon Titan Embeddings v1
- **Future Chat/QA**: Claude 3.5 Sonnet (text)

