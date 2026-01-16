"""
LLM-based TOC parser for PDFs without embedded TOC structures.

Adapted from MAExpert's toc_parser.py for AWS Bedrock.
Uses Claude vision to find and parse table of contents pages.
"""

import base64
import json
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

import fitz  # PyMuPDF
from PIL import Image
import io

from shared.bedrock_client import invoke_claude

logger = logging.getLogger(__name__)


@dataclass
class ChapterRange:
    """A chapter with its title and page range."""
    chapter_number: int
    title: str
    start_page: int  # Book page number (from TOC)
    end_page: Optional[int] = None  # Book page number (if specified in TOC)


@dataclass
class TOCParseResult:
    """Result of parsing the table of contents."""
    chapters: List[ChapterRange]
    toc_start_page: int  # PDF page number where TOC starts
    toc_end_page: int  # PDF page number where TOC ends
    page_offset: int  # Offset between PDF page numbers and book page numbers
    raw_toc_text: str


def _render_page_as_image(document: fitz.Document, page_num: int, zoom: float = 2.0) -> bytes:
    """Render a PDF page as a JPEG image."""
    page = document[page_num - 1]  # 0-indexed
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix)
    
    # Convert to PIL Image
    pil_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
    # Convert to JPEG
    buffer = io.BytesIO()
    pil_image.convert("RGB").save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def find_toc(
    pdf_bytes: bytes,
    pages: List[str],
    book_title: str = "Unknown Book",
    max_pages_to_check: int = 20,
) -> Optional[Tuple[int, int]]:
    """
    Find the table of contents pages using LLM vision with hyperlink extraction.
    
    Args:
        pdf_bytes: PDF file as bytes
        pages: List of page text content
        book_title: Title of the book
        max_pages_to_check: Maximum number of pages to check (default 20)
    
    Returns:
        Tuple of (start_page, end_page) in PDF page numbers (1-indexed), or None if not found
    """
    # Extract hyperlinks from first N pages
    # Start from page 2 since TOC can appear very early
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    page_data = []
    pages_to_check = min(max_pages_to_check, len(pages), len(document))
    
    # Start from page 2 (page 1 is usually cover/title page)
    for page_num in range(2, pages_to_check + 1):
        try:
            page = document[page_num - 1]  # 0-indexed
            page_text = pages[page_num - 1] if page_num - 1 < len(pages) else ""
            
            # Extract hyperlinks from the page
            links = page.get_links()
            hyperlink_info = []
            for link in links:
                if link.get("kind") == fitz.LINK_GOTO:  # Internal link (page reference)
                    dest_page = link.get("page", -1) + 1  # Convert to 1-indexed
                    # Get the rectangle where the link is located
                    link_rect = link.get("from")  # This is a Rect object, not a dict
                    if link_rect:
                        try:
                            # Get text in the link area
                            link_text_content = page.get_textbox(link_rect)
                            hyperlink_info.append({
                                "text": link_text_content.strip(),
                                "target_page": dest_page,
                            })
                        except:
                            pass
            
            # Also render as image for LLM to see visual structure
            image_bytes = _render_page_as_image(document, page_num, zoom=2.0)
            
            page_data.append({
                "page_num": page_num,
                "text": page_text,
                "hyperlinks": hyperlink_info,
                "image": image_bytes,
            })
        except Exception as e:
            logger.warning(f"Failed to process page {page_num}: {e}")
    
    document.close()
    
    if not page_data:
        logger.warning("Could not process pages for TOC detection")
        return None
    
    # Build prompt with hyperlink information
    hyperlink_summary = []
    for page_info in page_data:
        if page_info["hyperlinks"]:
            link_count = len(page_info["hyperlinks"])
            sample_links = page_info["hyperlinks"][:3]  # First 3 links as examples
            link_examples = ", ".join([f'"{link["text"][:30]}"→page{link["target_page"]}' for link in sample_links])
            hyperlink_summary.append(f"Page {page_info['page_num']}: {link_count} hyperlinks (e.g., {link_examples})")
    
    hyperlink_text = "\n".join(hyperlink_summary) if hyperlink_summary else "No hyperlinks found in these pages."
    
    prompt = f"""You are analyzing a book titled "{book_title}" to find the table of contents (TOC).

I'm showing you pages 2-{len(page_data)+1} of the PDF (starting from page 2, as page 1 is usually the cover).

HYPERLINK INFORMATION (extracted from PDF structure):
{hyperlink_text}

The table of contents can appear in various formats:
- Traditional: Has a heading like "CONTENTS", "TABLE OF CONTENTS", or "Table of Contents" with visible page numbers
- Modern/Interactive: May have HYPERLINKS (blue/underlined clickable text) instead of visible page numbers
  * In hyperlinked TOCs, the page numbers are embedded in the hyperlink targets
  * The hyperlink information above shows which text links to which page
  * Look for pages with many hyperlinks that point to later pages in the book
- May start VERY EARLY (page 2, 3, 4, etc.) - check these pages carefully!
- May span multiple consecutive pages
- May include PARTS (which contain chapters) and CHAPTERS
- May have lists of tables, figures, illustrations (these are NOT the main TOC)

What to look for:
- Pages with headings like "CONTENTS", "TABLE OF CONTENTS", "Table of Contents", or similar
- Pages that list the main structural divisions of the book (chapters, parts, major sections)
- Pages with MANY HYPERLINKS that lead to chapters (check the hyperlink information above)
- The TOC typically lists the highest-level organizational structure (chapters, not subsections)
- The TOC may span multiple consecutive pages - continue until you see "INDEX" or other non-TOC sections

IMPORTANT: A TOC page must contain actual chapter/section listings - pages with only headings or blank pages are NOT part of the TOC.
- The TOC starts on the FIRST page that lists actual chapters (even if earlier pages have "Contents" headings)
- The TOC ends on the LAST page that contains chapter listings
- Empty pages or pages without chapter content should NOT be included in the TOC range
- Stop immediately after the last page with chapter listings - do not include empty pages

CRITICAL INSTRUCTIONS: 
- Check pages 2-20 VERY CAREFULLY - TOCs can start anywhere in this range
- Use the hyperlink information to identify TOC pages - pages with many hyperlinks to later pages are likely TOC
- If you see a page with chapter titles and hyperlinks (visible in images OR in hyperlink data), that's likely the TOC
- The TOC might NOT have a clear "CONTENTS" heading if it's hyperlinked
- Look for the FIRST page that lists actual chapters/sections - NOT just a "Contents" heading
- **A page with only a "Contents" heading but no chapter listings should NOT be included as the start page**
- **The TOC starts where chapters are actually listed, not where there's just a heading**
- **If a page has no text/chapter content but only a heading, exclude it from the TOC range**
- **The TOC start page must have visible chapter listings (like "CHAPTER 1", "Chapter 1", etc.)**
- Continue until the main content listing ends - TOCs often span multiple consecutive pages (7-10 pages is common)
- DO NOT stop early - continue through ALL pages that list chapters, even if there are subsections mixed in
- IMPORTANT: Check ALL pages with chapter listings - TOCs can continue well into the teens (pages 10-17+)
- Make sure to include the VERY LAST page that contains any chapter listings
- **Empty pages or pages without chapter content should NOT be included - stop at the last page with actual chapters**
- Stop ONLY when you see "INDEX" or other clearly non-TOC sections like appendices, bibliography, or when there are NO more chapter listings
- Double-check that you've included the final page with chapter content - missing the last page means missing the final chapters

Return a JSON object:
{{
  "toc_start_page": <first_page_number_of_TOC_or_null>,
  "toc_end_page": <last_page_number_of_TOC_or_null>,
  "confidence": "high" | "medium" | "low",
  "reason": "brief explanation of what you found, including hyperlink patterns"
}}

If no TOC is found, return:
{{
  "toc_start_page": null,
  "toc_end_page": null,
  "confidence": "low",
  "reason": "explanation"
}}

The images are in order, corresponding to PDF pages: {", ".join(f"Page {p['page_num']}" for p in page_data)}"""

    # Prepare images
    image_messages = []
    for page_info in page_data:
        image_base64 = base64.b64encode(page_info["image"]).decode("utf-8")
        image_messages.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": image_base64,
            },
        })
    
    try:
        # Use Bedrock Claude (same message format as Anthropic)
        response = invoke_claude(
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    *image_messages,
                ]
            }],
            max_tokens=1000,
            temperature=0.3,  # Lower temperature for more consistent detection
        )
        
        response_text = response['content']
        logger.debug(f"LLM TOC detection response: {response_text[:200]}")
        
        # Parse JSON
        json_match = re.search(r'\{.*?"toc_start_page".*?\}', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            toc_start = result.get("toc_start_page")
            toc_end = result.get("toc_end_page")
            confidence = result.get("confidence", "unknown")
            
            if toc_start and toc_end:
                # Validate page numbers are in range
                if 1 <= toc_start <= len(pages) and 1 <= toc_end <= len(pages) and toc_start <= toc_end:
                    # Post-process: Trim empty pages from start/end
                    # Check if start page actually has chapter content
                    start_page_text = pages[toc_start - 1] if toc_start <= len(pages) else ""
                    if toc_start < toc_end and (not start_page_text.strip() or "CHAPTER" not in start_page_text.upper()):
                        # Start page is empty or has no chapters, try next page
                        if toc_start + 1 <= len(pages):
                            next_page_text = pages[toc_start] if toc_start < len(pages) else ""
                            if "CHAPTER" in next_page_text.upper():
                                logger.info(f"Adjusting TOC start from page {toc_start} to {toc_start + 1} (empty/heading-only page)")
                                toc_start = toc_start + 1
                    
                    # Check if end page actually has chapter content
                    end_page_text = pages[toc_end - 1] if toc_end <= len(pages) else ""
                    if toc_start < toc_end and (not end_page_text.strip() or "CHAPTER" not in end_page_text.upper()):
                        # End page is empty, try previous page
                        if toc_end - 1 >= toc_start:
                            prev_page_text = pages[toc_end - 2] if toc_end > 1 else ""
                            if "CHAPTER" in prev_page_text.upper():
                                logger.info(f"Adjusting TOC end from page {toc_end} to {toc_end - 1} (empty page)")
                                toc_end = toc_end - 1
                    
                    logger.info(
                        f"LLM found TOC: pages {toc_start}-{toc_end} (confidence: {confidence})"
                    )
                    return (toc_start, toc_end)
                else:
                    logger.warning(
                        f"LLM returned invalid page numbers: {toc_start}-{toc_end} "
                        f"(valid range: 1-{len(pages)})"
                    )
            else:
                logger.info(f"LLM did not find TOC in first {len(page_data)} pages")
    
    except Exception as e:
        logger.error(f"Failed to find TOC with LLM: {e}", exc_info=True)
    
    logger.warning("Could not find TOC in first pages")
    return None


def extract_chapters_from_hyperlinks(
    pdf_bytes: bytes,
    toc_pages: Tuple[int, int],
    book_title: str = "Unknown Book",
) -> List[ChapterRange]:
    """
    Extract chapters from TOC hyperlinks using LLM to filter substantial content.
    
    Uses LLM to identify chapters and significant appendices from the hyperlink list,
    rather than hardcoded filtering rules. This is more accurate and consistent.
    
    Args:
        pdf_bytes: PDF file as bytes
        toc_pages: Tuple of (start_page, end_page) for TOC in PDF
        book_title: Title of the book
    
    Returns:
        List of ChapterRange objects
    """
    import re
    import json
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    toc_start, toc_end = toc_pages
    
    # Extract all hyperlinks from TOC pages
    unique_targets = {}
    for page_num in range(toc_start, toc_end + 1):
        try:
            page = document[page_num - 1]  # 0-indexed
            links = page.get_links()
            for link in links:
                if link.get("kind") == fitz.LINK_GOTO:
                    dest_page = link.get("page", -1) + 1
                    if dest_page > toc_end:  # Only chapters (not TOC internal links)
                        link_rect = link.get("from")
                        if link_rect:
                            try:
                                link_text = page.get_textbox(link_rect).strip()
                                # Keep the longest text for each target page
                                if dest_page not in unique_targets or len(link_text) > len(unique_targets[dest_page]):
                                    unique_targets[dest_page] = link_text
                            except:
                                pass
        except Exception as e:
            logger.warning(f"Failed to process TOC page {page_num}: {e}")
    document.close()
    
    if not unique_targets:
        logger.warning("No hyperlinks found in TOC")
        return []
    
    logger.info(f"Found {len(unique_targets)} hyperlink entries in TOC")
    
    # Use LLM to filter chapters and appendices
    # Build entry list for LLM
    entry_list = []
    for idx, (page, text) in enumerate(sorted(unique_targets.items()), 1):
        entry_list.append(f"{idx}. Page {page}: {text}")
    
    entry_text = "\n".join(entry_list)
    
    prompt = f"""You are analyzing the table of contents for "{book_title}".

Below are {len(unique_targets)} TOC entries extracted from hyperlinks. Each entry shows:
- Entry number (for your reference)
- Page number (book page, not PDF page)
- Title text

ENTRIES:
{entry_text}

Your task: Identify which entries are CHAPTERS or SIGNIFICANT APPENDICES that should be processed.

INCLUDE:
- All numbered chapters (e.g., "Chapter 1", "Chapter 2", "CHAPTER 1:", etc.)
- Significant standalone appendices (e.g., "Appendix A", "Appendix B", NOT "Appendix 2A" within a chapter)
- Major content sections that are chapter-level divisions

EXCLUDE:
- Front/back matter: Additional Resources, About the Authors, Foreword, Acknowledgments, Disclaimer, Bibliography, Index, Advert, EULA
- Container sections: "Part One", "Part Two", etc.
- Minor subsections: "Step I", "Step II", "Summary of...", "Key Pros and Cons"
- Exhibits within chapters: "Exhibit 1.1", "Exhibit 2.3"
- Notes sections

Look at the TITLE CONTENT, not structure. For example:
- "CHAPTER 1: Comparable Companies" → INCLUDE (obvious chapter)
- "Chapter 5 LBO Analysis" → INCLUDE (obvious chapter)
- "Appendix A Financial Statements" → INCLUDE (significant appendix)
- "Appendix 2A Supplemental Data" → EXCLUDE (sub-appendix within Chapter 2)
- "Step V. Determine Valuation" → EXCLUDE (procedure step within a chapter)
- "Additional Resources" → EXCLUDE (front matter)

Return a JSON array of entry numbers to INCLUDE:
{{"chapters": [2, 5, 9, 15, ...]}}

Only include the entry numbers (1-{len(unique_targets)}) of items that should be processed as chapters or significant appendices.
Be thorough - this book likely has 40-45 chapters plus significant appendices."""

    try:
        response = invoke_claude(
            messages=[{
                "role": "user",
                "content": prompt,
            }],
            max_tokens=2000,
            temperature=0.0,
        )
        
        # Parse JSON response
        json_match = re.search(r'\{.*?"chapters".*?\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            chapter_indices = result.get("chapters", [])
            
            if not chapter_indices:
                logger.warning("LLM returned empty chapter list")
                return []
            
            logger.info(f"LLM identified {len(chapter_indices)} chapters/appendices from {len(unique_targets)} entries")
            
            # Build chapter list from LLM-selected indices
            sorted_entries = list(sorted(unique_targets.items()))
            chapters = []
            for idx in chapter_indices:
                if 1 <= idx <= len(sorted_entries):
                    page, text = sorted_entries[idx - 1]  # Convert 1-indexed to 0-indexed
                    chapters.append(ChapterRange(
                        chapter_number=len(chapters) + 1,
                        title=text,
                        start_page=page,
                    ))
                else:
                    logger.warning(f"LLM returned invalid index: {idx} (valid range: 1-{len(sorted_entries)})")
            
            logger.info(f"Extracted {len(chapters)} chapters from hyperlinks using LLM filtering")
            return chapters
        else:
            logger.error("Could not parse LLM response for chapter filtering")
            return []
            
    except Exception as e:
        logger.error(f"LLM-based filtering failed: {e}", exc_info=True)
        return []


def identify_chapter_ranges(
    pdf_bytes: bytes,
    toc_pages: Tuple[int, int],
    pages: List[str],
    book_title: str = "Unknown Book",
) -> List[ChapterRange]:
    """
    Parse the table of contents to extract chapter titles and page ranges.
    
    Args:
        pdf_bytes: PDF file as bytes
        toc_pages: Tuple of (start_page, end_page) for TOC in PDF
        pages: List of page text content
        book_title: Title of the book
    
    Returns:
        List of ChapterRange objects
    """
    # Extract TOC text
    toc_start, toc_end = toc_pages
    toc_text_parts = []
    for page_idx in range(toc_start - 1, toc_end):  # Convert to 0-indexed
        if page_idx < len(pages):
            toc_text_parts.append(pages[page_idx])
    toc_text = "\n".join(toc_text_parts)
    
    # Extract hyperlinks from TOC pages
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    toc_data = []
    for page_num in range(toc_start, toc_end + 1):
        try:
            page = document[page_num - 1]  # 0-indexed
            # Extract hyperlinks
            links = page.get_links()
            hyperlink_info = []
            for link in links:
                if link.get("kind") == fitz.LINK_GOTO:  # Internal link
                    dest_page = link.get("page", -1) + 1  # Convert to 1-indexed
                    link_rect = link.get("from")  # This is a Rect object
                    if link_rect:
                        try:
                            link_text_content = page.get_textbox(link_rect)
                            hyperlink_info.append({
                                "text": link_text_content.strip(),
                                "target_page": dest_page,
                            })
                        except:
                            pass
            
            # Also render as image
            image_bytes = _render_page_as_image(document, page_num, zoom=2.0)
            toc_data.append({
                "page_num": page_num,
                "hyperlinks": hyperlink_info,
                "image": image_bytes,
            })
        except Exception as e:
            logger.warning(f"Failed to process TOC page {page_num}: {e}")
    document.close()
    
    if not toc_data:
        logger.error("Could not process TOC pages")
        return []
    
    # Build comprehensive hyperlink summary
    hyperlink_summary = []
    all_chapter_links = []
    for page_info in toc_data:
        if page_info["hyperlinks"]:
            # Group links by target page to find chapter links
            chapter_links = [link for link in page_info["hyperlinks"] if link["target_page"] > toc_end]
            all_chapter_links.extend(chapter_links)
            if chapter_links:
                sample_links = chapter_links[:8]  # Show more examples
                link_examples = ", ".join([f'"{link["text"][:35]}"→{link["target_page"]}' for link in sample_links])
                hyperlink_summary.append(f"Page {page_info['page_num']}: {len(chapter_links)} links (e.g., {link_examples})")
    
    # Also provide a complete list of all unique hyperlink targets
    unique_targets = {}
    for link in all_chapter_links:
        target = link["target_page"]
        if target not in unique_targets or len(link["text"]) > len(unique_targets[target]):
            unique_targets[target] = link["text"]
    
    hyperlink_text = "\n".join(hyperlink_summary) if hyperlink_summary else "No hyperlinks found in TOC pages."
    hyperlink_text += f"\n\nCOMPLETE HYPERLINK LIST ({len(unique_targets)} unique target pages):\n"
    for target_page in sorted(unique_targets.keys())[:100]:  # First 100 targets
        hyperlink_text += f"  Page {target_page}: {unique_targets[target_page][:60]}\n"
    if len(unique_targets) > 100:
        hyperlink_text += f"  ... and {len(unique_targets) - 100} more targets\n"
    
    prompt = f"""You are analyzing the table of contents for a book titled "{book_title}".

HYPERLINK INFORMATION (extracted from PDF structure):
{hyperlink_text}

Your task: Extract ALL substantial content sections from the TOC. This book should have approximately 40+ chapters/sections.

STRATEGY:
1. Use the COMPLETE HYPERLINK LIST above - it shows ALL {len(unique_targets)} sections that have hyperlinks
2. For each hyperlink entry, determine if it represents a substantial content section (chapter-level)
3. Extract ALL substantial sections, not just those explicitly labeled "Chapter X"
4. **If there are NO hyperlinks, read the chapter titles and page numbers directly from the visible TOC text in the images**

What constitutes a "substantial content section" (extract these):
- Explicitly numbered chapters: "Chapter 1", "Chapter 2", etc.
- Major unnumbered sections with substantial titles (e.g., "Key Participants", "Characteristics of...", "Economics of...")
- Sections that appear to be major content divisions (not minor subsections)
- Case studies with their own page numbers (e.g., "A WOFC Case Study", "Case Study: ...")
- Landmark cases or legal cases sections (e.g., "Landmark and Recent M&A Legal Cases")
- Major appendices (standalone appendices with their own page numbers, not sub-appendices like "Appendix 2A" within a chapter)
- If a section has its own hyperlink and substantial title, it's likely a chapter-level division

What to SKIP (do not extract):
- PARTS (Part One, Part Two, etc.) - these are containers
- Very minor subsections: "Step I", "Step II", "Summary of...", "Key Pros and Cons"
- Exhibits: "Exhibit 1.1", "Exhibit 1.2", etc.
- Non-content: Preface, Introduction, Foreword, Acknowledgments, Cover, etc.
- Lists: tables, figures, illustrations
- Minor sub-appendices within chapters (e.g., "Appendix 2A", "Appendix 6B" - these are parts of chapters, not standalone)

For each section you extract:
- chapter_number: Assign sequential numbers (1, 2, 3, ...) starting from 1
- title: The section title from the TOC
- start_page: Use the target_page from the hyperlink list (this is the book page number) **OR extract the page number from the visible text in the images if hyperlinks aren't available**

CRITICAL: 
- Extract ALL chapters/sections - be thorough and systematic
- Go through the COMPLETE HYPERLINK LIST and ALL TOC pages systematically
- Extract every chapter that appears in the TOC, not just a subset
- Count the chapters as you extract them - make sure you get them ALL
- **If there are no hyperlinks, read the page numbers directly from the visible TOC text in the images**
- Use the hyperlink target_page values directly for start_page, or extract from visible text if hyperlinks aren't available
- Do not stop early - continue through ALL TOC pages until you've extracted every chapter

Return a JSON array of ALL chapters/sections:
[
  {{"chapter_number": 1, "title": "Chapter Title", "start_page": 13}},
  {{"chapter_number": 2, "title": "Another Chapter", "start_page": 45}},
  {{"chapter_number": 3, "title": "Another Chapter", "start_page": null}},
  ...
]

The start_page should be the book page number (not PDF page number) if visible/determinable, or null if not found.

VERY IMPORTANT: Extract ALL chapters from the TOC. Do not skip any. Count them as you extract - there should be many chapters (typically 20-40+). 

CRITICAL: Make sure you extract chapters from the LAST page(s) of the TOC as well - missing the final chapters (like chapters 30-34) is a common error. Count backwards from the highest chapter number to ensure you have them all. If you see chapters numbered 30, 31, 32, 33, 34, make absolutely sure you extract all of them.

Make sure you've gone through every page of the TOC before finishing."""

    # Prepare images
    image_messages = []
    for page_info in toc_data:
        image_base64 = base64.b64encode(page_info["image"]).decode("utf-8")
        image_messages.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": image_base64,
            },
        })
    
    try:
        response = invoke_claude(
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    *image_messages,
                ]
            }],
            max_tokens=8000,  # Increased to ensure all chapters fit
            temperature=0.3,  # Lower temperature for more consistent extraction
        )
        
        response_text = response['content']
        logger.info(f"LLM TOC parsing response received ({len(response_text)} chars)")
        
        # Parse JSON
        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if json_match:
            chapters_data = json.loads(json_match.group(0))
            chapters = [
                ChapterRange(
                    chapter_number=ch["chapter_number"],
                    title=ch["title"],
                    start_page=ch["start_page"],
                    end_page=ch.get("end_page"),
                )
                for ch in chapters_data
            ]
            logger.info(f"Parsed {len(chapters)} chapters from TOC")
            return chapters
    except Exception as e:
        logger.error(f"Failed to parse TOC with LLM: {e}", exc_info=True)
    
    # Fallback: Try simple regex parsing
    logger.warning("Falling back to regex-based TOC parsing")
    return _parse_toc_regex(toc_text)


def _parse_toc_regex(toc_text: str) -> List[ChapterRange]:
    """Fallback regex-based TOC parsing."""
    chapters = []
    
    # Pattern: "Chapter N" or "N." followed by title and page number
    patterns = [
        r'chapter\s+(\d+)[\.\s]+([^\n]+?)(?:\.{2,}|\s+)(\d+)',
        r'(\d+)[\.\s]+([^\n]+?)(?:\.{2,}|\s+)(\d+)',
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, toc_text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            chapter_num = int(match.group(1))
            title = match.group(2).strip()
            page_num = int(match.group(3))
            
            # Filter out non-chapter entries
            if len(title) < 10:  # Too short to be a chapter title
                continue
            
            chapters.append(
                ChapterRange(
                    chapter_number=chapter_num,
                    title=title,
                    start_page=page_num,
                )
            )
    
    # Deduplicate by chapter number
    seen = {}
    deduped = []
    for ch in chapters:
        if ch.chapter_number not in seen:
            seen[ch.chapter_number] = ch
            deduped.append(ch)
    
    return deduped


def find_page_offset(
    pdf_bytes: bytes,
    toc_pages: Tuple[int, int],
    pages: List[str],
    first_chapter_book_page: int,
    first_chapter_title: str = "Chapter 1",
    book_title: str = "Unknown Book",
) -> int:
    """
    Find the offset between PDF page numbers and book page numbers.
    
    The offset is the difference: PDF_page_number = book_page_number + offset
    
    Strategy:
    1. Search PDF pages after TOC for Chapter 1 markers using regex
    2. Find candidate pages (pages that might be Chapter 1)
    3. Use LLM vision to verify which candidate is actually Chapter 1
    4. Calculate offset = PDF_page - book_page
    
    Args:
        pdf_bytes: PDF file as bytes
        toc_pages: Tuple of (start_page, end_page) for TOC in PDF
        pages: List of page text content
        first_chapter_book_page: Book page number for Chapter 1 (from TOC)
        first_chapter_title: Title of Chapter 1 (for verification)
        book_title: Title of the book
    
    Returns:
        Page offset (positive number, e.g., 12 means PDF page 13 = book page 1)
    """
    toc_start, toc_end = toc_pages
    
    # Step 1: Find candidate pages that might be Chapter 1
    # Search for various patterns of "Chapter 1" or "CHAPTER 1"
    candidate_pages: List[int] = []
    
    # Search pages after TOC (up to 50 pages to be safe)
    search_end = min(toc_end + 50, len(pages))
    
    for page_idx in range(toc_end, search_end):  # Start after TOC
        page_text = pages[page_idx]
        page_text_upper = page_text.upper()
        
        # Pattern 1: "CHAPTER 1" or "Chapter 1" (normal or spaced)
        patterns = [
            r'C\s*H\s*A\s*P\s*T\s*E\s*R\s+1\b',  # Spaced out: "C H A P T E R 1"
            r'CHAPTER\s+1\b',  # Normal: "CHAPTER 1"
            r'Chapter\s+1\b',  # Mixed case: "Chapter 1"
        ]
        
        for pattern in patterns:
            if re.search(pattern, page_text, re.IGNORECASE):
                # Additional check: make sure it's not just a reference to Chapter 1
                # Chapter 1 should appear near the top of the page
                lines = page_text.split('\n')[:10]  # First 10 lines
                for line in lines:
                    if re.search(pattern, line, re.IGNORECASE):
                        candidate_pages.append(page_idx + 1)  # Convert to 1-indexed
                        break
                break
    
    if not candidate_pages:
        logger.warning("No candidate pages found for Chapter 1, using default offset 0")
        return 0
    
    logger.info(f"Found {len(candidate_pages)} candidate pages for Chapter 1: {candidate_pages}")
    
    # Step 2: Use LLM to verify which candidate is actually Chapter 1
    # Render candidate pages as images
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    candidate_images = []
    for page_num in candidate_pages[:5]:  # Limit to first 5 candidates
        try:
            if page_num <= len(document):
                image_bytes = _render_page_as_image(document, page_num, zoom=2.0)
                candidate_images.append((page_num, image_bytes))
        except Exception as e:
            logger.warning(f"Failed to render candidate page {page_num}: {e}")
    document.close()
    
    if not candidate_images:
        # Fallback: use first candidate
        offset = candidate_pages[0] - first_chapter_book_page
        logger.warning(f"Could not render candidate pages, using first candidate: offset = {offset}")
        return offset
    
    # Step 3: Ask LLM to identify which page is actually Chapter 1
    prompt = f"""You are analyzing a book titled "{book_title}" to find where Chapter 1 actually starts.

According to the table of contents, Chapter 1 ("{first_chapter_title}") should start on book page {first_chapter_book_page}.

I'm showing you {len(candidate_images)} candidate pages from the PDF. One of these should be where Chapter 1 actually starts.

For each page, determine:
1. Is this page the start of Chapter 1? (Look for "CHAPTER 1" or "Chapter 1" at the top, followed by the chapter title)
2. What is the PDF page number? (I'll tell you which page number each image corresponds to)

Return a JSON object:
{{
  "chapter_1_pdf_page": <page_number>,
  "confidence": "high" | "medium" | "low",
  "reason": "brief explanation"
}}

If none of the pages appear to be Chapter 1, return:
{{
  "chapter_1_pdf_page": null,
  "confidence": "low",
  "reason": "explanation"
}}"""

    # Prepare images with page numbers
    image_messages = []
    for page_num, image_bytes in candidate_images:
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        image_messages.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": image_base64,
            },
        })
    
    # Add page numbers to prompt
    page_numbers_text = ", ".join(f"Page {p}" for p, _ in candidate_images)
    prompt += f"\n\nThe images are in order, corresponding to PDF pages: {page_numbers_text}"
    
    try:
        response = invoke_claude(
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    *image_messages,
                ]
            }],
            max_tokens=1000,
            temperature=0.3,
        )
        
        response_text = response['content']
        logger.debug(f"LLM offset detection response: {response_text[:200]}")
        
        # Parse JSON
        json_match = re.search(r'\{.*?"chapter_1_pdf_page".*?\}', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            pdf_page = result.get("chapter_1_pdf_page")
            
            if pdf_page and pdf_page in candidate_pages:
                offset = pdf_page - first_chapter_book_page
                confidence = result.get("confidence", "unknown")
                logger.info(
                    f"LLM identified Chapter 1 at PDF page {pdf_page} "
                    f"(book page {first_chapter_book_page}), offset = {offset} (confidence: {confidence})"
                )
                return offset
            else:
                logger.warning(f"LLM returned invalid page number: {pdf_page}")
    
    except Exception as e:
        logger.error(f"Failed to verify Chapter 1 with LLM: {e}", exc_info=True)
    
    # Fallback: Use first candidate page
    offset = candidate_pages[0] - first_chapter_book_page
    logger.warning(
        f"LLM verification failed, using first candidate page {candidate_pages[0]}, "
        f"offset = {offset}"
    )
    return offset


def parse_toc_llm(
    pdf_bytes: bytes,
    pages: List[str],
    book_title: str = "Unknown Book",
) -> TOCParseResult:
    """
    Main function to parse TOC and extract chapter information using LLM.
    
    Args:
        pdf_bytes: PDF file as bytes
        pages: List of page text content
        book_title: Title of the book
    
    Returns:
        TOCParseResult with chapters, TOC pages, and page offset
    """
    # Step 1: Find TOC using LLM
    toc_pages = find_toc(
        pdf_bytes=pdf_bytes,
        pages=pages,
        book_title=book_title,
    )
    if not toc_pages:
        logger.warning("Could not find TOC, returning empty result")
        return TOCParseResult(
            chapters=[],
            toc_start_page=0,
            toc_end_page=0,
            page_offset=0,
            raw_toc_text="",
        )
    
    toc_start, toc_end = toc_pages
    
    # Extract TOC text
    toc_text_parts = []
    for page_idx in range(toc_start - 1, toc_end):  # Convert to 0-indexed
        if page_idx < len(pages):
            toc_text_parts.append(pages[page_idx])
    toc_text = "\n".join(toc_text_parts)
    
    # Step 2: Identify chapter ranges
    chapters = identify_chapter_ranges(
        pdf_bytes=pdf_bytes,
        toc_pages=toc_pages,
        pages=pages,
        book_title=book_title,
    )
    
    # Step 3: Find page offset (using first chapter info and hyperlinks)
    page_offset = 0
    if chapters:
        first_chapter = chapters[0]
        # Try to find offset using hyperlinks first (more reliable)
        if first_chapter.start_page:
            # Extract hyperlinks from TOC to find where Chapter 1 actually points
            document = fitz.open(stream=pdf_bytes, filetype="pdf")
            chapter_1_pdf_page = None
            
            for page_num in range(toc_start, toc_end + 1):
                try:
                    page = document[page_num - 1]
                    links = page.get_links()
                    for link in links:
                        if link.get("kind") == fitz.LINK_GOTO:
                            dest_page = link.get("page", -1) + 1
                            link_rect = link.get("from")
                            if link_rect:
                                try:
                                    link_text = page.get_textbox(link_rect).strip()
                                    # Check if this link is for Chapter 1
                                    link_text_upper = link_text.upper()
                                    first_chapter_title_upper = first_chapter.title.upper()
                                    
                                    # Match if link text contains "CHAPTER 1" or matches the first chapter title
                                    is_chapter_1 = (
                                        "CHAPTER 1" in link_text_upper or
                                        (first_chapter.chapter_number == 1 and 
                                         first_chapter_title_upper in link_text_upper) or
                                        (first_chapter.chapter_number == 1 and 
                                         (link_text_upper.startswith("CHAPTER 1") or
                                          link_text_upper.startswith("CH. 1")))
                                    )
                                    
                                    if is_chapter_1:
                                        chapter_1_pdf_page = dest_page
                                        logger.debug(f"Found Chapter 1 hyperlink: '{link_text}' → PDF page {dest_page}")
                                        break
                                except:
                                    pass
                    if chapter_1_pdf_page:
                        break
                except:
                    pass
            
            if chapter_1_pdf_page:
                page_offset = chapter_1_pdf_page - first_chapter.start_page
                logger.info(
                    f"Found page offset using hyperlinks: "
                    f"Chapter 1 book page {first_chapter.start_page} → PDF page {chapter_1_pdf_page}, "
                    f"offset = {page_offset}"
                )
                document.close()
            else:
                document.close()
                # Fall back to LLM-based search
                page_offset = find_page_offset(
                    pdf_bytes=pdf_bytes,
                    toc_pages=toc_pages,
                    pages=pages,
                    first_chapter_book_page=first_chapter.start_page,
                    first_chapter_title=first_chapter.title,
                    book_title=book_title,
                )
        else:
            # No page number for first chapter, can't calculate offset
            logger.warning("First chapter has no page number, cannot calculate offset")
    
    return TOCParseResult(
        chapters=chapters,
        toc_start_page=toc_start,
        toc_end_page=toc_end,
        page_offset=page_offset,
        raw_toc_text=toc_text,
    )


def identify_chapter_level(
    toc_raw: List[Tuple[int, str, int]],
    book_title: str = "Unknown Book",
) -> Optional[int]:
    """
    Use LLM to identify which TOC level contains the actual chapters.
    
    This is useful when PyMuPDF finds TOC entries but we need to determine
    which level (1, 2, 3, etc.) actually represents chapters vs sections.
    
    Args:
        toc_raw: List of (level, title, page) tuples from PyMuPDF
        book_title: Title of the book
    
    Returns:
        The level number that contains chapters, or None if uncertain
    """
    # Count entries by level
    level_counts = {}
    level_samples = {}  # Sample entries for each level
    
    for level, title, page in toc_raw[:100]:  # Analyze first 100 entries
        level_counts[level] = level_counts.get(level, 0) + 1
        if level not in level_samples:
            level_samples[level] = []
        if len(level_samples[level]) < 5:  # Keep 5 samples per level
            level_samples[level].append((title, page))
    
    if not level_counts:
        return None
    
    # Build summary for LLM
    level_summary = []
    for level in sorted(level_counts.keys()):
        count = level_counts[level]
        samples = level_samples.get(level, [])
        sample_text = "\n".join([f"  - {title[:60]} (page {page})" for title, page in samples[:3]])
        level_summary.append(f"Level {level}: {count} entries\n{sample_text}")
    
    summary_text = "\n\n".join(level_summary)
    
    prompt = f"""You are analyzing the table of contents structure for a book titled "{book_title}".

The PDF has a hierarchical TOC structure with multiple levels. Here's what was extracted:

{summary_text}

Your task: Determine which level contains the ACTUAL CHAPTERS (not PARTS, not sections, not subsections).

Consider:
- PARTS (Part One, Part Two, etc.) are containers, not chapters
- CHAPTERS are the main content divisions (Chapter 1, Chapter 2, etc.)
- Sections are subdivisions within chapters
- The chapter level typically has:
  * Explicit "Chapter N" patterns
  * Sequential numbering
  * Substantial titles
  * Reasonable page gaps between entries (chapters span multiple pages)

Return a JSON object:
{{
  "chapter_level": <level_number>,
  "confidence": "high" | "medium" | "low",
  "reason": "brief explanation"
}}

If you cannot determine with confidence, return:
{{
  "chapter_level": null,
  "confidence": "low",
  "reason": "explanation"
}}"""

    try:
        response = invoke_claude(
            messages=[{
                "role": "user",
                "content": [{"type": "text", "text": prompt}]
            }],
            max_tokens=500,
            temperature=0.3,
        )
        
        response_text = response['content']
        logger.debug(f"LLM chapter level detection response: {response_text}")
        
        # Parse JSON
        json_match = re.search(r'\{.*?"chapter_level".*?\}', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            chapter_level = result.get("chapter_level")
            confidence = result.get("confidence", "unknown")
            
            if chapter_level is not None:
                logger.info(f"LLM identified chapter level: {chapter_level} (confidence: {confidence})")
                return chapter_level
            else:
                logger.info("LLM could not determine chapter level with confidence")
    
    except Exception as e:
        logger.error(f"Failed to identify chapter level with LLM: {e}", exc_info=True)
    
    return None


def convert_chapter_ranges_to_toc_raw(
    chapters: List[ChapterRange],
    page_offset: int = 0,
) -> List[Tuple[int, str, int]]:
    """
    Convert ChapterRange objects to toc_raw format (level, title, page).
    
    This allows LLM-extracted chapters to be processed by the same
    parse_toc_structure() function used for PyMuPDF results.
    
    Args:
        chapters: List of ChapterRange objects
        page_offset: Offset between PDF pages and book pages
    
    Returns:
        List of (level, title, page) tuples compatible with toc_raw format
    """
    toc_raw = []
    for chapter in chapters:
        # All chapters are at level 1 in the converted format
        # (parse_toc_structure will handle hierarchical structures)
        pdf_page = chapter.start_page + page_offset if chapter.start_page else None
        if pdf_page:
            toc_raw.append((1, chapter.title, pdf_page))
        else:
            # If no page number, still include it but with page 0
            # (parse_toc_structure can handle this)
            toc_raw.append((1, chapter.title, 0))
    
    return toc_raw
