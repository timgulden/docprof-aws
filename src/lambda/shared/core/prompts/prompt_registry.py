"""Prompt registry - resolves prompt names to text with variable substitution.

Pure function for resolving prompts from the base prompt dictionary.
"""

from typing import Any, Dict, Optional

from shared.core.prompts.base_prompts import BASE_PROMPTS


def get_prompt(
    name: str,
    variables: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Resolve a prompt by name with optional variable substitution.
    
    Pure function: no side effects, only string manipulation.
    
    Args:
        name: Prompt name (e.g., "courses.generate_parts")
        variables: Optional dictionary of variables to substitute in the prompt
                  Variables use {variable_name} format
    
    Returns:
        Resolved prompt text with variables substituted
    
    Raises:
        KeyError: If prompt name not found in BASE_PROMPTS
    """
    if name not in BASE_PROMPTS:
        raise KeyError(f"Prompt '{name}' not found in BASE_PROMPTS. Available prompts: {list(BASE_PROMPTS.keys())}")
    
    prompt_text = BASE_PROMPTS[name]
    
    # If no variables, return prompt as-is
    if not variables:
        return prompt_text
    
    # Substitute variables using .format()
    # Note: This will raise KeyError if a variable is missing
    try:
        return prompt_text.format(**variables)
    except KeyError as e:
        raise KeyError(
            f"Missing variable '{e.args[0]}' for prompt '{name}'. "
            f"Required variables: {_extract_variables(prompt_text)}"
        ) from e


def _extract_variables(prompt_text: str) -> list[str]:
    """
    Extract variable names from a prompt template.
    
    Helper function for error messages.
    """
    import re
    # Match {variable_name} patterns, ignore escaped braces
    pattern = r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}'
    matches = re.findall(pattern, prompt_text)
    return list(set(matches))  # Return unique variable names


def list_prompts() -> list[str]:
    """
    List all available prompt names.
    
    Returns:
        List of prompt names sorted alphabetically
    """
    return sorted(BASE_PROMPTS.keys())

