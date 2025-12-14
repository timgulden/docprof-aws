"""
Cover extraction utility for book covers.
Extracts first page of PDF as cover image.
"""

from PIL import Image
import io
import logging

logger = logging.getLogger(__name__)


def extract_cover_from_pdf_bytes(pdf_bytes: bytes, target_width: int = 400) -> tuple[bytes, str]:
    """Extract first page of PDF as cover image.
    
    Args:
        pdf_bytes: PDF file as bytes
        target_width: Target width in pixels (maintains aspect ratio)
    
    Returns:
        Tuple of (image_bytes, format)
    """
    # Import fitz here to avoid top-level import issues in Lambda
    import fitz  # PyMuPDF
    
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    if len(doc) == 0:
        raise ValueError("PDF has no pages")
    
    first_page = doc[0]
    
    # Calculate scale to achieve target width
    page_rect = first_page.rect
    scale = target_width / page_rect.width
    
    # Render page to image
    matrix = fitz.Matrix(scale, scale)
    pix = first_page.get_pixmap(matrix=matrix)
    
    # Convert to JPEG for reasonable file size
    # Convert pixmap to PIL Image
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
    # Save as JPEG with quality setting
    img_buffer = io.BytesIO()
    img.save(img_buffer, format="JPEG", quality=85, optimize=True)
    img_bytes = img_buffer.getvalue()
    
    doc.close()
    
    return img_bytes, "jpeg"

