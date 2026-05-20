import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_env_api_key(env_var: str = "GROQ_API_KEY") -> Optional[str]:
    """Safely read an API key (or multiple comma-separated keys) from the environment."""
    return os.getenv(env_var, "").strip() or None


def create_insight_engine(api_key: Optional[str] = None, model: str = "llama-3.3-70b-versatile"):
    """
    Factory function to instantiate an InsightEngine.
    If no api_key is provided, falls back to the GROQ_API_KEY environment variable.
    Supports a single key or a comma-separated list of keys for automatic rotation.

    Raises:
        RuntimeError: If no API key is available.

    Returns:
        InsightEngine instance.
    """
    from .analyzer import InsightEngine

    key = api_key or get_env_api_key()
    if not key:
        raise RuntimeError(
            "GROQ_API_KEY is not configured. Provide it as an argument or set the environment variable."
        )
    return InsightEngine(api_key=key, model=model)
