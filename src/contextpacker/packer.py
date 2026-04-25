"""Context window packer and truncator."""
from typing import List, Optional

DEFAULT_MAX_TOKENS = 8192

class Contextpacker:
    """Pack and truncate context for LLM prompts."""

    def __init__(self, max_tokens: int = DEFAULT_MAX_TOKENS, separator: str = "\n\n"):
        self._max_tokens = max_tokens
        self._separator = separator

    def _approx_tokens(self, text: str) -> int:
        """Approximate token count (chars / 4 heuristic)."""
        return max(1, len(text) // 4)

    def count(self, text: str) -> int:
        """Return approximate token count for text."""
        return self._approx_tokens(text)

    def truncate(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Truncate text to fit within max_tokens."""
        limit = max_tokens if max_tokens is not None else self._max_tokens
        max_chars = limit * 4
        if len(text) <= max_chars:
            return text
        return text[:max_chars]

    def pack(self, parts: List[str], max_tokens: Optional[int] = None) -> str:
        """Pack multiple text parts, truncating to fit token limit."""
        limit = max_tokens if max_tokens is not None else self._max_tokens
        joined = self._separator.join(p for p in parts if p)
        return self.truncate(joined, limit)

    @property
    def max_tokens(self) -> int:
        return self._max_tokens
