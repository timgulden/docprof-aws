from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import logging

logger = logging.getLogger(__name__)

from shared.core.chat_models import (
    AssistantMessagePayload,
    BackendFailed,
    BackendMessageReceived,
    BackendChatPayload,
    ChatEventType,
    ChatMessage,
    ChatState,
    ChatStateSnapshot,
    ResetRequested,
    SessionRestored,
    UserSubmittedMessage,
    FigureAttachment,
)
from shared.core.commands import (
    EmbedCommand,
    GetBookTitlesCommand,
    LLMCommand,
    PersistChatStateCommand,
    SearchCorpusCommand,
    SendChatMessageCommand,
    ShowErrorToastCommand,
    TrackUsageMetricCommand,
)
from shared.core.state import LogicResult
from shared.core.prompts import get_prompt


def create_initial_chat_state() -> ChatState:
    """Return the canonical empty chat state."""

    return ChatState()


def reduce_chat_event(state: ChatState, event: ChatEventType) -> LogicResult:
    """Main reducer that routes incoming events to pure handlers."""

    if isinstance(event, UserSubmittedMessage):
        return process_user_message(state, event)

    if isinstance(event, BackendMessageReceived):
        return process_backend_success(state, event)

    if isinstance(event, BackendFailed):
        return process_backend_failure(state, event)

    if isinstance(event, SessionRestored):
        return rehydrate_chat_state(state, event)

    if isinstance(event, ResetRequested):
        return reset_chat_state(state)

    raise ValueError(f"Unhandled chat event: {event}")


def process_user_message(state: ChatState, event: UserSubmittedMessage) -> LogicResult:
    """Handle a user-submitted message by appending and issuing send command."""

    user_message = ChatMessage(role="user", content=event.text)
    new_messages = [*state.messages, user_message]

    new_state = state.model_copy(
        update={
            "messages": new_messages,
            "status": "awaiting_response",
            "error": None,
            "ui_message": None,
        }
    )

    payload = BackendChatPayload(
        message=event.text,
        with_audio=event.with_audio,
        session_id=state.session_id,
    )

    commands = [
        SendChatMessageCommand(payload=payload),
        TrackUsageMetricCommand(
            metric="chat.user_message_submitted",
            data={"message_id": user_message.id},
        ),
    ]

    return LogicResult(new_state=new_state, commands=commands)


def process_backend_success(state: ChatState, event: BackendMessageReceived) -> LogicResult:
    """Apply assistant response payloads and prepare persistence command."""

    assistant_messages: List[ChatMessage] = [
        _payload_to_chat_message(payload) for payload in event.messages
    ]
    new_messages = [*state.messages, *assistant_messages]

    new_state = state.model_copy(
        update={
            "session_id": event.session_id or state.session_id,
            "messages": new_messages,
            "status": "idle",
            "error": None,
            "ui_message": event.ui_message,
        }
    )

    commands = [
        PersistChatStateCommand(snapshot=ChatStateSnapshot.from_state(new_state)),
        TrackUsageMetricCommand(
            metric="chat.assistant_message_received",
            data={"count": len(assistant_messages)},
        ),
    ]

    return LogicResult(
        new_state=new_state,
        commands=commands,
        ui_message=event.ui_message,
    )


def process_backend_failure(state: ChatState, event: BackendFailed) -> LogicResult:
    """Record backend failure and emit UI-facing error command."""

    new_state = state.model_copy(
        update={
            "status": "idle",
            "error": event.error,
            "ui_message": None,
        }
    )

    commands = [
        ShowErrorToastCommand(message=event.error.message, error_code=event.error.code),
        TrackUsageMetricCommand(
            metric="chat.backend_error",
            data={"code": event.error.code, "retryable": event.error.retryable},
        ),
    ]

    return LogicResult(new_state=new_state, commands=commands, ui_message=event.error.message)


def rehydrate_chat_state(state: ChatState, event: SessionRestored) -> LogicResult:
    """Replace state from persisted snapshot."""

    snapshot = event.snapshot

    new_state = state.model_copy(
        update={
            "session_id": snapshot.session_id,
            "messages": [message.model_copy(deep=True) for message in snapshot.messages],
            "status": "idle",
            "error": None,
            "ui_message": None,
        }
    )

    return LogicResult(new_state=new_state)


def reset_chat_state(state: ChatState) -> LogicResult:
    """Clear conversation and session metadata."""

    new_state = ChatState()

    commands = [
        TrackUsageMetricCommand(metric="chat.session_reset", data={"previous_session_id": state.session_id})
    ]

    return LogicResult(new_state=new_state, commands=commands)


def _payload_to_chat_message(payload: AssistantMessagePayload) -> ChatMessage:
    """Convert assistant payload into canonical chat message."""

    figures = [
        _copy_figure_attachment(figure)
        for figure in payload.figures
    ]
    return ChatMessage(
        id=payload.message_id or str(uuid4()),
        role="assistant",
        content=payload.content,
        figures=figures,
        audio_url=payload.audio_url,
        timestamp=payload.timestamp,
        sources=payload.sources,
        citation_spans=payload.citation_spans,
        general_spans=payload.general_spans,
    )


def _copy_figure_attachment(figure: FigureAttachment) -> FigureAttachment:
    """Create a deep copy of a figure attachment."""

    return figure.model_copy(deep=True)


# Pure business logic functions moved from API routes

def expand_query_for_retrieval(
    query: str, 
    session_context: Optional[str] = None,
    conversation_history: Optional[List[ChatMessage]] = None,
) -> str:
    """Expand and normalize query for better retrieval.
    
    Pure function: No side effects.
    Handles common variations and extracts key terms from conversational queries.
    Uses session context (e.g., lecture figures) to help reformulate queries about figures.
    Uses conversation history to include context in the query for better retrieval.
    
    Args:
        query: The user's query
        session_context: Optional session context (e.g., lecture figures)
        conversation_history: Optional conversation history to include context
    """
    # Include conversation history in query for better retrieval
    # This ensures the embedding captures context from previous questions/answers
    # Simple approach: append last Q&A pair directly to query text (as it was before)
    query_with_history = query
    
    if conversation_history and len(conversation_history) >= 2:
        # Get last Q&A pair (last user message + last assistant message)
        # This is the immediate context that helps with follow-up questions
        last_messages = conversation_history[-2:]
        
        # Build simple context string - just append Q&A content directly
        context_parts = [msg.content for msg in last_messages]
        
        # Append conversation context to query (simple concatenation)
        if context_parts:
            conversation_context = " ".join(context_parts)
            query_with_history = f"{query} {conversation_context}"
            logger.debug(f"Included last Q&A pair in query for better retrieval")
    
    # Normalize common term variations
    normalized = query_with_history.lower()
    
    # Fix common variations
    variations = {
        "good will": "goodwill",
        "good-will": "goodwill",
        "discounted cash flow": "DCF",
        "return on invested capital": "ROIC",
        "return on investment": "ROI",
        "earnings before interest and taxes": "EBIT",
        "earnings before interest taxes depreciation amortization": "EBITDA",
    }
    
    for variant, standard in variations.items():
        normalized = normalized.replace(variant, standard)
    
    # Extract figure information from session context if available
    figure_keywords = []
    if session_context:
        # Look for figure descriptions in the context
        # Pattern to match figure sections in lecture context (handles indentation)
        figure_section_match = re.search(r'=== FIGURES SHOWN IN LECTURE ===(.*?)(?=\n===|\Z)', session_context, re.DOTALL | re.IGNORECASE)
        if figure_section_match:
            figure_section = figure_section_match.group(1)
            # Extract captions (handles "Figure X: Caption" format)
            caption_matches = re.findall(r'Figure \d+: ([^\n]+)', figure_section)
            # Extract descriptions (handles "  - Description: ..." format with optional indentation)
            desc_matches = re.findall(r'[- ]*Description: ([^\n]+)', figure_section)
            # Extract explanations (handles "  - Explanation: ..." format)
            explanation_matches = re.findall(r'[- ]*Explanation: ([^\n]+)', figure_section)
            
            # If query mentions "figure" or "chart" or "diagram", add figure keywords
            # Also check for queries about "this figure", "the figure", "how does this relate", etc.
            figure_related_terms = ["figure", "chart", "diagram", "exhibit", "table", "this", "the", "relate", "relates", "relating"]
            if any(word in normalized for word in figure_related_terms):
                # Add captions (often contain key terms)
                figure_keywords.extend(caption_matches)
                # Add first 50 chars of descriptions (to avoid too much text)
                figure_keywords.extend([desc[:50] for desc in desc_matches if desc])
                # Add first 50 chars of explanations
                figure_keywords.extend([expl[:50] for expl in explanation_matches if expl])
    
    # For conversational queries, extract key terms
    # If query is very long and conversational, try to extract key concepts
    words = normalized.split()
    if len(words) > 10:
        # Look for key phrases that might be in the book
        key_terms = []
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            # Common valuation/finance terms
            if any(term in bigram for term in ["valuation", "value", "cash flow", "discount", 
                                               "return", "capital", "equity", "debt", "acquisition",
                                               "merger", "goodwill", "intangible", "asset", "liability"]):
                key_terms.append(bigram)
        
        if key_terms:
            # Combine original with key terms for better matching
            expanded = f"{normalized} {' '.join(key_terms[:3])}"
            if figure_keywords:
                # Add figure keywords to help find relevant content
                expanded += f" {' '.join(figure_keywords[:3])}"
            return expanded
    
    # If we have figure keywords but query wasn't long, still add them
    if figure_keywords:
        expanded = f"{normalized} {' '.join(figure_keywords[:3])}"
        return expanded
    
    return normalized


def build_synthesis_prompt(
    user_message: str,
    conversation_history: list[ChatMessage],
    chunks: list[dict],
    session_context: Optional[str] = None,
) -> str:
    """Build the prompt for LLM synthesis.
    
    Pure function: No side effects.
    Formats conversation history, retrieved chunks, and session context into a synthesis prompt.
    """
    # Include session context if present (guides conversation direction)
    context_section = ""
    if session_context:
        context_section = f"""Session Context and Goals:
{session_context}

Use this context to guide your responses. Stay focused on the current topic while maintaining natural conversation flow.

"""

    # Add recent conversation history (last 5 messages)
    history_text = ""
    if conversation_history:
        recent = conversation_history[-5:]
        for msg in recent:
            role = "User" if msg.role == "user" else "Assistant"
            history_text += f"{role}: {msg.content}\n"
        history_text += "\n"

    # Format retrieved chunks with citation numbers
    chunks_text = ""
    for i, chunk in enumerate(chunks, start=1):
        chunk_type = chunk.get("chunk_type", "unknown")
        chapter = chunk.get("chapter_title") or f"Chapter {chunk.get('chapter_number', '?')}"
        content = chunk.get("content", "")
        
        # For center-page indexed chunks, page_start = page_end = center page
        # Display as a single page number (the center page)
        page_start = chunk.get("page_start")
        page_end = chunk.get("page_end")
        
        if page_start == page_end:
            # Center-page chunk - display single page
            page_display = str(page_start) if page_start else "?"
        elif page_start and page_end:
            # Range (e.g., for chapter chunks)
            page_display = f"{page_start}-{page_end}"
        else:
            # Fallback
            page_display = str(page_start or chunk.get("page_number", "?"))
        
        chunks_text += f"\n[{i}] {chunk_type.upper()} - {chapter} (Page {page_display})\n{content}\n"
    
    # Get citation instructions from centralized prompts
    citation_instructions = get_prompt("chat.citation_instructions")
    chunks_text += citation_instructions

    # Build synthesis prompt using centralized template
    prompt = get_prompt(
        "chat.synthesis",
        variables={
            "context_section": context_section,
            "chunks_text": chunks_text,
            "history_text": history_text,
            "user_message": user_message,
        }
    )

    return prompt


# RAG Pipeline Logic Functions

def initiate_rag_flow(
    state: ChatState,
    context: Dict[str, Any],
) -> LogicResult:
    """Initiate RAG flow by reading metadata from context and issuing EmbedCommand.
    
    Pure function: No side effects.
    This is the entry point for RAG orchestration.
    
    The API route should create the initial context with rag_metadata containing:
    - original_query: User's message
    - conversation_history: Optional conversation history
    - session_context: Optional session context
    - book_ids: Optional list of book IDs
    
    Args:
        state: Current chat state
        context: Pipeline context (should contain rag_metadata)
    
    Returns:
        LogicResult with EmbedCommand to start the pipeline
    """
    rag_metadata = context.get("rag_metadata", {})
    user_message = rag_metadata.get("original_query", "")
    conversation_history = rag_metadata.get("conversation_history")
    session_context = rag_metadata.get("session_context")
    
    # Expand query for better retrieval
    expanded_query = expand_query_for_retrieval(
        user_message,
        session_context=session_context,
        conversation_history=conversation_history,
    )
    
    # Update metadata with expanded query
    rag_metadata["expanded_query"] = expanded_query
    context["rag_metadata"] = rag_metadata
    
    return LogicResult(
        new_state=state,
        commands=[
            EmbedCommand(text=expanded_query, task="rag_search"),
        ],
        ui_message="Searching for relevant content...",
    )


def handle_embedding_result(
    state: ChatState,
    context: Dict[str, Any],
) -> LogicResult:
    """Handle embedding result and issue SearchCorpusCommand.
    
    Pure function: No side effects.
    
    Args:
        state: Current chat state
        context: Pipeline context (contains rag_metadata and course_results with embedding)
    
    Returns:
        LogicResult with SearchCorpusCommand
    """
    rag_metadata = context.get("rag_metadata", {})
    book_ids = rag_metadata.get("book_ids")
    
    # Build metadata filters
    metadata_filters = {}
    if book_ids and len(book_ids) > 0:
        metadata_filters["book_id"] = book_ids
    
    return LogicResult(
        new_state=state,
        commands=[
            SearchCorpusCommand(
                query_text=rag_metadata.get("expanded_query", ""),
                chunk_types=["2page"],  # Only 2-page chunks for better citation accuracy
                top_k={"2page": 12},
                return_segments=False,
                include_scores=True,
                metadata_filters=metadata_filters,
            )
        ],
        ui_message="Retrieving relevant content...",
    )


def deduplicate_search_results(
    chapters: List[Any],
    two_page_chunks: List[Any],
) -> Tuple[List[Any], List[Any]]:
    """Deduplicate search results by chunk/chapter ID.
    
    Pure function: No side effects.
    
    Args:
        chapters: List of chapter results
        two_page_chunks: List of 2-page chunk results
    
    Returns:
        Tuple of (deduplicated_chapters, deduplicated_chunks)
    """
    unique_chapters = []
    seen_chapter_ids: set[str] = set()
    for chapter in chapters:
        chapter_id = getattr(chapter, "chapter_document_id", None)
        if chapter_id and chapter_id in seen_chapter_ids:
            continue
        if chapter_id:
            seen_chapter_ids.add(chapter_id)
        unique_chapters.append(chapter)
    
    unique_chunks = []
    seen_chunk_ids: set[str] = set()
    for chunk in two_page_chunks:
        chunk_id = getattr(chunk, "chunk_id", None)
        if chunk_id and chunk_id in seen_chunk_ids:
            continue
        if chunk_id:
            seen_chunk_ids.add(chunk_id)
        unique_chunks.append(chunk)
    
    return unique_chapters, unique_chunks


def build_citations_without_titles(
    chapters: List[Any],
    two_page_chunks: List[Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    """Build citation structures and chunks without book titles.
    
    Pure function: No side effects.
    Returns citations dicts (missing book_title field) and list of unique book_ids.
    
    Args:
        chapters: List of chapter results
        two_page_chunks: List of 2-page chunk results
    
    Returns:
        Tuple of (chunks_for_llm, citations_dicts, unique_book_ids)
    """
    import re
    
    chunks: List[Dict[str, Any]] = []
    citations: List[Dict[str, Any]] = []
    book_ids: set[str] = set()
    
    # Process chapters
    for i, chapter in enumerate(chapters, start=1):
        citation_id = f"[{i}]"
        book_ids.add(chapter.book_id)
        
        # Truncate content for context
        truncated_content = chapter.content[:10000]
        
        chunks.append({
            "chunk_type": "chapter",
            "chapter_title": chapter.chapter_title,
            "chapter_number": chapter.chapter_number,
            "page_start": chapter.metadata.get("page_start"),
            "content": truncated_content,
        })
        
        # Extract actual pages from truncated content
        page_markers = re.findall(r'\[PAGE (\d+)\]', truncated_content)
        page_start = chapter.metadata.get("page_start")
        target_page = int(page_markers[0]) if page_markers else page_start
        
        citations.append({
            "citation_id": citation_id,
            "chunk_id": chapter.chapter_document_id,
            "chunk_type": "chapter",
            "book_id": chapter.book_id,
            "book_title": None,  # Will be filled later
            "chapter_number": chapter.chapter_number,
            "chapter_title": chapter.chapter_title,
            "page_start": page_start,
            "target_page": target_page,
            "content": chapter.content[:1000],
            "score": chapter.score,
        })
    
    # Process 2-page chunks
    for i, chunk in enumerate(two_page_chunks, start=len(chapters) + 1):
        citation_id = f"[{i}]"
        book_ids.add(chunk.book_id)
        
        # Truncate content for context
        truncated_content = chunk.content[:8000]
        
        page_start = chunk.metadata.get("page_start")
        page_end = chunk.metadata.get("page_end")
        
        chunks.append({
            "chunk_type": "2page",
            "chapter_title": chunk.metadata.get("chapter_title"),
            "chapter_number": chunk.metadata.get("chapter_number"),
            "page_start": page_start,
            "page_end": page_end,
            "content": truncated_content,
        })
        
        target_page = page_start  # Center page for 2-page chunks
        
        citations.append({
            "citation_id": citation_id,
            "chunk_id": chunk.chunk_id,
            "chunk_type": "2page",
            "book_id": chunk.book_id,
            "book_title": None,  # Will be filled later
            "chapter_number": chunk.metadata.get("chapter_number"),
            "chapter_title": chunk.metadata.get("chapter_title"),
            "page_start": page_start,
            "page_end": page_end,
            "target_page": target_page,
            "content": chunk.content[:1000],
            "score": chunk.score,
        })
    
    return chunks, citations, list(book_ids)


def handle_search_result(
    state: ChatState,
    context: Dict[str, Any],
) -> LogicResult:
    """Handle search result: deduplicate, build citations, lookup book titles.
    
    Pure function: No side effects.
    
    Args:
        state: Current chat state
        context: Pipeline context (contains course_results with search_response)
    
    Returns:
        LogicResult with GetBookTitlesCommand
    """
    # Get search response from context
    search_response = context.get("course_results", {}).get("search_response")
    if not search_response:
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="Error: No search results in context",
        )
    
    # Deduplicate results
    unique_chapters, unique_chunks = deduplicate_search_results(
        search_response.chapters,
        search_response.two_page_chunks,
    )
    
    # Build citations without book titles
    chunks, citations_dicts, book_ids = build_citations_without_titles(
        unique_chapters,
        unique_chunks,
    )
    
    if not chunks:
        # No results - create assistant message with "no results" response
        # This should be treated as a normal response, not an error
        from uuid import uuid4
        from datetime import datetime
        
        no_results_message = ChatMessage(
            id=str(uuid4()),
            role="assistant",
            content="I apologize, but I couldn't find relevant information in the textbook to answer your question. Could you try rephrasing it?",
            timestamp=datetime.utcnow(),
            sources=[],
        )
        
        new_messages = [*state.messages, no_results_message]
        new_state = state.model_copy(
            update={
                "messages": new_messages,
                "status": "idle",
            }
        )
        
        return LogicResult(
            new_state=new_state,
            commands=[],
            ui_message=None,  # No UI message needed - it's a normal response
        )
    
    # Store chunks and citations in context for later use
    rag_metadata = context.get("rag_metadata", {})
    rag_metadata.update({
        "chunks": chunks,
        "citations_dicts": citations_dicts,
    })
    context["rag_metadata"] = rag_metadata
    
    # Issue command to lookup book titles
    return LogicResult(
        new_state=state,
        commands=[
            GetBookTitlesCommand(book_ids=book_ids),
        ],
        ui_message="Preparing response...",
    )


def handle_book_titles_result(
    state: ChatState,
    context: Dict[str, Any],
) -> LogicResult:
    """Handle book titles result: complete citations and issue LLMCommand.
    
    Pure function: No side effects.
    
    Args:
        state: Current chat state
        context: Pipeline context (contains rag_metadata and book_titles)
    
    Returns:
        LogicResult with LLMCommand for synthesis
    """
    from src.core.chat_models import SourceCitation
    
    rag_metadata = context.get("rag_metadata", {})
    citations_dicts = rag_metadata.get("citations_dicts", [])
    chunks = rag_metadata.get("chunks", [])
    book_titles = context.get("course_results", {}).get("book_titles", {})
    
    # Complete citations with book titles
    source_citations: List[SourceCitation] = []
    for citation_dict in citations_dicts:
        book_id = citation_dict["book_id"]
        book_title = book_titles.get(book_id, "Unknown Book")
        
        source_citations.append(SourceCitation(
            citation_id=citation_dict["citation_id"],
            chunk_id=citation_dict["chunk_id"],
            chunk_type=citation_dict["chunk_type"],
            book_id=book_id,
            book_title=book_title,
            chapter_number=citation_dict.get("chapter_number"),
            chapter_title=citation_dict.get("chapter_title"),
            page_start=citation_dict.get("page_start"),
            page_end=citation_dict.get("page_end"),
            target_page=citation_dict.get("target_page"),
            content=citation_dict["content"],
            score=citation_dict.get("score"),
        ))
    
    # Build synthesis prompt
    user_message = rag_metadata.get("original_query", "")
    conversation_history = rag_metadata.get("conversation_history", [])
    session_context = rag_metadata.get("session_context")
    
    prompt = build_synthesis_prompt(
        user_message,
        conversation_history,
        chunks,
        session_context,
    )
    
    # Store citations in context for final result
    rag_metadata["source_citations"] = source_citations
    context["rag_metadata"] = rag_metadata
    
    # Issue LLM command for synthesis
    return LogicResult(
        new_state=state,
        commands=[
            LLMCommand(
                prompt=prompt,
                task="rag_synthesis",
                temperature=0.3,
                max_tokens=8000,
            )
        ],
        ui_message="Generating response...",
    )


def handle_synthesis_result(
    state: ChatState,
    context: Dict[str, Any],
) -> LogicResult:
    """Handle LLM synthesis result: extract sources and create assistant message.
    
    Pure function: No side effects.
    
    Args:
        state: Current chat state
        context: Pipeline context (contains rag_metadata and course_results with llm_response)
    
    Returns:
        LogicResult with assistant message added to state
    """
    from uuid import uuid4
    from datetime import datetime
    
    rag_metadata = context.get("rag_metadata", {})
    source_citations = rag_metadata.get("source_citations", [])
    course_results = context.get("course_results", {})
    llm_response = course_results.get("llm_response", "")
    
    # Check for empty string or missing response
    if not llm_response or llm_response.strip() == "":
        # Log detailed context for debugging
        logger.error(
            f"No LLM response in context (empty or missing). "
            f"Context keys: {list(context.keys())}, "
            f"Course results keys: {list(course_results.keys())}, "
            f"Task: {course_results.get('task')}, "
            f"Has search_response: {'search_response' in course_results}, "
            f"Has book_titles: {'book_titles' in course_results}, "
            f"LLM response value: {repr(llm_response)}"
        )
        return LogicResult(
            new_state=state,
            commands=[],
            ui_message="Error: No LLM response in context. The pipeline may have stopped before synthesis completed.",
        )
    
    # Create assistant message
    assistant_message = ChatMessage(
        id=str(uuid4()),
        role="assistant",
        content=llm_response,
        timestamp=datetime.utcnow(),
        sources=source_citations,
    )
    
    # Add to state
    new_messages = [*state.messages, assistant_message]
    new_state = state.model_copy(
        update={
            "messages": new_messages,
            "status": "idle",
        }
    )
    
    return LogicResult(
        new_state=new_state,
        commands=[],
        ui_message=None,
    )

