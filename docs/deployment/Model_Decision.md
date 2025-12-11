# Model Selection Decision

## Final Decision: Claude Sonnet 4.5

We've standardized on **Claude Sonnet 4.5** (September 2025) as our primary model for all LLM tasks.

## Rationale

### Why Sonnet 4.5?
- ✅ **Excellent Quality**: Provides 5/5 quality for all tasks (figure descriptions, classification, chat)
- ✅ **Fast**: Significantly faster than Opus (2-3x faster)
- ✅ **Cost-Effective**: Much cheaper than Opus (3-5x cheaper) without sacrificing quality
- ✅ **No Marketplace**: No AWS Marketplace subscription required
- ✅ **Reliable**: Well-tested and stable
- ✅ **ACTIVE Status**: Not marked as LEGACY

### Why Not Opus 4.5?
- ❌ **Expensive**: 3-5x more expensive than Sonnet
- ❌ **Slower**: Significantly slower response times
- ❌ **Marketplace Required**: Requires AWS Marketplace subscription (adds complexity)
- ❌ **Diminishing Returns**: Quality improvement doesn't justify cost/speed tradeoff
- ❌ **Overkill**: Sonnet 4.5 already provides excellent quality for all use cases

## Usage

### All Tasks Use Sonnet 4.5:
- **Figure Descriptions**: Sonnet 4.5 (temperature 0.2, max_tokens 2000)
- **Caption Classification**: Sonnet 4.5 (temperature 0.2, max_tokens 2000)
- **Future Chat/QA**: Sonnet 4.5 (temperature 0.7, max_tokens 4096)

### Quality Settings:
- **Factual Tasks** (descriptions, classification): Temperature 0.2
- **Creative Tasks** (chat, Q&A): Temperature 0.7
- **Max Tokens**: 2000 for descriptions, 4096 for chat

## Conclusion

Sonnet 4.5 provides the best balance of quality, speed, and cost for all use cases. There's no need for Opus 4.5 - Sonnet 4.5 already delivers excellent results.

