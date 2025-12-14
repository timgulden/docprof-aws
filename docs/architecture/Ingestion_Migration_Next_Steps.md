# Ingestion Pipeline Migration - Next Steps

**Status**: Code migration complete, ready for testing  
**Date**: 2025-12-12

---

## ✅ What We've Completed

1. **Extracted Pure Logic** (`shared/logic/chunking.py`)
   - `build_page_chunks()` - Pure function for page chunking
   - `build_chapter_chunks_simple()` - Pure function for chapter chunking
   - `attach_content_hash()` - Pure function for hashing
   - `split_chunk_if_needed()` - Pure function for splitting
   - `build_figure_chunk()` - Pure function for figure chunks

2. **Created AWS-Native Orchestrator** (`shared/ingestion_orchestrator.py`)
   - Broken into small, focused functions
   - Each function has single responsibility
   - Uses existing AWS adapters
   - No MAExpert dependencies

3. **Updated Document Processor** (`document_processor/handler.py`)
   - Removed all MAExpert imports
   - Removed sys.path manipulation
   - Removed monkey-patching
   - Uses native orchestrator

4. **Cover Extraction** (`shared/cover_extractor.py`)
   - Already implemented and integrated

---

## 🔍 Next Steps: Testing & Validation

### Step 1: Code Review & Static Checks

**Actions**:
- [ ] Verify all imports resolve correctly
- [ ] Check for any missing dependencies
- [ ] Verify async/await usage is correct (or simplify if not needed)
- [ ] Run linter/type checker

**Commands**:
```bash
# Check for import errors
cd src/lambda/document_processor
python3 -m py_compile handler.py

# Check orchestrator
cd ../shared
python3 -m py_compile ingestion_orchestrator.py
python3 -m py_compile logic/chunking.py
```

### Step 2: Simplify Async/Await (If Needed)

**Issue**: The orchestrator uses `async def` but doesn't actually perform async operations yet.

**Options**:
1. **Remove async/await** - Simplify to synchronous functions (easier for now)
2. **Keep async/await** - Prepare for future parallelization of embeddings/figures

**Recommendation**: Remove async/await for now to simplify, add back when we implement parallel processing.

### Step 3: Deploy and Test

**Actions**:
1. Deploy updated Lambda function
2. Upload a test PDF via the frontend
3. Monitor CloudWatch logs
4. Verify chunks are created in database
5. Verify figures are extracted and stored
6. Verify cover is extracted and stored

**Commands**:
```bash
# Deploy document processor Lambda
cd terraform/environments/dev
terraform apply -target=module.document_processor_lambda

# Monitor logs
aws logs tail /aws/lambda/docprof-dev-document-processor --follow
```

### Step 4: Verify Database State

**Actions**:
- [ ] Check `books` table - verify book record exists
- [ ] Check `chunks` table - verify chunks are inserted
- [ ] Check `figures` table - verify figures are inserted
- [ ] Check book metadata - verify cover is stored

**SQL Queries**:
```sql
-- Check book
SELECT book_id, title, total_pages, metadata->'cover'->>'format' as cover_format
FROM books
WHERE book_id = '<book_id>';

-- Check chunks
SELECT COUNT(*) as chunk_count, chunk_type
FROM chunks
WHERE book_id = '<book_id>'
GROUP BY chunk_type;

-- Check figures
SELECT COUNT(*) as figure_count
FROM figures
WHERE book_id = '<book_id>';
```

### Step 5: Test Edge Cases

**Test Scenarios**:
- [ ] Small PDF (< 10 pages)
- [ ] Large PDF (> 500 pages)
- [ ] PDF with no figures
- [ ] PDF with many figures
- [ ] Re-upload same book (should skip duplicates)
- [ ] Rebuild existing book (should clear and re-process)

---

## 🐛 Potential Issues to Watch For

### 1. Async/Await in Lambda
- **Issue**: Using `asyncio.run()` in Lambda handler
- **Solution**: Either remove async/await or ensure Lambda runtime supports it
- **Status**: Should work, but worth testing

### 2. Missing Dependencies
- **Issue**: New imports might not be in Lambda layer
- **Solution**: Verify all imports are available
- **Check**: `shared/logic/chunking.py` imports

### 3. Database Connection Timeout
- **Issue**: Long-running ingestion might timeout
- **Solution**: Monitor Lambda timeout settings (currently 15 minutes)
- **Check**: Large PDFs might need longer timeout

### 4. Memory Limits
- **Issue**: Large PDFs might exceed Lambda memory
- **Solution**: Monitor memory usage, increase if needed
- **Check**: Current memory is 512MB, might need more for large PDFs

---

## 📋 Testing Checklist

### Pre-Deployment
- [ ] Code compiles without errors
- [ ] All imports resolve
- [ ] No linter errors
- [ ] Terraform validates

### Post-Deployment
- [ ] Lambda deploys successfully
- [ ] Can upload PDF via frontend
- [ ] Document processor Lambda is triggered
- [ ] CloudWatch logs show progress
- [ ] No errors in logs

### Data Verification
- [ ] Book record created in database
- [ ] Cover image stored in metadata
- [ ] Chunks created (chapter + page chunks)
- [ ] Embeddings generated and stored
- [ ] Figures extracted and stored
- [ ] Chapter documents created

### Functional Verification
- [ ] Can search for content from ingested book
- [ ] Cover image displays in frontend
- [ ] Figures are accessible
- [ ] Re-upload skips duplicates correctly

---

## 🚀 Quick Start Testing

1. **Deploy**:
   ```bash
   cd terraform/environments/dev
   terraform apply -target=module.document_processor_lambda
   ```

2. **Upload Test PDF**:
   - Go to frontend: http://localhost:5173/sources
   - Upload a test PDF
   - Watch for success message

3. **Check Logs**:
   ```bash
   aws logs tail /aws/lambda/docprof-dev-document-processor --follow
   ```

4. **Verify in Database**:
   - Connect to Aurora
   - Run verification queries above

---

## 📝 Notes

- The orchestrator is designed to be easily testable - each function can be tested independently
- Pure logic functions in `shared/logic/chunking.py` can be tested without any AWS dependencies
- Effect functions use existing adapters that are already tested
- If issues arise, we can debug function by function

---

*Ready to test! The migration is complete and the code follows clean FP principles.*

