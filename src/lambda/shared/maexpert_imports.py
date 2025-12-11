"""
MAExpert Import Utilities
Provides utilities for importing MAExpert logic functions into Lambda handlers
"""

import os
import sys
from pathlib import Path
from typing import Any, Optional

# Calculate path to MAExpert codebase
# Assuming docprof-aws and MAExpert are sibling directories
_CURRENT_DIR = Path(__file__).parent
_PROJECT_ROOT = _CURRENT_DIR.parent.parent.parent
_MAEXPERT_PATH = _PROJECT_ROOT.parent / "MAExpert" / "src"

# Add MAExpert to Python path if it exists
if _MAEXPERT_PATH.exists():
    sys.path.insert(0, str(_MAEXPERT_PATH.parent))  # Add parent to get imports working
    _MAEXPERT_AVAILABLE = True
else:
    _MAEXPERT_AVAILABLE = False
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"MAExpert codebase not found at {_MAEXPERT_PATH}. Some imports may fail.")


def ensure_maexpert_path():
    """Ensure MAExpert is in Python path. Call this before importing MAExpert modules."""
    if not _MAEXPERT_AVAILABLE:
        raise ImportError(
            f"MAExpert codebase not found at {_MAEXPERT_PATH}. "
            "Ensure MAExpert is a sibling directory to docprof-aws."
        )
    
    if str(_MAEXPERT_PATH.parent) not in sys.path:
        sys.path.insert(0, str(_MAEXPERT_PATH.parent))


def import_maexpert_logic(module_name: str):
    """
    Import a logic module from MAExpert.
    
    Usage:
        chat_logic = import_maexpert_logic('logic.chat')
        result = chat_logic.process_user_message(state, message)
    
    Args:
        module_name: Module name relative to MAExpert/src (e.g., 'logic.chat')
    
    Returns:
        Imported module
    """
    ensure_maexpert_path()
    
    try:
        module = __import__(module_name, fromlist=[''])
        return module
    except ImportError as e:
        raise ImportError(
            f"Failed to import MAExpert module '{module_name}'. "
            f"Ensure MAExpert codebase is available at {_MAEXPERT_PATH.parent}. "
            f"Original error: {e}"
        )


def get_maexpert_path() -> Optional[Path]:
    """Get the path to MAExpert codebase if available."""
    return _MAEXPERT_PATH if _MAEXPERT_AVAILABLE else None


def is_maexpert_available() -> bool:
    """Check if MAExpert codebase is available for import."""
    return _MAEXPERT_AVAILABLE

