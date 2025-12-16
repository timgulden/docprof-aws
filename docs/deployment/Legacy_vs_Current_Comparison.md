# Legacy MAExpert vs Current AWS Implementation - Function Comparison

## Executive Summary

After comparing the legacy MAExpert code with our current AWS implementation, here are the key differences and recommendations:

**Status**: Our current implementation has **diverged significantly** from the tested legacy code, particularly in TOC parsing logic.

**Key Finding**: The legacy `parse_toc_structure` is **simpler and more robust** than our current version. We've over-complicated it.

---

## Function-by-Function Comparison

### 1. `parse_toc_structure()` - **CRITICAL DIFFERENCE**

#### Legacy (MAExpert):
```python
def parse_toc_structure(
    toc_raw: List[Tuple[int, str, int]],
    book_title: str,
    author: str,
    total_pages: int,
) -> Dict[str, Any]:
```

**Logic:**
- **Simple hierarchical parsing**: Level 1 = chapters, Level 2+ = sections
- **No complex chapter detection**: Just skips front matter, treats everything else as chapters
- **No PARTS handling**: Doesn't try to detect "PART" containers
- **No `is_real_chapter()` heuristics**: Simpler filtering

**Key Code:**
```python
for level, title, page in toc_raw:
    if level == 1:
        if is_front_matter(title):
            continue  # Skip front matter
        
        # This is a real chapter - simple!
        current_chapter = {
            "chapter_number": len(chapters) + 1,
            "chapter_title": title.strip(),
            "page_number": page,
            "sections": [],
        }
    elif level >= 2 and current_chapter:
        # Everything else is a section
        current_chapter["sections"].append(...)
```

#### Current (AWS):
```python
def parse_toc_structure(
    toc_raw: List[tuple],
    source_title: str,
    author: str,
    total_pages: int,
    identified_chapter_level: Optional[int] = None,  # NEW - added complexity
) -> Dict[str, Any]:
```

**Logic:**
- **Complex multi-level parsing**: Tries to handle Level 1 as PARTS, Level 2 as chapters
- **`is_real_chapter()` heuristics**: Complex page gap analysis, pattern matching
- **`is_part()` detection**: Additional PART container logic
- **`is_chapter_title()` matching**: Extra validation for chapter detection
- **Level 2 special handling**: Conditional logic based on `identified_chapter_level`

**Key Code:**
```python
for level, title, page in toc_raw:
    if level == 1:
        if is_front_matter(title):
            continue
        if is_part(title):  # NEW - PARTS detection
            current_part = title.strip()
            continue
        if not is_real_chapter(title, page, current_chapter):  # NEW - complex heuristics
            # Section at level 1
            continue
        # ... create chapter
    
    elif level == 2:
        # NEW - complex conditional logic
        if identified_chapter_level == 2 or is_chapter_title(title):
            # This is a chapter at level 2
            ...
        elif current_chapter:
            # This is a section at level 2
            ...
```

**Verdict:** ⚠️ **REVERT TO LEGACY LOGIC**

The current version is **over-engineered** and likely **breaking the 43-chapter detection**. The legacy version worked because:
1. It trusts PyMuPDF's TOC levels
2. It doesn't try to second-guess the structure
3. Simpler = fewer edge cases

---

### 2. TOC Extraction Strategy - **PARTIAL MATCH**

#### Legacy (MAExpert):
1. **Try PyMuPDF `get_toc()` first** (fast, embedded TOC)
2. **If no TOC found** → Use LLM vision (`parse_toc_llm()`)
3. **If few entries** → Use LLM to identify chapter level
4. **Always use hyperlink data** to assist LLM extraction

#### Current (AWS):
1. **Try PyMuPDF `get_toc()` first** ✅
2. **If multiple levels** → Use LLM to identify chapter level ✅
3. **If few chapters** → Try BOTH hyperlink AND visual extraction ✅ **BETTER**
4. **Use best result** (whichever finds more chapters) ✅ **BETTER**

**Verdict:** ✅ **CURRENT IS BETTER**

Our dual-path approach (hyperlink + visual) is an improvement over legacy. We just need to fix the `parse_toc_structure` logic that processes the results.

---

### 3. Chapter Text Truncation - **CRITICAL DIFFERENCE**

#### Legacy:
```python
# Limit chapter text to avoid token limits (keep ~50k chars)
text_preview = chapter_text[:50000] if len(chapter_text) > 50000 else chapter_text
if len(chapter_text) > 50000:
    text_preview += "\n\n[Content truncated for length...]"
```

**Limit:** 50,000 characters (~12,500 tokens)

#### Current:
```python
# Limit chapter text to avoid token limits (keep ~500k chars, ~125k tokens)
# Standard 200k token context window can handle up to ~800k chars, so 500k is safe
text_preview = chapter_text[:500000] if len(chapter_text) > 500000 else chapter_text
if len(chapter_text) > 500000:
    text_preview += "\n\n[Content truncated for length (chapter exceeds 500k characters)...]"
```

**Limit:** 500,000 characters (~125,000 tokens)

**Verdict:** ✅ **CURRENT IS BETTER**

The higher limit makes sense with Claude's 200k context window. Legacy was conservative for older models.

---

### 4. Chapter Summary Prompt Variables - **MATCH**

Both versions have identical logic:
- Build prompt variables with chapter number, title, sections, text preview
- Format sections as bullet list with page numbers
- Truncate text (different limits, see above)

**Verdict:** ✅ **NO CHANGE NEEDED**

---

### 5. Chapter-by-Chapter Processing - **ARCHITECTURAL DIFFERENCE**

#### Legacy (MAExpert):
- **Sequential processing** in a single function
- **Synchronous LLM calls** for each chapter
- **State machine** with handlers: `handle_toc_extracted` → `process_chapter` → `handle_chapter_text_extracted` → `handle_chapter_summary_generated`
- **All in one execution context**

#### Current (AWS):
- **Event-driven parallel processing**
- **Separate Lambda per chapter** (`chapter_summary_processor`)
- **DynamoDB for state tracking**
- **EventBridge for orchestration**
- **Assembler Lambda** to collect results

**Verdict:** 🤷 **DIFFERENT BY DESIGN**

The new architecture is **better for scalability** (no timeouts, parallel processing), but **more complex** (distributed state, eventual consistency). This is an **intentional AWS-native improvement**, not a regression.

---

### 6. TOC Parser (`find_toc`, `identify_chapter_ranges`) - **SIMILAR**

Both versions use identical LLM-based TOC extraction:
- Vision-based TOC page detection
- Hyperlink extraction for chapter page numbers
- LLM parsing of TOC images
- Page offset calculation

**Differences:**
- **Legacy**: Uses Anthropic API directly
- **Current**: Uses Bedrock (AWS-native)

**Verdict:** ✅ **NO CHANGE NEEDED** (just API differences)

---

### 7. Front Matter Detection (`is_front_matter`) - **MATCH**

Identical logic in both versions. ✅

---

## Key Recommendations

### 🔴 CRITICAL: Revert `parse_toc_structure` to Legacy Logic

**Problem:** Our current `parse_toc_structure` is over-engineered with:
- PARTS detection
- `is_real_chapter()` heuristics
- `is_chapter_title()` validation
- Level 2 conditional logic

**Solution:** Revert to legacy's simpler approach:
1. Level 1 = chapters (skip front matter)
2. Level 2+ = sections
3. Trust PyMuPDF's TOC structure
4. No complex heuristics

**Why this will fix the "43 chapters" issue:**
- Legacy successfully processed Valuation with 43 chapters
- Legacy trusts the embedded TOC structure
- Current version is trying to be "smart" and filtering out valid chapters

### 🟡 KEEP: Dual-Path TOC Extraction

**What to keep:**
- Hyperlink-based extraction (fast)
- Visual/LLM extraction (comprehensive)
- Using whichever finds more chapters

**Why:** This is an improvement over legacy's single-path approach.

### 🟢 KEEP: Higher Character Limits

**What to keep:**
- 500k character limit for chapter text
- Utilizes Claude's larger context window

**Why:** More context = better summaries.

### 🟢 KEEP: Event-Driven Architecture

**What to keep:**
- Separate Lambdas for orchestration, processing, assembly
- Parallel chapter processing
- DynamoDB state tracking

**Why:** Solves timeout issues, enables scalability.

---

## Proposed Changes

### Priority 1: Fix `parse_toc_structure` (HIGH IMPACT)

**File:** `src/lambda/shared/logic/source_summaries.py`

**Changes:**
1. Remove `is_part()` detection
2. Remove `is_real_chapter()` heuristics
3. Remove `is_chapter_title()` validation
4. Simplify to: Level 1 = chapters (except front matter), Level 2+ = sections
5. Remove `identified_chapter_level` parameter (no longer needed)

**Expected Result:** Will correctly identify 43 chapters in Valuation.

### Priority 2: Test with Valuation Book (VALIDATION)

**Action:**
1. Deploy simplified `parse_toc_structure`
2. Reprocess Valuation book
3. Verify: 43 chapters extracted
4. Verify: Summaries generated for all chapters

### Priority 3: Add Integration Tests (PREVENTION)

**File:** `tests/integration/test_toc_extraction.py`

**Tests to add:**
```python
def test_valuation_book_toc_extraction():
    """Valuation book should extract 43 chapters."""
    result = extract_toc("Valuation8thEd.pdf")
    assert len(result.chapters) == 43
    assert result.chapters[0].title.startswith("Chapter 1")

def test_toc_structure_parsing():
    """Test parse_toc_structure with known TOC."""
    toc_raw = [
        (1, "Additional Resources", 36),
        (1, "Chapter 1 Title", 83),
        (2, "Section 1.1", 86),
        (1, "Chapter 2 Title", 193),
    ]
    result = parse_toc_structure(toc_raw, "Test Book", "Author", 1000)
    assert len(result["chapters"]) == 2  # Should find 2 chapters, not 4
```

---

## Conclusion

**Main Issue:** We **over-complicated** `parse_toc_structure` during the refactor, adding logic that:
- Tries to detect PARTS (not needed - PyMuPDF handles this)
- Applies complex heuristics to determine if entries are "real chapters"
- Conditionally handles Level 2 based on LLM identification

**Legacy Approach:** Simple, trust PyMuPDF's structure, skip front matter, everything else is a chapter.

**Fix:** **Revert to legacy logic** for `parse_toc_structure`. This will restore the tested, working behavior that successfully processed Valuation with 43 chapters.

**Timeline:**
- Priority 1 fix: ~30 minutes
- Testing: ~1 hour
- Integration tests: ~1 hour
- **Total: ~2.5 hours to restore full functionality**
