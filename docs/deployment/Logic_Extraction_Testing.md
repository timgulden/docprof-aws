# Logic Extraction Testing Guide

This guide walks through deploying and testing the extracted logic in Lambda runtime.

## Overview

We've extracted logic from MAExpert prototype into `src/lambda/shared/logic/` and `src/lambda/shared/core/`. This guide tests that:
1. Logic imports work correctly in Lambda runtime
2. Functions execute without import errors
3. Logic is properly packaged with Lambda functions

## Pre-Deployment Checklist

- [x] Logic extracted to `shared/logic/` and `shared/core/`
- [x] Imports updated to use `shared.*` pattern
- [x] Syntax validated (all files compile)
- [ ] Terraform infrastructure deployed
- [ ] Lambda layer built
- [ ] Chat handler Lambda deployed

## Deployment Steps

### 1. Build Lambda Layer (if needed)

The Lambda layer contains Python dependencies. Build it if it doesn't exist:

```bash
cd terraform/modules/lambda-layer
./build_layer_docker.sh
```

### 2. Deploy Infrastructure

Deploy or update Terraform to package and deploy the chat handler:

```bash
cd terraform/environments/dev

# Initialize (if needed)
terraform init

# See what will change
terraform plan

# Apply changes (this will package Lambda with shared/ directory)
terraform apply
```

**What Terraform does:**
- Lambda module automatically packages `src/lambda/chat_handler/` with `src/lambda/shared/`
- Creates ZIP file with handler + shared logic
- Deploys to AWS Lambda
- Attaches Lambda layer with Python dependencies

### 3. Test Lambda Function

Test that imports work correctly:

```bash
# From project root
./scripts/test_chat_handler.sh
```

Or manually invoke:

```bash
aws lambda invoke \
  --function-name docprof-dev-chat-handler \
  --payload '{"body": "{\"message\": \"test\", \"session_id\": \"test-123\"}", "httpMethod": "POST"}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/response.json

cat /tmp/response.json | python3 -m json.tool
```

### 4. Check CloudWatch Logs

Check for import errors:

```bash
aws logs tail /aws/lambda/docprof-dev-chat-handler --follow
```

Or query for errors:

```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/docprof-dev-chat-handler \
  --filter-pattern "ERROR ImportError ModuleNotFoundError" \
  --start-time $(date -d '5 minutes ago' +%s)000
```

## Expected Results

### Success Indicators

✅ Lambda invokes without errors  
✅ No `ImportError` or `ModuleNotFoundError` in logs  
✅ Logic functions execute (even if business logic fails due to missing data)  
✅ Response contains expected structure  

### Failure Indicators

❌ `ModuleNotFoundError: No module named 'shared'`  
   → Logic not packaged correctly  
   → Check Lambda module packaging in Terraform  

❌ `ImportError: cannot import name 'expand_query_for_retrieval'`  
   → Logic file not included  
   → Check `shared/logic/chat.py` is in ZIP  

❌ `ImportError: cannot import name 'ChatMessage'`  
   → Core models not included  
   → Check `shared/core/chat_models.py` is in ZIP  

## Troubleshooting

### Logic Not Found

If imports fail, check the Lambda package:

```bash
# Download Lambda package
aws lambda get-function --function-name docprof-dev-chat-handler \
  --query 'Code.Location' \
  --output text | xargs curl -o /tmp/lambda.zip

# Extract and check structure
unzip -l /tmp/lambda.zip | grep shared
```

Should see:
```
shared/logic/chat.py
shared/core/chat_models.py
shared/core/prompts/__init__.py
...
```

### Terraform Packaging Issues

Check Lambda module packaging logic:

```bash
cd terraform/modules/lambda
# Check main.tf - should include shared/ in all_content
```

### Import Path Issues

Verify imports use `shared.*` not `src.*`:

```bash
grep -r "from src\." src/lambda/shared/
# Should return nothing (all should be "from shared.")
```

## Next Steps After Successful Test

1. ✅ Logic extraction validated
2. Test full chat flow (create session, send message, get response)
3. Test with real data (books in Aurora)
4. Monitor performance and errors
5. Document any issues or improvements needed

## Notes

- Logic is packaged with each Lambda function (not in layer)
- Lambda layer contains only Python dependencies
- No external MAExpert dependencies - logic is self-contained
- All imports use `shared.*` pattern
