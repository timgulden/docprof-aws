"""
Pure chunking logic functions.
Extracted from MAExpert for AWS-native ingestion pipeline.
"""

import re
import hashlib
import math
from typing import Dict, List, Any, Optional

# Chapter detection pattern
CHAPTER_PATTERN = re.compile(
    r"\[PAGE (?P<page>\d+)\](?:\n[^\n]*){0,3}\n(?:(?:Chapter\s+|CHAPTER\s+)(?P<number>\d{1,2})|(?P<number_alt>[1-9]|1[0-9]|20)(?!\n\s*(?:Chapter|CHAPTER)))\n(?P<title>[A-Z][^\n]{7,}(?:\s|$))",
)

PAGE_MARKER_PATTERN = re.compile(r"\[PAGE (\d+)\]")


def build_page_chunks(
    full_text: str,
    pages: List[str],
    overlap_percentage: float = 0.20
) -> List[Dict[str, Any]]:
    """
    Build page chunks with percentage-based overlap.
    
    Each chunk is centered on a page N and includes:
    - Last X% of page N-1
    - Full page N (the center page)
    - First X% of page N+1
    
    Where X = overlap_percentage (default 20%).
    
    Args:
        full_text: Full text with [PAGE X] markers
        pages: List of page texts
        overlap_percentage: Percentage of adjacent pages to include (0.0-1.0)
    
    Returns:
        List of chunk dictionaries
    """
    page_markers = list(PAGE_MARKER_PATTERN.finditer(full_text))
    page_positions = [match.start() for match in page_markers]
    page_ids = [int(match.group(1)) for match in page_markers]

    chunks: List[Dict[str, Any]] = []
    
    # Build one chunk per page (centered on that page)
    for i, center_page_id in enumerate(page_ids):
        # Get the boundaries for the center page
        center_start = page_positions[i]
        center_end = page_positions[i + 1] if i + 1 < len(page_positions) else len(full_text)
        center_page_text = full_text[center_start:center_end]
        
        chunk_parts = []
        
        # Add overlap from previous page (last X%)
        if i > 0:
            prev_start = page_positions[i - 1]
            prev_end = page_positions[i]
            prev_page_text = full_text[prev_start:prev_end]
            
            # Calculate starting position for last X% of previous page
            prev_page_len = len(prev_page_text)
            overlap_start = int(prev_page_len * (1.0 - overlap_percentage))
            
            chunk_parts.append(prev_page_text[overlap_start:])
        
        # Add full center page
        chunk_parts.append(center_page_text)
        
        # Add overlap from next page (first X%)
        if i + 1 < len(page_positions):
            next_start = page_positions[i + 1]
            next_end = page_positions[i + 2] if i + 2 < len(page_positions) else len(full_text)
            next_page_text = full_text[next_start:next_end]
            
            # Calculate ending position for first X% of next page
            next_page_len = len(next_page_text)
            overlap_end = int(next_page_len * overlap_percentage)
            
            chunk_parts.append(next_page_text[:overlap_end])
        
        # Combine all parts
        chunk_text = "".join(chunk_parts)
        
        chunks.append({
            "chunk_type": "2page",
            "content": chunk_text,
            "page_start": center_page_id,
            "page_end": center_page_id,  # Same as start - this is a center-page chunk
        })
    
    return chunks


def build_chapter_chunks_simple(
    full_text: str
) -> List[Dict[str, Any]]:
    """
    Build chapter chunks using simple regex pattern matching.
    
    This is a simplified version that doesn't require LLM classification.
    For a full implementation, we could add TOC parsing and LLM classification later.
    
    Args:
        full_text: Full text with [PAGE X] markers
    
    Returns:
        List of chapter chunk dictionaries
    """
    matches = list(CHAPTER_PATTERN.finditer(full_text))
    
    chapter_chunks: List[Dict[str, Any]] = []
    
    for index, match in enumerate(matches):
        chapter_number = int(match.group("number") or match.group("number_alt"))
        start_pos = match.start()
        
        # Find next match for end position
        next_match = matches[index + 1] if index + 1 < len(matches) else None
        end_pos = next_match.start() if next_match else len(full_text)
        
        chapter_text = full_text[start_pos:end_pos]
        
        # Infer page end from last page marker in chapter
        page_matches = PAGE_MARKER_PATTERN.findall(chapter_text)
        page_end = int(page_matches[-1]) if page_matches else int(match.group("page"))
        
        chapter_chunks.append({
            "chunk_type": "chapter",
            "content": chapter_text,
            "chapter_number": chapter_number,
            "chapter_title": match.group("title").strip(),
            "page_start": int(match.group("page")),
            "page_end": page_end,
        })
    
    return chapter_chunks


def attach_content_hash(chunk: Dict[str, Any]) -> str:
    """
    Attach content hash to chunk metadata.
    
    Args:
        chunk: Chunk dictionary
    
    Returns:
        Content hash string
    """
    metadata = dict(chunk.get("metadata") or {})
    content_hash = hashlib.sha256(chunk["content"].encode("utf-8")).hexdigest()
    metadata["content_hash"] = content_hash
    chunk["metadata"] = metadata
    return content_hash


def split_chunk_if_needed(
    chunk: Dict[str, Any],
    max_chars: int = 12000
) -> List[Dict[str, Any]]:
    """
    Split chunk if it exceeds embedding character limit.
    
    Args:
        chunk: Chunk dictionary
        max_chars: Maximum characters per chunk
    
    Returns:
        List of chunk dictionaries (may be single chunk if no split needed)
    """
    content = chunk.get("content", "")
    if len(content) <= max_chars:
        return [chunk]

    total_segments = math.ceil(len(content) / max_chars)
    
    segments: List[Dict[str, Any]] = []
    for segment_index, start in enumerate(range(0, len(content), max_chars), start=1):
        segment = content[start : start + max_chars]
        segment_chunk = dict(chunk)
        segment_chunk["content"] = segment
        metadata = dict(segment_chunk.get("metadata") or {})
        metadata.update({
            "segment_index": segment_index,
            "segment_total": total_segments,
            "segment_offset": start,
        })
        segment_chunk["metadata"] = metadata
        segments.append(segment_chunk)
    
    return segments


def build_figure_chunk(
    figure: Dict[str, Any],
    description: str,
    *,
    key_takeaways: Optional[List[str]] = None,
    use_cases: Optional[List[str]] = None,
    description_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build a figure chunk from figure data and description.
    
    Args:
        figure: Figure dictionary with figure_id, page_number, etc.
        description: Figure description text
        key_takeaways: Optional list of key takeaways
        use_cases: Optional list of use cases
        description_metadata: Optional metadata from description
    
    Returns:
        Figure chunk dictionary
    """
    figure_id = figure.get("figure_id")
    if not figure_id:
        raise ValueError(
            f"build_figure_chunk requires figure_id to be set in figure dict. "
            f"Figure page_number: {figure.get('page_number')}, "
            f"caption: {figure.get('caption')}"
        )
    
    figure_metadata = figure.get("metadata")
    metadata = dict(figure_metadata) if isinstance(figure_metadata, dict) else {}
    if description_metadata:
        metadata.update(description_metadata)

    content_parts = [description.strip()]
    if key_takeaways:
        content_parts.append("Key Takeaways:")
        content_parts.extend(f"- {item.strip()}" for item in key_takeaways if item.strip())
    if use_cases:
        content_parts.append("Use Cases:")
        content_parts.extend(f"- {item.strip()}" for item in use_cases if item.strip())
    content_text = "\n".join(part for part in content_parts if part)

    return {
        "chunk_type": "figure",
        "content": content_text,
        "figure_id": figure_id,
        "figure_caption": figure.get("caption"),
        "figure_type": figure.get("figure_type"),
        "context_text": figure.get("context_text"),
        "chapter_number": figure.get("chapter_number"),
        "chapter_title": figure.get("chapter_title"),
        "page_start": figure["page_number"],
        "page_end": figure["page_number"],
        "metadata": metadata,
    }

