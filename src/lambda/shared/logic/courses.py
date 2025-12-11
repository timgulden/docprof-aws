"""Course system logic layer - pure functions for course management."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import logging

logger = logging.getLogger(__name__)

from shared.core.commands import (
    CreateCourseCommand,
    CreateSectionsCommand,
    UpdateCourseCommand,
    UpdateSectionsCommand,
    DeleteSectionsCommand,
    EmbedCommand,
    LLMCommand,
    QuerySectionsCommand,
    RetrieveChunksCommand,
    StoreLectureCommand,
    UpdateSectionStatusCommand,
    LoadSectionCommand,
    CheckPrerequisitesCommand,
    CreateQASessionCommand,
    AppendQAMessageCommand,
    EndQASessionCommand,
    RecordCourseHistoryCommand,
    SearchCorpusCommand,
    SearchBookSummariesCommand,
    UpdateGenerationProgressCommand,
    GenerateAudioCommand,
)
from shared.core.course_models import (
    Course,
    CourseSection,
    CoursePreferences,
    CourseState,
    SectionDelivery,
    QASession,
    QAMessage,
)
from shared.core.course_events import (
    CourseEvent,
    CourseRequestedEvent,
    EmbeddingGeneratedEvent,
    CorpusSearchCompletedEvent,
    BookSummariesFoundEvent,
    OutlineGeneratedEvent,  # Legacy
    PartsGeneratedEvent,  # Phase 1
    PartSectionsGeneratedEvent,  # Phase 2-N
    AllPartsCompleteEvent,  # All parts done
    OutlineReviewEvent,  # Phase N+1
    CourseStoredEvent,
    CourseEventError,
)
from shared.core.state import LogicResult


def create_initial_course_state() -> CourseState:
    """Return the canonical empty course state."""
    return CourseState()


def reduce_course_event(state: CourseState, event: CourseEvent) -> LogicResult:
    """
    Main reducer that routes incoming course events to pure handlers.
    
    This is the entry point for all course-related events, following
    the same pattern as reduce_chat_event.
    """
    if isinstance(event, CourseRequestedEvent):
        return request_course(
            state,
            query=event.query,
            time_hours=event.time_hours,
            preferences=event.preferences,
        )
    
    elif isinstance(event, EmbeddingGeneratedEvent):
        return handle_embedding_generated(state, event.embedding)
    
    elif isinstance(event, CorpusSearchCompletedEvent):
        return handle_corpus_search_result(state, event.chunks)
    
    elif isinstance(event, BookSummariesFoundEvent):
        return handle_book_summaries_found(state, event.books)
    
    elif isinstance(event, PartsGeneratedEvent):
        return handle_parts_generated(state, event.parts_text)
    
    elif isinstance(event, PartSectionsGeneratedEvent):
        return handle_part_sections_generated(state, event.sections_text, event.part_index)
    
    elif isinstance(event, AllPartsCompleteEvent):
        return check_and_review_outline(state)
    
    elif isinstance(event, OutlineReviewEvent):
        return handle_outline_reviewed(state, event.reviewed_outline_text)
    
    elif isinstance(event, OutlineGeneratedEvent):  # Legacy
        return store_course_outline(state, event.outline_json)
    
    elif isinstance(event, CourseStoredEvent):
        # Course is stored, return success state
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="Course created successfully!",
        )
    
    elif isinstance(event, CourseEventError):
        # Handle error - could update state with error info
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message=f"Error: {event.error_message}",
        )
    
    else:
        # Exhaustiveness check
        raise ValueError(f"Unhandled course event: {type(event)}")


def handle_embedding_generated(
    state: CourseState,
    embedding: List[float],
) -> LogicResult:
    """
    Handle embedding generation result.
    
    Continues pipeline by searching corpus.
    """
    return find_relevant_corpus_areas(state, embedding)


def request_course(
    state: CourseState,
    query: str,
    time_hours: float,
    preferences: Optional[CoursePreferences] = None,
) -> LogicResult:
    """
    Initiate course creation.
    
    This is the entry point when user requests a new course.
    Creates course record and triggers outline generation pipeline.
    """
    from uuid import uuid4
    
    # Create course with basic info
    course = Course(
        user_id=state.session_id or str(uuid4()),  # TODO: Get from auth context
        title="",  # Will be set by LLM
        original_query=query,
        estimated_hours=time_hours,
        preferences=preferences or CoursePreferences(),
    )
    
    # Store pending course info in state
    new_state = state.model_copy(
        update={
            "pending_course_query": query,
            "pending_course_hours": time_hours,
            "pending_course_prefs": preferences or CoursePreferences(),
        }
    )
    
    # Step 1: Find relevant corpus areas
    return LogicResult(
        new_state=new_state,
        commands=[
            EmbedCommand(text=query, task="find_relevant_corpus"),
        ],
        ui_message="Analyzing your request and finding relevant material...",
    )


def find_relevant_corpus_areas(
    state: CourseState,
    query_embedding: List[float],
) -> LogicResult:
    """
    Search book summaries for relevant books based on user query.
    
    This finds the source material that will inform the course outline.
    Uses semantic search on book summary embeddings.
    """
    # Search for relevant book summaries
    search_cmd = SearchBookSummariesCommand(
        query_embedding=query_embedding,
        top_k=10,
        min_similarity=0.2,
    )
    
    new_state = state.model_copy(
        update={
            "pending_book_search": True,
        }
    )
    
    return LogicResult(
        new_state=new_state,
        commands=[search_cmd],
        ui_message="Searching knowledge base for relevant material...",
    )


def handle_corpus_search_result(
    state: CourseState,
    search_results: List[Dict[str, Any]],
) -> LogicResult:
    """
    Handle result from corpus search (legacy - kept for backward compatibility).
    """
    new_state = state.model_copy(
        update={
            "pending_corpus_search": False,
        }
    )
    
    return generate_course_outline(new_state, search_results)


def handle_book_summaries_found(
    state: CourseState,
    books: List[Dict[str, Any]],
) -> LogicResult:
    """
    Handle result from book summary search.
    
    Uses book summaries to generate course outline.
    """
    # Store book summaries JSON in state for Phase 2-N
    import json
    book_summaries_json = []
    for book in books:
        summary_json = book.get("summary_json")
        if isinstance(summary_json, str):
            summary_json = json.loads(summary_json)
        book_summaries_json.append(summary_json)
    summaries_json_str = json.dumps(book_summaries_json, indent=2)
    
    new_state = state.model_copy(
        update={
            "pending_book_search": False,
            "book_summaries_json": summaries_json_str,
        }
    )
    
    return generate_course_parts(new_state, books)


def generate_course_parts(
    state: CourseState,
    books: List[Dict[str, Any]],
) -> LogicResult:
    """
    Phase 1: Generate course parts structure.
    
    Identifies major topic areas (parts) that organize the course,
    ensuring no single part exceeds 2 hours.
    """
    import json
    
    query = state.pending_course_query or ""
    hours = state.pending_course_hours or 2.0
    target_minutes = int(hours * 60)
    
    if not books:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="No relevant books found. Please try a different query.",
        )
    
    # Format book summaries for context
    book_summaries_json = []
    for book in books:
        summary_json = book.get("summary_json")
        if isinstance(summary_json, str):
            summary_json = json.loads(summary_json)
        book_summaries_json.append(summary_json)
    
    summaries_context = json.dumps(book_summaries_json, indent=2)
    
    # Phase 1 prompt: Generate parts structure
    # Determine guidance based on course length
    if hours < 2.0:
        parts_guidance = f"""IMPORTANT: This is a short course ({hours} hours). Courses under 2 hours should normally have only ONE part. Do not split this into multiple parts unless absolutely necessary for logical organization."""
        parts_count_guidance = "1 part"
    elif hours < 4.0:
        parts_guidance = "Aim for 2-3 parts for this medium-length course."
        parts_count_guidance = "2-3 parts"
    else:
        parts_guidance = "Aim for 3-5 parts for this longer course."
        parts_count_guidance = "3-5 parts"
    
    new_state = state.model_copy(
        update={
            "pending_outline_generation": True,
        }
    )
    
    return LogicResult(
        new_state=new_state,
        commands=[
            LLMCommand(
                prompt_name="courses.generate_parts",
                prompt_variables={
                    "query": query,
                    "hours": hours,
                    "target_minutes": target_minutes,
                    "summaries_context": summaries_context,
                    "parts_guidance": parts_guidance,
                    "parts_count_guidance": parts_count_guidance,
                },
                temperature=0.7,
                max_tokens=2000,
                task="generate_course_parts",
            )
        ],
        ui_message="Planning course structure...",
    )


def parse_parts_text(
    parts_text: str,
    target_minutes: int,
) -> List[Dict[str, Any]]:
    """
    Parse Phase 1 output (parts text) into structured list.
    
    Returns: [{title: str, minutes: int}, ...]
    """
    import re
    
    parts = []
    lines = parts_text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or line.lower().startswith('total'):
            continue
        
        # Match "Part N: Title - X minutes"
        match = re.match(r'Part\s+\d+:\s*(.+?)\s*-\s*(\d+)\s*minutes?', line, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            minutes = int(match.group(2))
            parts.append({"title": title, "minutes": minutes})
    
    # Validate total
    total = sum(p["minutes"] for p in parts)
    if abs(total - target_minutes) > target_minutes * 0.05:  # 5% tolerance
        logger.warning(f"Parts total ({total} min) doesn't match target ({target_minutes} min)")
    
    return parts


def handle_parts_generated(
    state: CourseState,
    parts_text: str,
) -> LogicResult:
    """
    Handle Phase 1 completion: Parse parts and start Phase 2 for first part.
    """
    target_minutes = int((state.pending_course_hours or 2.0) * 60)
    parts_list = parse_parts_text(parts_text, target_minutes)
    
    if not parts_list:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="Error: Could not parse course parts. Please try again.",
        )
    
    # Store parts and start with first part
    new_state = state.model_copy(
        update={
            "parts_list": parts_list,
            "current_part_index": 0,
            "outline_text": parts_text + "\n\n",  # Start building outline text
        }
    )
    
    # Start Phase 2 for first part
    return generate_part_sections(new_state, part_index=0)


def generate_part_sections(
    state: CourseState,
    part_index: int,
) -> LogicResult:
    """
    Phase 2-N: Generate sections for a specific part.
    """
    import json
    
    if part_index >= len(state.parts_list):
        # All parts done, check if review needed
        return check_and_review_outline(state)
    
    part = state.parts_list[part_index]
    query = state.pending_course_query or ""
    
    # Get book summaries (stored in state or need to retrieve)
    # For now, we'll need to pass books through state or retrieve them
    # This is a simplification - in practice we might store book summaries in state
    # For now, assume we have access to them via a helper
    
    # Build context: existing outline + remaining parts
    existing_outline = state.outline_text or ""
    remaining_parts = [
        f"Part {i+1}: {p['title']} - {p['minutes']} minutes"
        for i, p in enumerate(state.parts_list[part_index+1:], start=part_index+1)
    ]
    remaining_text = "\n".join(remaining_parts) if remaining_parts else "None"
    
    # Get book summaries from state
    book_summaries_context = state.book_summaries_json or "No source material available"
    
    new_state = state.model_copy(
        update={
            "current_part_index": part_index,
        }
    )
    
    return LogicResult(
        new_state=new_state,
        commands=[
            LLMCommand(
                prompt_name="courses.expand_part",
                prompt_variables={
                    "query": query,
                    "book_summaries_context": book_summaries_context,
                    "existing_outline": existing_outline,
                    "remaining_text": remaining_text,
                    "part_index": part_index + 1,  # Display index (1-based)
                    "part_title": part['title'],
                    "part_minutes": part['minutes'],
                },
                temperature=0.7,
                max_tokens=3000,
                task=f"generate_part_sections_{part_index}",
            )
        ],
        ui_message=f"Generating sections for Part {part_index + 1}: {part['title']}...",
    )


def handle_part_sections_generated(
    state: CourseState,
    sections_text: str,
    part_index: int,
) -> LogicResult:
    """
    Handle Phase 2-N completion: Append sections to outline, move to next part.
    """
    # Append this part's sections to outline
    current_outline = state.outline_text or ""
    new_outline = current_outline + sections_text + "\n\n"
    
    # Move to next part
    next_part_index = part_index + 1
    
    new_state = state.model_copy(
        update={
            "outline_text": new_outline,
            "current_part_index": next_part_index,
        }
    )
    
    if next_part_index >= len(state.parts_list):
        # All parts done
        new_state = new_state.model_copy(update={"outline_complete": True})
        return check_and_review_outline(new_state)
    else:
        # Continue with next part
        return generate_part_sections(new_state, next_part_index)


def check_and_review_outline(
    state: CourseState,
) -> LogicResult:
    """
    Check if outline needs review/adjustment (Phase N+1).
    """
    # Parse outline to calculate total time
    total_minutes = parse_outline_total_time(state.outline_text or "")
    target_minutes = int((state.pending_course_hours or 2.0) * 60)
    
    variance = abs(total_minutes - target_minutes) / target_minutes if target_minutes > 0 else 1.0
    
    if variance > 0.05:  # More than 5% off
        # Need review
        return review_and_adjust_outline(state, total_minutes, target_minutes)
    else:
        # Close enough, parse and store
        return parse_text_outline_to_database(state)


def parse_outline_total_time(
    outline_text: str,
) -> int:
    """
    Parse outline text to calculate total time.
    
    Looks for section times (### Section N: Title - X minutes)
    and part totals (Total for this part: X minutes).
    """
    import re
    
    total = 0
    
    # Find section times: "### Section N: Title - X minutes"
    section_pattern = r'###\s*Section\s+\d+:\s*.+?\s*-\s*(\d+)\s*minutes?'
    section_matches = re.findall(section_pattern, outline_text, re.IGNORECASE)
    total += sum(int(m) for m in section_matches)
    
    # If no sections found, try part totals: "Total for this part: X minutes"
    if not section_matches:
        part_total_pattern = r'Total\s+(?:for\s+this\s+part|for\s+part\s+\d+):\s*(\d+)\s*minutes?'
        part_matches = re.findall(part_total_pattern, outline_text, re.IGNORECASE)
        total += sum(int(m) for m in part_matches)
    
    # Fallback: look for "Total: X minutes" at end
    if total == 0:
        final_total_pattern = r'Total:\s*(\d+)\s*minutes?'
        final_match = re.search(final_total_pattern, outline_text, re.IGNORECASE)
        if final_match:
            total = int(final_match.group(1))
    
    return total


def review_and_adjust_outline(
    state: CourseState,
    current_total: int,
    target_total: int,
) -> LogicResult:
    """
    Phase N+1: Review and adjust outline to match target time.
    """
    import json
    
    query = state.pending_course_query or ""
    hours = state.pending_course_hours or 2.0
    variance_percent = abs(current_total - target_total) / target_total * 100 if target_total > 0 else 0
    
    # Get book summaries from state
    book_summaries_context = state.book_summaries_json or "No source material available"
    
    min_acceptable = int(target_total * 0.95)
    max_acceptable = int(target_total * 1.05)
    
    return LogicResult(
        new_state=state,
        commands=[
            LLMCommand(
                prompt_name="courses.review_outline",
                prompt_variables={
                    "query": query,
                    "hours": hours,
                    "target_total": target_total,
                    "book_summaries_context": book_summaries_context,
                    "outline_text": state.outline_text or "",
                    "current_total": current_total,
                    "variance_percent": variance_percent,
                    "min_acceptable": min_acceptable,
                    "max_acceptable": max_acceptable,
                },
                temperature=0.7,
                max_tokens=4000,
                task="review_and_adjust_outline",
            )
        ],
        ui_message="Reviewing and adjusting course outline for time accuracy...",
    )


def handle_outline_reviewed(
    state: CourseState,
    reviewed_outline_text: str,
) -> LogicResult:
    """
    Handle Phase N+1 completion: Parse reviewed outline and store.
    """
    new_state = state.model_copy(
        update={
            "outline_text": reviewed_outline_text,
        }
    )
    
    return parse_text_outline_to_database(new_state)


def parse_text_outline_to_database(
    state: CourseState,
) -> LogicResult:
    """
    Parse complete text outline into database structure and store.
    """
    import re
    import json
    from uuid import uuid4
    
    outline_text = state.outline_text or ""
    if not outline_text:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="Error: No outline to parse.",
        )
    
    # If this is a revision, convert to JSON and use store_course_outline which handles revisions
    if state.is_revision:
        logger.info(f"Revision: Parsing text outline (length: {len(outline_text)} chars)")
        logger.debug(f"Revision: Outline text preview: {outline_text[:500]}...")
        
        # Parse the text outline into structured format first
        # (we'll convert it to JSON format expected by store_course_outline)
        parts = []
        current_part = None
        current_sections = []
        in_objectives = False
        current_objectives = []
        
        lines = outline_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                in_objectives = False
                continue
            
            # Part header: "## Part N: Title" or "Part N: Title - X minutes"
            part_match = re.match(r'##?\s*Part\s+\d+:\s*(.+?)(?:\s*-\s*(\d+)\s*minutes?)?$', line, re.IGNORECASE)
            if part_match:
                if current_part and current_sections:
                    parts.append({
                        "title": current_part,
                        "sections": current_sections,
                    })
                current_part = part_match.group(1).strip()
                current_sections = []
                in_objectives = False
                continue
            
            # Section: "### Section N: Title - X minutes"
            section_match = re.match(r'###\s*Section\s+\d+:\s*(.+?)\s*-\s*(\d+)\s*minutes?', line, re.IGNORECASE)
            if section_match:
                if current_sections and current_objectives:
                    current_sections[-1]["learning_objectives"] = current_objectives
                    current_objectives = []
                
                section_title = section_match.group(1).strip()
                section_minutes = int(section_match.group(2))
                logger.debug(f"Revision: Parsed section '{section_title}' with {section_minutes} minutes")
                current_sections.append({
                    "title": section_title,
                    "time_minutes": section_minutes,
                    "learning_objectives": [],
                })
                in_objectives = False
                continue
            
            # "Learning objectives:" header
            if "learning objectives" in line.lower() and current_sections:
                in_objectives = True
                current_objectives = []
                continue
            
            # Learning objective
            if (line.startswith('-') or in_objectives) and current_sections:
                objective = line[1:].strip() if line.startswith('-') else line.strip()
                if objective and objective.lower() not in ["learning objectives:", "objectives:"]:
                    current_objectives.append(objective)
                    in_objectives = True
                continue
            
            # "Total for this part:" or "Total:" - end of part
            if "total" in line.lower() and "minutes" in line.lower():
                in_objectives = False
                if current_sections and current_objectives:
                    current_sections[-1]["learning_objectives"] = current_objectives
                    current_objectives = []
        
        # Save last section's objectives
        if current_sections and current_objectives:
            current_sections[-1]["learning_objectives"] = current_objectives
        
        # Add last part
        if current_part and current_sections:
            parts.append({
                "title": current_part,
                "sections": current_sections,
            })
        
        logger.info(f"Revision: Parsed {len(parts)} parts with {sum(len(p.get('sections', [])) for p in parts)} total sections")
        if parts and parts[0].get('sections'):
            sample_section = parts[0]['sections'][0]
            logger.debug(f"Revision: Sample section from parsing: title='{sample_section.get('title')}', time_minutes={sample_section.get('time_minutes')}")
        
        # Convert to JSON format expected by store_course_outline
        # Format: {"title": "...", "sections": [{"title": "...", "order_index": 1, "parent_section_id": ...}]}
        # We need to create parts as top-level sections and child sections with parent_section_id
        all_sections = []
        section_order = 1
        
        for part in parts:
            # Generate a UUID for the part (top-level section)
            from uuid import uuid4
            part_section_id = str(uuid4())
            
            # Add part as a top-level section (parent_section_id=None)
            all_sections.append({
                "title": part["title"],
                "order_index": section_order,
                "estimated_minutes": sum(s.get("time_minutes", 0) for s in part.get("sections", [])),
                "learning_objectives": [],
                "content_summary": None,
                "can_standalone": False,
                "prerequisites": [],
                "parent_section_id": None,  # Top-level part
                "section_id": part_section_id,  # Temporary ID for reference
            })
            section_order += 1
            
            # Add child sections with parent_section_id pointing to the part
            for section_data in part.get("sections", []):
                time_minutes = section_data.get("time_minutes", 15)
                if time_minutes == 0:
                    # Fallback to 15 if time wasn't parsed correctly
                    time_minutes = 15
                all_sections.append({
                    "title": section_data.get("title", "Untitled Section"),
                    "order_index": section_order,
                    "estimated_minutes": time_minutes,
                    "learning_objectives": section_data.get("learning_objectives", []),
                    "content_summary": None,
                    "can_standalone": False,
                    "prerequisites": [],
                    "parent_section_id": part_section_id,  # Child of part
                })
                section_order += 1
        
        # Generate course title
        query = state.pending_course_query or ""
        course_title = "Custom Course"
        
        if parts:
            first_part_title = parts[0].get("title", "")
            if first_part_title:
                clean_title = re.sub(r'^Part\s+\d+:\s*', '', first_part_title, flags=re.IGNORECASE).strip()
                if clean_title:
                    course_title = clean_title
                    if len(course_title) < 50 and ":" not in course_title:
                        course_title = course_title + " Course"
        
        if course_title == "Custom Course" and query:
            title_candidate = query.split('.')[0].strip()[:60]
            if title_candidate:
                course_title = title_candidate + " Course"
        
        logger.info(f"Revision: Converted to {len(all_sections)} sections, total time: {sum(s.get('estimated_minutes', 0) for s in all_sections)} minutes")
        logger.debug(f"Revision: Sample section: {all_sections[0] if all_sections else 'None'}")
        
        outline_json = json.dumps({
            "title": course_title,
            "sections": all_sections,
        })
        
        # Use store_course_outline which handles revisions properly
        return store_course_outline(state, outline_json)
    
    # Parse outline text into structured format
    # Format: Parts with sections, each section has title, time, objectives
    
    parts = []
    current_part = None
    current_sections = []
    in_objectives = False
    current_objectives = []
    
    lines = outline_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            in_objectives = False
            continue
        
        # Part header: "## Part N: Title" or "Part N: Title - X minutes"
        part_match = re.match(r'##?\s*Part\s+\d+:\s*(.+?)(?:\s*-\s*(\d+)\s*minutes?)?$', line, re.IGNORECASE)
        if part_match:
            # Save previous part if exists
            if current_part and current_sections:
                parts.append({
                    "title": current_part,
                    "sections": current_sections,
                })
            current_part = part_match.group(1).strip()
            current_sections = []
            in_objectives = False
            continue
        
        # Section: "### Section N: Title - X minutes"
        section_match = re.match(r'###\s*Section\s+\d+:\s*(.+?)\s*-\s*(\d+)\s*minutes?', line, re.IGNORECASE)
        if section_match:
            # Save previous section's objectives if any
            if current_sections and current_objectives:
                current_sections[-1]["learning_objectives"] = current_objectives
                current_objectives = []
            
            section_title = section_match.group(1).strip()
            section_minutes = int(section_match.group(2))
            current_sections.append({
                "title": section_title,
                "time_minutes": section_minutes,
                "learning_objectives": [],
            })
            in_objectives = False
            continue
        
        # "Learning objectives:" header - next lines will be objectives
        if "learning objectives" in line.lower() and current_sections:
            in_objectives = True
            current_objectives = []
            continue
        
        # Learning objective: "- Objective text" or just "Objective text" after "Learning objectives:"
        if (line.startswith('-') or in_objectives) and current_sections:
            objective = line[1:].strip() if line.startswith('-') else line.strip()
            if objective and objective.lower() not in ["learning objectives:", "objectives:"]:
                current_objectives.append(objective)
                in_objectives = True
            continue
        
        # "Total for this part:" or "Total:" - end of part
        if "total" in line.lower() and "minutes" in line.lower():
            in_objectives = False
            # Save current section's objectives
            if current_sections and current_objectives:
                current_sections[-1]["learning_objectives"] = current_objectives
                current_objectives = []
    
    # Save last section's objectives
    if current_sections and current_objectives:
        current_sections[-1]["learning_objectives"] = current_objectives
    
    # Add last part
    if current_part and current_sections:
        parts.append({
            "title": current_part,
            "sections": current_sections,
        })
    
    # If no parts structure found, try to parse as flat sections
    if not parts:
        # Look for sections without part headers
        for line in lines:
            line = line.strip()
            section_match = re.match(r'###\s*Section\s+\d+:\s*(.+?)\s*-\s*(\d+)\s*minutes?', line, re.IGNORECASE)
            if section_match:
                if not current_sections:  # First section, create default part
                    current_part = "Course Content"
                section_title = section_match.group(1).strip()
                section_minutes = int(section_match.group(2))
                current_sections.append({
                    "title": section_title,
                    "time_minutes": section_minutes,
                    "learning_objectives": [],
                })
        
        if current_sections:
            parts = [{
                "title": current_part or "Course Content",
                "sections": current_sections,
            }]
    
    # Generate course title - try to extract from first part, fallback to query
    import re as re_module  # Use different name to avoid conflict
    query = state.pending_course_query or ""
    course_title = "Custom Course"
    
    if parts:
        # Try to use first part title as base
        first_part_title = parts[0].get("title", "")
        if first_part_title:
            # Clean up part title (remove "Part 1:" prefix if present)
            clean_title = re_module.sub(r'^Part\s+\d+:\s*', '', first_part_title, flags=re_module.IGNORECASE).strip()
            if clean_title:
                course_title = clean_title
                # If it's too long or seems like a part title, add "Course" suffix
                if len(course_title) < 50 and ":" not in course_title:
                    course_title = course_title + " Course"
    
    # Fallback to query-based title
    if course_title == "Custom Course" and query:
        # Extract a reasonable title from query (first sentence or first 60 chars)
        title_candidate = query.split('.')[0].strip()[:60]
        if title_candidate:
            course_title = title_candidate + " Course"
    
    # Create course
    prefs = state.pending_course_prefs
    if prefs is None:
        prefs = CoursePreferences()
    
    course = Course(
        user_id=state.session_id or str(uuid4()),
        title=course_title,
        original_query=query,
        estimated_hours=state.pending_course_hours or 2.0,
        preferences=prefs,
    )
    
    # Create sections (parts are top-level, sections are children)
    all_sections = []
    section_order = 1
    
    for part_idx, part in enumerate(parts):
        # Create part as top-level section
        part_section = CourseSection(
            course_id=course.course_id,
            order_index=section_order,
            title=part["title"],
            learning_objectives=[],  # Parts don't have objectives
            estimated_minutes=sum(s.get("time_minutes", 0) for s in part.get("sections", [])),
            can_standalone=False,
            prerequisites=[],
            chunk_ids=[],
            parent_section_id=None,  # Top-level
        )
        all_sections.append(part_section)
        section_order += 1
        
        # Create child sections
        for section_data in part.get("sections", []):
            child_section = CourseSection(
                course_id=course.course_id,
                order_index=section_order,
                title=section_data.get("title", "Untitled Section"),
                learning_objectives=section_data.get("learning_objectives", []),
                estimated_minutes=section_data.get("time_minutes", 15),
                can_standalone=section_data.get("can_standalone", False),
                prerequisites=[],
                chunk_ids=[],
                parent_section_id=part_section.section_id,  # Child of part
            )
            all_sections.append(child_section)
            section_order += 1
    
    # Update state with course
    new_state = state.model_copy(
        update={
            "current_course": course,
            "pending_course_query": None,
            "pending_course_hours": None,
            "pending_course_prefs": None,
            "pending_outline_generation": False,
            "outline_complete": True,
        }
    )
    
    return LogicResult(
        new_state=new_state,
        commands=[
            CreateCourseCommand(course=course),
            CreateSectionsCommand(sections=all_sections),
            RecordCourseHistoryCommand(
                course_id=course.course_id,
                change_type="created",
                change_description="Course created with multi-phase outline generation",
            ),
        ],
        ui_message="Course outline generated and stored!",
    )


def generate_course_outline(
    state: CourseState,
    relevant_chunks: List[Dict[str, Any]],
) -> LogicResult:
    """
    Generate course outline using LLM based on user query, time, and corpus.
    
    This is the core outline generation step.
    """
    query = state.pending_course_query or ""
    hours = state.pending_course_hours or 2.0
    prefs = state.pending_course_prefs or CoursePreferences()
    
    # Log the query being used (for debugging revisions)
    if state.is_revision:
        logger.info(f"Revision: Generating outline with query (length: {len(query)} chars)")
        logger.debug(f"Revision query: {query[:300]}...")
    
    # Format relevant chunks for context
    chunk_summaries = []
    for chunk in relevant_chunks[:30]:  # Limit context
        summary = f"- {chunk.get('chapter_title', 'Unknown')}: {chunk.get('content', '')[:200]}..."
        chunk_summaries.append(summary)
    
    chunk_context = "\n".join(chunk_summaries)
    
    # Build prompt variables for outline generation
    minutes = hours * 60
    section_count = int(hours * 4)
    additional_notes_section = f"- Additional notes: {prefs.additional_notes}" if prefs.additional_notes else ""
    style_instruction = (
        "IMPORTANT: Style is 'podcast' - Present all material in an engaging podcast format with a consistent, engaging podcast persona. Questions should be handled by the same podcast persona in a natural, conversational podcast style."
        if prefs.presentation_style == "podcast"
        else ""
    )
    
    new_state = state.model_copy(
        update={
            "pending_outline_generation": True,
        }
    )
    
    return LogicResult(
        new_state=new_state,
        commands=[
            LLMCommand(
                prompt_name="courses.generate_outline",
                prompt_variables={
                    "query": query,
                    "hours": hours,
                    "minutes": minutes,
                    "depth": prefs.depth,
                    "presentation_style": prefs.presentation_style,
                    "additional_notes_section": additional_notes_section,
                    "style_instruction": style_instruction,
                    "chunk_context": chunk_context,
                    "section_count": section_count,
                },
                temperature=0.7,
                max_tokens=4000,
                task="generate_course_outline",
            )
        ],
        ui_message="Generating personalized course outline...",
    )


def store_course_outline(
    state: CourseState,
    outline_json: str,
) -> LogicResult:
    """
    Parse LLM-generated outline and store course + sections in database.
    
    This finalizes course creation.
    """
    import json
    from uuid import uuid4
    
    try:
        outline_data = json.loads(outline_json)
    except json.JSONDecodeError as e:
        # Try to extract JSON from markdown code blocks (```json ... ```)
        import re
        logger.warning(f"Failed to parse outline as JSON, trying to extract: {e}")
        
        # First, try to extract from markdown code blocks (```json ... ``` or ``` ... ```)
        # Use non-greedy match but with DOTALL to handle multiline JSON
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', outline_json, re.DOTALL)
        if json_match:
            try:
                outline_data = json.loads(json_match.group(1))
                logger.info("Successfully extracted JSON from markdown code block")
            except json.JSONDecodeError as e2:
                logger.warning(f"Failed to parse JSON from code block: {e2}")
                json_match = None  # Fall through to next attempt
        
        # If code block extraction failed, try to find any JSON object
        if not json_match:
            json_match = re.search(r'\{.*\}', outline_json, re.DOTALL)
            if json_match:
                try:
                    outline_data = json.loads(json_match.group())
                    logger.info("Successfully extracted JSON from text")
                except json.JSONDecodeError as e2:
                    logger.error(f"Failed to parse extracted JSON: {e2}")
                    logger.error(f"Outline JSON (first 500 chars): {outline_json[:500]}")
                    return LogicResult(
                        new_state=state,
                        commands=[],
                        ui_message="Error: Could not parse course outline. Please try again.",
                    )
            else:
                logger.error(f"No JSON found in outline response")
                logger.error(f"Outline JSON (first 500 chars): {outline_json[:500]}")
                return LogicResult(
                    new_state=state,
                    commands=[],
                    ui_message="Error: Could not parse course outline. Please try again.",
                )
    
    # Handle both old format ("title") and new format ("course_title")
    course_title = outline_data.get("course_title") or outline_data.get("title", "Custom Course")
    
    # Validate and log time estimates
    sections_data = outline_data.get("sections", [])
    total_minutes = sum(s.get("time_minutes", 0) for s in sections_data)
    target_minutes = int((state.pending_course_hours or 2.0) * 60)
    time_variance = abs(total_minutes - target_minutes) / target_minutes if target_minutes > 0 else 0
    
    if time_variance > 0.10:  # More than 10% off
        logger.warning(
            f"Course time estimate is {time_variance:.1%} off target: "
            f"{total_minutes} minutes vs {target_minutes} minutes target"
        )
    else:
        logger.info(
            f"Course time estimate: {total_minutes} minutes (target: {target_minutes}, "
            f"variance: {time_variance:.1%})"
        )
    
    # Log section complexity distribution
    objectives_counts = [len(s.get("learning_objectives", [])) for s in sections_data]
    time_ranges = [s.get("time_minutes", 0) for s in sections_data]
    if objectives_counts:
        logger.info(
            f"Section complexity: {len(sections_data)} sections, "
            f"objectives range {min(objectives_counts)}-{max(objectives_counts)}, "
            f"time range {min(time_ranges)}-{max(time_ranges)} minutes"
        )
    
    # Check if this is a revision
    is_revision = state.is_revision
    revision_course_id = state.pending_revision_course_id
    completed_section_ids = state.pending_revision_completed_section_ids or set()
    
    if is_revision and revision_course_id:
        # This is a revision - use existing course, delete old remaining sections, create new ones
        # Get the existing course from state
        existing_course = state.current_course
        if not existing_course or existing_course.course_id != revision_course_id:
            return LogicResult(
                new_state=state,
                commands=[],
                ui_message="Error: Course not found for revision.",
            )
        
        # Use existing course but update title and original_query to the combined prompt
        # The original_query should reflect the revised/combined prompt
        combined_query = state.pending_course_query or existing_course.original_query
        course = existing_course.model_copy(
            update={
                "title": course_title,
                "original_query": combined_query,  # Replace with the combined/revised prompt
                "last_modified": datetime.utcnow(),
            }
        )
        
        # Create new sections for the revised outline
        # Handle hierarchical structure: parts (parent_section_id=None) and child sections
        # Match the normal course creation flow: create parts first, then children
        sections = []
        sections_data = outline_data.get("sections", [])
        logger.info(f"Revision: Creating sections from outline_data with {len(sections_data)} items")
        
        # Track mapping from temp section_id (from JSON) to real section_id (generated)
        temp_id_to_real_id = {}
        
        # Process sections in order, creating parts first, then their children
        for idx, section_data in enumerate(sections_data):
            prereq_list = section_data.get("prerequisites", [])
            if prereq_list and isinstance(prereq_list[0], int):
                prereq_list = []
            
            objectives = section_data.get("learning_objectives") or section_data.get("objectives", [])
            estimated_minutes = section_data.get("estimated_minutes") or section_data.get("time_minutes", 15)
            
            # Check if this is a part (has section_id in data, meaning it's a top-level part)
            temp_section_id = section_data.get("section_id")
            parent_temp_id = section_data.get("parent_section_id")
            
            if temp_section_id and not parent_temp_id:
                # This is a part (top-level section)
                section = CourseSection(
                    course_id=course.course_id,
                    parent_section_id=None,  # Parts are top-level
                    order_index=section_data.get("order_index", idx + 1),
                    title=section_data.get("title", "Untitled Section"),
                    learning_objectives=objectives,
                    content_summary=section_data.get("content_summary"),
                    estimated_minutes=estimated_minutes,
                    can_standalone=section_data.get("can_standalone", False),
                    prerequisites=prereq_list,
                    chunk_ids=[],
                )
                sections.append(section)
                temp_id_to_real_id[temp_section_id] = section.section_id
                logger.debug(f"Revision: Created part '{section.title}' (temp_id={temp_section_id}, real_id={section.section_id})")
            else:
                # This is a child section
                parent_real_id = temp_id_to_real_id.get(parent_temp_id) if parent_temp_id else None
                
                section = CourseSection(
                    course_id=course.course_id,
                    parent_section_id=parent_real_id,  # Child of part
                    order_index=section_data.get("order_index", idx + 1),
                    title=section_data.get("title", "Untitled Section"),
                    learning_objectives=objectives,
                    content_summary=section_data.get("content_summary"),
                    estimated_minutes=estimated_minutes,
                    can_standalone=section_data.get("can_standalone", False),
                    prerequisites=prereq_list,
                    chunk_ids=[],
                )
                sections.append(section)
                logger.debug(f"Revision: Created child section '{section.title}' with parent={parent_real_id}")
        
        # Store new sections in state so they can be used when deleting old ones
        new_state = state.model_copy(
            update={
                "current_course": course,
                "pending_course_query": None,
                "pending_course_hours": None,
                "pending_course_prefs": None,
                "pending_outline_generation": False,
                "pending_revision_completed_section_ids": completed_section_ids,  # Keep for deletion step
                "pending_revision_new_sections": sections,  # Store new sections for creation
            }
        )
        
        return LogicResult(
            new_state=new_state,
            commands=[
                QuerySectionsCommand(
                    course_id=revision_course_id,
                    status=None,  # Get ALL sections (complete regeneration)
                ),
                # After query, we'll delete ALL old sections and create new ones
            ],
            ui_message="Preparing to regenerate course outline...",
        )
    
    else:
        # This is a new course creation
        # Handle None preferences (new simplified flow)
        prefs = state.pending_course_prefs
        if prefs is None:
            prefs = CoursePreferences()  # Use defaults
        
        course = Course(
            user_id=state.session_id or str(uuid4()),
            title=course_title,
            original_query=state.pending_course_query or "",
            estimated_hours=state.pending_course_hours or 2.0,
            preferences=prefs,
        )
        
        # Create sections
        sections = []
        for idx, section_data in enumerate(outline_data.get("sections", [])):
            prereq_list = section_data.get("prerequisites", [])
            if prereq_list and isinstance(prereq_list[0], int):
                prereq_list = []
            
            objectives = section_data.get("learning_objectives") or section_data.get("objectives", [])
            
            section = CourseSection(
                course_id=course.course_id,
                order_index=section_data.get("order_index", idx + 1),
                title=section_data.get("title", "Untitled Section"),
                learning_objectives=objectives,
                content_summary=section_data.get("content_summary"),
                estimated_minutes=section_data.get("estimated_minutes", 15),
                can_standalone=section_data.get("can_standalone", False),
                prerequisites=prereq_list,
                chunk_ids=[],
            )
            sections.append(section)
        
        # Update state with new course
        new_state = state.model_copy(
            update={
                "current_course": course,
                "pending_course_query": None,
                "pending_course_hours": None,
                "pending_course_prefs": None,
                "pending_outline_generation": False,
            }
        )
        
        return LogicResult(
            new_state=new_state,
            commands=[
                CreateCourseCommand(course=course),
                CreateSectionsCommand(sections=sections),
                RecordCourseHistoryCommand(
                    course_id=course.course_id,
                    change_type="created",
                    change_description=f"Course created: {course.title}",
                    outline_snapshot={"section_count": len(sections)},
                ),
            ],
            ui_message=f"Course '{course.title}' created with {len(sections)} sections!",
        )


def request_outline_revision(
    state: CourseState,
    course_id: str,
    revision_request: str,
) -> LogicResult:
    """
    User requests changes to course outline.
    
    This reuses the existing course generation flow by:
    1. Loading current course and sections
    2. Formatting previous outline as context
    3. Combining original query + previous outline + revision request
    4. Calling the same course generation pipeline
    5. After generation, replacing remaining sections (keeping completed ones)
    
    Examples:
    - "Can we add a section on tax implications?"
    - "Let's compress this to 2 hours instead of 3"
    - "Make the remaining sections more technical"
    """
    from src.core.commands import QuerySectionsCommand
    
    # Store revision request in state
    new_state = state.model_copy(
        update={
            "pending_revision_course_id": course_id,
            "pending_revision_request": revision_request,
            "is_revision": True,  # Flag to indicate this is a revision
        }
    )
    
    # First, query all sections to get current state
    return LogicResult(
        new_state=new_state,
        commands=[
            QuerySectionsCommand(
                course_id=course_id,
                status=None,  # Get all sections
            ),
        ],
        ui_message="Analyzing current course outline...",
    )


def handle_sections_loaded_for_revision(
    state: CourseState,
    sections: List[Dict[str, Any]],
) -> LogicResult:
    """
    After sections are loaded, use an LLM to combine the original prompt and revision request
    into a single prompt for complete course regeneration.
    
    We regenerate everything from scratch - no preserving completed sections.
    """
    course_id = state.pending_revision_course_id
    revision_request = state.pending_revision_request
    
    if not course_id or not revision_request:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="Error: Missing revision request data.",
        )
    
    # Get course info (should be in state.current_course)
    course = state.current_course
    if not course:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="Error: Course not found in state.",
        )
    
    # Format current outline for context (just for the LLM to understand what exists)
    current_outline = "\n".join([
        f"{s.get('order_index', 0)}. {s.get('title', 'Untitled')} ({s.get('estimated_minutes', 0)} min)"
        for s in sorted(sections, key=lambda x: x.get("order_index", 0))
    ]) if sections else "No sections yet."
    
    # Use LLM to combine the prompts intelligently
    combine_prompt = f"""This prompt: "{course.original_query}"

produced the following course outline:
{current_outline}

The user has asked for a revised course outline with this prompt: "{revision_request}"

Combine the two prompts in a way that will produce a course outline that reflects the revised request. 
Your response should be a single, coherent prompt that can be used to regenerate the entire course outline from scratch.
The prompt should incorporate both the original intent and the revision request.

Respond with ONLY the combined prompt - no explanations or additional text."""
    
    # Store state for the LLM call
    # No need to track completed sections - we're regenerating everything
    new_state = state.model_copy(
        update={
            "pending_revision_completed_section_ids": set(),  # Empty - no sections to preserve
            "pending_revision_course_id": course_id,
            "is_revision": True,
        }
    )
    
    # Call LLM to combine the prompts
    return LogicResult(
        new_state=new_state,
        commands=[
            LLMCommand(
                prompt=combine_prompt,
                task="combine_revision_prompts",
                temperature=0.7,
            ),
        ],
        ui_message="Combining prompts for revision...",
    )


def handle_revision_prompts_combined(
    state: CourseState,
    combined_prompt: str,
) -> LogicResult:
    """
    After LLM combines the prompts, use the combined prompt to regenerate the course.
    """
    course_id = state.pending_revision_course_id
    course = state.current_course
    
    if not course:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="Error: Course not found in state.",
        )
    
    # Clean up the combined prompt (remove any markdown formatting, extra quotes, etc.)
    import re
    cleaned_prompt = combined_prompt.strip()
    
    # Remove markdown code blocks if present
    if cleaned_prompt.startswith("```"):
        cleaned_prompt = re.sub(r'```[a-z]*\n?', '', cleaned_prompt).strip()
        cleaned_prompt = cleaned_prompt.rstrip('```').strip()
    
    # Remove surrounding quotes if present
    if (cleaned_prompt.startswith('"') and cleaned_prompt.endswith('"')) or \
       (cleaned_prompt.startswith("'") and cleaned_prompt.endswith("'")):
        cleaned_prompt = cleaned_prompt[1:-1].strip()
    
    # Remove any remaining prompt artifacts that the LLM might include
    # (like "This prompt:" or "produced the following course outline:")
    cleaned_prompt = re.sub(r'^(This prompt:|produced the following course outline:).*?\n', '', cleaned_prompt, flags=re.IGNORECASE | re.MULTILINE)
    cleaned_prompt = cleaned_prompt.strip()
    
    # Remove any outline text that might have been included
    # Look for patterns like "Completed sections:" or "Remaining sections:" and remove everything after
    outline_markers = ['Completed sections', 'Remaining sections', 'No sections completed', 'No remaining sections']
    for marker in outline_markers:
        if marker in cleaned_prompt:
            # Find the marker and remove everything from there to the end (or next newline section)
            idx = cleaned_prompt.find(marker)
            if idx > 0:
                # Keep everything before the marker, but try to find a natural break
                # Look for the last sentence before the marker
                before = cleaned_prompt[:idx].strip()
                # If there's a question mark or period before, that's probably the end of the prompt
                last_sentence_end = max(before.rfind('?'), before.rfind('.'), before.rfind('!'))
                if last_sentence_end > len(before) * 0.5:  # If it's in the latter half, use it
                    cleaned_prompt = before[:last_sentence_end + 1].strip()
                else:
                    cleaned_prompt = before.strip()
            break
    
    logger.info(f"Revision: Using cleaned combined prompt (length: {len(cleaned_prompt)} chars)")
    logger.debug(f"Revision combined prompt: {cleaned_prompt[:300]}...")
    
    # Use the combined prompt to start course generation
    new_state = state.model_copy(
        update={
            "pending_course_query": cleaned_prompt,  # Use cleaned combined prompt
            "pending_course_hours": course.estimated_hours,  # Keep same time estimate
            "pending_course_prefs": course.preferences,
            "pending_revision_course_id": course_id,
            "is_revision": True,
        }
    )
    
    # Start the course generation flow with the combined prompt
    return LogicResult(
        new_state=new_state,
        commands=[
            EmbedCommand(text=cleaned_prompt, task="find_relevant_corpus"),
        ],
        ui_message="Regenerating course outline with your revisions...",
    )


def apply_outline_revision(
    state: CourseState,
    revision_json: str,
) -> LogicResult:
    """
    Apply outline changes to database.
    
    - Delete removed sections (not completed)
    - Update modified sections
    - Create new sections
    - Record change in course_history
    """
    import json
    from uuid import uuid4
    
    try:
        revision_data = json.loads(revision_json)
    except json.JSONDecodeError as e:
        # Try to extract JSON from markdown code blocks
        import re
        logger.warning(f"Failed to parse revision as JSON, trying to extract: {e}")
        
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', revision_json, re.DOTALL)
        if json_match:
            try:
                revision_data = json.loads(json_match.group(1))
            except json.JSONDecodeError:
                json_match = None
        
        if not json_match:
            json_match = re.search(r'\{.*\}', revision_json, re.DOTALL)
            if json_match:
                try:
                    revision_data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    return LogicResult(
                        new_state=state,
                        commands=[],
                        ui_message="Error: Could not parse revision response. Please try again.",
                    )
            else:
                return LogicResult(
                    new_state=state,
                    commands=[],
                    ui_message="Error: Could not parse revision response. Please try again.",
                )
    
    course_id = state.pending_revision_course_id
    if not course_id:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="Error: Missing course ID for revision.",
        )
    
    # Parse changes
    remaining_sections_data = revision_data.get("remaining_sections", [])
    
    # First, we need to get current sections to match by title/order_index
    # This will be done in a previous step - for now, we'll query them
    # Actually, we should have received them in state from the previous query
    # But we don't have them here, so we'll need to query again or pass them through state
    
    # Helper function to validate UUID format
    def is_valid_uuid(uuid_string: str) -> bool:
        """Check if string is a valid UUID format."""
        try:
            from uuid import UUID
            UUID(uuid_string)
            return True
        except (ValueError, TypeError):
            return False
    
    # Separate sections into: to_update (existing IDs), to_create (NEW_X), to_delete (missing from new outline)
    to_update = []
    to_create = []
    valid_section_ids = set()  # Track valid UUIDs for deletion comparison
    
    for section_data in remaining_sections_data:
        section_id = section_data.get("section_id", "")
        
        if section_id.startswith("NEW_"):
            # New section - create with new UUID (don't pass section_id, let default factory generate it)
            from uuid import uuid4
            section = CourseSection(
                section_id=str(uuid4()),  # Explicitly generate new UUID
                course_id=course_id,
                order_index=section_data.get("order_index", 0),
                title=section_data.get("title", "Untitled Section"),
                learning_objectives=section_data.get("learning_objectives", []),
                content_summary=section_data.get("content_summary"),
                estimated_minutes=section_data.get("estimated_minutes", 15),
                can_standalone=section_data.get("can_standalone", False),
                prerequisites=section_data.get("prerequisites", []),
                chunk_ids=[],  # No chunk_ids at revision time
            )
            to_create.append(section)
        elif is_valid_uuid(section_id):
            # Existing section with valid UUID (possibly modified)
            section = CourseSection(
                section_id=section_id,  # Preserve existing ID
                course_id=course_id,
                order_index=section_data.get("order_index", 0),
                title=section_data.get("title", "Untitled Section"),
                learning_objectives=section_data.get("learning_objectives", []),
                content_summary=section_data.get("content_summary"),
                estimated_minutes=section_data.get("estimated_minutes", 15),
                can_standalone=section_data.get("can_standalone", False),
                prerequisites=section_data.get("prerequisites", []),
                chunk_ids=[],  # Preserve existing chunk_ids if any
            )
            to_update.append(section)
            valid_section_ids.add(section_id)
        else:
            # Invalid UUID format - LLM returned placeholder like "existing-uuid-1"
            # We'll need to match by title/order_index instead
            # For now, log a warning and skip this section
            logger.warning(
                f"LLM returned invalid section_id format: {section_id}. "
                f"Section '{section_data.get('title', 'Unknown')}' will be matched by title/order_index."
            )
            # We'll handle this by matching sections in the finalize step
            # Store the title/order_index for matching
            pass
    
    # Find sections to delete (in DB but not in new outline)
    # Only include valid UUIDs in the set for comparison
    new_section_ids = valid_section_ids
    
    commands = []
    
    if to_update:
        commands.append(UpdateSectionsCommand(sections=to_update))
    
    if to_create:
        commands.append(CreateSectionsCommand(sections=to_create))
    
    # Delete sections not in new outline (we'll need to query first, but for now we'll add a command)
    # Actually, we should query remaining sections first, then determine what to delete
    # Let's add a QuerySectionsCommand to get current remaining sections, then compare
    
    # For now, we'll add the delete command with a placeholder - the API will handle the actual deletion logic
    # We need to query remaining sections first to know what to delete
    
    commands.append(
        QuerySectionsCommand(
            course_id=course_id,
            status="not_started",  # Only query remaining (not completed) sections
        )
    )
    
    # Store revision data in state for next step
    new_state = state.model_copy(
        update={
            "pending_revision_sections_to_delete": new_section_ids,  # Store new IDs to compare
            "pending_revision_data": revision_data,
        }
    )
    
    return LogicResult(
        new_state=new_state,
        commands=commands,
        ui_message="Applying outline changes...",
    )


def finalize_revision_section_replacement(
    state: CourseState,
    old_all_sections: List[Dict[str, Any]],  # All old sections (not just remaining)
    new_sections: List[CourseSection],
) -> LogicResult:
    """
    Finalize revision by deleting ALL old sections and creating new ones from scratch.
    
    We regenerate everything - no preserving completed sections.
    """
    course_id = state.pending_revision_course_id
    
    if not course_id:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="Error: Missing course ID.",
        )
    
    logger.info(f"Revision: Finalizing complete course regeneration - deleting {len(old_all_sections)} old sections, creating {len(new_sections)} new sections")
    
    # Delete ALL old sections (complete regeneration)
    all_section_ids = [s.get("section_id") for s in old_all_sections if s.get("section_id")]
    
    logger.info(f"Revision: Will delete all {len(all_section_ids)} old sections (complete regeneration)")
    
    commands = []
    
    # Delete ALL old sections
    if all_section_ids:
        logger.info(f"Revision: Deleting all {len(all_section_ids)} old sections")
        commands.append(DeleteSectionsCommand(section_ids=all_section_ids))
    else:
        logger.warning("Revision: No sections to delete!")
    
    # Create new sections
    if new_sections:
        logger.info(f"Revision: Creating {len(new_sections)} new sections")
        commands.append(CreateSectionsCommand(sections=new_sections))
    else:
        logger.warning("Revision: No new sections to create!")
    
    # Update course (title, original_query, last_modified)
    course = state.current_course
    if course:
        logger.info(f"Revision: Updating course {course_id} with new original_query (length: {len(course.original_query)} chars)")
        commands.append(UpdateCourseCommand(course=course))
    
    # Record history
    commands.append(
        RecordCourseHistoryCommand(
            course_id=course_id,
            change_type="outline_modified",
            change_description=f"Course outline completely regenerated: {len(new_sections)} new sections",
            outline_snapshot={"new_sections": len(new_sections), "deleted_sections": len(all_section_ids)},
        )
    )
    
    # Don't clear revision flags yet - they'll be cleared after commands execute
    # Keep is_revision=True so the loop continues to process the delete/create/update commands
    new_state = state.model_copy(
        update={
            # Keep revision flags until commands are executed
            # They'll be cleared by RecordCourseHistoryCommand handler
        }
    )
    
    return LogicResult(
        new_state=new_state,
        commands=commands,
        ui_message=f"Course outline revised successfully!",
    )


def select_next_section(
    state: CourseState,
) -> LogicResult:
    """
    Select next uncompleted section in course order.
    
    Returns command to load section or message if course complete.
    """
    if not state.current_course:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="No active course. Please create a course first.",
        )
    
    # Query for next uncompleted section
    query_cmd = QuerySectionsCommand(
        course_id=state.current_course.course_id,
        status="not_started",
    )
    
    new_state = state.model_copy(
        update={
            "pending_next_section_query": True,
        }
    )
    
    return LogicResult(
        new_state=new_state,
        commands=[query_cmd],
        ui_message="Finding next section...",
    )


def select_standalone_section(
    state: CourseState,
    available_minutes: int,
) -> LogicResult:
    """
    User: "I have 10 minutes, teach me something from the course"
    
    Find best standalone section that fits time constraint.
    """
    if not state.current_course:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="No active course.",
        )
    
    # Query for uncompleted, standalone sections within time limit
    query_cmd = QuerySectionsCommand(
        course_id=state.current_course.course_id,
        status="not_started",
        can_standalone=True,
        max_minutes=available_minutes,
    )
    
    new_state = state.model_copy(
        update={
            "standalone_request_minutes": available_minutes,
        }
    )
    
    return LogicResult(
        new_state=new_state,
        commands=[query_cmd],
        ui_message=f"Finding a {available_minutes}-minute section for you...",
    )


def handle_standalone_section_query(
    state: CourseState,
    sections: List[Dict[str, Any]],
) -> LogicResult:
    """
    Handle result from standalone section query.
    
    If multiple candidates, use first one. Could use LLM to choose best.
    """
    if not sections:
        return LogicResult(
            new_state=state.model_copy(update={"standalone_request_minutes": None}),
            commands=[],
            ui_message="No standalone sections available in that timeframe.",
        )
    
    # Use first section (could enhance with LLM selection)
    section_data = sections[0]
    section = CourseSection(
        course_id=section_data["course_id"],
        section_id=section_data["section_id"],
        order_index=section_data["order_index"],
        title=section_data["title"],
        learning_objectives=section_data.get("learning_objectives", []),
        content_summary=section_data.get("content_summary"),
        estimated_minutes=section_data.get("estimated_minutes", 15),
        can_standalone=section_data.get("can_standalone", False),
        prerequisites=section_data.get("prerequisites", []),
        chunk_ids=section_data.get("chunk_ids", []),
        status=section_data.get("status", "not_started"),
    )
    
    new_state = state.model_copy(
        update={
            "current_section": section,
            "standalone_request_minutes": None,
        }
    )
    
    return prepare_section_delivery(new_state, section)


def handle_next_section_query_result(
    state: CourseState,
    sections: List[Dict[str, Any]],
) -> LogicResult:
    """
    Handle result from next section query.
    
    Selects the first section (lowest order_index) that has learning objectives and loads it.
    Skips sections without learning objectives (they can't generate lectures).
    """
    if not sections:
        return LogicResult(
            new_state=state.model_copy(update={"pending_next_section_query": False}),
            commands=[],
            ui_message="Course completed! All sections covered.",
        )
    
    # Sort by order_index
    sorted_sections = sorted(sections, key=lambda s: s.get("order_index", 999))
    
    # Filter out:
    # 1. Parent sections (parts) - these have no parent_section_id and are organizational containers
    # 2. Sections without learning objectives - these can't generate lectures
    # learning_objectives might be a list or a JSON string that needs parsing
    sections_with_objectives = []
    for section in sorted_sections:
        # Skip parent sections (parts) - they don't have a parent_section_id
        # and are just organizational containers
        if not section.get("parent_section_id"):
            continue  # This is a part, not a section
        
        objectives = section.get("learning_objectives", [])
        # Handle both list and string formats
        if isinstance(objectives, str):
            if objectives and objectives not in ('{}', '[]', ''):
                try:
                    import json
                    parsed = json.loads(objectives)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        sections_with_objectives.append(section)
                except (json.JSONDecodeError, ValueError):
                    pass
        elif isinstance(objectives, list) and len(objectives) > 0:
            sections_with_objectives.append(section)
    
    if not sections_with_objectives:
        return LogicResult(
            new_state=state.model_copy(update={"pending_next_section_query": False}),
            commands=[],
            ui_message="No sections with learning objectives found. All available sections have been completed or cannot be generated.",
        )
    
    # Take first section with objectives
    next_section_data = sections_with_objectives[0]
    
    # Convert to CourseSection model
    next_section = CourseSection(
        course_id=next_section_data["course_id"],
        section_id=next_section_data["section_id"],
        order_index=next_section_data["order_index"],
        title=next_section_data["title"],
        learning_objectives=next_section_data.get("learning_objectives", []),
        content_summary=next_section_data.get("content_summary"),
        estimated_minutes=next_section_data.get("estimated_minutes", 15),
        can_standalone=next_section_data.get("can_standalone", False),
        prerequisites=next_section_data.get("prerequisites", []),
        chunk_ids=next_section_data.get("chunk_ids", []),
        status=next_section_data.get("status", "not_started"),
    )
    
    new_state = state.model_copy(
        update={
            "current_section": next_section,
            "pending_next_section_query": False,
        }
    )
    
    return LogicResult(
        new_state=new_state,
        commands=[LoadSectionCommand(section_id=next_section.section_id)],
        ui_message=f"Next section: {next_section.title}",
    )


def handle_section_loaded(
    state: CourseState,
    section: Dict[str, Any],
    delivery: Optional[Dict[str, Any]] = None,
) -> LogicResult:
    """
    Handle result from LoadSectionCommand.
    
    Updates state with loaded section and delivery (if exists).
    """
    # Convert to CourseSection model
    loaded_section = CourseSection(
        course_id=section["course_id"],
        section_id=section["section_id"],
        order_index=section["order_index"],
        title=section["title"],
        learning_objectives=section.get("learning_objectives", []),
        content_summary=section.get("content_summary"),
        estimated_minutes=section.get("estimated_minutes", 15),
        can_standalone=section.get("can_standalone", False),
        prerequisites=section.get("prerequisites", []),
        chunk_ids=section.get("chunk_ids", []),
        status=section.get("status", "not_started"),
    )
    
    # Convert delivery if provided
    loaded_delivery = None
    if delivery:
        loaded_delivery = SectionDelivery(
            delivery_id=delivery["delivery_id"],
            section_id=delivery["section_id"],
            user_id=delivery["user_id"],
            lecture_script=delivery["lecture_script"],
            style_snapshot=delivery.get("style_snapshot", {}),
            audio_data=delivery.get("audio_data"),  # Include audio_data if present
        )
    
    new_state = state.model_copy(
        update={
            "current_section": loaded_section,
            "current_delivery": loaded_delivery,
        }
    )
    
    # If delivery exists, we're ready to play
    if loaded_delivery:
        return LogicResult(
            new_state=new_state.model_copy(
                update={"section_delivery_mode": "lecture"}
            ),
            commands=[],
            ui_message=f"Ready to deliver: {loaded_section.title}",
        )
    
    # No delivery yet, prepare to generate
    return prepare_section_delivery(new_state, loaded_section)


def jump_to_section(
    state: CourseState,
    section_id: str,
) -> LogicResult:
    """
    User explicitly selects a section from outline.
    
    Check prerequisites and warn if not met.
    """
    if not state.current_course:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="No active course.",
        )
    
    return LogicResult(
        new_state=state,
        commands=[
            CheckPrerequisitesCommand(section_id=section_id),
            LoadSectionCommand(section_id=section_id),
        ],
        ui_message="Loading section...",
    )


def handle_prerequisites_check(
    state: CourseState,
    prerequisites_met: bool,
    missing_prerequisites: List[str],
    section_id: str,
) -> LogicResult:
    """
    Handle result from prerequisites check.
    
    If prerequisites not met, warn user. Otherwise proceed with loading.
    """
    if not prerequisites_met:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message=f"Prerequisites not met. Please complete {len(missing_prerequisites)} section(s) first.",
        )
    
    # Prerequisites met, section will be loaded by LoadSectionCommand
    return LogicResult(
        new_state=state,
        commands=[],
        ui_message="Prerequisites satisfied. Loading section...",
    )


def prepare_section_delivery(
    state: CourseState,
    section: CourseSection,
) -> LogicResult:
    """
    Prepare to deliver a section.
    
    Retrieves relevant chunks and prepares for lecture generation.
    """
    new_state = state.model_copy(
        update={
            "current_section": section,
        }
    )
    
    # If section has chunk_ids, retrieve them
    if section.chunk_ids:
        return LogicResult(
            new_state=new_state,
            commands=[RetrieveChunksCommand(chunk_ids=section.chunk_ids)],
            ui_message=f"Preparing: {section.title}",
        )
    
    # Otherwise, use vector search based on section title/objectives
    embed_text = f"{section.title}. {' '.join(section.learning_objectives)}"
    
    return LogicResult(
        new_state=new_state,
        commands=[EmbedCommand(text=embed_text, task="retrieve_for_section")],
        ui_message=f"Finding material for: {section.title}",
    )


def handle_chunks_retrieved(
    state: CourseState,
    chunks: List[Dict[str, Any]],
) -> LogicResult:
    """
    Handle result from RetrieveChunksCommand or SearchCorpusCommand.
    
    Uses retrieved chunks to generate lecture.
    """
    if not state.current_section:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="No active section.",
        )
    
    return generate_section_lecture(state, chunks)


def generate_section_lecture(
    state: CourseState,
    chunks: List[Dict[str, Any]],
) -> LogicResult:
    """
    Generate lecture script for section using retrieved chunks.
    
    Applies course preferences to delivery style.
    """
    if not state.current_section or not state.current_course:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="No active section or course.",
        )
    
    section = state.current_section
    course = state.current_course
    prefs = course.preferences
    
    # Get context from completed sections (simplified - would query DB in real implementation)
    completed_context = "No previous sections completed yet."  # TODO: Query completed sections
    
    # Format source chunks
    chunk_content = "\n\n".join([
        f"[From Chapter {c.get('chapter_number', '?')}, p.{c.get('page_start', '?')}]\n{c.get('content', '')[:500]}"
        for c in chunks[:10]  # Limit to avoid token limits
    ])
    
    # Build prompt variables
    learning_objectives_list = "\n".join(f"- {obj}" for obj in section.learning_objectives)
    additional_notes_section = f"- Special instructions: {prefs.additional_notes}" if prefs.additional_notes else ""
    style_instruction = (
        "IMPORTANT: Style is 'podcast' - Present this lecture in an engaging podcast format with a consistent, engaging podcast persona. The lecture should feel like a natural podcast episode, engaging and conversational."
        if prefs.presentation_style == "podcast"
        else ""
    )
    
    new_state = state.model_copy(
        update={
            "pending_lecture_generation": True,
        }
    )
    
    return LogicResult(
        new_state=new_state,
        commands=[
            LLMCommand(
                prompt_name="courses.generate_section_lecture",
                prompt_variables={
                    "course_title": course.title,
                    "section_title": section.title,
                    "section_order": section.order_index,
                    "estimated_minutes": section.estimated_minutes,
                    "learning_objectives_list": learning_objectives_list,
                    "completed_context": completed_context,
                    "chunk_content": chunk_content,
                    "depth": prefs.depth,
                    "presentation_style": prefs.presentation_style,
                    "pace": prefs.pace,
                    "additional_notes_section": additional_notes_section,
                    "style_instruction": style_instruction,
                },
                temperature=0.7,
                max_tokens=3000,
                task="generate_section_lecture",
            )
        ],
        ui_message="Generating lecture...",
    )


def handle_lecture_generated(
    state: CourseState,
    lecture_script: str,
) -> LogicResult:
    """
    Handle result from LLMCommand for lecture generation.
    
    Stores lecture and prepares for delivery.
    """
    return finalize_section_delivery(state, lecture_script)


def finalize_section_delivery(
    state: CourseState,
    lecture_script: str,
) -> LogicResult:
    """
    Store lecture and prepare for delivery.
    
    Can optionally generate audio here or do it on-demand.
    """
    if not state.current_section or not state.current_course:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="No active section or course.",
        )
    
    section = state.current_section
    course = state.current_course
    
    delivery = SectionDelivery(
        section_id=section.section_id,
        user_id=course.user_id,
        lecture_script=lecture_script,
        style_snapshot=course.preferences.model_dump(),
    )
    
    new_state = state.model_copy(
        update={
            "current_delivery": delivery,
            "section_delivery_mode": "lecture",
            "pending_lecture_generation": False,
        }
    )
    
    commands = [
        StoreLectureCommand(delivery=delivery),
        UpdateSectionStatusCommand(
            section_id=section.section_id,
            status="in_progress",
        ),
        # NOTE: Audio generation is now handled on-demand via the streaming endpoint
        # when the user clicks play. This provides better UX with immediate playback.
        # We no longer generate audio automatically during delivery.
        # GenerateAudioCommand(
        #     delivery_id=delivery.delivery_id,
        #     text=lecture_script,
        #     voice="onyx",
        #     optional=True,
        # ),
    ]
    
    return LogicResult(
        new_state=new_state,
        commands=commands,
        ui_message="Lecture ready!",
    )


def mark_section_complete(
    state: CourseState,
    section_id: str,
) -> LogicResult:
    """
    Mark section as completed.
    
    This makes it immutable in future outline modifications.
    """
    if not state.current_course:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="No active course.",
        )
    
    new_state = state.model_copy(
        update={
            "current_section": None,
            "current_delivery": None,
            "section_delivery_mode": None,
        }
    )
    
    return LogicResult(
        new_state=new_state,
        commands=[
            UpdateSectionStatusCommand(
                section_id=section_id,
                status="completed",
            ),
            RecordCourseHistoryCommand(
                course_id=state.current_course.course_id,
                change_type="section_completed",
                change_description=f"Section {section_id} marked as completed",
                outline_snapshot={"section_id": section_id},
            ),
        ],
        ui_message="Section marked complete",
    )


# Objective-by-Objective Lecture Generation Functions

def format_previous_lectures(previous_deliveries: List[Dict[str, Any]], sections: List[Dict[str, Any]]) -> str:
    """
    Format previous section lectures with clear section markers.
    
    Args:
        previous_deliveries: List of delivery dicts with section_id and lecture_script
        sections: List of section dicts with section_id and title
    
    Returns:
        Formatted string with section markers
    """
    if not previous_deliveries:
        return "No previous sections have been completed yet."
    
    # Create a map of section_id -> section title
    section_map = {s["section_id"]: s.get("title", "Unknown Section") for s in sections}
    
    # Create a map of section_id -> delivery
    delivery_map = {d["section_id"]: d for d in previous_deliveries}
    
    # Format each delivery with section marker
    formatted = []
    for delivery in previous_deliveries:
        section_id = delivery["section_id"]
        section_title = section_map.get(section_id, "Unknown Section")
        lecture_script = delivery.get("lecture_script", "")
        
        formatted.append(
            f"=== SECTION: {section_title} ===\n\n{lecture_script}\n\n"
        )
    
    return "\n".join(formatted)


def format_course_outline(sections: List[Dict[str, Any]]) -> str:
    """
    Format course outline for context, including part structure.
    
    Args:
        sections: List of section dicts with order_index, title, learning_objectives, parent_section_id
    
    Returns:
        Formatted outline string with parts and sections
    """
    if not sections:
        return "No course outline available."
    
    # Separate parts (parent sections) and child sections
    parts = {}  # part_id -> part_data
    child_sections = {}  # part_id -> [child_sections]
    
    for section in sections:
        parent_id = section.get("parent_section_id")
        if not parent_id:
            # This is a part (parent section)
            parts[section["section_id"]] = section
        else:
            # This is a child section
            if parent_id not in child_sections:
                child_sections[parent_id] = []
            child_sections[parent_id].append(section)
    
    # Build formatted outline
    formatted = []
    
    # Sort parts by order_index
    sorted_parts = sorted(parts.items(), key=lambda x: x[1].get("order_index", 0))
    
    for part_id, part_data in sorted_parts:
        part_title = part_data.get("title", "Unknown Part")
        part_order = part_data.get("order_index", 0)
        
        formatted.append(f"PART {part_order}: {part_title}")
        
        # Get and sort child sections for this part
        children = sorted(
            child_sections.get(part_id, []),
            key=lambda s: s.get("order_index", 0)
        )
        
        for child in children:
            title = child.get("title", "Unknown")
            objectives = child.get("learning_objectives", [])
            order = child.get("order_index", 0)
            
            obj_text = "\n    ".join(f"- {obj}" for obj in objectives) if objectives else "    (No objectives listed)"
            formatted.append(f"  Section {order}: {title}\n    {obj_text}")
        
        formatted.append("")  # Blank line between parts
    
    return "\n".join(formatted)


def prepare_section_delivery_with_context(
    state: CourseState,
    section: CourseSection,
    previous_deliveries: List[Dict[str, Any]],
    all_sections: List[Dict[str, Any]],
) -> LogicResult:
    """
    Prepare section delivery with full context (course outline, previous lectures, part information).
    
    Initializes state for objective-by-objective generation.
    """
    if not state.current_course:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="No active course.",
        )
    
    # Format context
    previous_lectures = format_previous_lectures(previous_deliveries, all_sections)
    course_outline = format_course_outline(all_sections)
    
    # Find part information for this section
    part_info = None
    if section.parent_section_id:
        # Find the parent section (part) in all_sections
        for s in all_sections:
            if s.get("section_id") == section.parent_section_id:
                part_info = {
                    "part_id": s.get("section_id"),
                    "part_title": s.get("title", "Unknown Part"),
                    "part_order": s.get("order_index", 0),
                }
                break
    
    # Check if this is the first section in a new part
    is_first_section_in_part = False
    if part_info:
        # Check if any previous deliveries are from this part
        part_deliveries = [
            d for d in previous_deliveries
            if any(s.get("parent_section_id") == part_info["part_id"] for s in all_sections if s.get("section_id") == d.get("section_id"))
        ]
        is_first_section_in_part = len(part_deliveries) == 0
    
    # Add part context to previous lectures context
    part_context = ""
    if part_info:
        part_context = (
            f"\n\n=== PART CONTEXT ===\n"
            f"Current section is part of: {part_info['part_title']} (Part {part_info['part_order']})\n"
            f"{'This is the FIRST section in this part - include a smooth transition introducing the new part.' if is_first_section_in_part else 'This section continues within the current part.'}"
        )
    
    # Initialize generation state
    new_state = state.model_copy(
        update={
            "current_section": section,
            "current_section_draft": "",
            "covered_objectives": [],
            "section_generation_phase": "objectives",
            "previous_lectures_context": previous_lectures + part_context,
            "course_outline_context": course_outline,
        }
    )
    
    # Find first uncovered objective
    if not section.learning_objectives:
        return LogicResult(
            new_state=new_state,
            commands=[],
            ui_message="Section has no learning objectives.",
        )
    
    # Start with first objective (index 0)
    objective_index = 0
    objective_text = section.learning_objectives[objective_index]
    
    # Generate embedding for this objective
    embed_text = f"{section.title}. {objective_text}"
    
    return LogicResult(
        new_state=new_state,
        commands=[EmbedCommand(text=embed_text, task="retrieve_for_objective")],
        ui_message=f"Preparing objective {objective_index + 1}/{len(section.learning_objectives)}: {objective_text[:50]}...",
    )


def generate_objective_content(
    state: CourseState,
    objective_index: int,
    chunks: List[Dict[str, Any]],
) -> LogicResult:
    """
    Generate lecture content for a specific objective.
    
    Uses RAG chunks retrieved for this objective.
    """
    if not state.current_section or not state.current_course:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="No active section or course.",
        )
    
    section = state.current_section
    course = state.current_course
    prefs = course.preferences
    
    # Validate objective index
    if objective_index < 0 or objective_index >= len(section.learning_objectives):
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message=f"Invalid objective index: {objective_index}",
        )
    
    objective_text = section.learning_objectives[objective_index]
    
    # Format chunks for this objective
    chunk_content = "\n\n".join([
        f"[From Chapter {c.get('chapter_number', '?')}, p.{c.get('page_start', '?')}]\n{c.get('content', '')[:1000]}"
        for c in chunks[:10]  # Limit to avoid token limits
    ])
    
    # Build prompt with full context
    previous_lectures = state.previous_lectures_context or "No previous sections completed yet."
    course_outline = state.course_outline_context or "Course outline not available."
    current_draft = state.current_section_draft or "(No content generated yet for this section)"
    
    # Build style directive - use presentation_style field, default to "conversational"
    style_directive = prefs.presentation_style if prefs.presentation_style else "conversational"
    # If presentation_style is a simple keyword, expand it; otherwise use as-is (allows detailed descriptions)
    if style_directive == "formal":
        style_directive = "Present this material in a formal, academic style appropriate for a university lecture."
    elif style_directive == "conversational":
        style_directive = "Present this material in a conversational, engaging style that feels natural when spoken."
    elif style_directive == "casual":
        style_directive = "Present this material in a casual, relaxed style that feels friendly and approachable."
    elif style_directive == "podcast":
        style_directive = "Present this material in an engaging podcast format with a consistent, engaging podcast persona. The content should feel like a natural podcast episode, engaging and conversational."
    # If it's something else (a detailed description), use it as-is
    
    # Extract part context if present in previous_lectures_context
    part_context_section = ""
    if "=== PART CONTEXT ===" in previous_lectures:
        # Extract the part context section
        parts = previous_lectures.split("=== PART CONTEXT ===")
        if len(parts) > 1:
            part_context_section = "=== PART CONTEXT ===" + parts[1]
            # Remove it from previous_lectures for cleaner display
            previous_lectures_clean = parts[0].strip()
        else:
            previous_lectures_clean = previous_lectures
    else:
        previous_lectures_clean = previous_lectures
    
    # Build prompt variables
    additional_notes_section = f"- Additional notes: {prefs.additional_notes}" if prefs.additional_notes else ""
    
    new_state = state.model_copy(
        update={
            "pending_lecture_generation": True,
        }
    )
    
    return LogicResult(
        new_state=new_state,
        commands=[
            LLMCommand(
                prompt_name="courses.generate_objective_content",
                prompt_variables={
                    "style_directive": style_directive,
                    "course_outline": course_outline,
                    "previous_lectures": previous_lectures_clean,
                    "part_context": part_context_section,
                    "current_draft": current_draft,
                    "section_title": section.title,
                    "estimated_minutes": section.estimated_minutes,
                    "objective_text": objective_text,
                    "chunk_content": chunk_content,
                    "depth": prefs.depth,
                    "pace": prefs.pace,
                    "additional_notes_section": additional_notes_section,
                },
                temperature=0.2,
                max_tokens=2000,  # Per objective, so smaller than full lecture
                task=f"generate_objective_content_{objective_index}",
            ),
            UpdateGenerationProgressCommand(
                section_id=section.section_id,
                phase="objectives",
                covered_objectives=list(state.covered_objectives or []),
                total_objectives=len(section.learning_objectives),
            ),
        ],
        ui_message=f"Generating content for objective {objective_index + 1}/{len(section.learning_objectives)}...",
    )


def handle_objective_generated(
    state: CourseState,
    objective_index: int,
    objective_content: str,
) -> LogicResult:
    """
    Handle generated content for an objective.
    
    Adds to draft and marks objective as covered.
    """
    if not state.current_section:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="No active section.",
        )
    
    section = state.current_section
    
    # Validate objective index
    if objective_index < 0 or objective_index >= len(section.learning_objectives):
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message=f"Invalid objective index: {objective_index}",
        )
    
    # Add content to draft
    current_draft = state.current_section_draft or ""
    new_draft = current_draft + "\n\n" + objective_content if current_draft else objective_content
    
    # Mark objective as covered
    covered = list(state.covered_objectives)
    if objective_index not in covered:
        covered.append(objective_index)
    
    new_state = state.model_copy(
        update={
            "current_section_draft": new_draft,
            "covered_objectives": covered,
            "pending_lecture_generation": False,
        }
    )
    
    # Check if all objectives are covered
    all_covered = len(covered) >= len(section.learning_objectives)
    
    if all_covered:
        # All objectives complete - find relevant figures using the combined draft
        # BEFORE moving to refinement phase, so UI can see the completion
        return LogicResult(
            new_state=new_state,
            commands=[
                UpdateGenerationProgressCommand(
                    section_id=section.section_id,
                    phase="objectives",
                    covered_objectives=list(covered),  # All objectives now covered
                    total_objectives=len(section.learning_objectives),
                ),
                # Embed the combined draft to find relevant figures
                EmbedCommand(
                    text=new_draft,  # Combined draft from all objectives
                    task="find_figures_for_lecture"
                ),
            ],
            ui_message=f"All {len(section.learning_objectives)} objectives complete. Finding relevant figures...",
        )
        # Note: Next iteration will process figure search, then call refine_section_lecture
        # Note: Next iteration will process figure search, then call refine_section_lecture
    else:
        # Continue with next objective
        # Find next uncovered objective
        next_index = None
        for i in range(len(section.learning_objectives)):
            if i not in covered:
                next_index = i
                break
        
        if next_index is None:
            # Shouldn't happen, but handle gracefully
            return refine_section_lecture(new_state)
        
        objective_text = section.learning_objectives[next_index]
        embed_text = f"{section.title}. {objective_text}"
        
        return LogicResult(
            new_state=new_state,
            commands=[
                EmbedCommand(text=embed_text, task="retrieve_for_objective"),
                UpdateGenerationProgressCommand(
                    section_id=section.section_id,
                    phase="objectives",
                    covered_objectives=list(covered),
                    total_objectives=len(section.learning_objectives),
                ),
            ],
            ui_message=f"Objective {objective_index + 1} complete. Preparing objective {next_index + 1}/{len(section.learning_objectives)}: {objective_text[:50]}...",
        )


def find_figures_for_combined_draft(
    state: CourseState,
    draft_embedding: List[float],
) -> LogicResult:
    """
    After all objectives complete, find 0-3 relevant figures using the combined draft.
    
    Returns command to search figure chunks, then selects best 0-3.
    """
    from src.core.commands import SearchFiguresCommand
    
    return LogicResult(
        new_state=state,
        commands=[
            SearchFiguresCommand(
                embedding=draft_embedding,
                limit=5,  # Get top 5, will select best 0-1
                similarity_threshold=0.0  # No threshold for testing - accept any similarity
            )
        ],
        ui_message="Searching for relevant figures...",
    )


def select_and_store_figures(
    state: CourseState,
    figure_candidates: List[Dict[str, Any]],
) -> LogicResult:
    """
    Select 0-3 best figures from candidates and store in state.
    
    Then proceed to refinement phase with figures included.
    """
    logger.info(f"select_and_store_figures: Received {len(figure_candidates)} figure candidates")
    
    # Log all similarity scores for debugging
    if figure_candidates:
        similarities = [f.get('similarity', 0) for f in figure_candidates]
        logger.info(f"select_and_store_figures: All similarity scores: {similarities}")
        logger.info(f"select_and_store_figures: Max similarity: {max(similarities) if similarities else 0:.3f}, Min: {min(similarities) if similarities else 0:.3f}")
    
    # For testing: accept any figure, no threshold filtering
    # Just sort by similarity and take the highest one
    qualified = figure_candidates.copy()  # Accept all candidates for testing
    
    logger.info(f"select_and_store_figures: Accepting all {len(qualified)} figures (no threshold filter for testing)")
    
    # Sort by similarity (descending)
    qualified.sort(key=lambda x: x.get('similarity', 0), reverse=True)
    
    # Select top 1 (highest similarity) for testing
    selected = qualified[:1] if qualified else []
    
    logger.info(f"select_and_store_figures: Selected {len(selected)} figures for lecture")
    
    # Extract figure metadata
    selected_figures = []
    for f in selected:
        figure_id = f.get('figure_id')
        if not figure_id:
            logger.warning(f"select_and_store_figures: Figure candidate missing figure_id: {f}")
            continue
        
        # Build caption with book title and page number
        base_caption = f.get('figure_caption', '') or f.get('caption', '')
        book_title = f.get('book_title', '')
        page_num = f.get('page_start', 0) or f.get('page', 0)
        
        # Format caption: "Caption (Book Title, Page X)" or just "Caption (Page X)" if no book title
        if base_caption:
            if book_title:
                full_caption = f"{base_caption} ({book_title}, Page {page_num})"
            else:
                full_caption = f"{base_caption} (Page {page_num})"
        else:
            # No caption, just show source
            if book_title:
                full_caption = f"Figure ({book_title}, Page {page_num})"
            else:
                full_caption = f"Figure (Page {page_num})"
        
        figure_dict = {
            'figure_id': str(figure_id),
            'chunk_id': str(f.get('chunk_id', '')),
            'caption': full_caption,  # Full caption with book and page
            'base_caption': base_caption,  # Original caption without source
            'description': f.get('content', '') or f.get('description', ''),
            'page': page_num,
            'book_id': str(f.get('book_id', '')),
            'book_title': book_title,
            'chapter_number': f.get('chapter_number'),
            'similarity': f.get('similarity', 0)
        }
        selected_figures.append(figure_dict)
        logger.info(f"select_and_store_figures: Storing figure {figure_dict['figure_id']} (page {figure_dict['page']}, similarity {figure_dict['similarity']:.3f})")
    
    new_state = state.model_copy(update={
        'selected_lecture_figures': selected_figures
    })
    
    # Now proceed to refinement with figures
    return refine_section_lecture(new_state)


def refine_section_lecture(
    state: CourseState,
) -> LogicResult:
    """
    Refine the complete section draft for flow, style consistency, and reordering.
    
    All objectives have been covered. This final call ensures the lecture flows
    well and matches the style of previous lectures.
    """
    if not state.current_section or not state.current_course:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="No active section or course.",
        )
    
    section = state.current_section
    course = state.current_course
    prefs = course.preferences
    
    if not state.current_section_draft:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="No draft content to refine.",
        )
    
    previous_lectures = state.previous_lectures_context or "No previous sections completed yet."
    course_outline = state.course_outline_context or "Course outline not available."
    
    # Extract part context if present
    part_context_section = ""
    if "=== PART CONTEXT ===" in previous_lectures:
        parts = previous_lectures.split("=== PART CONTEXT ===")
        if len(parts) > 1:
            part_context_section = "=== PART CONTEXT ===" + parts[1]
            previous_lectures_clean = parts[0].strip()
        else:
            previous_lectures_clean = previous_lectures
    else:
        previous_lectures_clean = previous_lectures
    
    # List all objectives to ensure coverage
    objectives_list = "\n".join(f"{i+1}. {obj}" for i, obj in enumerate(section.learning_objectives))
    
    # Build style directive - use presentation_style field, default to "conversational"
    style_directive = prefs.presentation_style if prefs.presentation_style else "conversational"
    # If presentation_style is a simple keyword, expand it; otherwise use as-is (allows detailed descriptions)
    if style_directive == "formal":
        style_directive = "Present this material in a formal, academic style appropriate for a university lecture."
    elif style_directive == "conversational":
        style_directive = "Present this material in a conversational, engaging style that feels natural when spoken."
    elif style_directive == "casual":
        style_directive = "Present this material in a casual, relaxed style that feels friendly and approachable."
    elif style_directive == "podcast":
        style_directive = "Present this material in an engaging podcast format with a consistent, engaging podcast persona. The content should feel like a natural podcast episode, engaging and conversational."
    # If it's something else (a detailed description), use it as-is
    
    # Build prompt variables
    additional_notes_section = f"- Additional notes: {prefs.additional_notes}" if prefs.additional_notes else ""
    
    # Format figure context if figures were selected (NEW)
    figure_context = ""
    figure_instructions = ""
    if state.selected_lecture_figures and len(state.selected_lecture_figures) > 0:
        figure_context = "\n\n=== RELEVANT FIGURES TO INCORPORATE ===\n"
        for i, fig in enumerate(state.selected_lecture_figures, 1):
            figure_id = fig.get('figure_id', '')
            figure_context += f"""
Figure {i} (ID: {figure_id}):
- Caption: {fig.get('base_caption', fig.get('caption', 'N/A'))}
- Description: {fig.get('description', 'N/A')}
- Source: {fig.get('book_title', 'Unknown Book')}, Page {fig.get('page', '?')}, Chapter {fig.get('chapter_number', '?')}
- When referencing this figure in your lecture, use the marker: [FIGURE:{figure_id}]
- After the lecture content, provide a brief explanation (2-3 sentences) for each figure using the format: [FIGURE_EXPLANATION:{figure_id}]Your explanation here[/FIGURE_EXPLANATION]
"""
        figure_instructions = """Naturally incorporate the provided figures at appropriate points in the lecture where they are most relevant to the content being discussed. When mentioning a figure, describe what it shows in your own words as part of the narrative flow. 

IMPORTANT: 
1. When you reference a figure, include a special marker in this exact format: [FIGURE:figure_id] where figure_id is the figure's ID. For example, if discussing a figure with ID "abc123", you might write: "As we can see in this visualization [FIGURE:abc123], the relationship between these variables becomes clear."

2. At the END of the lecture (after all content), provide a brief explanation (2-3 sentences) for each figure that was referenced, explaining what the figure illustrates about the lecture content. Use this format:
[FIGURE_EXPLANATION:figure_id]Your explanation of what this figure illustrates about the lecture content[/FIGURE_EXPLANATION]

Place the figure discussion where it adds the most value to understanding the concept being explained. The [FIGURE:figure_id] markers will be converted to clickable links that allow users to navigate to the figure."""
    else:
        figure_instructions = ""
    
    new_state = state.model_copy(
        update={
            "section_generation_phase": "refining",
            "pending_lecture_generation": True,
        }
    )
    
    # Calculate appropriate max_tokens based on estimated lecture length
    # Rough estimate: 1 minute of lecture ≈ 150-200 words ≈ 200-250 tokens
    # For a 20-minute lecture, we need ~4000-5000 tokens, but add buffer for refinement
    estimated_tokens = max(8000, int(section.estimated_minutes * 250 * 1.5))  # 1.5x buffer
    
    return LogicResult(
        new_state=new_state,
        commands=[
            LLMCommand(
                prompt_name="courses.refine_section_lecture",
                prompt_variables={
                    "style_directive": style_directive,
                    "course_outline": course_outline,
                    "previous_lectures": previous_lectures_clean,
                    "part_context": part_context_section,
                    "section_title": section.title,
                    "estimated_minutes": section.estimated_minutes,
                    "objectives_list": objectives_list,
                    "current_draft": state.current_section_draft or "",
                    "figure_context": figure_context,  # NEW
                    "figure_instructions": figure_instructions,  # NEW
                    "depth": prefs.depth,
                    "pace": prefs.pace,
                    "additional_notes_section": additional_notes_section,
                },
                temperature=0.2,
                max_tokens=estimated_tokens,  # Dynamic based on lecture length
                task="refine_section_lecture",
            ),
            UpdateGenerationProgressCommand(
                section_id=section.section_id,
                phase="refining",
                covered_objectives=list(state.covered_objectives or []),
                total_objectives=len(section.learning_objectives),
            ),
        ],
        ui_message=f"Refining lecture with {len(state.selected_lecture_figures)} figure(s)..." if state.selected_lecture_figures else "Refining lecture for flow and style consistency...",
    )


def handle_lecture_refined(
    state: CourseState,
    refined_script: str,
) -> LogicResult:
    """
    Handle refined lecture script.
    
    Post-processes the script to convert [FIGURE:figure_id] markers into HTML links.
    Also programmatically splits paragraphs that are too long.
    
    Stores the final lecture and prepares for delivery.
    """
    if not state.current_section or not state.current_course:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="No active section or course.",
        )
    
    # Validate refined script is not empty
    if not refined_script or len(refined_script.strip()) < 50:
        logger.warning("Refined lecture script is too short or empty, using draft instead")
        # Fall back to draft if refinement failed
        refined_script = state.current_section_draft or "Lecture content could not be generated."
    
    # Post-process: Convert [FIGURE:figure_id] markers to HTML links and extract figure explanations
    import re
    figure_explanations: Dict[str, str] = {}
    if state.selected_lecture_figures:
        # Create a mapping of figure_id to figure data for link text
        figure_map = {fig.get('figure_id', ''): fig for fig in state.selected_lecture_figures}
        
        def replace_figure_marker(match):
            figure_id = match.group(1)
            if figure_id in figure_map:
                fig = figure_map[figure_id]
                caption = fig.get('base_caption', fig.get('caption', 'Figure'))
                # Create a clickable link that will be handled by frontend
                return f'<a href="#figure-{figure_id}" class="figure-link" data-figure-id="{figure_id}" style="color: #2563eb; text-decoration: underline; cursor: pointer;">{caption}</a>'
            else:
                # Figure ID not found, just remove the marker
                logger.warning(f"Figure ID {figure_id} not found in selected figures")
                return ""
        
        # Extract figure explanations first (before removing markers)
        explanation_pattern = r'\[FIGURE_EXPLANATION:([^\]]+)\](.*?)\[/FIGURE_EXPLANATION\]'
        explanation_matches = re.findall(explanation_pattern, refined_script, re.DOTALL)
        for figure_id, explanation in explanation_matches:
            explanation_clean = explanation.strip()
            if explanation_clean:
                figure_explanations[figure_id] = explanation_clean
                logger.debug(f"Extracted explanation for figure {figure_id}: {explanation_clean[:50]}...")
        
        # Remove explanation markers from the script
        refined_script = re.sub(explanation_pattern, '', refined_script, flags=re.DOTALL)
        
        # Replace [FIGURE:figure_id] with HTML links
        matches_found = len(re.findall(r'\[FIGURE:([^\]]+)\]', refined_script))
        refined_script = re.sub(r'\[FIGURE:([^\]]+)\]', replace_figure_marker, refined_script)
        logger.info(f"Post-processed lecture script: found {matches_found} figure markers, converted to links, extracted {len(figure_explanations)} explanations")
    
    section = state.current_section
    course = state.current_course
    
    delivery = SectionDelivery(
        section_id=section.section_id,
        user_id=course.user_id,
        lecture_script=refined_script,
        style_snapshot=course.preferences.model_dump(),
    )
    
    new_state = state.model_copy(
        update={
            "current_delivery": delivery,
            "section_delivery_mode": "lecture",
            "pending_lecture_generation": False,
            "section_generation_phase": "complete",
            # Clear draft state (no longer needed)
            "current_section_draft": None,
            "covered_objectives": [],
        }
    )
    
    from src.core.commands import LinkFiguresToDeliveryCommand
    
    # Prepare figures with explanations for storage
    figures_for_storage = []
    if state.selected_lecture_figures:
        for fig in state.selected_lecture_figures:
            figure_id = fig.get('figure_id', '')
            figure_dict = {
                'figure_id': figure_id,
                'chunk_id': fig.get('chunk_id'),
                'caption': fig.get('caption'),  # Full caption with book and page
                'description': fig.get('description'),
                'page': fig.get('page'),
                'book_id': fig.get('book_id'),
                'chapter_number': fig.get('chapter_number'),
                'similarity': fig.get('similarity', 0),
                'explanation': figure_explanations.get(figure_id, ''),  # Add explanation if available
            }
            figures_for_storage.append(figure_dict)
    
    commands = [
        StoreLectureCommand(delivery=delivery),
        UpdateSectionStatusCommand(
            section_id=section.section_id,
            status="in_progress",
        ),
        UpdateGenerationProgressCommand(
            section_id=section.section_id,
            phase="complete",
            covered_objectives=list(state.covered_objectives or []),
            total_objectives=len(section.learning_objectives),
        ),
    ]
    
    # Link figures if any were selected (NEW)
    figures_count = len(figures_for_storage)
    if figures_count > 0:
        commands.append(
            LinkFiguresToDeliveryCommand(
                delivery_id=delivery.delivery_id,
                figures=figures_for_storage  # Use figures with explanations
            )
        )
    
    # Clear selected figures after linking
    new_state = new_state.model_copy(update={
        "selected_lecture_figures": []
    })
    
    return LogicResult(
        new_state=new_state,
        commands=commands,
        ui_message=f"Lecture ready with {figures_count} figure(s)!" if figures_count > 0 else "Lecture ready!",
    )


def generate_audio_for_section(
    state: CourseState,
    section_id: str,
    delivery_data: Dict[str, Any],
) -> LogicResult:
    """
    Generate audio for an existing section delivery on-demand.
    
    This is called when user requests audio for a lecture that doesn't have it yet.
    """
    if not delivery_data:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="Delivery not found. Cannot generate audio.",
        )
    
    lecture_script = delivery_data.get("lecture_script")
    if not lecture_script:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="Lecture script not found. Cannot generate audio.",
        )
    
    # Check if audio already exists
    if delivery_data.get("audio_data"):
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="Audio already exists for this lecture.",
        )
    
    delivery_id = delivery_data["delivery_id"]
    
    # NOTE: Audio generation is now handled on-demand via the streaming endpoint
    # when the user clicks play. We no longer generate audio automatically.
    # Return empty commands - audio will be generated on-demand when user plays.
    return LogicResult(
        new_state=state,
        commands=[],
        ui_message="Lecture ready. Click play to generate audio on-demand.",
    )


def handle_audio_generated(
    state: CourseState,
    audio_results: Dict[str, Any],
) -> LogicResult:
    """
    Handle audio generation result and update delivery with audio_data.
    
    If audio generation failed, logs error and notifies user but doesn't block delivery.
    """
    if not state.current_delivery:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="No active delivery to update with audio.",
        )
    
    audio_generated = audio_results.get("audio_generated", False)
    audio_data = audio_results.get("audio_data")
    audio_error = audio_results.get("audio_error")
    
    if audio_generated and audio_data:
        # Audio generated successfully - update delivery with audio_data
        logger.info(f"Audio generated successfully for delivery {state.current_delivery.delivery_id}")
        
        updated_delivery = state.current_delivery.model_copy(
            update={"audio_data": audio_data}
        )
        
        new_state = state.model_copy(
            update={"current_delivery": updated_delivery}
        )
        
        # Store updated delivery with audio
        return LogicResult(
            new_state=new_state,
            commands=[
                StoreLectureCommand(delivery=updated_delivery),
            ],
            ui_message="Lecture with audio ready!",
        )
    else:
        # Audio generation failed - log error and notify user
        error_msg = audio_error or "Audio generation failed"
        logger.error(
            f"Audio generation failed for delivery {state.current_delivery.delivery_id}: {error_msg}"
        )
        
        # User still has written script - just notify them
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message=f"Lecture ready! Note: Audio generation failed ({error_msg}). Written script is available.",
        )


# Q&A Functions

def pause_section_for_qa(
    state: CourseState,
    section_id: str,
    lecture_position_seconds: int,
) -> LogicResult:
    """
    Pause lecture delivery and enter Q&A mode.
    
    User can ask questions about the current section material.
    After Q&A, they can resume the lecture.
    """
    if not state.current_delivery:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="No active delivery to pause.",
        )
    
    new_state = state.model_copy(
        update={
            "section_delivery_mode": "qa",
            "lecture_pause_position": lecture_position_seconds,
        }
    )
    
    return LogicResult(
        new_state=new_state,
        commands=[
            CreateQASessionCommand(
                section_id=section_id,
                delivery_id=state.current_delivery.delivery_id,
                lecture_position_seconds=lecture_position_seconds,
            )
        ],
        ui_message="Q&A mode activated. Ask any questions about this section.",
    )


def handle_qa_session_created(
    state: CourseState,
    qa_session_id: str,
) -> LogicResult:
    """
    Handle Q&A session creation result.
    
    Updates state with active Q&A session.
    """
    if not state.current_section or not state.current_course:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="No active section or course.",
        )
    
    qa_session = QASession(
        qa_session_id=qa_session_id,
        section_id=state.current_section.section_id,
        delivery_id=state.current_delivery.delivery_id if state.current_delivery else None,
        user_id=state.current_course.user_id,
        lecture_position_seconds=state.lecture_pause_position or 0,
    )
    
    new_state = state.model_copy(
        update={
            "current_qa_session": qa_session,
        }
    )
    
    return LogicResult(
        new_state=new_state,
        commands=[],
        ui_message=None,  # UI handles display
    )


def process_qa_question(
    state: CourseState,
    question: str,
) -> LogicResult:
    """
    Process a question during section Q&A.
    
    Uses the section's source chunks and course context to answer.
    Integrates with existing chat/retrieval system.
    """
    if not state.current_section or not state.current_course:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="No active section or course.",
        )
    
    section = state.current_section
    course = state.current_course
    prefs = course.preferences
    
    # Build context-aware query
    podcast_instruction = ""
    if prefs.presentation_style == "podcast":
        podcast_instruction = "\n\nIMPORTANT: Answer this question in the same engaging podcast persona used for the course lectures. Keep the response conversational, engaging, and in podcast style."
    
    context_query = f"""Question about course section: {section.title}
Course: {course.title}

User question: {question}

Answer using the source material for this section, and reference 
previously covered sections if relevant.{podcast_instruction}
"""
    
    new_state = state.model_copy(
        update={
            "pending_qa_question": question,
        }
    )
    
    return LogicResult(
        new_state=new_state,
        commands=[
            EmbedCommand(text=context_query, task="qa_question"),
            SearchCorpusCommand(
                query_text=context_query,
                chunk_types=["text"],
                top_k={"text": 5},
                metadata_filters={},
                exclude_filters={},
            ),
        ],
        ui_message="Finding answer...",
    )


def record_qa_interaction(
    state: CourseState,
    question: str,
    answer: str,
    context_chunks: List[str],
) -> LogicResult:
    """
    Record Q&A interaction in the session.
    
    Stores question/answer pair for context in future Q&A.
    """
    if not state.current_qa_session:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="No active Q&A session.",
        )
    
    qa_message_user = {
        "role": "user",
        "content": question,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    qa_message_assistant = {
        "role": "assistant",
        "content": answer,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    new_state = state.model_copy(
        update={
            "pending_qa_question": None,
        }
    )
    
    return LogicResult(
        new_state=new_state,
        commands=[
            AppendQAMessageCommand(
                qa_session_id=state.current_qa_session.qa_session_id,
                messages=[qa_message_user, qa_message_assistant],
                context_chunks=context_chunks,
            )
        ],
        ui_message=None,  # UI handles display
    )


def resume_section_lecture(
    state: CourseState,
) -> LogicResult:
    """
    Resume lecture delivery after Q&A session.
    
    Returns to lecture at the pause position.
    """
    if not state.current_qa_session:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="No active Q&A session to end.",
        )
    
    pause_position = state.lecture_pause_position or 0
    qa_session_id = state.current_qa_session.qa_session_id
    
    new_state = state.model_copy(
        update={
            "section_delivery_mode": "lecture",
            "lecture_pause_position": None,
            "current_qa_session": None,
        }
    )
    
    minutes = pause_position // 60
    seconds = pause_position % 60
    
    return LogicResult(
        new_state=new_state,
        commands=[
            EndQASessionCommand(qa_session_id=qa_session_id),
        ],
        ui_message=f"Resuming lecture at {minutes}:{seconds:02d}",
    )


def complete_section_with_qa(
    state: CourseState,
    section_id: str,
) -> LogicResult:
    """
    Mark section complete after Q&A session.
    
    Ensures Q&A session is closed and section is marked complete.
    """
    if not state.current_course:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="No active course.",
        )
    
    # End any active Q&A session
    commands = []
    if state.current_qa_session:
        commands.append(
            EndQASessionCommand(
                qa_session_id=state.current_qa_session.qa_session_id,
            )
        )
    
    # Mark section complete
    commands.extend([
        UpdateSectionStatusCommand(
            section_id=section_id,
            status="completed",
        ),
        RecordCourseHistoryCommand(
            course_id=state.current_course.course_id,
            change_type="section_completed",
            change_description=f"Section {section_id} completed with Q&A",
            outline_snapshot={"section_id": section_id},
        ),
    ])
    
    new_state = state.model_copy(
        update={
            "section_delivery_mode": None,
            "current_qa_session": None,
            "lecture_pause_position": None,
            "current_section": None,
            "current_delivery": None,
        }
    )
    
    return LogicResult(
        new_state=new_state,
        commands=commands,
        ui_message="Section completed!",
    )


def process_generation_step(
    state: CourseState,
    command_results: Dict[str, Any],
) -> LogicResult:
    """
    Process command results and determine next step in lecture generation.
    
    This is a pure function that:
    1. Examines command results to determine what was executed
    2. Calls appropriate logic functions based on the phase
    3. Returns next LogicResult with commands to execute
    
    This allows the route handler to simply loop:
    - Call logic → execute commands → call logic with results → repeat
    """
    if not state.current_section:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="No active section.",
        )
    
    section = state.current_section
    course_results = command_results.get("course_results", {})
    
    # Debug logging
    logger.debug(f"process_generation_step: phase={state.section_generation_phase}, course_results keys={list(course_results.keys())}")
    
    # Check what phase we're in
    phase = state.section_generation_phase
    
    if phase == "objectives":
        # We're generating objectives
        # Check what command result we have
        # Priority: llm_response > chunks > embedding (process most recent first)
        
        # Case 1: LLMCommand result (objective content generated) - highest priority
        # BUT: Only process if task matches - if not, it's stale and we should check other results
        if "llm_response" in course_results:
            llm_response = course_results["llm_response"]
            task = course_results.get("task", "")
            logger.debug(f"process_generation_step: Found llm_response, task='{task}'")
            
            if task.startswith("generate_objective_content_"):
                # Extract objective index from task
                try:
                    obj_index = int(task.split("_")[-1])
                    logger.debug(f"process_generation_step: Processing LLM response for objective {obj_index}")
                    result = handle_objective_generated(state, obj_index, llm_response)
                    # Note: If all objectives are complete, handle_objective_generated returns a progress update command
                    # The transition to refining will happen in the next iteration after progress is updated
                    return result
                except (ValueError, IndexError):
                    logger.error(f"Could not parse objective index from task: {task}")
                    return LogicResult(
                        new_state=state,
                        commands=[],
                        ui_message=f"Error: Could not parse objective index from task: {task}",
                    )
            elif task == "retrieve_for_objective":
                # This is a stale llm_response from a previous EmbedCommand - ignore it
                logger.debug(f"process_generation_step: LLM response with task 'retrieve_for_objective' is stale, ignoring and checking other results")
                # Continue to check chunks or embedding (don't return, fall through)
            elif task.startswith("refine_lecture") or task == "refine_section_lecture":
                # This is from refinement - handle it in the refining phase
                if phase == "refining":
                    logger.debug(f"process_generation_step: Processing refinement LLM response with task '{task}'")
                    return handle_lecture_refined(state, llm_response)
                else:
                    logger.debug(f"process_generation_step: LLM response with task '{task}' is from refinement, but we're in {phase} phase, ignoring")
                    # Continue to check other results
            else:
                logger.warning(f"process_generation_step: LLM response task '{task}' doesn't match known patterns, ignoring and checking other results")
                # Continue to check chunks or embedding (don't return, fall through)
        
        # If we get here, either no llm_response or it was stale/ignored
        # Check for chunks or embedding
        
        # Case 2: SearchFiguresCommand result (figures retrieved)
        if "figure_chunks" in course_results:
            figure_chunks = course_results["figure_chunks"]
            logger.debug(f"process_generation_step: Found figure chunks ({len(figure_chunks)}), selecting best figures")
            return select_and_store_figures(state, figure_chunks)
        
        # Case 2b: SearchCorpusCommand result (chunks retrieved)
        if "chunks" in course_results:
            chunks = course_results["chunks"]
            logger.debug(f"process_generation_step: Found chunks ({len(chunks)}), finding next objective")
            
            # Find which objective we're working on
            covered = state.covered_objectives or []
            next_obj_index = None
            for i in range(len(section.learning_objectives)):
                if i not in covered:
                    next_obj_index = i
                    break
            
            if next_obj_index is None:
                # All objectives covered, move to refinement
                logger.debug("process_generation_step: All objectives covered, moving to refinement")
                return refine_section_lecture(state)
            
            logger.debug(f"process_generation_step: Generating content for objective {next_obj_index}")
            # Generate content for this objective
            return generate_objective_content(state, next_obj_index, chunks or [])
        
        # Case 3: EmbedCommand result (embedding generated)
        if "embedding" in course_results:
            embedding = course_results["embedding"]
            task = course_results.get("task")
            
            logger.debug(f"process_generation_step: Received embedding with task='{task}'")
            
            # NEW: Handle figure search embedding
            if task == "find_figures_for_lecture":
                logger.info("process_generation_step: Processing figure search embedding")
                return find_figures_for_combined_draft(state, embedding)
            
            # Process embedding for objective retrieval
            # Even if task doesn't match expected pattern, if we have embedding we should use it
            # (task might be missing or stale, but embedding is valid)
            if task and task != "retrieve_for_objective":
                logger.warning(f"process_generation_step: Embedding has unexpected task '{task}', processing anyway")
            
            # Find next uncovered objective
            covered = state.covered_objectives or []
            next_obj_index = None
            for i in range(len(section.learning_objectives)):
                if i not in covered:
                    next_obj_index = i
                    break
            
            if next_obj_index is None:
                # All objectives covered, move to refinement
                return refine_section_lecture(state)
            
            # Search corpus for this objective
            objective_text = section.learning_objectives[next_obj_index]
            
            logger.debug(f"process_generation_step: Processing embedding for objective {next_obj_index} (task={task})")
            
            return LogicResult(
                new_state=state,
                commands=[
                    SearchCorpusCommand(
                        query_text=objective_text,
                        chunk_types=["chapter", "2page"],
                        top_k={"chapter": 3, "2page": 7},
                    ),
                    UpdateGenerationProgressCommand(
                        section_id=section.section_id,
                        phase="objectives",
                        covered_objectives=list(covered),
                        total_objectives=len(section.learning_objectives),
                    ),
                ],
                ui_message=f"Retrieving content for objective {next_obj_index + 1}/{len(section.learning_objectives)}...",
            )
        
        
        # Unknown result - check if we should continue
        covered = state.covered_objectives or []
        if len(covered) >= len(section.learning_objectives):
            # All objectives covered, move to refinement
            return refine_section_lecture(state)
        
        # Otherwise, continue with next objective
        next_obj_index = None
        for i in range(len(section.learning_objectives)):
            if i not in covered:
                next_obj_index = i
                break
        
        if next_obj_index is not None:
            objective_text = section.learning_objectives[next_obj_index]
            embed_text = f"{section.title}. {objective_text}"
            
            return LogicResult(
                new_state=state,
                commands=[EmbedCommand(text=embed_text, task="retrieve_for_objective")],
                ui_message=f"Preparing objective {next_obj_index + 1}/{len(section.learning_objectives)}...",
            )
    
    elif phase == "refining":
        # We're refining the lecture
        if "llm_response" in course_results:
            llm_response = course_results["llm_response"]
            task = course_results.get("task", "")
            
            if task == "refine_section_lecture":
                return handle_lecture_refined(state, llm_response)
    
    # Check if all objectives are covered but we're still in objectives phase
    # This can happen after the last objective completes - transition to refining
    if phase == "objectives":
        covered = state.covered_objectives or []
        section = state.current_section
        if section and len(covered) >= len(section.learning_objectives):
            # All objectives complete but still in objectives phase - transition to refining
            logger.debug("process_generation_step: All objectives covered but still in objectives phase, transitioning to refining")
            return refine_section_lecture(state)
    
    # Check if generation is complete (after StoreLectureCommand executed)
    if state.section_generation_phase == "complete":
        # Check for audio generation results
        if "audio_generated" in course_results:
            return handle_audio_generated(state, course_results)
        
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="Lecture generation complete.",
        )
    
    # Default: no more commands
    return LogicResult(
        new_state=state,
        commands=[],
        ui_message="Generation step complete, but no next step determined.",
    )

