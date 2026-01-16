"""
Adapter to replace MAExpert's caption classifier with AWS Bedrock version
This allows MAExpert code to use AWS caption classifier without modification
"""

import sys
from typing import Any, Dict, List

# Import AWS caption classifier
from shared.caption_classifier import classify_caption_types_for_figures as aws_classify_caption_types


def classify_caption_types_for_figures(
    pdf_bytes: bytes,
    pages: List[str],
    caption_tokens: List[str],
    anthropic_api_key: str = None,  # Ignored - we use Bedrock
    book_title: str = "Unknown Book",
    samples_per_type: int = 4,
    model: str = None,  # Ignored - we use Bedrock Claude
) -> Any:
    """
    AWS adapter for MAExpert's caption classifier.
    Uses Bedrock Claude Vision instead of Anthropic API.
    
    This function matches MAExpert's signature so it can be used as a drop-in replacement.
    """
    # Call AWS Bedrock version (ignores anthropic_api_key and model params)
    return aws_classify_caption_types(
        pdf_bytes=pdf_bytes,
        pages=pages,
        caption_tokens=caption_tokens,
        book_title=book_title,
        samples_per_type=samples_per_type
    )

