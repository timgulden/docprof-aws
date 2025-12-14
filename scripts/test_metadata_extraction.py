#!/usr/bin/env python3
"""
Test script for metadata extraction functions.
Can be run independently to test metadata extraction without the UI.

Usage:
    python scripts/test_metadata_extraction.py <path_to_pdf_file>
    
Or with environment variables for AWS:
    export AWS_PROFILE=docprof-dev
    export AWS_REGION=us-east-1
    python scripts/test_metadata_extraction.py <path_to_pdf_file>
"""

import sys
import os
import json
from pathlib import Path

# Add parent directory to path to import Lambda functions
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "lambda" / "book_upload"))

def test_metadata_extraction(pdf_path: str):
    """Test metadata extraction from a PDF file."""
    import handler
    
    # Read PDF file
    with open(pdf_path, 'rb') as f:
        pdf_data = f.read()
    
    print(f"Testing metadata extraction for: {pdf_path}")
    print(f"PDF size: {len(pdf_data):,} bytes\n")
    
    # Generate a test book_id
    import uuid
    book_id = str(uuid.uuid4())
    
    # Call the extraction function directly
    print("Calling _extract_metadata_from_pdf...")
    try:
        result = handler._extract_metadata_from_pdf(pdf_data, book_id)
        
        print("\n=== EXTRACTION RESULTS ===")
        print(json.dumps(result, indent=2, default=str))
        
        # Validate results
        print("\n=== VALIDATION ===")
        if result.get('title'):
            print(f"✓ Title extracted: {result['title']}")
        else:
            print("✗ Title missing or empty")
        
        if result.get('author'):
            print(f"✓ Author extracted: {result['author']}")
        else:
            print("✗ Author missing or empty")
        
        if result.get('isbn'):
            print(f"✓ ISBN extracted: {result['isbn']}")
        else:
            print("✗ ISBN missing or empty")
        
        if result.get('total_pages'):
            print(f"✓ Page count: {result['total_pages']}")
        else:
            print("✗ Page count missing")
        
        confidence = result.get('confidence', {})
        if 'error' in confidence:
            print(f"\n⚠ Warning: {confidence.get('message', confidence.get('error'))}")
        else:
            print(f"\n✓ Extraction method: {confidence.get('extraction_method', 'unknown')}")
        
        return result
        
    except Exception as e:
        print(f"\n✗ Error during extraction: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_cover_extraction(pdf_path: str):
    """Test cover image extraction from a PDF file."""
    import handler
    
    # Read PDF file
    with open(pdf_path, 'rb') as f:
        pdf_data = f.read()
    
    print(f"\n\nTesting cover extraction for: {pdf_path}")
    print(f"PDF size: {len(pdf_data):,} bytes\n")
    
    # Generate a test book_id
    import uuid
    book_id = str(uuid.uuid4())
    
    # Call cover extraction (this is part of _process_pdf_for_analysis)
    print("Extracting cover image...")
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        
        # Try to get cover from first page
        first_page = doc[0]
        image_list = first_page.get_images()
        
        if image_list:
            print(f"Found {len(image_list)} images on first page")
            # Get the first image
            xref = image_list[0][0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            
            print(f"✓ Cover extracted: {len(image_bytes):,} bytes, format: {image_ext}")
            
            # Save to file for verification
            output_path = f"/tmp/test_cover.{image_ext}"
            with open(output_path, "wb") as img_file:
                img_file.write(image_bytes)
            print(f"  Saved to: {output_path}")
            
            return True
        else:
            print("✗ No images found on first page")
            return False
            
    except Exception as e:
        print(f"✗ Error during cover extraction: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_metadata_extraction.py <path_to_pdf_file>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)
    
    # Test metadata extraction
    metadata_result = test_metadata_extraction(pdf_path)
    
    # Test cover extraction
    cover_result = test_cover_extraction(pdf_path)
    
    # Summary
    print("\n\n=== SUMMARY ===")
    if metadata_result and metadata_result.get('title'):
        print("✓ Metadata extraction: SUCCESS")
    else:
        print("✗ Metadata extraction: FAILED")
    
    if cover_result:
        print("✓ Cover extraction: SUCCESS")
    else:
        print("✗ Cover extraction: FAILED")
    
    sys.exit(0 if (metadata_result and cover_result) else 1)

