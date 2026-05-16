"""Model routing logic.

For now, this is a thin wrapper that maps a 'task type' to a model name.
Phase 1 implements simple lookup; Phase 4 may upgrade to LLM-based
classification of the user's intent.
"""

from agent_api.settings import settings


# Task types the router knows about. Add more as new use cases emerge.
TASK_TYPES = {"general", "code", "code_heavy"}


def pick_model(task_type: str = "general") -> str:
    """Return the Ollama model name for a given task type.

    Args:
        task_type: One of TASK_TYPES. Falls back to "general" if unknown.

    Returns:
        The model name to use (e.g., "llama3.1:8b").
    """
    if task_type == "code":
        return settings.model_code
    if task_type == "code_heavy":
        return settings.model_code_heavy
    return settings.model_general
