"""
AWS-native ingestion pipeline orchestrator.
Replaces MAExpert's run_ingestion_pipeline with clean, AWS-native implementation.

This module is organized into small, focused functions following FP principles:
- Each function has a single responsibility
- Functions are pure where possible (no side effects)
- Effect functions are clearly separated
- Easy to test and maintain
- Uses async/await for parallel processing of embeddings and figure descriptions
"""

import logging
import hashlib
import asyncio
from typing import Dict, List, Any, Optional, Set

from .protocol_implementations import (
    AWSDatabaseClient,
    AWSPDFExtractor,
    AWSEmbeddingClient,
    AWSFigureDescriptionClient
)
from .logic.chunking import (
    build_page_chunks,
    build_chapter_chunks_simple,
    attach_content_hash,
    split_chunk_if_needed,
    build_figure_chunk
)
from .cover_extractor import extract_cover_from_pdf_bytes
from .db_utils import insert_chunks_batch, insert_figures_batch
from .bedrock_client import generate_embeddings, describe_figure

logger = logging.getLogger(__name__)


async def run_ingestion_pipeline(
    pdf_bytes: bytes,
    book_id: str,
    metadata: Dict[str, Any],
    *,
    skip_figures: bool = False,
    rebuild: bool = False
) -> Dict[str, Any]:
    """
    Main ingestion pipeline orchestrator.
    
    Coordinates all ingestion steps using smaller, focused functions.
    
    Args:
        pdf_bytes: PDF file as bytes
        book_id: Book UUID
        metadata: Book metadata (title, author, etc.)
        skip_figures: If True, skip figure extraction
        rebuild: If True, delete existing book data first
    
    Returns:
        Dictionary with ingestion results
    """
    database = AWSDatabaseClient()
    pdf_extractor = AWSPDFExtractor()
    embeddings_client = AWSEmbeddingClient()
    figure_client = AWSFigureDescriptionClient()
    
    # Step 1: Ensure book record exists
    book_id = _ensure_book_record(
        database=database,
        pdf_extractor=pdf_extractor,
        book_id=book_id,
        metadata=metadata,
        pdf_bytes=pdf_bytes,
        rebuild=rebuild
    )
    
    # Step 2: Extract and store cover
    _extract_and_store_cover(database, book_id, pdf_bytes)
    
    # Step 3: Extract text from PDF
    text_payload = _extract_text_from_pdf(pdf_extractor, database, book_id, pdf_bytes)
    full_text = text_payload['full_text']
    pages = text_payload['pages']
    
    # Step 4: Get existing hashes to avoid duplicates
    existing_chunk_hashes = database.get_existing_chunk_hashes(book_id)
    existing_figure_hashes = database.get_existing_figure_hashes(book_id)
    _log_existing_hashes(existing_chunk_hashes, existing_figure_hashes)
    
    # Step 5: Build chunks (pure logic)
    chapter_chunks, page_chunks = _build_text_chunks(full_text, pages)
    
    # Step 6: Store chapter documents and update chunk metadata
    _store_chapter_documents(database, book_id, chapter_chunks)
    
    # Step 7: Process and store text chunks with embeddings
    chunks_created = await _process_and_store_chunks(
        book_id=book_id,
        chunks=chapter_chunks + page_chunks,
        existing_hashes=existing_chunk_hashes,
        embeddings_client=embeddings_client,
        database=database
    )
    
    # Step 8: Extract and process figures (if not skipped)
    figures_created = 0
    if not skip_figures:
        figures_created = await _extract_and_store_figures(
            pdf_extractor=pdf_extractor,
            figure_client=figure_client,
            database=database,
            book_id=book_id,
            pdf_bytes=pdf_bytes,
            existing_hashes=existing_figure_hashes
        )
    
    logger.info(f"Ingestion complete: {chunks_created} chunks, {figures_created} figures")
    
    return {
        'book_id': book_id,
        'chunks_created': chunks_created,
        'figures_created': figures_created,
        'status': 'success'
    }


def _ensure_book_record(
    database: AWSDatabaseClient,
    pdf_extractor: AWSPDFExtractor,
    book_id: str,
    metadata: Dict[str, Any],
    pdf_bytes: bytes,
    rebuild: bool
) -> str:
    """Ensure book record exists, handling rebuild if needed.
    
    Logic:
    1. First check if book with given book_id exists (primary check)
    2. If not, try to find by metadata (title/author/isbn)
    3. If neither exists, create new book record using the provided book_id
    """
    # Step 1: Check if book with given book_id already exists
    existing_book = database.get_book_by_id(book_id)
    if existing_book:
        if rebuild:
            logger.info(f"Rebuild requested - clearing existing data for book {book_id}")
            database.delete_book_contents(book_id)
            return book_id
        else:
            logger.info(f"Book record exists with book_id {book_id} - using existing record")
            return book_id
    
    # Step 2: If no book with this book_id, check by metadata (in case book was created elsewhere)
    existing_book_id = database.find_book(metadata)
    if existing_book_id:
        if rebuild:
            logger.info(f"Rebuild requested - clearing existing data for book {existing_book_id}")
            database.delete_book_contents(existing_book_id)
            return existing_book_id
        else:
            logger.info(f"Found existing book by metadata with book_id {existing_book_id} - using existing record")
            return existing_book_id
    
    # Step 3: No existing book found - create new one using the provided book_id
    logger.info(f"Creating new book record with book_id {book_id}")
    text_payload = pdf_extractor.extract_text(pdf_bytes)
    page_count = text_payload.get('page_count', 0)
    
    # Insert book with the provided book_id directly
    from .db_utils import get_db_connection
    import json
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO books (book_id, title, author, edition, isbn, total_pages, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                RETURNING book_id
                """,
                (
                    book_id,
                    metadata.get('title', 'Unknown'),
                    metadata.get('author'),
                    metadata.get('edition'),
                    metadata.get('isbn'),
                    page_count,
                    json.dumps(metadata.get('extra', {})) if metadata.get('extra') else None
                )
            )
            new_book_id = str(cur.fetchone()[0])
            conn.commit()
    
    logger.info(f"Created book record {new_book_id}")
    return new_book_id


def _extract_and_store_cover(
    database: AWSDatabaseClient,
    book_id: str,
    pdf_bytes: bytes
) -> None:
    """Extract cover image from PDF and store in database."""
    try:
        logger.info("Extracting cover image from first page")
        cover_bytes, cover_format = extract_cover_from_pdf_bytes(pdf_bytes, target_width=400)
        database.update_book_cover(book_id, cover_bytes, cover_format)
        logger.info(f"Stored cover image ({len(cover_bytes):,} bytes, {cover_format})")
    except Exception as e:
        logger.warning(f"Failed to extract cover: {e}")


def _extract_text_from_pdf(
    pdf_extractor: AWSPDFExtractor,
    database: AWSDatabaseClient,
    book_id: str,
    pdf_bytes: bytes
) -> Dict[str, Any]:
    """Extract text from PDF and update book page count."""
    logger.info("Extracting text from PDF")
    text_payload = pdf_extractor.extract_text(pdf_bytes)
    page_count = text_payload.get('page_count', 0)
    
    if page_count:
        database.update_book_total_pages(book_id, page_count)
    
    return text_payload


def _log_existing_hashes(
    existing_chunk_hashes: Set[str],
    existing_figure_hashes: Set[str]
) -> None:
    """Log information about existing hashes."""
    if existing_chunk_hashes:
        logger.info(f"Found {len(existing_chunk_hashes)} existing chunk hashes - will skip duplicates")
    if existing_figure_hashes:
        logger.info(f"Found {len(existing_figure_hashes)} existing figure hashes - will skip duplicates")


def _build_text_chunks(
    full_text: str,
    pages: List[str]
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Build chapter and page chunks using pure logic functions."""
    logger.info("Building text chunks")
    chapter_chunks = build_chapter_chunks_simple(full_text)
    page_chunks = build_page_chunks(full_text, pages, overlap_percentage=0.20)
    
    logger.info(f"Built {len(chapter_chunks)} chapter chunks and {len(page_chunks)} page chunks")
    return chapter_chunks, page_chunks


def _store_chapter_documents(
    database: AWSDatabaseClient,
    book_id: str,
    chapter_chunks: List[Dict[str, Any]]
) -> None:
    """Store chapter documents and update chunk metadata with chapter document IDs."""
    for chapter_chunk in chapter_chunks:
        chapter_number = chapter_chunk.get("chapter_number")
        if chapter_number is None:
            continue
        
        chapter_doc_id = database.upsert_chapter_document(
            book_id=book_id,
            chapter_number=int(chapter_number),
            chapter_title=chapter_chunk.get("chapter_title") or "",
            content=chapter_chunk.get("content", ""),
            metadata={
                "chapter_title": chapter_chunk.get("chapter_title"),
                "page_start": chapter_chunk.get("page_start"),
                "page_end": chapter_chunk.get("page_end"),
            }
        )
        
        # Update chunk metadata
        chunk_metadata = dict(chapter_chunk.get("metadata") or {})
        chunk_metadata.update({
            "chapter_document_id": chapter_doc_id,
            "chapter_number": int(chapter_number),
        })
        chapter_chunk["metadata"] = chunk_metadata


async def _process_and_store_chunks(
    book_id: str,
    chunks: List[Dict[str, Any]],
    existing_hashes: Set[str],
    embeddings_client: AWSEmbeddingClient,
    database: AWSDatabaseClient
) -> int:
    """
    Process chunks: expand, deduplicate, generate embeddings, store.
    
    Returns:
        Number of chunks inserted
    """
    # Step 1: Expand chunks (split large ones)
    expanded_chunks = _expand_chunks(chunks)
    
    # Step 2: Deduplicate
    deduped_chunks = _deduplicate_chunks(expanded_chunks, existing_hashes)
    
    if not deduped_chunks:
        logger.info("All chunks already present in database")
        return 0
    
    # Step 3: Batch and store chunks with embeddings
    return await _batch_and_store_chunks(
        book_id=book_id,
        chunks=deduped_chunks,
        existing_hashes=existing_hashes,
        embeddings_client=embeddings_client,
        database=database
    )


def _expand_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Expand chunks by splitting large ones and attaching content hashes."""
    expanded_chunks: List[Dict[str, Any]] = []
    for chunk in chunks:
        for split_chunk in split_chunk_if_needed(chunk, max_chars=12000):
            attach_content_hash(split_chunk)
            expanded_chunks.append(split_chunk)
    return expanded_chunks


def _deduplicate_chunks(
    chunks: List[Dict[str, Any]],
    existing_hashes: Set[str]
) -> List[Dict[str, Any]]:
    """Remove chunks that already exist in database."""
    deduped_chunks: List[Dict[str, Any]] = []
    skipped = 0
    
    for chunk in chunks:
        hash_value = chunk.get("metadata", {}).get("content_hash")
        if hash_value and hash_value in existing_hashes:
            skipped += 1
            continue
        deduped_chunks.append(chunk)
    
    if skipped:
        logger.info(f"Skipped {skipped} duplicate chunks (already in database)")
    
    return deduped_chunks


async def _batch_and_store_chunks(
    book_id: str,
    chunks: List[Dict[str, Any]],
    existing_hashes: Set[str],
    embeddings_client: AWSEmbeddingClient,
    database: AWSDatabaseClient
) -> int:
    """Batch chunks and store with embeddings (parallelized)."""
    max_tokens_per_batch = 200000
    max_chars_per_batch = max_tokens_per_batch * 4  # ~4 chars per token
    
    # Create batches
    batches: List[List[Dict[str, Any]]] = []
    current_batch: List[Dict[str, Any]] = []
    current_batch_chars = 0
    
    for chunk in chunks:
        chunk_chars = len(chunk.get("content", ""))
        
        # If adding this chunk would exceed limit, save current batch
        if current_batch and (current_batch_chars + chunk_chars) > max_chars_per_batch:
            batches.append(current_batch)
            current_batch = []
            current_batch_chars = 0
        
        current_batch.append(chunk)
        current_batch_chars += chunk_chars
    
    # Add final batch
    if current_batch:
        batches.append(current_batch)
    
    # Process all batches in parallel (with concurrency limit)
    max_concurrent_batches = 5  # Process up to 5 batches in parallel
    inserted_total = 0
    
    for i in range(0, len(batches), max_concurrent_batches):
        batch_group = batches[i:i + max_concurrent_batches]
        
        # Process this group of batches in parallel
        tasks = [
            _store_chunk_batch(
                book_id=book_id,
                batch=batch,
                batch_index=i + j + 1,
                embeddings_client=embeddings_client,
                database=database
            )
            for j, batch in enumerate(batch_group)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Update existing hashes and sum inserted counts
        for batch, inserted in zip(batch_group, results):
            for chunk in batch:
                hash_value = chunk.get("metadata", {}).get("content_hash")
                if hash_value:
                    existing_hashes.add(hash_value)
            inserted_total += inserted
    
    return inserted_total


async def _store_chunk_batch(
    book_id: str,
    batch: List[Dict[str, Any]],
    batch_index: int,
    embeddings_client: AWSEmbeddingClient,
    database: AWSDatabaseClient
) -> int:
    """Store a single batch of chunks with embeddings (async wrapper)."""
    batch_chars = sum(len(chunk.get("content", "")) for chunk in batch)
    logger.info(
        f"Processing chunk batch {batch_index} ({len(batch)} chunks, "
        f"{batch_chars:,} chars)"
    )
    
    chunk_contents = [chunk["content"] for chunk in batch]
    
    # Run embedding generation in thread pool (Bedrock is synchronous)
    loop = asyncio.get_event_loop()
    embeddings_batch = await loop.run_in_executor(
        None,
        embeddings_client.embed_texts,
        chunk_contents
    )
    
    # Database insert is also synchronous, run in thread pool
    inserted = await loop.run_in_executor(
        None,
        database.insert_chunks,
        book_id,
        batch,
        embeddings_batch
    )
    
    return inserted


async def _extract_and_store_figures(
    pdf_extractor: AWSPDFExtractor,
    figure_client: AWSFigureDescriptionClient,
    database: AWSDatabaseClient,
    book_id: str,
    pdf_bytes: bytes,
    existing_hashes: Set[str]
) -> int:
    """Extract figures from PDF, classify/describe them, and store in database."""
    logger.info("Extracting figures from PDF")
    figures = pdf_extractor.extract_figures(pdf_bytes)
    logger.info(f"Extracted {len(figures)} figures")
    
    if not figures:
        return 0
    
    # Filter duplicates and describe figures
    described_figures = await _describe_figures(
        figures=figures,
        figure_client=figure_client,
        existing_hashes=existing_hashes
    )
    
    if not described_figures:
        return 0
    
    # Store figures
    figure_ids = insert_figures_batch(book_id, described_figures)
    figures_created = len(figure_ids)
    logger.info(f"Stored {figures_created} figures")
    
    return figures_created


def _filter_duplicate_figures(
    figures: List[Dict[str, Any]],
    existing_hashes: Set[str]
) -> List[Dict[str, Any]]:
    """Filter out figures that already exist in database."""
    filtered_figures = []
    
    for fig in figures:
        image_bytes = fig.get('image_bytes') or fig.get('image_data')
        if image_bytes:
            fig_hash = hashlib.sha256(image_bytes).hexdigest()
            if fig_hash in existing_hashes:
                continue
            fig['image_hash'] = fig_hash
        filtered_figures.append(fig)
    
    if not filtered_figures:
        logger.info("All figures already processed")
    
    return filtered_figures


async def _describe_figures(
    figures: List[Dict[str, Any]],
    figure_client: AWSFigureDescriptionClient,
    existing_hashes: Set[str]
) -> List[Dict[str, Any]]:
    """Describe figures using Claude vision (parallelized)."""
    # Filter duplicates
    filtered_figures = _filter_duplicate_figures(figures, existing_hashes)
    
    if not filtered_figures:
        return []
    
    # Describe figures in parallel (with concurrency limit)
    max_concurrent = 10  # Process up to 10 figures in parallel
    loop = asyncio.get_event_loop()
    
    # Create tasks for parallel execution
    tasks = [
        loop.run_in_executor(None, _describe_single_figure, fig, figure_client)
        for fig in filtered_figures
    ]
    
    # Process in batches to limit concurrency
    described_figures = []
    for i in range(0, len(tasks), max_concurrent):
        batch_tasks = tasks[i:i + max_concurrent]
        results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Failed to describe figure: {result}")
            elif result:  # result is not None
                described_figures.append(result)
    
    return described_figures


def _describe_single_figure(
    fig: Dict[str, Any],
    figure_client: AWSFigureDescriptionClient
) -> Optional[Dict[str, Any]]:
    """Describe a single figure using Claude vision."""
    try:
        # Build description request
        class Request:
            def __init__(self, image_bytes, context_text):
                self.image_bytes = image_bytes
                self.context_text = context_text
        
        image_bytes = fig.get('image_bytes') or fig.get('image_data')
        context = fig.get('caption', '')
        
        request = Request(image_bytes, context)
        result = figure_client.describe_figure(request)
        
        # Convert to database format
        return {
            'page_number': fig.get('page_number') or fig.get('page'),
            'image_data': image_bytes,
            'image_format': fig.get('image_format') or fig.get('format', 'png'),
            'width': fig.get('width'),
            'height': fig.get('height'),
            'caption': fig.get('caption'),
            'metadata': {
                'description': result.description,
                'key_takeaways': result.key_takeaways,
                'use_cases': result.use_cases,
                'image_hash': fig.get('image_hash'),
            }
        }
    except Exception as e:
        logger.warning(f"Failed to describe figure on page {fig.get('page_number')}: {e}")
        return None

