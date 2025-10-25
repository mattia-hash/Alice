from typing import List

from agent.tools import get_tool_functions


def get_llm_tool_schemas() -> List:
    """Return tool functions for the LLM (ollama format).

    With the ollama library, we pass actual Python functions
    instead of JSON schemas. The library automatically generates
    schemas from function signatures and docstrings.
    """
    return get_tool_functions()
