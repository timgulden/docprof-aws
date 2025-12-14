"""
Chat handler Lambda - processes chat messages using RAG pipeline.
Adapts MAExpert chat logic to AWS Lambda + Bedrock.

Follows FP mapping strategy:
- Imports MAExpert logic directly (pure functions) - preserves all tuned logic
- Adapts effects to AWS services (Bedrock, Aurora, DynamoDB)
- Thin handler wrapper around logic layer

MAExpert Integration:
- MAExpert source code MUST be included in Lambda layer at python/lib/python3.11/site-packages/src/
- Uses adapters to convert between DynamoDB dicts and MAExpert Pydantic models
- Fails fast if MAExpert not available - no fallbacks
- Lambda layer build process copies MAExpert/src/ into the layer

Key MAExpert functions used:
- expand_query_for_retrieval() - Carefully tuned query expansion with figure keywords, bigrams, etc.
- build_synthesis_prompt() - Uses centralized prompt system with citation instructions
- get_prompt("chat.system") - System prompt with citation and quoting rules
"""

import json
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from uuid import uuid4

# Import shared utilities
# Lambda layer includes shared/ at the root, so we can import directly
from shared.session_manager import get_session, create_session, update_session
from shared.bedrock_client import invoke_claude, generate_embeddings
from shared.db_utils import vector_similarity_search, get_db_connection
from shared.response import success_response, error_response
from shared.book_filter import get_selected_book_ids, update_selected_book_ids
from shared.model_adapters import (
    dict_to_chat_state,
    chat_state_to_dict,
    dict_to_chat_message,
    chat_message_to_dict,
    get_expand_query,
    get_build_prompt,
    get_system_prompt
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for chat messages.
    
    Request format (API Gateway proxy):
    {
        "body": "{\"message\": \"What is DCF?\", \"session_id\": \"...\"}",
        "headers": {...}
    }
    
    Response format:
    {
        "statusCode": 200,
        "body": "{\"session_id\": \"...\", \"messages\": [...]}"
    }
    """
    try:
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        message = body.get('message')
        session_id = body.get('session_id')
        with_audio = body.get('with_audio', False)
        request_book_ids = body.get('book_ids')  # Optional filter by book IDs from request
        
        if not message:
            return error_response("Missing required field: message", 400)
        
        # Get or create session
        if session_id:
            session = get_session(session_id)
            if not session:
                return error_response(f"Session not found: {session_id}", 404)
        else:
            session = create_session()
            session_id = session['session_id']
        
        # Handle book_ids: update session if provided in request, otherwise use session's stored selection
        if request_book_ids is not None:
            # Request explicitly provides book_ids - update session to persist this selection
            session = update_selected_book_ids(session, request_book_ids)
            update_session(session)  # Persist to DynamoDB
        
        # Get selected book_ids (from request if provided, otherwise from session)
        search_book_ids = get_selected_book_ids(session, request_book_ids)
        
        # Convert session dict to MAExpert ChatState (preserves all tuned logic)
        chat_state = dict_to_chat_state(session)
        conversation_history = chat_state.messages
        
        # Perform RAG retrieval and synthesis
        # Step 1: Expand query using logic (preserves all tuning)
        expand_query_fn = get_expand_query()
        expanded_query = expand_query_fn(
            message,
            session_context=chat_state.session_context,
            conversation_history=conversation_history
        )
        
        # Step 2: Generate embedding for search
        # IMPORTANT: Use same embedding service as ingestion (Bedrock Titan, normalized)
        # This ensures query embeddings are compatible with stored chunk embeddings
        logger.info(f"Generating embedding for query: {expanded_query[:100]}...")
        logger.info("Using Bedrock Titan (amazon.titan-embed-text-v1) with normalization=True (same as ingestion)")
        embeddings = generate_embeddings([expanded_query], normalize=True)  # Explicitly normalize to match ingestion
        query_embedding = embeddings[0]
        logger.info(f"Query embedding generated: {len(query_embedding)} dimensions, normalized={True}")
        
        # Step 3: Vector search
        logger.info("Performing vector search...")
        chunk_types = ["2page"]  # Use 2-page chunks for better citation accuracy
        
        # Use selected book_ids (from session or request) to filter search
        # This matches MAExpert behavior: metadata_filters["book_id"] = book_ids
        # which gets normalized to book_ids and used with book_id = ANY(%s::uuid[])
        if search_book_ids:
            logger.info(f"Searching across {len(search_book_ids)} selected book(s): {search_book_ids[:3]}{'...' if len(search_book_ids) > 3 else ''}")
        else:
            logger.info("No book_ids selected, searching across all books")
        
        # Vector search strategy:
        # 1. Try with threshold to get high-quality results first
        # 2. If we don't get at least 10 results, lower threshold or remove it
        # 3. Always return top 10 hits (or as many as available)
        # 
        # Note: MAExpert used OpenAI embeddings (different model), so thresholds may differ.
        # For Titan embeddings, we'll be more permissive and ensure we get results.
        search_results = None
        target_limit = 10  # User wants at least top 10 hits
        
        # Start with moderate threshold, progressively lower if needed
        thresholds = [0.6, 0.5, 0.4, 0.3, 0.2, 0.0]  # 0.0 = no threshold, just top K
        
        for threshold in thresholds:
            logger.info(f"Trying vector search with threshold={threshold}, limit={target_limit}")
            search_results = vector_similarity_search(
                query_embedding=query_embedding,
                chunk_types=chunk_types,
                book_ids=search_book_ids,  # Pass all selected book_ids (or None for all books)
                limit=target_limit,
                similarity_threshold=threshold if threshold > 0 else None  # None = no threshold filter
            )
            
            if search_results and len(search_results) >= target_limit:
                logger.info(f"Found {len(search_results)} results with threshold={threshold}")
                break
            elif search_results:
                logger.info(f"Found {len(search_results)} results with threshold={threshold} (less than target {target_limit})")
                # Continue to try lower thresholds to get more results
                if len(search_results) >= 5:  # If we have at least 5, might be good enough
                    break
        
        if not search_results:
            logger.warning(f"No chunks found for query after trying all thresholds")
            logger.warning(f"Query: {expanded_query[:200]}")
            logger.warning(f"Query embedding dimensions: {len(query_embedding)}")
            logger.warning(f"Chunk types: {chunk_types}, Book IDs filter: {search_book_ids or 'all books'}")
            assistant_message = {
                'id': str(uuid4()),
                'role': 'assistant',
                'content': "I apologize, but I couldn't find relevant information in the textbook to answer your question. Could you try rephrasing it?",
                'timestamp': datetime.utcnow().isoformat(),
                'sources': []
            }
        else:
            # Step 4: Build synthesis prompt using logic (preserves all tuning)
            chunks = _format_chunks_for_prompt(search_results)
            build_prompt_fn = get_build_prompt()
            # Use logic function - expects ChatMessage objects
            history_for_prompt = conversation_history[-5:] if len(conversation_history) >= 5 else conversation_history
            prompt = build_prompt_fn(
                user_message=message,
                conversation_history=history_for_prompt,
                chunks=chunks,
                session_context=chat_state.session_context
            )
            
            # Step 5: Call Claude for synthesis
            logger.info("Calling Claude for synthesis...")
            system_prompt = get_system_prompt()
            
            llm_response = invoke_claude(
                messages=[{"role": "user", "content": prompt}],
                system=system_prompt,
                max_tokens=8000,
                temperature=0.3,
                stream=False
            )
            
            synthesized_text = llm_response['content']
            
            # Step 6: Build source citations
            source_citations = _build_source_citations(search_results)
            
            assistant_message = {
                'id': str(uuid4()),
                'role': 'assistant',
                'content': synthesized_text,
                'timestamp': datetime.utcnow().isoformat(),
                'sources': source_citations
            }
        
        # Step 7: Update session with new messages
        # Convert assistant_message dict back to ChatMessage for state update
        # Use ChatState for proper state management (immutable updates)
        user_msg = dict_to_chat_message({
            'id': str(uuid4()),
            'role': 'user',
            'content': message,
            'timestamp': datetime.utcnow().isoformat()
        })
        assistant_msg = dict_to_chat_message(assistant_message)
        
        # Update ChatState immutably
        new_messages = [*chat_state.messages, user_msg, assistant_msg]
        updated_state = chat_state.model_copy(update={
            'messages': new_messages,
            'updated_at': datetime.utcnow()
        })
        
        # Convert back to dict for DynamoDB
        session = chat_state_to_dict(updated_state)
        update_session(session)
        
        # Step 8: Format response
        response_payload = {
            'session_id': session_id,
            'messages': [{
                'message_id': assistant_message['id'],
                'content': assistant_message['content'],
                'timestamp': assistant_message['timestamp'],
                'sources': assistant_message['sources']
            }]
        }
        
        return success_response(response_payload)
        
    except Exception as e:
        logger.exception("Error processing chat message")
        return error_response(f"Failed to process message: {str(e)}", 500)


def _expand_query_for_retrieval(
    query: str,
    session_context: Optional[str] = None,
    conversation_history: Optional[list] = None
) -> str:
    """
    DEPRECATED: This function should not be used.
    Logic is required and included in shared/logic/.
    This function exists only for reference/comparison.
    """
    raise RuntimeError("Logic is required - this fallback should never be called")
    # Include conversation history
    query_with_history = query
    if conversation_history and len(conversation_history) >= 2:
        last_messages = conversation_history[-2:]
        # Handle both dict and ChatMessage objects
        context_parts = []
        for msg in last_messages:
            if isinstance(msg, dict):
                context_parts.append(msg.get('content', ''))
            elif hasattr(msg, 'content'):
                context_parts.append(msg.content)
            else:
                context_parts.append(str(msg))
        if context_parts:
            conversation_context = " ".join(context_parts)
            query_with_history = f"{query} {conversation_context}"
    
    # Simple normalization
    normalized = query_with_history.lower()
    variations = {
        "discounted cash flow": "DCF",
        "return on invested capital": "ROIC",
        "earnings before interest and taxes": "EBIT",
        "earnings before interest taxes depreciation amortization": "EBITDA",
    }
    for variant, standard in variations.items():
        normalized = normalized.replace(variant, standard)
    
    return normalized


def _format_chunks_for_prompt(chunks: list) -> list:
    """Format chunks for LLM prompt."""
    formatted = []
    for chunk in chunks:
        formatted.append({
            'chunk_type': chunk.get('chunk_type', '2page'),
            'chapter_title': chunk.get('chapter_title'),
            'chapter_number': chunk.get('chapter_number'),
            'page_start': chunk.get('page_start'),
            'page_end': chunk.get('page_end'),
            'content': chunk.get('content', '')[:8000]  # Truncate for context
        })
    return formatted


def _build_synthesis_prompt(
    user_message: str,
    conversation_history: list,
    chunks: list,
    session_context: Optional[str] = None
) -> str:
    """
    DEPRECATED: This function should not be used.
    Logic is required and included in shared/logic/.
    This function exists only for reference/comparison.
    """
    raise RuntimeError("Logic is required - this fallback should never be called")
    # Format conversation history
    history_text = ""
    if conversation_history:
        for msg in conversation_history:
            if isinstance(msg, dict):
                role = msg.get('role', 'user')
                content = msg.get('content', '')
            elif hasattr(msg, 'role') and hasattr(msg, 'content'):
                role = msg.role
                content = msg.content
            else:
                role = 'user'
                content = str(msg)
            history_text += f"{role.capitalize()}: {content}\n\n"
    
    # Format chunks
    chunks_text = ""
    for i, chunk in enumerate(chunks, 1):
        chunk_type = chunk.get('chunk_type', '2page')
        chapter = chunk.get('chapter_title', 'Unknown Chapter')
        pages = f"pages {chunk.get('page_start')}-{chunk.get('page_end')}" if chunk.get('page_start') else ""
        content = chunk.get('content', '')
        chunks_text += f"[{i}] {chunk_type} chunk from {chapter} ({pages}):\n{content}\n\n"
    
    prompt = f"""You are an expert tutor helping a student learn about valuation and investment banking.

Use the following textbook excerpts to answer the student's question. Cite specific sources using [1], [2], etc.

Previous conversation:
{history_text}

Textbook excerpts:
{chunks_text}

Student's question: {user_message}

Provide a clear, educational answer citing the relevant sources."""
    
    return prompt


def _build_source_citations(chunks: list) -> list:
    """Build source citations from search results."""
    citations = []
    
    # Get book titles (cache to avoid repeated queries)
    book_title_cache = {}
    
    for i, chunk in enumerate(chunks, 1):
        book_id = chunk.get('book_id')
        if book_id and book_id not in book_title_cache:
            # Query database for book title
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT title FROM books WHERE book_id = %s", (book_id,))
                        result = cur.fetchone()
                        if result:
                            book_title_cache[book_id] = result[0]
                        else:
                            book_title_cache[book_id] = "Unknown Book"
            except Exception as e:
                logger.warning(f"Failed to get book title for {book_id}: {e}")
                book_title_cache[book_id] = "Unknown Book"
        
        citation = {
            'citation_id': f"[{i}]",
            'chunk_id': chunk.get('chunk_id', ''),
            'chunk_type': chunk.get('chunk_type', '2page'),
            'book_id': book_id or '',
            'book_title': book_title_cache.get(book_id, 'Unknown Book'),
            'chapter_number': chunk.get('chapter_number'),
            'chapter_title': chunk.get('chapter_title'),
            'page_start': chunk.get('page_start'),
            'page_end': chunk.get('page_end'),
            'target_page': chunk.get('page_start'),  # Use page_start as target
            'content': chunk.get('content', '')[:1000],  # Excerpt
            'score': chunk.get('similarity')
        }
        citations.append(citation)
    
    return citations
