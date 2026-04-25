"""Context window packer — truncation, splitting, chat packing, sliding window."""
from typing import Any, Dict, List, Optional

DEFAULT_MAX_TOKENS = 8192
CHARS_PER_TOKEN = 4  # standard heuristic


class Contextpacker:
    """Pack and manage context for LLM prompts."""

    def __init__(self, max_tokens: int = DEFAULT_MAX_TOKENS, separator: str = "\n\n"):
        self._max_tokens = max_tokens
        self._separator = separator

    # ------------------------------------------------------------------
    # Token counting
    # ------------------------------------------------------------------

    def count(self, text: str) -> int:
        """Approximate token count (word-aware heuristic)."""
        words = text.split()
        # Average English word ~ 5 chars; tokens slightly shorter
        return max(1, round(len(words) * 1.3))

    def count_chars(self, text: str) -> int:
        """Char-based token count fallback (chars / 4)."""
        return max(1, len(text) // CHARS_PER_TOKEN)

    # ------------------------------------------------------------------
    # Truncation
    # ------------------------------------------------------------------

    def truncate(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Truncate text to fit within a token limit (char-based)."""
        limit = max_tokens if max_tokens is not None else self._max_tokens
        max_chars = limit * CHARS_PER_TOKEN
        return text[:max_chars] if len(text) > max_chars else text

    def truncate_start(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Keep the END of text (drop oldest context first)."""
        limit = max_tokens if max_tokens is not None else self._max_tokens
        max_chars = limit * CHARS_PER_TOKEN
        return text[-max_chars:] if len(text) > max_chars else text

    # ------------------------------------------------------------------
    # Packing
    # ------------------------------------------------------------------

    def pack(self, parts: List[str], max_tokens: Optional[int] = None) -> str:
        """Pack text parts together, truncating to fit token limit."""
        limit = max_tokens if max_tokens is not None else self._max_tokens
        joined = self._separator.join(p for p in parts if p)
        return self.truncate(joined, limit)

    def pack_priority(self, parts: List[Dict[str, Any]],
                      max_tokens: Optional[int] = None) -> str:
        """Pack parts with priority scores; drop lowest-priority first.

        Each part: {"text": str, "priority": int (higher = keep longer)}
        """
        limit = max_tokens if max_tokens is not None else self._max_tokens
        sorted_parts = sorted(parts, key=lambda p: p.get("priority", 0), reverse=True)
        selected: List[str] = []
        used = 0
        for part in sorted_parts:
            text = part.get("text", "")
            tokens = self.count_chars(text)
            if used + tokens <= limit:
                selected.append((part.get("priority", 0), text))
                used += tokens
        selected.sort(key=lambda x: x[0], reverse=True)
        return self._separator.join(t for _, t in selected)

    def pack_chat(self, messages: List[Dict[str, str]],
                  max_tokens: Optional[int] = None,
                  keep_system: bool = True) -> List[Dict[str, str]]:
        """Fit a chat message list within a token budget.

        Drops oldest non-system messages first.
        Each message: {"role": str, "content": str}
        """
        limit = max_tokens if max_tokens is not None else self._max_tokens
        system = [m for m in messages if m.get("role") == "system"]
        others = [m for m in messages if m.get("role") != "system"]
        system_tokens = sum(self.count_chars(m["content"]) for m in system)
        budget = limit - (system_tokens if keep_system else 0)
        result: List[Dict[str, str]] = []
        used = 0
        for msg in reversed(others):
            t = self.count_chars(msg["content"])
            if used + t <= budget:
                result.insert(0, msg)
                used += t
            else:
                break
        return (system if keep_system else []) + result

    # ------------------------------------------------------------------
    # Splitting
    # ------------------------------------------------------------------

    def split(self, text: str, max_tokens: Optional[int] = None) -> List[str]:
        """Split text into chunks that each fit within max_tokens."""
        limit = max_tokens if max_tokens is not None else self._max_tokens
        max_chars = limit * CHARS_PER_TOKEN
        if len(text) <= max_chars:
            return [text]
        chunks = []
        while text:
            chunks.append(text[:max_chars])
            text = text[max_chars:]
        return chunks

    # ------------------------------------------------------------------
    # Sliding window
    # ------------------------------------------------------------------

    def sliding_window(self, parts: List[str],
                       max_tokens: Optional[int] = None) -> List[str]:
        """Return the most recent parts that fit within the token budget."""
        limit = max_tokens if max_tokens is not None else self._max_tokens
        result: List[str] = []
        used = 0
        for part in reversed(parts):
            t = self.count_chars(part)
            if used + t <= limit:
                result.insert(0, part)
                used += t
            else:
                break
        return result

    @property
    def max_tokens(self) -> int:
        return self._max_tokens
