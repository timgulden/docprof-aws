"""
Shared utilities for Lambda functions

Note: This __init__.py does not eagerly import modules to avoid blocking
imports of shared.logic and other submodules. Import directly when needed:
  from shared.db_utils import get_db_connection
  from shared.bedrock_client import invoke_claude
  from shared.logic.courses import create_initial_course_state
"""

# Don't eagerly import - let modules import directly when needed
# This prevents import errors from blocking shared.logic imports

__all__ = [
    # Export names for backward compatibility, but don't import here
    'get_db_connection',
    'vector_similarity_search',
    'insert_chunks_batch',
    'insert_book',
    'insert_figures_batch',
    'generate_embeddings',
    'invoke_claude',
    'describe_figure'
]

