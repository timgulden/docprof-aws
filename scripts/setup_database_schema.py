#!/usr/bin/env python3
"""
Setup database schema for DocProf Aurora PostgreSQL
Enables pgvector extension and creates all necessary tables
"""

import sys
import os
import boto3
import json
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_db_connection_info() -> Dict[str, Any]:
    """Get database connection info from Terraform outputs or environment variables"""
    import subprocess
    
    # Try to get from Terraform outputs
    try:
        result = subprocess.run(
            ['terraform', 'output', '-json'],
            cwd='terraform/environments/dev',
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            outputs = json.loads(result.stdout)
            cluster_endpoint = outputs.get('aurora_cluster_endpoint', {}).get('value', '')
            secret_arn = outputs.get('aurora_master_password_secret_arn', {}).get('value', '')
            
            if cluster_endpoint and secret_arn:
                # Get password from Secrets Manager
                secrets_client = boto3.client('secretsmanager')
                secret_response = secrets_client.get_secret_value(SecretId=secret_arn)
                password = secret_response['SecretString']
                
                # Parse endpoint (format: cluster-name.cluster-xxxxx.region.rds.amazonaws.com)
                host = cluster_endpoint.split('.')[0] + '.cluster-' + cluster_endpoint.split('.')[1]
                
                return {
                    'host': cluster_endpoint,
                    'port': 5432,
                    'database': 'docprof',
                    'user': 'docprof_admin',
                    'password': password
                }
    except Exception as e:
        print(f"Could not get from Terraform: {e}")
    
    # Fallback to environment variables
    return {
        'host': os.getenv('DB_HOST', ''),
        'port': int(os.getenv('DB_PORT', '5432')),
        'database': os.getenv('DB_NAME', 'docprof'),
        'user': os.getenv('DB_USER', 'docprof_admin'),
        'password': os.getenv('DB_PASSWORD', '')
    }

def create_schema(conn_info: Dict[str, Any]) -> None:
    """Create database schema with pgvector extension"""
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    
    print("Connecting to Aurora...")
    conn = psycopg2.connect(
        host=conn_info['host'],
        port=conn_info['port'],
        database=conn_info['database'],
        user=conn_info['user'],
        password=conn_info['password'],
        connect_timeout=30
    )
    
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    
    try:
        # Enable pgvector extension
        print("Enabling pgvector extension...")
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        print("✓ pgvector extension enabled")
        
        # Create books table
        print("Creating books table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS books (
                book_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                title TEXT NOT NULL,
                author TEXT,
                edition TEXT,
                isbn TEXT,
                total_pages INTEGER,
                ingestion_date TIMESTAMP DEFAULT NOW(),
                metadata JSONB,
                pdf_data BYTEA
            );
        """)
        print("✓ books table created")
        
        # Create figures table
        print("Creating figures table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS figures (
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
            
            CREATE INDEX IF NOT EXISTS figures_book_idx ON figures(book_id);
            CREATE INDEX IF NOT EXISTS figures_page_idx ON figures(book_id, page_number);
        """)
        print("✓ figures table created")
        
        # Create chapter_documents table
        print("Creating chapter_documents table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chapter_documents (
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
            
            CREATE INDEX IF NOT EXISTS chapter_documents_book_idx ON chapter_documents(book_id);
        """)
        print("✓ chapter_documents table created")
        
        # Create chunks table (core table with embeddings)
        print("Creating chunks table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                book_id UUID REFERENCES books(book_id) ON DELETE CASCADE,
                chunk_type TEXT CHECK (chunk_type IN ('chapter', '2page', 'figure')),
                content TEXT NOT NULL,
                embedding vector(1536),  -- Bedrock Titan embeddings
                
                -- Metadata
                chapter_number INTEGER,
                chapter_title TEXT,
                section_title TEXT,
                page_start INTEGER,
                page_end INTEGER,
                keywords TEXT[],
                
                -- Figure-specific fields (NULL for non-figure chunks)
                figure_id UUID REFERENCES figures(figure_id) ON DELETE SET NULL,
                figure_caption TEXT,
                figure_type TEXT,
                figure_context TEXT,
                
                metadata JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            );
            
            -- Critical index for vector similarity search
            CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks 
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
            
            -- Indexes for filtering
            CREATE INDEX IF NOT EXISTS chunks_book_idx ON chunks(book_id);
            CREATE INDEX IF NOT EXISTS chunks_type_idx ON chunks(chunk_type);
            CREATE INDEX IF NOT EXISTS chunks_chapter_idx ON chunks(book_id, chapter_number);
            CREATE INDEX IF NOT EXISTS chunks_keywords_idx ON chunks USING gin(keywords);
        """)
        print("✓ chunks table created with vector index")
        
        # Create user_progress table (for future use)
        print("Creating user_progress table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_progress (
                progress_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL,
                chunk_id UUID REFERENCES chunks(chunk_id) ON DELETE CASCADE,
                
                interaction_type TEXT CHECK (interaction_type IN 
                    ('viewed', 'lecture', 'quiz', 'mastered')),
                
                timestamp TIMESTAMP DEFAULT NOW(),
                
                -- Quiz-specific (NULL for non-quiz interactions)
                quiz_score FLOAT,
                quiz_data JSONB,
                
                -- Mastery indicators
                confidence_level INTEGER CHECK (confidence_level BETWEEN 1 AND 5),
                
                metadata JSONB
            );
            
            CREATE INDEX IF NOT EXISTS user_progress_user_idx ON user_progress(user_id);
            CREATE INDEX IF NOT EXISTS user_progress_chunk_idx ON user_progress(chunk_id);
            CREATE INDEX IF NOT EXISTS user_progress_timestamp_idx ON user_progress(user_id, timestamp DESC);
            CREATE INDEX IF NOT EXISTS user_progress_type_idx ON user_progress(user_id, interaction_type);
        """)
        print("✓ user_progress table created")
        
        # Create quizzes table (for future use)
        print("Creating quizzes table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS quizzes (
                quiz_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL,
                topic TEXT NOT NULL,
                questions JSONB NOT NULL,
                attempts JSONB,
                score FLOAT,
                started_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP,
                metadata JSONB
            );
            
            CREATE INDEX IF NOT EXISTS quizzes_user_idx ON quizzes(user_id);
            CREATE INDEX IF NOT EXISTS quizzes_topic_idx ON quizzes(user_id, topic);
            CREATE INDEX IF NOT EXISTS quizzes_completed_idx ON quizzes(user_id, completed_at);
        """)
        print("✓ quizzes table created")
        
        # Create ingestion_runs table (for tracking ingestion jobs)
        print("Creating ingestion_runs table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ingestion_runs (
                run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                book_id UUID REFERENCES books(book_id) ON DELETE CASCADE,
                total_chunks INTEGER DEFAULT 0,
                total_figures INTEGER DEFAULT 0,
                status TEXT CHECK (status IN ('pending', 'processing', 'complete', 'error')),
                error_message TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS ingestion_runs_book_idx ON ingestion_runs(book_id);
            CREATE INDEX IF NOT EXISTS ingestion_runs_status_idx ON ingestion_runs(status);
        """)
        print("✓ ingestion_runs table created")
        
        # Create source_summaries table (for course planning)
        print("Creating source_summaries table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS source_summaries (
                summary_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                book_id UUID NOT NULL REFERENCES books(book_id) ON DELETE CASCADE,
                summary_json JSONB NOT NULL,
                generated_at TIMESTAMP DEFAULT NOW(),
                generated_by TEXT,
                version INTEGER DEFAULT 1,
                metadata JSONB DEFAULT '{}'::jsonb
            );
            
            CREATE INDEX IF NOT EXISTS source_summaries_book_idx ON source_summaries(book_id);
            CREATE INDEX IF NOT EXISTS source_summaries_generated_at_idx ON source_summaries(generated_at);
            CREATE UNIQUE INDEX IF NOT EXISTS source_summaries_book_version_idx ON source_summaries(book_id, version);
        """)
        print("✓ source_summaries table created")
        
        # Create courses table (for course system)
        print("Creating courses table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS courses (
                course_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL,
                title TEXT NOT NULL,
                original_query TEXT NOT NULL,
                estimated_hours FLOAT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                last_modified TIMESTAMP DEFAULT NOW(),
                preferences JSONB DEFAULT '{"depth": "balanced", "formality": "conversational", "pace": "moderate", "additional_notes": ""}'::jsonb,
                status TEXT DEFAULT 'active' CHECK (status IN ('active', 'completed', 'archived'))
            );
            
            CREATE INDEX IF NOT EXISTS courses_user_idx ON courses(user_id);
            CREATE INDEX IF NOT EXISTS courses_status_idx ON courses(user_id, status);
        """)
        print("✓ courses table created")
        
        # Create course_sections table
        print("Creating course_sections table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS course_sections (
                section_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                course_id UUID NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
                parent_section_id UUID REFERENCES course_sections(section_id) ON DELETE CASCADE,
                order_index INTEGER NOT NULL,
                title TEXT NOT NULL,
                learning_objectives TEXT[] DEFAULT '{}',
                content_summary TEXT,
                estimated_minutes INTEGER NOT NULL,
                chunk_ids UUID[] DEFAULT '{}',
                status TEXT DEFAULT 'not_started' CHECK (status IN ('not_started', 'in_progress', 'completed')),
                completed_at TIMESTAMP,
                can_standalone BOOLEAN DEFAULT FALSE,
                prerequisites UUID[] DEFAULT '{}',
                created_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS sections_course_idx ON course_sections(course_id, order_index);
            CREATE INDEX IF NOT EXISTS sections_status_idx ON course_sections(course_id, status);
            CREATE INDEX IF NOT EXISTS sections_parent_idx ON course_sections(parent_section_id);
        """)
        print("✓ course_sections table created")
        
        # Create section_deliveries table
        print("Creating section_deliveries table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS section_deliveries (
                delivery_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                section_id UUID NOT NULL REFERENCES course_sections(section_id) ON DELETE CASCADE,
                user_id UUID NOT NULL,
                lecture_script TEXT NOT NULL,
                delivered_at TIMESTAMP DEFAULT NOW(),
                duration_actual_minutes INTEGER,
                user_notes TEXT,
                style_snapshot JSONB
            );
            
            CREATE INDEX IF NOT EXISTS deliveries_section_idx ON section_deliveries(section_id);
            CREATE INDEX IF NOT EXISTS deliveries_user_idx ON section_deliveries(user_id, delivered_at);
        """)
        print("✓ section_deliveries table created")
        
        # Create section_qa_sessions table
        print("Creating section_qa_sessions table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS section_qa_sessions (
                qa_session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                section_id UUID NOT NULL REFERENCES course_sections(section_id) ON DELETE CASCADE,
                delivery_id UUID REFERENCES section_deliveries(delivery_id) ON DELETE SET NULL,
                user_id UUID NOT NULL,
                started_at TIMESTAMP DEFAULT NOW(),
                ended_at TIMESTAMP,
                lecture_position_seconds INTEGER,
                qa_messages JSONB NOT NULL DEFAULT '[]'::jsonb,
                context_chunks UUID[] DEFAULT '{}',
                metadata JSONB DEFAULT '{}'::jsonb
            );
            
            CREATE INDEX IF NOT EXISTS qa_sessions_section_idx ON section_qa_sessions(section_id);
            CREATE INDEX IF NOT EXISTS qa_sessions_user_idx ON section_qa_sessions(user_id, started_at);
        """)
        print("✓ section_qa_sessions table created")
        
        # Create course_history table
        print("Creating course_history table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS course_history (
                history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                course_id UUID NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
                change_type TEXT NOT NULL,
                change_description TEXT NOT NULL,
                outline_snapshot JSONB,
                timestamp TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS history_course_idx ON course_history(course_id, timestamp);
        """)
        print("✓ course_history table created")
        
        # Create lecture_qa table
        print("Creating lecture_qa table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS lecture_qa (
                qa_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID,
                section_id UUID NOT NULL,
                chunk_index INTEGER NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                sources JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS lecture_qa_user_section_idx ON lecture_qa(user_id, section_id, chunk_index, created_at DESC);
            CREATE INDEX IF NOT EXISTS lecture_qa_section_idx ON lecture_qa(section_id, chunk_index, created_at DESC);
        """)
        print("✓ lecture_qa table created")
        
        # Verify pgvector extension
        cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector';")
        if cur.fetchone():
            print("\n✓ Database schema setup complete!")
            print("✓ pgvector extension is enabled")
            print("✓ All tables created successfully")
        else:
            print("\n⚠️  Warning: pgvector extension not found")
            
    except Exception as e:
        print(f"\n✗ Error creating schema: {e}")
        raise
    finally:
        cur.close()
        conn.close()

def test_vector_operations(conn_info: Dict[str, Any]) -> None:
    """Test that vector operations work"""
    import psycopg2
    import random
    
    print("\nTesting vector operations...")
    conn = psycopg2.connect(
        host=conn_info['host'],
        port=conn_info['port'],
        database=conn_info['database'],
        user=conn_info['user'],
        password=conn_info['password']
    )
    
    cur = conn.cursor()
    
    try:
        # Test vector distance calculation
        vec1 = [random.random() for _ in range(1536)]
        vec2 = [random.random() for _ in range(1536)]
        
        cur.execute("SELECT %s::vector <=> %s::vector;", (vec1, vec2))
        distance = cur.fetchone()[0]
        print(f"✓ Vector distance calculation works: {distance:.4f}")
        
        # Test similarity calculation
        similarity = 1 - distance
        print(f"✓ Similarity calculation works: {similarity:.4f}")
        
    except Exception as e:
        print(f"✗ Vector test failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("DocProf Database Schema Setup")
    print("=" * 60)
    print()
    
    # Get connection info
    conn_info = get_db_connection_info()
    
    if not conn_info.get('host'):
        print("✗ Error: Could not determine database connection info")
        print("Set environment variables: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD")
        sys.exit(1)
    
    print(f"Connecting to: {conn_info['host']}:{conn_info['port']}/{conn_info['database']}")
    print()
    
    # Create schema
    create_schema(conn_info)
    
    # Test vector operations
    test_vector_operations(conn_info)
    
    print("\n" + "=" * 60)
    print("✓ Database setup complete!")
    print("=" * 60)

