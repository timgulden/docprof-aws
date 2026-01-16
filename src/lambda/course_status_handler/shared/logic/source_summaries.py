"""
Source summary generation logic - pure functions.
Adapted from MAExpert book_summaries.py for Lambda/S3 environment.
"""

from typing import Any, Dict, List, Optional
import json
import logging
import re

from shared.core.commands import LLMCommand, ExtractTOCCommand, ExtractChapterTextCommand, StoreSourceSummaryCommand
from shared.core.state import LogicResult

logger = logging.getLogger(__name__)


def is_front_matter(title: str) -> bool:
    """
    Check if a TOC entry is front matter (not a real content chapter).
    
    Pure function: string matching only.
    
    Args:
        title: Chapter/section title from TOC
    
    Returns:
        True if this is front matter, False if it's a real chapter
    """
    title_lower = title.lower().strip()
    
    # Common front matter patterns
    front_matter_patterns = [
        "table of contents",
        "contents",
        "title page",
        "copyright",
        "dedication",
        "preface",
        "foreword",
        "acknowledgments",
        "acknowledgements",
        "introduction",  # Sometimes intro is separate from Chapter 1
        "prologue",
        "list of",
        "about the",
        "about this",
    ]
    
    # Check if title matches any front matter pattern
    for pattern in front_matter_patterns:
        if pattern in title_lower:
            return True
    
    return False


# Removed: is_real_chapter(), is_part(), is_chapter_title()
# These complex heuristics are not needed with LLM extraction.
# LLM extraction already filters chapters, returns them as Level 1 entries.
# Simple parse_toc_structure (below) trusts the extraction.


def parse_toc_structure(
    toc_raw: List[tuple],
    source_title: str,
    author: str,
    total_pages: int,
) -> Dict[str, Any]:
    """
    Parse raw TOC into structured format with chapters and sections.
    
    SIMPLIFIED LEGACY LOGIC (tested and working):
    - Level 1 = chapters (skip front matter only)
    - Level 2+ = sections
    
    When LLM extraction is used (hyperlink/visual), all entries come in as Level 1,
    so this naturally treats them all as chapters.
    
    Pure function: transforms data structure.
    
    Args:
        toc_raw: List of (level, title, page) tuples from extraction
        source_title: Source title
        author: Source author
        total_pages: Total pages in source
    
    Returns:
        Structured TOC with chapters and nested sections (front matter excluded)
    """
    chapters: List[Dict[str, Any]] = []
    current_chapter: Optional[Dict[str, Any]] = None
    found_first_real_chapter = False
    
    for level, title, page in toc_raw:
        # Level 1 items are chapters
        if level == 1:
            # Check if this is front matter
            if is_front_matter(title):
                # Skip front matter - don't save current chapter if it's front matter
                if current_chapter and not found_first_real_chapter:
                    current_chapter = None
                continue
            
            # This is a real chapter (simple - trust the extraction)
            found_first_real_chapter = True
            
            # Save previous chapter if exists
            if current_chapter:
                chapters.append(current_chapter)
            
            # Start new chapter
            current_chapter = {
                "chapter_number": len(chapters) + 1,
                "chapter_title": title.strip(),
                "page_number": page,
                "sections": [],
            }
        
        elif level >= 2 and current_chapter:
            # All Level 2+ items are sections (simple - no conditional logic)
            current_chapter["sections"].append({
                "section_title": title.strip(),
                "page_number": page,
                "level": level,
            })
    
    # Add final chapter
    if current_chapter:
        chapters.append(current_chapter)
    
    return {
        "source_title": source_title,
        "author": author,
        "total_pages": total_pages,
        "chapters": chapters,
    }


def calculate_chapter_page_range(
    chapter: Dict[str, Any],
    next_chapter: Optional[Dict[str, Any]],
    total_pages: int,
) -> tuple:
    """
    Calculate page range for a chapter.
    
    Pure function: calculates start and end pages.
    
    Args:
        chapter: Current chapter dict with page_number
        next_chapter: Next chapter dict (if exists)
        total_pages: Total pages in source
    
    Returns:
        (start_page, end_page) tuple
    """
    start_page = chapter["page_number"]
    
    if next_chapter:
        end_page = next_chapter["page_number"] - 1
    else:
        end_page = total_pages
    
    return (start_page, end_page)


def build_chapter_summary_prompt_variables(
    chapter_number: int,
    chapter_title: str,
    chapter_text: str,
    sections: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build variables for chapter summary generation prompt.
    
    Pure function: prepares variables for prompt template.
    """
    # Format sections from TOC
    sections_list = "\n".join([
        f"- {s['section_title']} (page {s['page_number']})"
        for s in sections
    ])
    
    # Limit chapter text to avoid token limits (keep ~500k chars, ~125k tokens)
    # Standard 200k token context window can handle up to ~800k chars, so 500k is safe
    # This prevents truncation for most chapters while staying well within limits
    text_preview = chapter_text[:500000] if len(chapter_text) > 500000 else chapter_text
    if len(chapter_text) > 500000:
        text_preview += "\n\n[Content truncated for length (chapter exceeds 500k characters)...]"
    
    return {
        "chapter_number": chapter_number,
        "chapter_title": chapter_title,
        "sections_list": sections_list,
        "text_preview": text_preview,
    }


def generate_chapter_summary(
    chapter: Dict[str, Any],
    chapter_text: str,
) -> LogicResult:
    """
    Generate summary for a single chapter.
    
    Pure function: returns command to call LLM.
    """
    prompt_variables = build_chapter_summary_prompt_variables(
        chapter["chapter_number"],
        chapter["chapter_title"],
        chapter_text,
        chapter.get("sections", []),
    )
    
    return LogicResult(
        new_state={},
        commands=[
            LLMCommand(
                prompt_name="source_summaries.chapter",
                prompt_variables=prompt_variables,
                task="generate_chapter_summary",
                temperature=0.0,  # Zero temperature for precision - we need valid JSON, not creative variation
                max_tokens=2000,
            )
        ],
        ui_message=f"Summarizing chapter {chapter['chapter_number']}: {chapter['chapter_title']}...",
    )


def build_source_overview_prompt_variables(
    chapter_one_text: str,
) -> Dict[str, Any]:
    """
    Build variables for source overview extraction prompt.
    
    Pure function: prepares variables for prompt template.
    Chapter 1 typically contains the source's introduction and overview.
    """
    return {
        "chapter_one_text": chapter_one_text[:10000],  # First 10k chars should have the overview
    }


def assemble_source_summary_json(
    source_title: str,
    author: str,
    chapter_summaries: List[Dict[str, Any]],
    source_summary_text: str,
) -> str:
    """
    Mechanically assemble source summary JSON from chapter summaries.
    
    Pure function: JSON assembly only, no LLM call.
    """
    source_summary = {
        "source_title": source_title,
        "author": author,
        "total_chapters": len(chapter_summaries),
        "chapters": chapter_summaries,
        "source_summary": source_summary_text,
    }
    
    return json.dumps(source_summary, indent=2)


def start_source_summary_generation(
    source_id: str,
    source_title: str,
    author: str,
    s3_bucket: str,
    s3_key: str,
) -> LogicResult:
    """
    Start source summary generation process.
    
    Pure function: returns command to extract TOC.
    """
    return LogicResult(
        new_state={
            "source_id": source_id,
            "source_title": source_title,
            "author": author,
            "s3_bucket": s3_bucket,
            "s3_key": s3_key,
            "chapter_summaries": [],
            "current_chapter_index": 0,
            "chapter_one_text": None,
        },
        commands=[
            ExtractTOCCommand(
                s3_bucket=s3_bucket,
                s3_key=s3_key,
            )
        ],
        ui_message="Extracting table of contents...",
    )


def handle_toc_extracted(
    state: Dict[str, Any],
    toc_result: Dict[str, Any],
) -> LogicResult:
    """
    Handle TOC extraction result.
    
    Parse TOC and start processing first chapter.
    """
    toc_data = parse_toc_structure(
        toc_result["toc_raw"],
        state["source_title"],
        state["author"],
        toc_result["total_pages"],
    )
    
    chapters = toc_data.get("chapters", [])
    
    if not chapters:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="No chapters found in TOC",
        )
    
    # Preserve all existing state keys, add new ones
    new_state = dict(state)  # Make a copy
    new_state.update({
        "toc_data": toc_data,
        "total_pages": toc_result["total_pages"],
    })
    
    # Start with first chapter
    first_chapter = chapters[0]
    return process_chapter(new_state, first_chapter, 0)


def process_chapter(
    state: Dict[str, Any],
    chapter: Dict[str, Any],
    chapter_index: int,
) -> LogicResult:
    """
    Process a single chapter: extract text, then generate summary.
    """
    # Calculate page range
    next_chapter = None
    if chapter_index + 1 < len(state["toc_data"]["chapters"]):
        next_chapter = state["toc_data"]["chapters"][chapter_index + 1]
    
    start_page, end_page = calculate_chapter_page_range(
        chapter,
        next_chapter,
        state["total_pages"],
    )
    
    return LogicResult(
        new_state=state,
        commands=[
            ExtractChapterTextCommand(
                s3_bucket=state["s3_bucket"],
                s3_key=state["s3_key"],
                start_page=start_page,
                end_page=end_page,
                chapter_title=chapter["chapter_title"],
            )
        ],
        ui_message=f"Extracting text for chapter {chapter['chapter_number']}: {chapter['chapter_title']}...",
    )


def handle_chapter_text_extracted(
    state: Dict[str, Any],
    chapter_text: str,
    chapter: Dict[str, Any],
) -> LogicResult:
    """
    Handle chapter text extraction - generate summary.

    Also store Chapter 1 text for source summary extraction.
    """
    # Store Chapter 1 text for source summary
    new_state = state.copy()
    if chapter.get("chapter_number") == 1:
        new_state["chapter_one_text"] = chapter_text

    # Generate chapter summary command
    summary_result = generate_chapter_summary(chapter, chapter_text)
    
    # Preserve state (including toc_data) while adding the command
    return LogicResult(
        new_state=new_state,  # Preserve all state including toc_data
        commands=summary_result.commands,
        ui_message=summary_result.ui_message,
    )


def repair_json_with_llm(
    malformed_json: str,
    parse_error: str,
    chapter_number: int,
    chapter_title: str,
    sections_list: str,
) -> LogicResult:
    """
    Use LLM to repair malformed JSON.
    
    Pure function: returns command to call LLM for JSON repair.
    """
    prompt_variables = {
        "malformed_json": malformed_json[:5000],  # Limit length
        "parse_error": parse_error,
        "chapter_number": chapter_number,
        "chapter_title": chapter_title,
        "sections_list": sections_list[:2000] if sections_list else "",  # Limit length
    }
    
    return LogicResult(
        new_state={},
        commands=[
            LLMCommand(
                prompt_name="source_summaries.repair_json",
                prompt_variables=prompt_variables,
                task="repair_json",
                temperature=0.0,  # Zero temperature for precision - no creativity needed
                max_tokens=2500,  # Slightly more than original to allow for fixes
            )
        ],
        ui_message=f"Repairing malformed JSON for chapter {chapter_number}...",
    )


def handle_chapter_summary_generated(
    state: Dict[str, Any],
    chapter_summary_json: str,
    max_chapters: Optional[int] = None,
) -> LogicResult:
    """
    Handle chapter summary - store and move to next chapter.
    
    Args:
        state: Current state
        chapter_summary_json: JSON string from LLM
        max_chapters: Optional limit on number of chapters to process (for testing)
    """
    try:
        chapter_summary = json.loads(chapter_summary_json)
    except json.JSONDecodeError:
        # Try to extract and clean JSON from markdown or malformed JSON
        import re
        
        # Step 1: Remove markdown code blocks if present
        cleaned_json = chapter_summary_json.strip()
        if cleaned_json.startswith("```"):
            # Remove markdown code block markers
            cleaned_json = re.sub(r"^```(?:json)?\s*\n?", "", cleaned_json)
            cleaned_json = re.sub(r"\n?```\s*$", "", cleaned_json)
        
        # Step 2: Extract JSON object using regex (more robust)
        json_match = re.search(r"\{.*\}", cleaned_json, re.DOTALL)
        if not json_match:
            logger.error(f"Could not find JSON object in response: {cleaned_json[:500]}")
            return LogicResult(
                new_state=state,
                commands=[],
                ui_message="Error: Could not find JSON object in chapter summary",
            )
        
        json_str = json_match.group()
        
        # Step 3: Try to fix common JSON issues
        # Remove trailing commas before closing braces/brackets (more aggressive)
        json_str = re.sub(r",(\s*[}\]])", r"\1", json_str)
        
        # Remove comments (though JSON doesn't support them)
        json_str = re.sub(r"//.*?$", "", json_str, flags=re.MULTILINE)
        json_str = re.sub(r"/\*.*?\*/", "", json_str, flags=re.DOTALL)
        
        # Remove any control characters except newlines and tabs
        json_str = ''.join(char if ord(char) >= 32 or char in '\n\t' else ' ' for char in json_str)
        
        # Try to fix common structural issues
        # Fix missing commas: look for }" or ]" patterns and add comma
        json_str = re.sub(r'}\s*"', r'}, "', json_str)
        json_str = re.sub(r']\s*"', r'], "', json_str)
        
        # Fix missing commas after values before closing brace
        # Pattern: "value" } -> "value", }
        json_str = re.sub(r'(")\s*}', r'\1, }', json_str)
        json_str = re.sub(r'(\d+)\s*}', r'\1, }', json_str)
        
        # But be careful - if we just added a comma before }, remove trailing commas again
        json_str = re.sub(r",(\s*[}\]])", r"\1", json_str)
        
        try:
            chapter_summary = json.loads(json_str)
        except json.JSONDecodeError as e:
            # Log the problematic JSON for debugging
            error_pos = getattr(e, 'pos', None)
            logger.error(f"JSON parse error after cleaning: {e}")
            if error_pos:
                start = max(0, error_pos - 300)
                end = min(len(json_str), error_pos + 300)
                problematic_section = json_str[start:end]
                logger.error(f"Problematic area around position {error_pos} (chars {start}-{end}):\n{repr(problematic_section)}")
            else:
                logger.error(f"Problematic JSON (first 1500 chars): {json_str[:1500]}")
            
            # Try one more time with more aggressive cleaning
            # Remove any non-printable characters except newlines and tabs
            json_str_clean = re.sub(r'[^\x20-\x7E\n\t]', '', json_str)
            
            # Fix missing commas - this is the most common issue
            # Pattern: "value" "key" -> "value", "key"  
            # Pattern: "value" } -> "value", }
            # Pattern: number "key" -> number, "key"
            # Pattern: } "key" -> }, "key"
            # Pattern: ] "key" -> ], "key"
            
            # More sophisticated: find places where we have a value followed by a quote (new key)
            # This handles: "value" "key" or number "key" or } "key"
            json_str_clean = re.sub(r'(")\s+(")', r'\1, \2', json_str_clean)  # "value" "key"
            json_str_clean = re.sub(r'(\d+)\s+(")', r'\1, \2', json_str_clean)  # number "key"
            json_str_clean = re.sub(r'}\s+(")', r'}, \1', json_str_clean)  # } "key"
            json_str_clean = re.sub(r']\s+(")', r'], \1', json_str_clean)  # ] "key"
            json_str_clean = re.sub(r'(true|false|null)\s+(")', r'\1, \2', json_str_clean)  # bool/null "key"
            
            # Fix missing commas before closing braces/brackets (but only if not already there)
            # This is tricky - we want to add commas but not duplicate them
            # Actually, let's remove trailing commas first, then the above fixes should work
            
            # Remove trailing commas again after our fixes
            json_str_clean = re.sub(r",(\s*[}\]])", r"\1", json_str_clean)
            
            try:
                chapter_summary = json.loads(json_str_clean)
                logger.info("Successfully parsed JSON after aggressive cleaning")
            except json.JSONDecodeError as e2:
                error_pos2 = getattr(e2, 'pos', None)
                error_msg2 = str(e2)
                logger.warning(f"JSON parse error after aggressive cleaning: {e2}")
                if error_pos2:
                    start2 = max(0, error_pos2 - 200)
                    end2 = min(len(json_str_clean), error_pos2 + 200)
                    logger.warning(f"Still problematic area (chars {start2}-{end2}): {repr(json_str_clean[start2:end2])}")
                
                # NEW: Try LLM-based JSON repair before manual extraction
                # Get chapter context from state
                current_idx = state.get('current_chapter_index', 0)
                chapter_number = current_idx + 1  # Default to 1-indexed
                chapter_title = "Unknown"
                sections_list = ""
                
                if state.get('toc_data'):
                    toc_data = state['toc_data']
                    current_chapter = None
                    if current_idx < len(toc_data.get('chapters', [])):
                        current_chapter = toc_data['chapters'][current_idx]
                        chapter_title = current_chapter.get('title', 'Unknown')
                        chapter_number = current_chapter.get('chapter_number', chapter_number)
                        
                        # Build sections list from TOC
                        if current_chapter.get('sections'):
                            sections_list = "\n".join([
                                f"- {s.get('title', 'Unknown')} (pages {s.get('page_start', '?')}-{s.get('page_end', '?')})"
                                for s in current_chapter['sections']
                            ])
                
                logger.info(
                    f"Attempting LLM-based JSON repair for chapter {chapter_number} "
                    f"({chapter_title}). Error: {error_msg2}"
                )
                
                # Return command to repair JSON using LLM
                # This will be handled by the handler, which will call the LLM and then
                # call handle_chapter_summary_generated again with the repaired JSON
                return repair_json_with_llm(
                    malformed_json=json_str_clean,
                    parse_error=error_msg2,
                    chapter_number=chapter_number,
                    chapter_title=chapter_title,
                    sections_list=sections_list,
                )
                
                # Last resort: try to extract just the essential fields manually
                # (This code should rarely be reached now that we have LLM repair)
                logger.warning("LLM repair failed, attempting manual JSON field extraction as final fallback")
                try:
                    # Extract chapter_number (more flexible patterns)
                    chapter_num_match = re.search(r'"chapter_number"\s*:\s*(\d+)', json_str_clean) or re.search(r'chapter_number["\s]*:\s*(\d+)', json_str_clean)
                    chapter_title_match = re.search(r'"chapter_title"\s*:\s*"([^"]+)"', json_str_clean) or re.search(r'chapter_title["\s]*:\s*"([^"]+)"', json_str_clean)
                    
                    # Extract summary (handle multi-line and escaped quotes)
                    summary_match = re.search(r'"summary"\s*:\s*"((?:[^"\\]|\\.|\\n)*?)"', json_str_clean, re.DOTALL)
                    
                    # Extract sections if present
                    sections_match = re.search(r'"sections"\s*:\s*\[(.*?)\]', json_str_clean, re.DOTALL)
                    sections = []
                    if sections_match:
                        # Try to extract section titles
                        section_titles = re.findall(r'"section_title"\s*:\s*"([^"]+)"', sections_match.group(1))
                        for i, title in enumerate(section_titles):
                            sections.append({
                                "section_title": title,
                                "topics": [],
                                "key_concepts": [],
                                "page_range": ""
                            })
                    
                    if chapter_num_match and chapter_title_match:
                        chapter_summary = {
                            "chapter_number": int(chapter_num_match.group(1)),
                            "chapter_title": chapter_title_match.group(1),
                            "summary": summary_match.group(1) if summary_match else "",
                            "sections": sections
                        }
                        logger.warning(
                            f"MANUAL EXTRACTION FALLBACK USED: Chapter {chapter_summary.get('chapter_number')} "
                            f"({chapter_summary.get('chapter_title', 'Unknown')}) - Both JSON parsing and LLM repair failed, "
                            f"extracted minimal fields via regex. This indicates serious LLM output quality issues."
                        )
                        # Add metadata to indicate manual extraction was used
                        chapter_summary['_extraction_method'] = 'manual_fallback'
                        chapter_summary['_extraction_warning'] = 'Both JSON parsing and LLM repair failed, used regex-based field extraction'
                    else:
                        logger.error(f"Could not extract essential fields. chapter_num: {bool(chapter_num_match)}, chapter_title: {bool(chapter_title_match)}")
                        raise ValueError("Could not extract essential fields from malformed JSON")
                except Exception as manual_error:
                    logger.error(f"Manual extraction also failed: {manual_error}", exc_info=True)
                    return LogicResult(
                        new_state=state,
                        commands=[],
                        ui_message=f"Error: Could not parse chapter summary JSON even with LLM repair and manual extraction: {str(manual_error)}",
                    )
    
    # Add to state - ensure chapter_summaries exists
    current_summaries = state.get("chapter_summaries", [])
    new_summaries = current_summaries + [chapter_summary]
    new_state = dict(state)  # Make a copy - preserve all existing state including toc_data
    new_state.update({
        "chapter_summaries": new_summaries,
        "current_chapter_index": state.get("current_chapter_index", 0) + 1,
    })
    
    # Check if we've hit the limit (for testing) or all chapters done
    # Ensure toc_data exists before accessing it
    toc_data = state.get("toc_data") or new_state.get("toc_data")
    if not toc_data or "chapters" not in toc_data:
        logger.error("toc_data missing from state - cannot determine remaining chapters")
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="Error: Table of contents data missing - cannot continue",
        )
    remaining = len(toc_data["chapters"]) - new_state["current_chapter_index"]
    is_complete = remaining == 0 or (max_chapters and len(new_summaries) >= max_chapters)
    
    if is_complete:
        # All chapters done (or max_chapters reached) - extract source summary and assemble JSON
        logger.info(f"Processing complete: {len(new_summaries)} chapters processed")
        
        if new_state.get("chapter_one_text"):
            # Extract source summary from Chapter 1
            logger.info("Extracting source overview from Chapter 1...")
            prompt_variables = build_source_overview_prompt_variables(new_state["chapter_one_text"])
            return LogicResult(
                new_state=new_state,
                commands=[
                    LLMCommand(
                        prompt_name="source_summaries.extract_overview",
                        prompt_variables=prompt_variables,
                        task="extract_source_summary",
                        temperature=0.7,
                        max_tokens=500,  # Short summary
                    )
                ],
                ui_message="Extracting source overview from Chapter 1...",
            )
        else:
            # No Chapter 1 text - create simple summary
            logger.warning("No Chapter 1 text found - creating simple summary")
            source_summary_text = f"{new_state['source_title']} by {new_state['author']} covers {len(new_summaries)} chapters. This is a partial summary (processing stopped early)."
            summary_json = assemble_source_summary_json(
                new_state["source_title"],
                new_state["author"],
                new_summaries,
                source_summary_text,
            )
            return LogicResult(
                new_state=new_state,
                commands=[
                    StoreSourceSummaryCommand(
                        source_id=new_state["source_id"],
                        summary_json=summary_json,
                    )
                ],
                ui_message="Assembling source summary...",
            )
    
    # More chapters to process
    next_chapter = state["toc_data"]["chapters"][new_state["current_chapter_index"]]
    return process_chapter(new_state, next_chapter, new_state["current_chapter_index"])


def handle_source_summary_extracted(
    state: Dict[str, Any],
    source_summary_text: str,
) -> LogicResult:
    """
    Handle source summary extraction from Chapter 1 - assemble JSON and store.
    
    Pure function: mechanically assembles JSON, no LLM call.
    """
    summary_json = assemble_source_summary_json(
        state["source_title"],
        state["author"],
        state["chapter_summaries"],
        source_summary_text,
    )
    
    return LogicResult(
        new_state=state,
        commands=[
            StoreSourceSummaryCommand(
                source_id=state["source_id"],
                summary_json=summary_json,
            )
        ],
        ui_message="Source summary assembled and ready to store!",
    )
