"""
Protocol Implementations for MAExpert Ingestion
Implements Protocol interfaces that MAExpert ingestion expects
"""

import os
import logging
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Sequence, Iterable
import fitz  # PyMuPDF
from PIL import Image
import io

from .db_utils import (
    get_db_connection,
    insert_chunks_batch,
    insert_book,
    insert_figures_batch,
    vector_similarity_search
)
from .bedrock_client import generate_embeddings, describe_figure

logger = logging.getLogger(__name__)


class AWSDatabaseClient:
    """
    Implements DatabaseClient Protocol for MAExpert ingestion.
    Maps MAExpert database operations to AWS Aurora PostgreSQL.
    """
    
    def find_book(self, metadata: Dict[str, Any]) -> Optional[str]:
        """Find existing book by metadata."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT book_id FROM books
                    WHERE title = %s
                    AND (%s IS NULL OR author = %s)
                    AND (%s IS NULL OR isbn = %s)
                    LIMIT 1
                    """,
                    (
                        metadata.get('title'),
                        metadata.get('author'),
                        metadata.get('author'),
                        metadata.get('isbn'),
                        metadata.get('isbn')
                    )
                )
                row = cur.fetchone()
                return str(row[0]) if row else None
    
    def delete_book_contents(self, book_id: str, *, delete_book: bool = False) -> None:
        """Delete book contents (chunks, figures). Optionally delete book record."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Delete chunks
                cur.execute("DELETE FROM chunks WHERE book_id = %s", (book_id,))
                # Delete figures
                cur.execute("DELETE FROM figures WHERE book_id = %s", (book_id,))
                # Delete chapter documents
                cur.execute("DELETE FROM chapter_documents WHERE book_id = %s", (book_id,))
                
                if delete_book:
                    cur.execute("DELETE FROM books WHERE book_id = %s", (book_id,))
                conn.commit()
    
    def insert_book(
        self,
        metadata: Dict[str, Any],
        pdf_data: Optional[bytes] = None,
        total_pages: Optional[int] = None
    ) -> str:
        """Insert book record. Returns book_id."""
        book_id = insert_book(
            title=metadata.get('title', 'Unknown'),
            author=metadata.get('author'),
            edition=metadata.get('edition'),
            isbn=metadata.get('isbn'),
            total_pages=total_pages,
            metadata=metadata.get('extra', {})
        )
        return book_id
    
    def update_book_cover(self, book_id: str, cover_bytes: bytes, cover_format: str) -> None:
        """Update book cover image."""
        # Store cover in metadata for now (could add cover column later)
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE books
                    SET metadata = jsonb_set(
                        COALESCE(metadata, '{}'::jsonb),
                        '{cover}',
                        jsonb_build_object(
                            'data', %s,
                            'format', %s
                        )
                    )
                    WHERE book_id = %s
                    """,
                    (cover_bytes.hex(), cover_format, book_id)
                )
                conn.commit()
    
    def update_book_total_pages(self, book_id: str, total_pages: int) -> None:
        """Update book total pages."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE books SET total_pages = %s WHERE book_id = %s",
                    (total_pages, book_id)
                )
                conn.commit()
    
    def get_book_by_id(self, book_id: str, include_pdf: bool = False) -> Optional[Dict[str, Any]]:
        """Get book by ID."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT book_id, title, author, edition, isbn, total_pages,
                           ingestion_date, metadata
                    FROM books
                    WHERE book_id = %s
                    """,
                    (book_id,)
                )
                row = cur.fetchone()
                if not row:
                    return None
                
                return {
                    'book_id': str(row[0]),
                    'title': row[1],
                    'author': row[2],
                    'edition': row[3],
                    'isbn': row[4],
                    'total_pages': row[5],
                    'ingestion_date': row[6],
                    'metadata': row[7] or {}
                }
    
    def update_book_pdf(self, book_id: str, pdf_bytes: bytes) -> None:
        """Update book PDF data."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE books SET pdf_data = %s WHERE book_id = %s",
                    (pdf_bytes, book_id)
                )
                conn.commit()
    
    def upsert_chapter_document(
        self,
        book_id: str,
        chapter_number: int,
        chapter_title: str,
        content: str,
        metadata: Dict[str, Any]
    ) -> str:
        """Upsert chapter document."""
        import json
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chapter_documents (
                        book_id, chapter_number, chapter_title, content, metadata
                    )
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (book_id, chapter_number)
                    DO UPDATE SET
                        chapter_title = EXCLUDED.chapter_title,
                        content = EXCLUDED.content,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    RETURNING chapter_document_id
                    """,
                    (book_id, chapter_number, chapter_title, content, json.dumps(metadata))
                )
                chapter_doc_id = cur.fetchone()[0]
                conn.commit()
                return str(chapter_doc_id)
    
    def insert_figures(self, book_id: str, figures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Insert figures. Returns list with figure_ids added."""
        # Convert MAExpert format to database format
        # MAExpert uses 'image_bytes', database expects 'image_data'
        # MAExpert uses 'format', database expects 'image_format'
        db_figures = []
        for fig in figures:
            db_fig = {
                'page_number': fig.get('page_number') or fig.get('page'),
                'image_data': fig.get('image_bytes') or fig.get('image_data'),
                'image_format': fig.get('image_format') or fig.get('format', 'png'),
                'width': fig.get('width'),
                'height': fig.get('height'),
                'caption': fig.get('caption'),
                'metadata': fig.get('metadata', {})
            }
            db_figures.append(db_fig)
        
        figure_ids = insert_figures_batch(book_id, db_figures)
        
        # Add figure_ids to original figures (preserve MAExpert format)
        for fig, fig_id in zip(figures, figure_ids):
            fig['figure_id'] = fig_id
        
        return figures
        result = []
        for fig, fig_id in zip(figures, figure_ids):
            result.append({**fig, 'figure_id': fig_id})
        return result
    
    def insert_chunks(
        self,
        book_id: str,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]]
    ) -> int:
        """Insert chunks with embeddings. Returns count inserted."""
        # Ensure each chunk has book_id
        chunks_with_book_id = [
            {**chunk, 'book_id': book_id}
            for chunk in chunks
        ]
        chunk_ids = insert_chunks_batch(chunks_with_book_id, embeddings)
        return len(chunk_ids)
    
    def update_ingestion_metrics(self, payload: Dict[str, Any]) -> None:
        """Update ingestion run metrics."""
        import json
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ingestion_runs (
                        run_id, book_id, total_chunks, total_figures, status, error_message
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (run_id) DO UPDATE SET
                        book_id = EXCLUDED.book_id,
                        total_chunks = EXCLUDED.total_chunks,
                        total_figures = EXCLUDED.total_figures,
                        status = EXCLUDED.status,
                        error_message = EXCLUDED.error_message,
                        updated_at = NOW()
                    """,
                    (
                        payload.get('run_id'),
                        payload.get('book_id'),
                        payload.get('total_chunks', 0),
                        payload.get('total_figures', 0),
                        payload.get('status', 'processing'),
                        payload.get('error_message')
                    )
                )
                conn.commit()
    
    def get_existing_figure_hashes(self, book_id: str) -> Set[str]:
        """Get existing figure content hashes."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT metadata->>'content_hash'
                    FROM figures
                    WHERE book_id = %s
                    AND metadata->>'content_hash' IS NOT NULL
                    """,
                    (book_id,)
                )
                return {row[0] for row in cur.fetchall() if row[0]}
    
    def get_existing_chunk_hashes(self, book_id: str) -> Set[str]:
        """Get existing chunk content hashes."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT metadata->>'content_hash'
                    FROM chunks
                    WHERE book_id = %s
                    AND metadata->>'content_hash' IS NOT NULL
                    """,
                    (book_id,)
                )
                return {row[0] for row in cur.fetchall() if row[0]}
    
    def get_ingestion_counts(self, book_id: str) -> Dict[str, int]:
        """Get ingestion counts for book."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 
                        COUNT(*) FILTER (WHERE chunk_type = 'chapter') as chapter_chunks,
                        COUNT(*) FILTER (WHERE chunk_type = '2page') as page_chunks,
                        COUNT(*) FILTER (WHERE chunk_type = 'figure') as figure_chunks,
                        (SELECT COUNT(*) FROM figures WHERE book_id = %s) as figures
                    FROM chunks
                    WHERE book_id = %s
                    """,
                    (book_id, book_id)
                )
                row = cur.fetchone()
                return {
                    'total_chunks': (row[0] or 0) + (row[1] or 0) + (row[2] or 0),
                    'chapter_chunks': row[0] or 0,
                    'page_chunks': row[1] or 0,
                    'figure_chunks': row[2] or 0,
                    'total_figures': row[3] or 0
                }
    
    def search_chunks(
        self,
        *,
        chunk_type: str,
        embedding_vector: Sequence[float],
        top_k: int,
        metadata_filters: Dict[str, Any],
        exclude_filters: Dict[str, Any],
        page_token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search chunks by vector similarity."""
        chunk_types = [chunk_type]
        book_ids = metadata_filters.get('book_ids')
        
        results = vector_similarity_search(
            query_embedding=list(embedding_vector),
            chunk_types=chunk_types,
            book_id=book_ids[0] if book_ids else None,
            limit=top_k,
            similarity_threshold=0.7
        )
        
        return results
    
    def fetch_chapter_documents(self, document_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        """Fetch chapter documents by IDs."""
        import json
        doc_ids = list(document_ids)
        if not doc_ids:
            return {}
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT chapter_document_id, book_id, chapter_number,
                           chapter_title, content, metadata
                    FROM chapter_documents
                    WHERE chapter_document_id = ANY(%s::uuid[])
                    """,
                    (doc_ids,)
                )
                result = {}
                for row in cur.fetchall():
                    result[str(row[0])] = {
                        'chapter_document_id': str(row[0]),
                        'book_id': str(row[1]),
                        'chapter_number': row[2],
                        'chapter_title': row[3],
                        'content': row[4],
                        'metadata': row[5] or {}
                    }
                return result


class AWSPDFExtractor:
    """
    Implements PDFExtractor Protocol for MAExpert ingestion.
    Uses PyMuPDF (fitz) for PDF extraction.
    """
    
    def load_pdf(self, path: Path) -> bytes:
        """Load PDF from path (for S3, path is temporary file location)."""
        return path.read_bytes()
    
    def extract_text(self, pdf_bytes: bytes) -> Dict[str, Any]:
        """Extract text from PDF. Returns text payload dict."""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        pages = []
        full_text_parts = []
        
        for page_num, page in enumerate(doc, start=1):
            page_text = page.get_text()
            pages.append(page_text)
            full_text_parts.append(f"\n[PAGE {page_num}]\n{page_text}")
        
        metadata = {
            'title': doc.metadata.get('title', ''),
            'author': doc.metadata.get('author', ''),
            'page_count': len(doc)
        }
        
        doc.close()
        
        return {
            'text': ''.join(full_text_parts),
            'full_text': ''.join(full_text_parts),  # MAExpert chunk_builder expects 'full_text'
            'pages': pages,
            'page_count': len(pages),
            'metadata': metadata
        }
    
    def extract_figures(
        self, 
        pdf_bytes: bytes,
        pages_with_captions: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """Extract figures from PDF."""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        figures = []
        figure_count = 0
        
        for page_num, page in enumerate(doc, start=1):
            image_list = page.get_images()
            
            for img_index, img_info in enumerate(image_list):
                xref = img_info[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                
                # Open with PIL to check dimensions
                img = Image.open(io.BytesIO(image_bytes))
                width, height = img.size
                
                # Filter small images (likely decorative)
                if width < 100 or height < 100:
                    continue
                
                figure_count += 1
                
                figures.append({
                    'figure_id': f"fig_{figure_count}",
                    'page': page_num,
                    'page_number': page_num,  # MAExpert expects 'page_number'
                    'image_bytes': image_bytes,
                    'width': width,
                    'height': height,
                    'format': image_ext,
                    'image_index': figure_count  # For tracking
                })
        
        doc.close()
        return figures


class AWSEmbeddingClient:
    """
    Implements EmbeddingClient Protocol for MAExpert ingestion.
    Uses Bedrock Titan for embeddings.
    """
    
    def embed_texts(self, texts: Iterable[str]) -> List[List[float]]:
        """Generate embeddings for texts."""
        text_list = list(texts)
        return generate_embeddings(text_list)


class AWSFigureDescriptionClient:
    """
    Implements FigureDescriptionClient Protocol for MAExpert ingestion.
    Uses Bedrock Claude with vision capabilities.
    """
    
    def describe_figure(self, request: Any) -> Any:
        """Describe figure using Claude Sonnet 4.5 vision (excellent quality)."""
        # FigureDescriptionRequest is a class with attributes, not a dict
        image_bytes = request.image_bytes
        context = request.context_text  # Note: it's context_text, not context
        
        # Use Sonnet 4.5 for excellent quality figure descriptions
        description = describe_figure(image_bytes, context)
        
        # Parse structured output from description
        # MAExpert expects: description, key_takeaways, use_cases, raw_response, model
        import re
        import json
        
        # Try to extract key_takeaways and use_cases from description
        # The description should be structured text that we can parse
        key_takeaways = []
        use_cases = []
        
        # Look for structured sections in the description
        takeaways_match = re.search(r'Key Takeaways?[:\s]+(.*?)(?:\n\n|\nUse Cases|$)', description, re.DOTALL | re.IGNORECASE)
        if takeaways_match:
            takeaways_text = takeaways_match.group(1).strip()
            key_takeaways = [t.strip() for t in re.split(r'[•\-\n]', takeaways_text) if t.strip()]
        
        use_cases_match = re.search(r'Use Cases?[:\s]+(.*?)$', description, re.DOTALL | re.IGNORECASE)
        if use_cases_match:
            use_cases_text = use_cases_match.group(1).strip()
            use_cases = [u.strip() for u in re.split(r'[•\-\n]', use_cases_text) if u.strip()]
        
        # Return FigureDescriptionResult-like object matching MAExpert's interface
        class Result:
            def __init__(self, description: str, key_takeaways: list, use_cases: list, raw_response: str, model: str):
                self.description = description
                self.key_takeaways = key_takeaways if key_takeaways else ["See description for details"]
                self.use_cases = use_cases if use_cases else ["Educational reference"]
                self.raw_response = raw_response
                self.model = model
        
        return Result(
            description=description,
            key_takeaways=key_takeaways,
            use_cases=use_cases,
            raw_response=description,  # Full description as raw response
            model="claude-sonnet-4-5-20250929-v1:0"
        )

