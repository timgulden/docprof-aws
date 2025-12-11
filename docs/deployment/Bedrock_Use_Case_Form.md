# Bedrock Anthropic Use Case Form

## Overview

AWS Bedrock requires a one-time use case submission for Anthropic models (Claude). This is a simple form that typically takes a few minutes to complete and is usually approved instantly or within 15 minutes.

## How to Submit

1. **Go to AWS Bedrock Console**
   - Navigate to: https://console.aws.amazon.com/bedrock/
   - Select your region (us-east-1)

2. **Access Model Access Page**
   - Go to "Model access" in the left sidebar
   - Or use the direct link: https://console.aws.amazon.com/bedrock/home?region=us-east-1#/modelaccess

3. **Find Anthropic Models**
   - Look for Claude Sonnet 4.5 or Claude models section
   - Click "Request model access" or "Submit use case"

4. **Fill Out the Form**
   - **Use Case**: Educational content analysis, textbook processing, figure description
   - **Description**: "Processing educational textbooks to extract and describe figures, classify content, and generate embeddings for semantic search in an educational platform"
   - **Intended Use**: Educational/research purposes
   - **Content Type**: Educational materials, textbooks, academic content

5. **Submit and Wait**
   - Form is usually approved instantly or within 15 minutes
   - You'll receive an email confirmation when approved

## After Approval

Once approved:
- ✅ Claude Sonnet 4.5 will work immediately
- ✅ No Marketplace subscription needed (Sonnet 4.5 is serverless)
- ✅ Figure extraction will run automatically
- ✅ All LLM calls will work

## Testing After Approval

After submitting the form, wait 15 minutes, then test:

```bash
# Upload a test PDF
./scripts/upload_book.sh "/path/to/test.pdf" "Test Book" "Author" "1st" "2024"

# Monitor logs
AWS_PROFILE=docprof-dev aws logs tail /aws/lambda/docprof-dev-document-processor --since 5m --format short
```

## Troubleshooting

If you still see errors after approval:
1. Wait 15 minutes (approval can take time to propagate)
2. Check CloudWatch logs for specific error messages
3. Verify IAM permissions are correct (should already be configured)
4. Try invoking the model directly via AWS CLI to test:

```bash
# Test Bedrock access
AWS_PROFILE=docprof-dev aws bedrock-runtime invoke-model \
  --model-id "arn:aws:bedrock:us-east-1:YOUR_ACCOUNT_ID:inference-profile/us.anthropic.claude-sonnet-4-5-20250929-v1:0" \
  --body '{"anthropic_version":"bedrock-2023-05-31","max_tokens":100,"messages":[{"role":"user","content":"Hello"}]}' \
  output.json

cat output.json
```

## Notes

- **One-time submission**: Once approved, all Anthropic models in your account are enabled
- **No cost**: The form submission is free
- **Instant approval**: Usually approved within minutes
- **Account-wide**: Approval applies to all IAM users/roles in the account
