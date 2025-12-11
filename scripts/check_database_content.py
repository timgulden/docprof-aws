#!/usr/bin/env python3
"""
Check what's in the database before running full ingestion.
Specifically checks for LLM-generated content in chapters and books.
"""

import sys
import os

# Add parent directory to path to import shared modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'lambda'))

from shared.db_utils import get_db_connection
import json

def check_database_content():
    """Check database for existing content and LLM-generated fields."""
    
    print("=" * 60)
    print("Database Content Check")
    print("=" * 60)
    print()
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check books table
                print("📚 BOOKS TABLE:")
                cur.execute("""
                    SELECT 
                        book_id,
                        title,
                        author,
                        edition,
                        total_pages,
                        ingestion_date,
                        metadata
                    FROM books
                    ORDER BY ingestion_date DESC
                    LIMIT 10
                """)
                books = cur.fetchall()
                
                if books:
                    print(f"   Found {len(books)} book(s)")
                    for book in books:
                        book_id, title, author, edition, pages, ingest_date, metadata = book
                        print(f"   • {title}")
                        print(f"     ID: {book_id}")
                        print(f"     Author: {author}")
                        print(f"     Pages: {pages}")
                        print(f"     Metadata: {json.dumps(metadata) if metadata else 'None'}")
                        
                        # Check if metadata has LLM-generated fields
                        if metadata:
                            llm_fields = ['summary', 'description', 'key_points', 'overview']
                            has_llm_content = any(field in metadata for field in llm_fields)
                            if has_llm_content:
                                print(f"     ⚠️  Contains LLM-generated content in metadata")
                        print()
                else:
                    print("   No books found")
                print()
                
                # Check chapter_documents table
                print("📖 CHAPTER_DOCUMENTS TABLE:")
                cur.execute("""
                    SELECT 
                        chapter_document_id,
                        book_id,
                        chapter_number,
                        chapter_title,
                        LENGTH(content) as content_length,
                        metadata
                    FROM chapter_documents
                    ORDER BY book_id, chapter_number
                    LIMIT 20
                """)
                chapters = cur.fetchall()
                
                if chapters:
                    print(f"   Found {len(chapters)} chapter document(s)")
                    for chapter in chapters:
                        ch_id, book_id, ch_num, ch_title, content_len, metadata = chapter
                        print(f"   • Chapter {ch_num}: {ch_title}")
                        print(f"     Book ID: {book_id}")
                        print(f"     Content length: {content_len:,} chars")
                        print(f"     Metadata: {json.dumps(metadata) if metadata else 'None'}")
                        
                        # Check if metadata has LLM-generated fields
                        if metadata:
                            llm_fields = ['summary', 'description', 'key_points', 'overview', 'generated_summary']
                            has_llm_content = any(field in metadata for field in llm_fields)
                            if has_llm_content:
                                print(f"     ⚠️  Contains LLM-generated content in metadata")
                        print()
                else:
                    print("   No chapter documents found")
                print()
                
                # Check chunks table
                print("📄 CHUNKS TABLE:")
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_chunks,
                        COUNT(DISTINCT book_id) as books_with_chunks,
                        chunk_type,
                        COUNT(*) as count_by_type
                    FROM chunks
                    GROUP BY chunk_type
                """)
                chunk_stats = cur.fetchall()
                
                if chunk_stats:
                    total = sum(row[2] for row in chunk_stats)
                    print(f"   Total chunks: {total:,}")
                    for stat in chunk_stats:
                        total_chunks, books, chunk_type, count = stat
                        print(f"   • {chunk_type}: {count:,} chunks")
                else:
                    print("   No chunks found")
                print()
                
                # Check figures table
                print("🖼️  FIGURES TABLE:")
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_figures,
                        COUNT(DISTINCT book_id) as books_with_figures
                    FROM figures
                """)
                figure_stats = cur.fetchone()
                
                if figure_stats and figure_stats[0] > 0:
                    total_figures, books_with_figures = figure_stats
                    print(f"   Total figures: {total_figures:,}")
                    print(f"   Books with figures: {books_with_figures}")
                else:
                    print("   No figures found")
                print()
                
                # Summary and recommendations
                print("=" * 60)
                print("RECOMMENDATIONS:")
                print("=" * 60)
                
                has_books = len(books) > 0
                has_chapters = len(chapters) > 0
                has_llm_in_books = any(
                    book[6] and any(field in book[6] for field in ['summary', 'description', 'key_points', 'overview'])
                    for book in books
                )
                has_llm_in_chapters = any(
                    ch[5] and any(field in ch[5] for field in ['summary', 'description', 'key_points', 'overview', 'generated_summary'])
                    for ch in chapters
                )
                
                if has_llm_in_books:
                    print("⚠️  Books table contains LLM-generated content")
                    print("   Recommendation: May need to regenerate book summaries")
                else:
                    print("✅ Books table: No LLM-generated content detected")
                
                if has_llm_in_chapters:
                    print("⚠️  Chapter documents contain LLM-generated content")
                    print("   Recommendation: May need to regenerate chapter summaries")
                else:
                    print("✅ Chapter documents: No LLM-generated content detected")
                
                if has_books and not has_llm_in_books and not has_llm_in_chapters:
                    print("✅ Database looks clean - ready for ingestion")
                elif has_books:
                    print("⚠️  Consider purging LLM-generated content before re-ingestion")
                
    except Exception as e:
        print(f"❌ Error checking database: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == '__main__':
    success = check_database_content()
    sys.exit(0 if success else 1)

