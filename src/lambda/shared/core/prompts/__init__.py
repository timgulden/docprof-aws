"""Prompt management system.

Centralized prompt registry for all LLM interactions.
"""

from shared.core.prompts.prompt_registry import get_prompt, list_prompts

__all__ = ["get_prompt", "list_prompts"]

