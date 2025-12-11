#!/usr/bin/env python3
"""
Create database schema for DocProf AWS
Based on MAExpert schema, adapted for Aurora PostgreSQL with pgvector
"""

import os
import sys
import boto3
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_db_connection():
    """Get database connection using Secrets Manager"""
    # Get secret ARN from environment or command line
    secret_arn = os.getenv('DB_PASSWORD_SECRET_ARN') or sys.argv[1] if len(sys.argv) > 1 else None
    
    if not secret_arn:
        raise ValueError("DB_PASSWORD_SECRET_ARN environment variable or secret ARN argument required")
    
    # Get connection info from environment
    cluster_endpoint = os.getenv('DB_CLUSTER_ENDPOINT')
    database = os.getenv('DB_NAME', 'docprof_dev')
    username = os.getenv('DB_MASTER_USERNAME', 'postgres')
    
    if not cluster_endpoint:
        raise ValueError("DB_CLUSTER_ENDPOINT environment variable required")
    
    # Get password from Secrets Manager
    secrets_client = boto3.client('secretsmanager')
    secret_response = secrets_client.get_secret_value(SecretId=secret_arn)
    password = secret_response['SecretString']
    
    # Connect to database
    conn = psycopg2.connect(
        host=cluster_endpoint,
        port=5432,
        database=database,
        user=username,
        password=password,
        connect_timeout=30
    )
    
    return conn


def create_schema(conn):
    """Create all database tables and indexes"""
    with conn.cursor() as cur:
        # Enable pgvector extension
        logger.info("Enabling pgvector extension...")
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        conn.commit()
        logger.info("✓ pgvector extension enabled")
        
        # Check if tables already exist
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'books'
            )
        """)
        if cur.fetchone()[0]:
            logger.warning("Schema already exists. Use --force to recreate.")
            return
        
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
                metadata JSONB
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
        logger.info("✓ Schema creation complete")


def verify_schema(conn):
    """Verify schema was created correctly"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = [row['table_name'] for row in cur.fetchall()]
        logger.info(f"Tables created: {', '.join(tables)}")
        
        # Check pgvector extension
        cur.execute("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';")
        vector_ext = cur.fetchone()
        if vector_ext:
            logger.info(f"✓ pgvector extension: {vector_ext['extversion']}")
        else:
            logger.error("✗ pgvector extension not found")
        
        # Check indexes
        cur.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE schemaname = 'public' 
            AND tablename = 'chunks'
            ORDER BY indexname;
        """)
        indexes = [row['indexname'] for row in cur.fetchall()]
        logger.info(f"Chunks table indexes: {', '.join(indexes)}")


def main():
    """Main function"""
    try:
        logger.info("Connecting to database...")
        conn = get_db_connection()
        logger.info("✓ Connected to database")
        
        logger.info("Creating schema...")
        create_schema(conn)
        
        logger.info("Verifying schema...")
        verify_schema(conn)
        
        logger.info("\n✓ Schema setup complete!")
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()


if __name__ == "__main__":
    main()

