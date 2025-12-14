# Bedrock Cost Analysis - Burst Usage Scenarios

## Quick Answer

**For occasional bursts (like lecture generation): NO, it won't cost a lot!**

Bedrock uses **On-Demand pricing** - you pay per token, no reservation fees. Perfect for occasional high usage.

---

## Pricing Model

Bedrock uses **On-Demand Pricing** (Standard Tier):
- **Pay per token**: Only pay for what you actually use
- **No monthly fees**: No reservation or subscription costs
- **No idle costs**: Zero cost when not in use

### Current Pricing (as of Dec 2024)

**Claude Sonnet 4.5** (our model):
- **Input tokens**: $0.003 per 1,000 tokens
- **Output tokens**: $0.015 per 1,000 tokens

**Claude 3.5 Sonnet** (reference pricing):
- **Input tokens**: $0.003 per 1,000 tokens  
- **Output tokens**: $0.015 per 1,000 tokens

**Bedrock Titan Embeddings**:
- **Input tokens**: $0.0001 per 1,000 tokens (very cheap!)

---

## Cost Examples

### Example 1: Book Metadata Extraction (Current Use Case)

**Per book ingestion**:
- Extracts text from first 15 pages (~10,000 tokens)
- Claude analyzes and returns metadata (~500 tokens)
- **Cost**: (10,000 × $0.003/1K) + (500 × $0.015/1K) = $0.03 + $0.0075 = **~$0.04 per book**

**Burst scenario**: Ingesting 10 books in a session
- **Total cost**: 10 × $0.04 = **$0.40** (40 cents!)

---

### Example 2: Lecture Generation (Your Use Case)

**Per lecture generation**:
- Input: Course material, book chapters, context (~50,000 tokens)
- Output: Generated lecture text (~20,000 tokens)
- **Cost**: (50,000 × $0.003/1K) + (20,000 × $0.015/1K) = $0.15 + $0.30 = **~$0.45 per lecture**

**Burst scenario**: Generating 5 lectures in one session
- **Total cost**: 5 × $0.45 = **$2.25** (two dollars and twenty-five cents)

**Even bigger burst**: Generating 20 lectures (full course)
- **Total cost**: 20 × $0.45 = **$9.00** (nine dollars)

---

### Example 3: Document Processing (Chunking + Embeddings)

**Per book processing**:
- Text extraction and chunking (handled locally/in Lambda)
- Embeddings: ~100,000 tokens (for a typical book)
- **Cost**: 100,000 × $0.0001/1K = **$0.01 per book** (1 cent!)

**Burst scenario**: Processing 50 books
- **Total cost**: 50 × $0.01 = **$0.50** (50 cents)

---

## Monthly Cost Scenarios

### Light Usage (Testing/Development)
- 10 book ingests: $0.40
- 5 lecture generations: $2.25
- 10 books processed: $0.10
- **Total: ~$3/month**

### Moderate Usage (Active Development)
- 50 book ingests: $2.00
- 20 lecture generations: $9.00
- 50 books processed: $0.50
- **Total: ~$12/month**

### Heavy Usage (Full Course Generation)
- 100 book ingests: $4.00
- 100 lecture generations: $45.00
- 100 books processed: $1.00
- **Total: ~$50/month**

---

## Rate Limit Increases (No Additional Cost!)

**Important**: Requesting a higher rate limit on Standard Tier:
- ✅ **No additional fees**
- ✅ **No subscription costs**
- ✅ **Still pay per token** (same pricing)
- ✅ **Just allows you to burst faster**

**What you're requesting**:
- Increase from 3 requests/minute → 100 requests/minute
- This just means you can make requests faster
- **Still pay the same per token**!

**Cost impact**: $0.00 (zero additional cost)

---

## Service Tiers Comparison

### Standard Tier (Recommended for You)
- **Pricing**: Pay per token (listed above)
- **Rate limits**: Default low, but can request increases (FREE)
- **Best for**: Occasional bursts, unpredictable usage
- **Cost**: Only pay for actual usage

### Priority Tier (Not Needed)
- **Pricing**: ~2x Standard Tier per token
- **Rate limits**: Much higher by default
- **Best for**: Sustained high throughput, guaranteed performance
- **Cost**: Higher per token + you still pay even if not using it

### Flex Tier (Not Needed)
- **Pricing**: Lower per token (~20% discount)
- **Rate limits**: Lower priority processing
- **Best for**: Non-time-critical batch jobs
- **Cost**: Cheaper but slower

**Recommendation**: **Stay on Standard Tier** - perfect for occasional bursts!

---

## Cost Optimization Tips

1. **Request limit increase** (FREE): Handle bursts without throttling
2. **Cache responses**: Store lecture outputs, don't regenerate
3. **Batch operations**: Process multiple items in one Lambda invocation
4. **Right-size inputs**: Don't send more context than needed
5. **Monitor usage**: Set up CloudWatch alarms for unexpected spikes

---

## Cost Monitoring

Track your Bedrock costs via:
1. **AWS Cost Explorer**: Shows actual charges
2. **CloudWatch Metrics**: Track token usage in real-time
3. **Billing Alerts**: Set thresholds (e.g., $50, $100/month)

**Current estimate** (from migration guide):
- Bedrock: $20-30/month during active development
- This includes all Claude + Titan usage

---

## Summary

✅ **Occasional bursts are CHEAP** - pay per use, no reservation fees  
✅ **Request limit increase is FREE** - no additional cost  
✅ **Standard Tier is perfect** - don't need Priority Tier  
✅ **Even heavy usage is reasonable** - $50/month for 100 lectures  

**Your use case** (occasional lecture generation bursts):
- **Cost per lecture**: ~$0.45
- **Cost per burst session** (5 lectures): ~$2.25
- **Monthly cost** (20 lectures): ~$9-10

**Conclusion**: Bedrock costs scale linearly with usage. Occasional bursts won't break the bank!

