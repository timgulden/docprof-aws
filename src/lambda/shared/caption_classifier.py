"""
AWS Bedrock Caption Classifier
Translates MAExpert's caption classification to use Bedrock Claude Vision
"""

import base64
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import fitz  # PyMuPDF
from loguru import logger
from PIL import Image
import io

from shared.bedrock_client import invoke_claude


def _media_type(image_format: str) -> str:
    """Convert image format to MIME type."""
    suffix = image_format.lower()
    if suffix in {"jpg", "jpeg"}:
        return "image/jpeg"
    if suffix == "png":
        return "image/png"
    if suffix == "webp":
        return "image/webp"
    return "image/png"


def _render_page_as_image(document: fitz.Document, page_num: int, zoom: float = 2.0) -> bytes:
    """Render a PDF page as a JPEG image."""
    page = document[page_num - 1]  # 0-indexed
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix)
    
    # Convert to PIL Image
    pil_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
    # Convert to JPEG
    buffer = io.BytesIO()
    pil_image.convert("RGB").save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


@dataclass
class CaptionTypeClassification:
    """Result of classifying which caption types indicate figures."""
    figure_caption_tokens: List[str]  # Caption types that indicate figures
    classification: Dict[str, bool]  # Token -> is_figure mapping
    raw_response: str


def classify_caption_types_for_figures(
    pdf_bytes: bytes,
    pages: List[str],
    caption_tokens: List[str],
    book_title: str = "Unknown Book",
    samples_per_type: int = 4,
) -> CaptionTypeClassification:
    """
    Use Bedrock Claude Vision to classify which caption types indicate figures vs. tables/text boxes.
    
    Args:
        pdf_bytes: PDF file as bytes
        pages: List of page text content
        caption_tokens: List of caption tokens to classify (e.g., ["figure", "exhibit", "table"])
        book_title: Title of the book (for context)
        samples_per_type: Number of sample pages to send per caption type
    
    Returns:
        CaptionTypeClassification with figure_caption_tokens list
    """
    # Find pages with each caption type
    caption_type_pages: Dict[str, List[int]] = {}
    
    for token in caption_tokens:
        pages_with_token = []
        for page_index, page_text in enumerate(pages, start=1):
            pattern = rf'^{re.escape(token)}\s+\d+'
            if re.search(pattern, page_text, re.MULTILINE | re.IGNORECASE):
                pages_with_token.append(page_index)
        caption_type_pages[token] = pages_with_token
    
    # Filter out tokens with no pages
    caption_type_pages = {k: v for k, v in caption_type_pages.items() if v}
    
    if not caption_type_pages:
        logger.warning("No pages found with any caption tokens - using all tokens as figure types")
        return CaptionTypeClassification(
            figure_caption_tokens=list(caption_tokens),
            classification={token: True for token in caption_tokens},
            raw_response="No pages found - defaulting to all tokens"
        )
    
    logger.info(
        f"Classifying caption types for '{book_title}': "
        f"{', '.join(f'{k}: {len(v)} pages' for k, v in caption_type_pages.items())}"
    )
    
    # Sample pages for each caption type
    samples: List[Dict[str, Any]] = []
    
    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        for token, page_nums in caption_type_pages.items():
            # Take up to samples_per_type pages, evenly distributed
            num_samples = min(samples_per_type, len(page_nums))
            step = max(1, len(page_nums) // num_samples) if len(page_nums) > num_samples else 1
            sample_pages = page_nums[::step][:num_samples]
            
            for page_num in sample_pages:
                try:
                    image_bytes = _render_page_as_image(document, page_num)
                    encoded_image = base64.standard_b64encode(image_bytes).decode("utf-8")
                    
                    # Get caption text from page
                    page_text = pages[page_num - 1]
                    caption_match = re.search(
                        rf'^{re.escape(token)}\s+\d+[:\-–]?\s*(.+?)$',
                        page_text,
                        re.MULTILINE | re.IGNORECASE
                    )
                    caption_text = caption_match.group(0) if caption_match else f"{token.upper()} (no caption found)"
                    
                    samples.append({
                        "token": token,
                        "page_num": page_num,
                        "image_base64": encoded_image,
                        "caption": caption_text[:200],  # Truncate caption
                    })
                except Exception as e:
                    logger.warning(f"Failed to render page {page_num} for token '{token}': {e}")
                    continue
    
    if not samples:
        logger.error("No sample pages could be rendered - defaulting to all tokens as figure types")
        return CaptionTypeClassification(
            figure_caption_tokens=list(caption_tokens),
            classification={token: True for token in caption_tokens},
            raw_response="No samples rendered - defaulting to all tokens"
        )
    
    logger.info(f"Sending {len(samples)} sample pages to Bedrock Claude for classification")
    
    # Build prompt with all samples
    system_prompt = """You are analyzing pages from a textbook to determine which caption types indicate visual figures (charts, diagrams, graphs, illustrations) versus text-based content (tables, text boxes, equations).

Your task is to classify each caption type as either:
- TRUE: This caption type indicates visual figures (charts, diagrams, graphs, illustrations) that should be processed
- FALSE: This caption type indicates text-based content (tables, text boxes, equations) that should be skipped

Respond with a JSON object mapping each caption token to a boolean:
{
  "figure": true,
  "exhibit": false,
  "table": false,
  ...
}

Also provide a brief explanation of your reasoning."""
    
    user_content = f"""Analyze the following sample pages from the book "{book_title}" and classify which caption types indicate visual figures versus text-based content.

For each sample page, I'll show you:
- The caption type (e.g., "FIGURE", "EXHIBIT", "TABLE")
- The page image
- The caption text

Please examine each sample and determine:
1. Does this caption type indicate visual figures (charts, diagrams, graphs, illustrations)?
2. Or does it indicate text-based content (tables, text boxes, equations)?

After analyzing all samples, respond with a JSON object mapping each caption token to true (indicates figures) or false (indicates text-based content).

Samples:
"""
    
    # Add each sample
    for i, sample in enumerate(samples, 1):
        user_content += f"\n--- Sample {i} ---\nCaption Type: {sample['token'].upper()}\nPage: {sample['page_num']}\nCaption: {sample['caption']}\n"
        # Note: Bedrock Claude vision API format is different - we'll send images separately
    
    user_content += "\n\nPlease analyze all samples and return a JSON object mapping each caption token to true (indicates figures) or false (indicates text-based content). Also provide a brief explanation."
    
    # Call Bedrock Claude with vision
    try:
        # Build messages with images (Bedrock format)
        messages = [
            {
                "role": "user",
                "content": user_content_parts
            }
        ]
        
        # Call Bedrock Claude Sonnet 4.5 (vision model)
        # Sonnet is sufficient for classification, Opus would be overkill
        response = invoke_claude(
            messages=messages,
            system=system_prompt,
            max_tokens=2000,
            temperature=0.2  # Lower temperature for more consistent classification
        )
        
        response_text = response['content'].strip()
        logger.info(f"Bedrock classification response received ({len(response_text)} chars)")
        
        # Parse JSON from response
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        if json_match:
            json_text = json_match.group(1)
        else:
            brace_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if not brace_match:
                raise ValueError("No JSON object detected in Bedrock response")
            json_text = brace_match.group(0)
        
        classification = json.loads(json_text)
        
        # Validate classification
        if not isinstance(classification, dict):
            raise ValueError("Classification must be a dictionary")
        
        # Ensure all tokens are classified (default to True if missing)
        for token in caption_tokens:
            if token not in classification:
                logger.warning(f"Token '{token}' not in classification - defaulting to True")
                classification[token] = True
        
        # Extract figure caption tokens
        figure_caption_tokens = [
            token for token, is_figure in classification.items()
            if is_figure and token in caption_tokens
        ]
        
        # If no tokens marked as figures, default to all (fallback)
        if not figure_caption_tokens:
            logger.warning("No caption types classified as figures - defaulting to all tokens")
            figure_caption_tokens = list(caption_tokens)
            classification = {token: True for token in caption_tokens}
        
        logger.info(
            f"Classification complete: {len(figure_caption_tokens)} figure types "
            f"({', '.join(figure_caption_tokens)}) out of {len(caption_tokens)} total"
        )
        
        return CaptionTypeClassification(
            figure_caption_tokens=figure_caption_tokens,
            classification=classification,
            raw_response=response_text,
        )
        
    except Exception as e:
        logger.error(f"Failed to classify caption types: {e}")
        # Fallback: exclude "table" by default, but include others
        # This is a safer default than including everything
        logger.warning("Falling back to heuristic: excluding 'table' token")
        fallback_tokens = [token for token in caption_tokens if token != "table"]
        return CaptionTypeClassification(
            figure_caption_tokens=fallback_tokens,
            classification={token: (token != "table") for token in caption_tokens},
            raw_response=f"Error: {str(e)}",
        )

