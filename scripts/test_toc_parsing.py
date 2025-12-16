#!/usr/bin/env python3
"""
Test TOC parsing and chapter detection in isolation.

This script tests the parse_toc_structure and is_real_chapter functions
to verify they correctly identify chapters vs sections.

Now also tests LLM-based TOC extraction for PDFs without embedded TOC.
"""

import sys
import os
import json
import boto3
from typing import List, Tuple
import re

# Add src/lambda to path to import shared modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'lambda'))

from shared.logic.source_summaries import (
    parse_toc_structure,
    is_real_chapter,
    is_front_matter,
    is_part,
    is_chapter_title,
)

# Import LLM-based TOC parser
try:
    from shared.toc_parser_llm import (
        parse_toc_llm,
        identify_chapter_level,
        convert_chapter_ranges_to_toc_raw,
    )
    LLM_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  LLM TOC parser not available: {e}")
    LLM_AVAILABLE = False

# Set AWS profile
os.environ['AWS_PROFILE'] = 'docprof-dev'

s3_client = boto3.client('s3')
SOURCE_BUCKET = 'docprof-dev-source-docs'


def extract_toc_from_s3(book_id: str, use_llm: bool = False) -> Tuple[List[Tuple], str, str, int, bytes, List[str]]:
    """
    Extract TOC from PDF in S3 using PyMuPDF, optionally with LLM fallback.
    
    Returns:
        (toc_raw, source_title, author, total_pages, pdf_data, pages_text)
    """
    import fitz  # PyMuPDF
    
    # Find the PDF in S3
    print(f"Looking for PDF for book_id: {book_id}")
    
    # List objects in books/{book_id}/
    prefix = f"books/{book_id}/"
    response = s3_client.list_objects_v2(Bucket=SOURCE_BUCKET, Prefix=prefix)
    
    if 'Contents' not in response:
        raise ValueError(f"No files found for book_id {book_id} in s3://{SOURCE_BUCKET}/{prefix}")
    
    # Find PDF file
    pdf_key = None
    for obj in response['Contents']:
        if obj['Key'].endswith('.pdf'):
            pdf_key = obj['Key']
            break
    
    if not pdf_key:
        raise ValueError(f"No PDF found for book_id {book_id}")
    
    print(f"Found PDF: s3://{SOURCE_BUCKET}/{pdf_key}")
    
    # Download PDF
    print("Downloading PDF...")
    pdf_response = s3_client.get_object(Bucket=SOURCE_BUCKET, Key=pdf_key)
    pdf_data = pdf_response['Body'].read()
    
    # Extract TOC
    print("Extracting TOC using PyMuPDF...")
    doc = fitz.open(stream=pdf_data, filetype="pdf")
    toc_raw = doc.get_toc()  # Returns list of (level, title, page) tuples
    
    # Get metadata
    metadata = doc.metadata
    source_title = metadata.get('title', 'Unknown')
    author = metadata.get('author', 'Unknown')
    total_pages = len(doc)
    
    # Extract page text for LLM (if needed)
    pages_text = []
    for page_num in range(len(doc)):
        try:
            page = doc[page_num]
            pages_text.append(page.get_text("text"))
        except Exception as e:
            print(f"Warning: Failed to extract text from page {page_num + 1}: {e}")
            pages_text.append("")
    
    doc.close()
    
    print(f"PyMuPDF extracted {len(toc_raw)} TOC entries, {total_pages} pages")
    print(f"Title: {source_title}, Author: {author}")
    
    # If very few entries and LLM is available, try LLM-based extraction
    if len(toc_raw) < 5 and use_llm and LLM_AVAILABLE:
        print("\n⚠️  PyMuPDF found very few TOC entries, trying LLM-based extraction...")
        try:
            toc_result = parse_toc_llm(
                pdf_bytes=pdf_data,
                pages=pages_text,
                book_title=source_title,
            )
            
            if toc_result.chapters:
                # Convert LLM results to toc_raw format
                toc_raw = convert_chapter_ranges_to_toc_raw(
                    toc_result.chapters,
                    page_offset=toc_result.page_offset,
                )
                print(f"✅ LLM-based extraction found {len(toc_raw)} chapters "
                      f"(TOC pages: {toc_result.toc_start_page}-{toc_result.toc_end_page})")
            else:
                print("⚠️  LLM-based extraction returned no chapters")
        except Exception as e:
            print(f"❌ LLM-based TOC extraction failed: {e}")
            import traceback
            traceback.print_exc()
    elif len(toc_raw) == 0:
        print("\n⚠️  WARNING: No TOC entries found!")
        print("   This PDF may not have an embedded TOC structure.")
        if LLM_AVAILABLE:
            print("   Use --use-llm flag to try LLM-based extraction.")
    
    return toc_raw, source_title, author, total_pages, pdf_data, pages_text


def analyze_toc_entries(toc_raw: List[Tuple], show_all: bool = False):
    """
    Analyze TOC entries and show what would be identified as chapters vs sections.
    """
    print("\n" + "=" * 80)
    print("TOC ENTRY ANALYSIS")
    print("=" * 80)
    
    # Count entries by level
    level_counts = {}
    for level, title, page in toc_raw:
        level_counts[level] = level_counts.get(level, 0) + 1
    
    print(f"\nTOC entries by level:")
    for level in sorted(level_counts.keys()):
        print(f"   Level {level}: {level_counts[level]} entries")
    
    level_1_items = []
    level_2_items = []
    for level, title, page in toc_raw:
        if level == 1:
            level_1_items.append((title, page))
        elif level == 2:
            level_2_items.append((title, page))
    
    print(f"\nFound {len(level_1_items)} level-1 TOC entries")
    print(f"Found {len(level_2_items)} level-2 TOC entries")
    
    # Analyze each level-1 item
    chapters = []
    sections = []
    front_matter_items = []
    current_chapter = None
    
    for title, page in level_1_items:
        if is_front_matter(title):
            front_matter_items.append((title, page))
            continue
        
        is_chapter = is_real_chapter(title, page, current_chapter)
        
        if is_chapter:
            chapters.append((title, page))
            current_chapter = {
                "chapter_number": len(chapters),
                "chapter_title": title,
                "page_number": page,
            }
        else:
            sections.append((title, page))
    
    print(f"\n📊 SUMMARY:")
    print(f"   Front matter: {len(front_matter_items)}")
    print(f"   Real chapters: {len(chapters)}")
    print(f"   Sections (at level 1): {len(sections)}")
    print(f"   Total level-1 items: {len(level_1_items)}")
    
    if front_matter_items:
        print(f"\n📄 Front Matter ({len(front_matter_items)} items):")
        for title, page in front_matter_items[:10]:  # Show first 10
            print(f"   - {title} (page {page})")
        if len(front_matter_items) > 10:
            print(f"   ... and {len(front_matter_items) - 10} more")
    
    print(f"\n📚 Chapters ({len(chapters)} items):")
    for i, (title, page) in enumerate(chapters, 1):
        prev_page = chapters[i-2][1] if i > 1 else 0
        gap = page - prev_page if i > 1 else 0
        print(f"   {i:2d}. {title[:60]:60s} (page {page:4d}, gap: {gap:3d})")
    
    if sections:
        print(f"\n📑 Sections at Level 1 ({len(sections)} items):")
        for title, page in sections[:20]:  # Show first 20
            print(f"   - {title[:60]:60s} (page {page})")
        if len(sections) > 20:
            print(f"   ... and {len(sections) - 20} more")
    
    # Analyze level 2 items (these might be the actual chapters!)
    print(f"\n" + "=" * 80)
    print("LEVEL 2 ANALYSIS (Potential Chapters)")
    print("=" * 80)
    
    level_2_chapters = []
    level_2_sections = []
    for title, page in level_2_items:
        # Check if it looks like a chapter
        title_lower = title.lower()
        if 'chapter' in title_lower or re.match(r'^\d+[\.\s]+', title):
            level_2_chapters.append((title, page))
        else:
            level_2_sections.append((title, page))
    
    print(f"\nLevel 2 items that look like chapters: {len(level_2_chapters)}")
    print(f"Level 2 items that look like sections: {len(level_2_sections)}")
    
    if level_2_chapters:
        print(f"\n📚 Level 2 Chapters ({len(level_2_chapters)} items):")
        for i, (title, page) in enumerate(level_2_chapters, 1):
            prev_page = level_2_chapters[i-2][1] if i > 1 else 0
            gap = page - prev_page if i > 1 else 0
            print(f"   {i:2d}. {title[:60]:60s} (page {page:4d}, gap: {gap:3d})")
    
    if show_all:
        print(f"\n📋 ALL Level-1 Items (for debugging):")
        for i, (title, page) in enumerate(level_1_items, 1):
            is_fm = is_front_matter(title)
            is_ch = is_real_chapter(title, page, current_chapter) if not is_fm else False
            status = "FM" if is_fm else ("CH" if is_ch else "SEC")
            print(f"   {i:3d}. [{status}] {title[:60]:60s} (page {page})")


def test_parse_toc_structure(toc_raw: List[Tuple], source_title: str, author: str, total_pages: int):
    """
    Test the full parse_toc_structure function.
    """
    print("\n" + "=" * 80)
    print("FULL TOC PARSING TEST")
    print("=" * 80)
    
    toc_data = parse_toc_structure(toc_raw, source_title, author, total_pages)
    
    chapters = toc_data.get("chapters", [])
    
    print(f"\n✅ Parsed {len(chapters)} chapters")
    print(f"\n📚 Chapter List:")
    for i, chapter in enumerate(chapters, 1):
        sections_count = len(chapter.get("sections", []))
        print(f"   {i:2d}. {chapter['chapter_title'][:60]:60s} "
              f"(page {chapter['page_number']:4d}, {sections_count} sections)")
    
    # Show sections for first few chapters
    print(f"\n📑 Sections in First 3 Chapters:")
    for i, chapter in enumerate(chapters[:3], 1):
        sections = chapter.get("sections", [])
        print(f"\n   Chapter {i}: {chapter['chapter_title']}")
        if sections:
            for section in sections[:5]:  # First 5 sections
                print(f"      - {section['section_title'][:50]} (page {section['page_number']}, level {section['level']})")
            if len(sections) > 5:
                print(f"      ... and {len(sections) - 5} more sections")
        else:
            print(f"      (no sections)")
    
    return toc_data


def test_llm_chapter_level_detection(toc_raw: List[Tuple], source_title: str):
    """
    Test LLM-based chapter level detection.
    """
    if not LLM_AVAILABLE:
        print("\n⚠️  LLM chapter level detection not available (import failed)")
        return None
    
    print("\n" + "=" * 80)
    print("LLM CHAPTER LEVEL DETECTION TEST")
    print("=" * 80)
    
    try:
        chapter_level = identify_chapter_level(toc_raw, book_title=source_title)
        if chapter_level:
            print(f"\n✅ LLM identified chapter level: {chapter_level}")
        else:
            print("\n⚠️  LLM could not determine chapter level with confidence")
        return chapter_level
    except Exception as e:
        print(f"\n❌ LLM chapter level detection failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Test TOC parsing and chapter detection')
    parser.add_argument('book_id', help='Book ID to test (UUID)')
    parser.add_argument('--show-all', action='store_true', help='Show all level-1 items for debugging')
    parser.add_argument('--json', action='store_true', help='Output results as JSON')
    parser.add_argument('--use-llm', action='store_true', help='Use LLM-based extraction if PyMuPDF finds < 5 entries')
    parser.add_argument('--test-llm-level', action='store_true', help='Test LLM chapter level detection')
    
    args = parser.parse_args()
    
    try:
        # Extract TOC from S3
        toc_raw, source_title, author, total_pages, pdf_data, pages_text = extract_toc_from_s3(
            args.book_id, 
            use_llm=args.use_llm
        )
        
        # Test LLM chapter level detection if requested
        if args.test_llm_level and len(toc_raw) > 0:
            test_llm_chapter_level_detection(toc_raw, source_title)
        
        # Analyze TOC entries
        analyze_toc_entries(toc_raw, show_all=args.show_all)
        
        # Test full parsing
        toc_data = test_parse_toc_structure(toc_raw, source_title, author, total_pages)
        
        if args.json:
            # Output as JSON
            output = {
                "book_id": args.book_id,
                "source_title": source_title,
                "author": author,
                "total_pages": total_pages,
                "toc_entries": len(toc_raw),
                "chapters": len(toc_data.get("chapters", [])),
                "chapters_detail": [
                    {
                        "chapter_number": ch["chapter_number"],
                        "chapter_title": ch["chapter_title"],
                        "page_number": ch["page_number"],
                        "sections_count": len(ch.get("sections", [])),
                    }
                    for ch in toc_data.get("chapters", [])
                ],
            }
            print("\n" + "=" * 80)
            print("JSON OUTPUT")
            print("=" * 80)
            print(json.dumps(output, indent=2))
        
        print("\n" + "=" * 80)
        print("✅ Test complete!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
