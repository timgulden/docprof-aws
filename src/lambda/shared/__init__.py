"""
Shared utilities for Lambda functions
"""

from .db_utils import (
    get_db_connection,
    vector_similarity_search,
    insert_chunks_batch,
    insert_book,
    insert_figures_batch
)

from .bedrock_client import (
    generate_embeddings,
    invoke_claude,
    describe_figure
)

__all__ = [
    'get_db_connection',
    'vector_similarity_search',
    'insert_chunks_batch',
    'insert_book',
    'insert_figures_batch',
    'generate_embeddings',
    'invoke_claude',
    'describe_figure'
]

