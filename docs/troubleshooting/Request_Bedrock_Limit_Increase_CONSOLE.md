# Request Bedrock Rate Limit Increase via Service Quotas Console

## Based on AWS Support AI Guidance

AWS Support recommends using the **Service Quotas console** (not API) to request increases. Here's the step-by-step process.

---

## Step-by-Step Instructions

### 1. Open Service Quotas Console

Go to: **https://console.aws.amazon.com/servicequotas/**

Or navigate:
- AWS Console → Service Quotas → AWS services → Amazon Bedrock

### 2. Search for Bedrock Quotas

1. In the left sidebar, click **"AWS services"**
2. Search for **"Amazon Bedrock"**
3. Click on **"Amazon Bedrock"**

### 3. Find the Token Quota

**Important**: Claude Sonnet 4.5 (accessed via inference profile) uses the same quotas as Claude 3.5 Sonnet. Search for:

**"On-demand model inference tokens per minute for Anthropic Claude 3.5 Sonnet"**

**Quota Code**: `L-A50569E5`

You should see:
- **Current quota value**: 400,000 tokens/minute
- **Usage**: Check if you have any current usage
- **Note**: This quota applies to both Claude 3.5 Sonnet and Claude 4.5 Sonnet (via inference profile)

### 4. Request Quota Increase

1. Click on the quota name to open details
2. Click **"Request quota increase"** button
3. Fill in the form:

   **Requested quota value**: `1000000` (1,000,000 tokens per minute)
   
   **Use case description** (copy/paste this):
   ```
   I am developing an educational document processing platform that uses Claude Sonnet 4.5 (via inference profile us.anthropic.claude-sonnet-4-5-20250929-v1:0) for:
   
   1. Book metadata extraction during ingestion
   2. Lecture generation from course materials
   
   Current Usage Patterns:
   - During book ingestion: Process 5-10 books in a session, each requiring 10-15K input tokens and 500 output tokens
   - During lecture generation: Generate 3-5 lectures per session, each requiring 50K input tokens and 20K output tokens
   - Usage is bursty - high activity during processing sessions, followed by idle periods
   
   Current Limitation:
   - 400,000 tokens/minute limit is insufficient for lecture generation bursts
   - A single lecture generation can require 70K tokens (50K in + 20K out)
   - Processing 5 lectures in quick succession would require 350K tokens, approaching the limit
   - When combined with concurrent book processing, we hit rate limits
   
   Business Justification:
   - Educational platform for document analysis and course generation
   - Bursty workload is inherent to the use case (users process batches of documents)
   - Need to support realistic workflows without rate limit errors
   - Usage patterns show clear peaks during processing sessions
   
   Requested Increase:
   - Tokens per minute: 400,000 → 1,000,000
   - This will allow processing 10-15 lectures per minute during bursts, which matches our actual usage patterns
   
   Note: I would also like to request an increase for requests per minute (quota code L-254CACF4) from 3 to 100 requests/minute, as the current limit of 3 requests/minute creates bottlenecks even when token limits are sufficient.
   
   Account: 176520790264
   Region: us-east-1
   Model: Claude Sonnet 4.5 (inference profile: us.anthropic.claude-sonnet-4-5-20250929-v1:0)
   
   Note: Claude Sonnet 4.5 is accessed via inference profile and uses the same quotas as Claude 3.5 Sonnet, so I am requesting increases for the Claude 3.5 Sonnet quotas (L-A50569E5 for tokens, L-254CACF4 for requests) which will apply to Claude 4.5 Sonnet usage.
   ```

4. Click **"Request"**

### 5. Request Requests Per Minute Increase (Separate Request)

After submitting the tokens request, also submit a request for:

**Quota**: **"On-demand model inference requests per minute for Anthropic Claude 3.5 Sonnet"**

**Quota Code**: `L-254CACF4`

**Note**: This quota applies to both Claude 3.5 Sonnet and Claude 4.5 Sonnet (via inference profile)

**Requested value**: `100` requests/minute

**Use case description**:
```
This request is related to my token quota increase request (L-A50569E5). 

Even with sufficient token capacity, the 3 requests/minute limit creates bottlenecks. During book processing sessions, we may need to process multiple books concurrently, and during lecture generation, we need to generate multiple lectures in sequence.

Current limitation of 3 requests/minute means we can only process 3 operations per minute, which is insufficient for batch processing workflows.

Requested: 3 → 100 requests/minute to support concurrent and batch processing.

Account: 176520790264
Region: us-east-1
```

### 6. Check Request Status

1. In Service Quotas console, go to **"Quota increase requests"** in the left sidebar
2. You'll see your pending requests
3. AWS typically responds within 24-48 hours (often faster)

---

## Important Notes

### Bundled Quota Request

According to AWS Support AI, you can mention in your request that you'd like both quotas increased together. However, submit the tokens quota first (as recommended), and when support contacts you, confirm you also want the requests quota increased.

### Usage Demonstration

AWS prioritizes customers who are actively using their quotas. If your request is initially denied:
- Continue using the service and generating traffic
- Document when you hit rate limits (check CloudWatch logs)
- Resubmit with actual usage data showing you're approaching limits

### Alternative: Priority Contact

If the console method doesn't work, you can also open a support case:
- AWS Support Center → Create case → Service limit increase
- Reference the quota codes and use case description above

---

## While Waiting for Approval

✅ **Retry logic is already deployed** - handles throttling gracefully  
✅ **System still works** - just slower during bursts  
✅ **No code changes needed** - works automatically after approval  

---

## Verification After Approval

Check that limits were increased:

```bash
export AWS_PROFILE=docprof-dev

# Check tokens quota
aws service-quotas get-service-quota \
  --service-code bedrock \
  --quota-code L-A50569E5 \
  --region us-east-1 \
  --query 'Quota.Value'

# Check requests quota  
aws service-quotas get-service-quota \
  --service-code bedrock \
  --quota-code L-254CACF4 \
  --region us-east-1 \
  --query 'Quota.Value'
```

Expected values after approval:
- Tokens: 1000000
- Requests: 100

