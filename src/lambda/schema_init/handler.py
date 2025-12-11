"""
Schema Initialization Lambda Handler
Creates database schema for DocProf AWS (books, chunks, figures tables)
"""

import json
import logging
from typing import Dict, Any

from shared.db_utils import get_db_connection
from shared.response import success_response, error_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Initialize database schema.
    
    Expected event:
    {
        "action": "create" | "verify",
        "force": false  # If true, drop existing tables first
    }
    """
    action = event.get('action', 'create')
    force = event.get('force', False)
    
    try:
        if action == 'create':
            result = create_schema(force=force)
            return success_response(result)
        elif action == 'verify':
            result = verify_schema()
            return success_response(result)
        else:
            return error_response(f"Unknown action: {action}", 400)
    except Exception as e:
        logger.error(f"Schema initialization error: {e}", exc_info=True)
        return error_response(f"Failed to initialize schema: {str(e)}", 500)


def create_schema(force: bool = False) -> Dict[str, Any]:
    """Create database schema"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Check if tables already exist
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'books'
                )
            """)
            tables_exist = cur.fetchone()[0]
            
            if tables_exist and not force:
                return {
                    'status': 'skipped',
                    'message': 'Schema already exists. Use force=true to recreate.',
                    'tables': get_table_list(cur)
                }
            
            if force and tables_exist:
                logger.info("Dropping existing tables...")
                cur.execute("DROP TABLE IF EXISTS chunks CASCADE;")
                cur.execute("DROP TABLE IF EXISTS figures CASCADE;")
                cur.execute("DROP TABLE IF EXISTS chapter_documents CASCADE;")
                cur.execute("DROP TABLE IF EXISTS books CASCADE;")
                conn.commit()
                logger.info("✓ Existing tables dropped")
            
            # Enable pgvector extension
            logger.info("Enabling pgvector extension...")
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            conn.commit()
            logger.info("✓ pgvector extension enabled")
            
            # Books table
            logger.info("Creating books table...")
            cur.execute("""
                CREATE TABLE books (
                    book_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    title TEXT NOT NULL,
                    author TEXT,
                    edition TEXT,
                    isbn TEXT,
                    total_pages INTEGER,
                    ingestion_date TIMESTAMP DEFAULT NOW(),
                    created_at TIMESTAMP DEFAULT NOW(),
                    metadata JSONB,
                    pdf_data BYTEA
                );
            """)
            logger.info("✓ books table created")
            
            # Figures table
            logger.info("Creating figures table...")
            cur.execute("""
                CREATE TABLE figures (
                    figure_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    book_id UUID REFERENCES books(book_id) ON DELETE CASCADE,
                    page_number INTEGER NOT NULL,
                    image_data BYTEA NOT NULL,
                    image_format TEXT NOT NULL,
                    width INTEGER,
                    height INTEGER,
                    caption TEXT,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE INDEX figures_book_idx ON figures(book_id);
                CREATE INDEX figures_page_idx ON figures(book_id, page_number);
            """)
            logger.info("✓ figures table created")
            
            # Chapter documents table
            logger.info("Creating chapter_documents table...")
            cur.execute("""
                CREATE TABLE chapter_documents (
                    chapter_document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    book_id UUID REFERENCES books(book_id) ON DELETE CASCADE,
                    chapter_number INTEGER NOT NULL,
                    chapter_title TEXT,
                    content TEXT NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE (book_id, chapter_number)
                );
                
                CREATE INDEX chapter_documents_book_idx ON chapter_documents(book_id);
            """)
            logger.info("✓ chapter_documents table created")
            
            # Chunks table (core table with embeddings)
            logger.info("Creating chunks table...")
            cur.execute("""
                CREATE TABLE chunks (
                    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    book_id UUID REFERENCES books(book_id) ON DELETE CASCADE,
                    chunk_type TEXT CHECK (chunk_type IN ('chapter', '2page', 'figure')),
                    content TEXT NOT NULL,
                    embedding vector(1536),
                    
                    -- Metadata
                    chapter_number INTEGER,
                    chapter_title TEXT,
                    section_title TEXT,
                    page_start INTEGER,
                    page_end INTEGER,
                    keywords TEXT[],
                    
                    -- Figure-specific fields
                    figure_id UUID REFERENCES figures(figure_id) ON DELETE SET NULL,
                    figure_caption TEXT,
                    figure_type TEXT,
                    figure_context TEXT,
                    
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                -- Critical index for vector similarity search
                CREATE INDEX chunks_embedding_idx ON chunks 
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100);
                
                -- Indexes for filtering
                CREATE INDEX chunks_book_idx ON chunks(book_id);
                CREATE INDEX chunks_type_idx ON chunks(chunk_type);
                CREATE INDEX chunks_chapter_idx ON chunks(book_id, chapter_number);
                CREATE INDEX chunks_keywords_idx ON chunks USING gin(keywords);
            """)
            logger.info("✓ chunks table created")
            
            conn.commit()
            
            return {
                'status': 'success',
                'message': 'Schema created successfully',
                'tables': get_table_list(cur),
                'indexes': get_index_list(cur)
            }


def verify_schema() -> Dict[str, Any]:
    """Verify schema exists and is correct"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Check tables
            tables = get_table_list(cur)
            
            # Check pgvector extension
            cur.execute("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';")
            vector_ext = cur.fetchone()
            
            # Check indexes
            indexes = get_index_list(cur)
            
            return {
                'status': 'verified',
                'tables': tables,
                'pgvector_installed': bool(vector_ext),
                'pgvector_version': vector_ext[1] if vector_ext else None,
                'indexes': indexes
            }


def get_table_list(cur):
    """Get list of tables"""
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    return [row[0] for row in cur.fetchall()]


def get_index_list(cur):
    """Get list of indexes"""
    cur.execute("""
        SELECT indexname, tablename
        FROM pg_indexes 
        WHERE schemaname = 'public'
        ORDER BY tablename, indexname;
    """)
    return {row[1]: [idx[0] for idx in cur.fetchall() if idx[1] == row[1]] for row in cur.fetchall()}

