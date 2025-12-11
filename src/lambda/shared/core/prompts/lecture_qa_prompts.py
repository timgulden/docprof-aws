"""
Prompts for lecture Q&A feature.

These prompts maintain the lecture persona and incorporate
rich context for high-quality answers.

Refactored to use centralized prompt system from base_prompts.py.
"""

from typing import List, Dict
from shared.core.prompts.prompt_registry import get_prompt


def get_question_enhancement_prompt(question: str, context: str) -> str:
    """
    Prompt to enhance vague questions with lecture context AND classify them.
    
    Takes questions like "Why?" or "What does that mean?" and
    restates them with specific references to lecture concepts
    for better RAG retrieval. Also classifies whether textbook
    retrieval is needed.
    
    Args:
        question: User's original question
        context: Full lecture context (course + delivered + remaining)
        
    Returns:
        Prompt string for LLM
    """
    return get_prompt(
        "lecture_qa.question_enhancement",
        variables={"context": context, "question": question},
    )


def _old_get_question_enhancement_prompt(question: str, context: str) -> str:
    """OLD VERSION - kept for reference during refactor, will be removed"""
    return f"""You are helping a student who paused during a lecture to ask a question.

{context}

IMPORTANT: You have access to BOTH what has been covered AND what's coming next in the lecture.
- Use "LECTURE DELIVERED SO FAR" for questions about past content
- Use "LECTURE STILL TO COME" for questions about future content

STUDENT'S QUESTION:
{question}

Your task has TWO parts:

1. CLASSIFY the question into one of these categories:
   - META: Question about the course/lecture itself (e.g., "What course is this?", "What topics are covered?", "What will we learn next?")
   - SIMPLE: Simple factual question that can be answered from lecture context alone (including future lecture content)
   - NEEDS_TEXTBOOK: Question that requires detailed textbook content beyond what's in the lecture

2. ENHANCE the question with lecture context to make it self-contained and specific.

Guidelines for enhancement:
- If the question is already clear and specific, you may return it unchanged or with minor improvements
- If the question is vague (like "why?", "what?", "what does that mean?"), add specific references to concepts from the lecture
- Include relevant terminology and context from the lecture
- Keep it as a question (don't answer it)
- Make it suitable for semantic search (clear, specific, complete)

Examples:
- Original: "What is the name of this course?"
  Classification: META
  Enhanced: "What is the name of this course?"

- Original: "What are we going to cover next?"
  Classification: META
  Enhanced: "What topics are covered in the remaining part of this lecture?"

- Original: "Why?"
  Classification: NEEDS_TEXTBOOK
  Enhanced: "In the context of DCF valuation, why is the discount rate calculated using WACC rather than just the cost of equity?"

- Original: "What does that mean?"
  Classification: NEEDS_TEXTBOOK
  Enhanced: "What does 'enterprise value' mean in the context of M&A transactions, and how is it different from equity value?"

- Original: "What did you just say about goodwill?"
  Classification: SIMPLE
  Enhanced: "What was just explained about goodwill in the context of M&A transactions?"

Respond in this exact format:
CLASSIFICATION: [META or SIMPLE or NEEDS_TEXTBOOK]
ENHANCED_QUESTION: [your enhanced question here]"""


def get_lecture_answer_prompt(
    enhanced_question: str,
    retrieved_chunks: List[Dict],
    lecture_context: str,
    presentation_style: str,
    classification: str = "NEEDS_TEXTBOOK"
) -> str:
    """
    Prompt to generate answer maintaining lecture persona.
    
    Uses centralized prompts from base_prompts.py with classification-specific variations.
    
    Args:
        enhanced_question: Question with added context
        retrieved_chunks: Relevant textbook passages from RAG (empty if RAG skipped)
        lecture_context: Full lecture context
        presentation_style: Persona to maintain
        classification: Question classification (META, SIMPLE, or NEEDS_TEXTBOOK)
        
    Returns:
        Prompt string for LLM
    """
    # Format retrieved chunks with citations (will be empty for META/SIMPLE)
    chunks_text = format_retrieved_chunks(retrieved_chunks)
    
    # Select appropriate prompt based on classification
    if classification == "META":
        prompt_name = "lecture_qa.answer_meta"
    elif classification == "SIMPLE":
        prompt_name = "lecture_qa.answer_simple"
    else:  # NEEDS_TEXTBOOK
        prompt_name = "lecture_qa.answer_textbook"
    
    return get_prompt(
        prompt_name,
        variables={
            "presentation_style": presentation_style,
            "lecture_context": lecture_context,
            "enhanced_question": enhanced_question,
            "chunks_text": chunks_text,
        },
    )


def format_retrieved_chunks(chunks: List[Dict]) -> str:
    """
    Format retrieved chunks with clear labels and citations.
    
    Args:
        chunks: List of retrieved chunk dictionaries
        
    Returns:
        Formatted string with all chunks
    """
    if not chunks:
        return "(No specific textbook passages retrieved)"
    
    formatted = []
    for i, chunk in enumerate(chunks, 1):
        formatted.append(f"--- Source {i} ---")
        formatted.append(f"Book: {chunk.get('book_title', 'Unknown')}")
        if chunk.get('page_number'):
            formatted.append(f"Page: {chunk['page_number']}")
        if chunk.get('section_title'):
            formatted.append(f"Section: {chunk['section_title']}")
        formatted.append(f"\nText:\n{chunk.get('text', '')}")
        formatted.append("")
    
    return "\n".join(formatted)

