# Quality Optimization for DocProf

## Model Selection Strategy

Since **quality is prioritized over cost**, we use the best available models:

### Figure Descriptions: Claude Sonnet 4.5
- **Model**: Claude Sonnet 4.5 (September 2025)
- **Why**: Excellent quality, produces detailed and accurate figure descriptions
- **Note**: Opus 4.5 requires AWS Marketplace subscription - Sonnet 4.5 provides excellent quality without Marketplace
- **Use Case**: Critical for semantic search - better descriptions = better retrieval
- **Settings**:
  - Temperature: 0.2 (lower for more factual, consistent descriptions)
  - Max Tokens: 2000 (allows for detailed descriptions)
  - Structured output: Includes key takeaways and use cases

### Caption Classification: Claude Sonnet 4.5
- **Model**: Claude Sonnet 4.5 (September 2025)
- **Why**: Excellent quality, faster than Opus, sufficient for classification task
- **Use Case**: One-time classification per book - speed matters less than accuracy
- **Settings**:
  - Temperature: 0.2 (lower for consistent classification)
  - Max Tokens: 2000

### Text Embeddings: Amazon Titan Embeddings v1
- **Model**: Amazon Titan Embeddings v1
- **Why**: Fast, reliable, 1536 dimensions (matches OpenAI)
- **Use Case**: Bulk embedding generation - speed matters

## Quality Settings

### Temperature
- **Figure Descriptions**: 0.2 (factual, consistent)
- **Caption Classification**: 0.2 (consistent decisions)
- **Future Chat/QA**: 0.7 (creative, conversational)

### Max Tokens
- **Figure Descriptions**: 2000 (allows detailed descriptions)
- **Caption Classification**: 2000 (allows reasoning)
- **Future Chat/QA**: 4096 (standard)

### System Prompts
- **Figure Descriptions**: Expert analyst persona, structured output format
- **Caption Classification**: Clear classification criteria, JSON output format

## Cost vs Quality Tradeoffs

| Task | Model | Quality | Speed | Cost | Rationale |
|------|-------|---------|-------|------|-----------|
| Figure Descriptions | Sonnet 4.5 | ⭐⭐⭐⭐⭐ | Fast | Medium | Excellent quality, no Marketplace needed |
| Caption Classification | Sonnet 4.5 | ⭐⭐⭐⭐ | Fast | Medium | One-time task, Sonnet sufficient |
| Text Embeddings | Titan v1 | ⭐⭐⭐⭐ | Fast | Low | Bulk operation, Titan sufficient |
| Future Chat/QA | Sonnet 4.5 | ⭐⭐⭐⭐ | Fast | Medium | Good balance for interactive use |

## Future Optimizations

If quality needs increase further:
1. **Use Opus 4.5 for all tasks** - Highest quality across the board
2. **Increase max_tokens** - Allow more detailed responses
3. **Fine-tune prompts** - Optimize system prompts for better output
4. **Add structured output** - Use Claude's structured output features

## Current Configuration

- ✅ Claude Sonnet 4.5 for figure descriptions (excellent quality, no Marketplace)
- ✅ Claude Sonnet 4.5 for classification (excellent quality)
- ✅ Optimized temperature settings (0.2 for factual tasks)
- ✅ Increased max_tokens (2000 for detailed descriptions)
- ✅ Structured output format (key takeaways, use cases)

## Why Sonnet 4.5 Over Opus 4.5?

**Claude Sonnet 4.5** is our standard model because:
- ✅ **Excellent Quality**: Provides 5/5 quality for all tasks
- ✅ **Fast**: Significantly faster than Opus
- ✅ **Cost-Effective**: Much cheaper than Opus without sacrificing quality
- ✅ **No Marketplace**: No AWS Marketplace subscription required
- ✅ **Reliable**: Well-tested and stable

**Claude Opus 4.5** was considered but rejected because:
- ❌ **Expensive**: 3-5x more expensive than Sonnet
- ❌ **Slower**: Significantly slower response times
- ❌ **Marketplace Required**: Requires AWS Marketplace subscription
- ❌ **Diminishing Returns**: Quality improvement doesn't justify cost/speed tradeoff

**Conclusion**: Sonnet 4.5 provides the best balance of quality, speed, and cost for all use cases.

