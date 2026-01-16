"""
Runtime patches to optimize MAExpert ingestion flow
Patches MAExpert code at runtime to add early exit checks and optimizations
"""

import logging
from typing import Any, Dict, Set

logger = logging.getLogger(__name__)


def patch_ingestion_flow_for_early_exit(
    run_ingestion_pipeline_func,
    database,
    book_id: str
):
    """
    Patch the ingestion flow to check for existing figures early.
    
    This wraps the run_ingestion_pipeline function to add early exit logic
    before expensive figure extraction and classification.
    """
    def optimized_run_ingestion_pipeline(*args, **kwargs):
        """
        Wrapper that checks for existing figures before running full pipeline.
        """
        command = kwargs.get('command') or args[0] if args else None
        
        if not command or command.skip_figures:
            # No optimization needed - skip figures anyway
            return run_ingestion_pipeline_func(*args, **kwargs)
        
        # Check for existing figures EARLY (before extraction)
        try:
            existing_figure_hashes = database.get_existing_figure_hashes(book_id)
            
            if existing_figure_hashes and len(existing_figure_hashes) > 10:
                # We have many existing figures - check if we should skip extraction
                # Estimate: if we have >80% of expected figures, skip extraction
                # For now, use a simple heuristic: if >10 figures exist, skip extraction
                # (This is conservative - user can force re-extraction if needed)
                logger.info(
                    f"Found {len(existing_figure_hashes)} existing figures - "
                    f"skipping expensive extraction and classification steps"
                )
                logger.info(
                    "To force re-extraction, delete existing figures from database or "
                    "set skip_figures=False and ensure fewer than 10 figures exist"
                )
                
                # Modify command to skip figures (temporary, just for this run)
                original_skip_figures = command.skip_figures
                command.skip_figures = True
                
                try:
                    result = run_ingestion_pipeline_func(*args, **kwargs)
                    # Restore original value
                    command.skip_figures = original_skip_figures
                    return result
                except Exception as e:
                    # Restore original value on error
                    command.skip_figures = original_skip_figures
                    raise
            else:
                # Proceed normally - extract and classify
                return run_ingestion_pipeline_func(*args, **kwargs)
                
        except Exception as e:
            logger.warning(f"Failed to check existing figures - proceeding with full extraction: {e}")
            # Fall back to normal flow
            return run_ingestion_pipeline_func(*args, **kwargs)
    
    return optimized_run_ingestion_pipeline

