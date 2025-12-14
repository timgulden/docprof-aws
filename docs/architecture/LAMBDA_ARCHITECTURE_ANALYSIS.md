# Lambda Architecture Analysis

**Date:** 2025-01-XX  
**Status:** Hybrid Approach - Partially Following Lambda Best Practices

## Current Architecture

### What We're Doing Well ✅

1. **Lambda Layer for Python Dependencies**
   - ✅ Python packages (psycopg2, pymupdf, Pillow, etc.) are in a Lambda Layer
   - ✅ Compiled for Amazon Linux 2 (correct Lambda runtime)
   - ✅ Reused across all Lambda functions
   - ✅ Reduces deployment package size

2. **Function-Specific Code Separation**
   - ✅ Each Lambda function has its own handler
   - ✅ Clear separation of concerns

### What We're Not Fully Leveraging ⚠️

**Shared Application Code Bundling**

Currently, we're **copying** the entire `shared/` directory (~484KB, 33 Python files) into **every Lambda function ZIP file**.

**Current Flow:**
```
Lambda Function ZIP:
├── handler.py              # Function-specific code
├── requirements.txt        # Function dependencies
└── shared/                 # ❌ 33 files duplicated in EVERY function
    ├── db_utils.py
    ├── bedrock_client.py
    ├── response.py
    └── ... (30 more files)
```

**Problems:**
1. **Code Duplication**: Each Lambda function contains a full copy of shared code
2. **Larger Packages**: Each deployment ZIP is ~500KB larger than needed
3. **Deployment Inefficiency**: Updating shared code requires redeploying ALL functions
4. **Version Mismatch Risk**: Different functions could have different versions of shared code
5. **Not Using Lambda Layers Fully**: We're treating Lambda more like a monolith

## Lambda Best Practices

### Recommended Architecture

**Lambda Layers Should Contain:**
1. ✅ **Layer 1**: Python dependencies (psycopg2, pymupdf, etc.) - **We're doing this**
2. ❌ **Layer 2**: Shared application code (shared/db_utils.py, etc.) - **Not doing this**

**Lambda Function ZIP Should Contain:**
- ✅ Only handler.py and function-specific code
- ✅ Minimal dependencies (if any)

### Proper Lambda Paradigm

```
Lambda Layer 1 (Python Dependencies):
├── python/lib/python3.11/site-packages/
│   ├── psycopg2/
│   ├── pymupdf/
│   ├── Pillow/
│   └── ...

Lambda Layer 2 (Shared Application Code):
├── python/
│   └── shared/
│       ├── db_utils.py
│       ├── bedrock_client.py
│       ├── response.py
│       └── ...

Lambda Function ZIP (Minimal):
├── handler.py  # Only function-specific code
└── (no shared/ directory)
```

**Benefits:**
- ✅ Smaller deployment packages (~10-50KB vs ~500KB)
- ✅ Faster deployments (less code to upload)
- ✅ Update shared code once, all functions benefit
- ✅ Version consistency (all functions use same shared code version)
- ✅ Better separation of concerns
- ✅ Follows AWS Lambda best practices

## Comparison: Current vs Recommended

| Aspect | Current (Bundled) | Recommended (Layered) |
|--------|------------------|----------------------|
| **Function ZIP Size** | ~500KB | ~10-50KB |
| **Deployment Speed** | Slower (more code) | Faster (less code) |
| **Shared Code Update** | Redeploy all functions | Update layer once |
| **Version Consistency** | Risk of mismatch | Guaranteed consistency |
| **Lambda Paradigm** | Monolithic-style | Serverless-style |
| **Code Reuse** | Copy-based | True reuse via layers |

## Migration Path

### Option 1: Keep Current Approach (Pragmatic)

**When to use:**
- Development/small scale
- Shared code changes frequently
- Simpler deployment workflow preferred

**Pros:**
- ✅ Simpler to understand and debug
- ✅ No layer versioning complexity
- ✅ All code versioned together (git)
- ✅ Works fine for <10 functions

**Cons:**
- ❌ Not following Lambda best practices
- ❌ Slower deployments as you scale
- ❌ Duplicated code

### Option 2: Migrate to Layers (Best Practice)

**When to use:**
- Production scale
- Many Lambda functions (>10)
- Need faster deployments
- Want to follow AWS best practices

**Steps:**
1. Create `terraform/modules/lambda-shared-code-layer/`
2. Package `shared/` directory into Lambda Layer
3. Update Lambda module to NOT bundle shared code
4. Attach layer to all functions
5. Test thoroughly

**Pros:**
- ✅ Follows AWS Lambda best practices
- ✅ Smaller, faster deployments
- ✅ True code reuse
- ✅ Better at scale

**Cons:**
- ❌ More complex (layer versioning)
- ❌ Requires careful testing (layer updates affect all functions)
- ❌ More moving parts

## Recommendation

**For Current Stage (Development):**
- ✅ **Keep current approach** - It works and is simpler
- ⚠️ **Be aware** - This is not fully leveraging Lambda Layers
- 📝 **Document** - This is a conscious trade-off for simplicity

**For Production:**
- 🔄 **Migrate to Layer 2** - When you have >10 functions or deployment speed becomes an issue
- 📊 **Measure** - Track deployment times and package sizes
- 🎯 **Optimize when needed** - Don't optimize prematurely

## Current Status

**We are using Lambda paradigm PARTIALLY:**
- ✅ Using Layers for dependencies (correct)
- ❌ Bundling shared code (acceptable trade-off, not ideal)
- ✅ Each function is independent and stateless (correct)
- ✅ Using environment variables (correct)
- ✅ Thin handlers with logic in shared code (correct)

**Conclusion:** We're not "monkey patching" in a bad way, but we're also not fully leveraging Lambda Layers for shared application code. This is a reasonable trade-off for development, but should be addressed before production scale.

