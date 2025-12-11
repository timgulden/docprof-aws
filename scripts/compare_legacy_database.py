#!/usr/bin/env python3
"""
Compare legacy MAExpert database with AWS database.
Queries both databases to compare what's actually stored.
"""

import sys
import os
import json

# Try to import MAExpert database client
try:
    sys.path.insert(0, "/Users/tgulden/Documents/AI Projects/MAExpert/src")
    from effects.database_client import PsycopgDatabaseClient, DatabaseConfig
    from utils.config import get_settings
    MAEXPERT_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Cannot import MAExpert database client: {e}")
    print("   Will only compare AWS database structure")
    MAEXPERT_AVAILABLE = False

# Import AWS database utilities
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'lambda'))
try:
    from shared.db_utils import get_db_connection
    AWS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Cannot import AWS database utilities: {e}")
    AWS_AVAILABLE = False

def get_maexpert_db_config():
    """Get MAExpert database configuration."""
    if not MAEXPERT_AVAILABLE:
        return None
    
    try:
        settings = get_settings()
        return DatabaseConfig(
            database=settings.database_name,
            user=settings.database_user,
            password=settings.database_password,
            host=settings.database_host,
            port=settings.database_port
        )
    except Exception as e:
        print(f"⚠️  Cannot get MAExpert DB config: {e}")
        return None

def compare_chunks():
    """Compare chunks between MAExpert and AWS."""
    print("=" * 80)
    print("CHUNKS COMPARISON")
    print("=" * 80)
    print()
    
    # Get MAExpert data
    maexpert_chunks = None
    if MAEXPERT_AVAILABLE:
        try:
            config = get_maexpert_db_config()
            if config:
                client = PsycopgDatabaseClient(config)
                # Query sample chunks
                # Note: This would require implementing a query method
                print("📖 MAExpert database: Available")
                print("   (Query implementation needed)")
            else:
                print("📖 MAExpert database: Config not available")
        except Exception as e:
            print(f"📖 MAExpert database: Error - {e}")
    
    # Get AWS data
    aws_chunks = None
    if AWS_AVAILABLE:
        try:
            from shared.db_utils import get_db_connection
            from psycopg2.extras import RealDictCursor
            
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Get sample chunks
                    cur.execute("""
                        SELECT 
                            chunk_type,
                            COUNT(*) as count,
                            COUNT(DISTINCT book_id) as books,
                            COUNT(DISTINCT chapter_number) FILTER (WHERE chapter_number IS NOT NULL) as chapters,
                            COUNT(DISTINCT figure_id) FILTER (WHERE figure_id IS NOT NULL) as figures
                        FROM chunks
                        GROUP BY chunk_type
                    """)
                    aws_chunks = cur.fetchall()
                    
                    print("☁️  AWS database chunks:")
                    for row in aws_chunks:
                        print(f"   • {row['chunk_type']}: {row['count']:,} chunks")
                        print(f"     Books: {row['books']}, Chapters: {row['chapters']}, Figures: {row['figures']}")
                    
                    # Check field usage
                    cur.execute("""
                        SELECT 
                            COUNT(*) FILTER (WHERE figure_context IS NOT NULL) as has_figure_context,
                            COUNT(*) FILTER (WHERE figure_id IS NOT NULL) as has_figure_id,
                            COUNT(*) FILTER (WHERE metadata IS NOT NULL) as has_metadata
                        FROM chunks
                    """)
                    field_usage = cur.fetchone()
                    print(f"\n   Field usage:")
                    print(f"     • figure_context: {field_usage['has_figure_context']:,} chunks")
                    print(f"     • figure_id: {field_usage['has_figure_id']:,} chunks")
                    print(f"     • metadata: {field_usage['has_metadata']:,} chunks")
                    
        except Exception as e:
            print(f"☁️  AWS database: Error - {e}")
            import traceback
            traceback.print_exc()

def compare_schema_fields():
    """Compare schema field names."""
    print("\n" + "=" * 80)
    print("SCHEMA FIELD COMPARISON")
    print("=" * 80)
    print()
    
    print("MAExpert insert_chunks expects chunk dict with:")
    print("  • context_text (mapped to figure_context column)")
    print()
    print("AWS insert_chunks_batch expects chunk dict with:")
    print("  • figure_context (mapped to figure_context column)")
    print()
    print("⚠️  NEED TO VERIFY: Does MAExpert's chunk_builder create 'context_text' or 'figure_context'?")
    print("   And does our adapter correctly map it?")

if __name__ == '__main__':
    compare_chunks()
    compare_schema_fields()

