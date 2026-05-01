"""Context window packer — truncation, splitting, chat packing, sliding window."""
from typing import Any, Dict, List, Optional

DEFAULT_MAX_TOKENS = 8192
CHARS_PER_TOKEN = 4  # standard heuristic (GPT-family average)


class Contextpacker:
    """Pack and manage context for LLM prompts.

    Parameters
    ----------
    max_tokens:
        Default token budget for all operations.  Must be >= 1.
    separator:
        String inserted between parts when joining (default ``"\\n\\n"``).
    """

    def __init__(self, max_tokens: int = DEFAULT_MAX_TOKENS, separator: str = "\n\n"):
        if max_tokens < 1:
            raise ValueError(f"max_tokens must be >= 1, got {max_tokens}")
        self._max_tokens = max_tokens
        self._separator = separator

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def max_tokens(self) -> int:
        """Default token budget."""
        return self._max_tokens

    @property
    def separator(self) -> str:
        """Separator used when joining text parts."""
        return self._separator

    # ------------------------------------------------------------------
    # Token counting
    # ------------------------------------------------------------------

    def count(self, text: str) -> int:
        """Approximate token count using a word-aware heuristic.

        Uses the observation that the average English word is ~0.75 tokens
        (words × 1.3 ≈ tokens).  Returns 0 for empty input.
        """
        if not text:
            return 0
        words = text.split()
        return max(1, round(len(words) * 1.3))

    def count_chars(self, text: str) -> int:
        """Character-based token count (chars ÷ 4).

        A fast fallback that avoids word splitting.
        Returns 0 for empty input.
        """
        if not text:
            return 0
        return max(1, len(text) // CHARS_PER_TOKEN)

    # ------------------------------------------------------------------
    # Truncation
    # ------------------------------------------------------------------

    def truncate(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Truncate *text* from the end to fit within *max_tokens* (char-based)."""
        limit = max_tokens if max_tokens is not None else self._max_tokens
        max_chars = limit * CHARS_PER_TOKEN
        return text[:max_chars] if len(text) > max_chars else text

    def truncate_start(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Keep the END of *text*, dropping oldest content first."""
        limit = max_tokens if max_tokens is not None else self._max_tokens
        max_chars = limit * CHARS_PER_TOKEN
        return text[-max_chars:] if len(text) > max_chars else text

    # ------------------------------------------------------------------
    # Packing
    # ------------------------------------------------------------------

    def pack(self, parts: List[str], max_tokens: Optional[int] = None) -> str:
        """Join *parts* with the instance separator and truncate to budget."""
        limit = max_tokens if max_tokens is not None else self._max_tokens
        joined = self._separator.join(p for p in parts if p)
        return self.truncate(joined, limit)

    def pack_priority(
        self,
        parts: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
    ) -> str:
        """Greedily select parts by descending priority until the budget is full.

        Each element must be a dict with:
        - ``"text"`` (str): the content
        - ``"priority"`` (int|float, default 0): higher value → kept first

        Selected items are returned joined in their **original** document order
        so that positional semantics (e.g., conversation flow) are preserved.

        Note: separator characters are not counted against the budget; in
        practice two newlines (~0.5 tokens) are negligible for most budgets.
        """
        limit = max_tokens if max_tokens is not None else self._max_tokens
        # Sort by priority descending to greedily include highest-value content
        sorted_indexed = sorted(
            enumerate(parts),
            key=lambda x: x[1].get("priority", 0),
            reverse=True,
        )
        selected_indices: List[int] = []
        used = 0
        for idx, part in sorted_indexed:
            text = part.get("text", "")
            tokens = self.count_chars(text)
            if used + tokens <= limit:
                selected_indices.append(idx)
                used += tokens
        # Restore original document order for coherent output
        selected_indices.sort()
        return self._separator.join(parts[i].get("text", "") for i in selected_indices)

    def pack_chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        keep_system: bool = True,
    ) -> List[Dict[str, str]]:
        """Trim a chat history to fit within *max_tokens*.

        Drops the oldest non-system messages first.  If ``keep_system`` is
        True the system message(s) are always included and their tokens are
        deducted from the budget before fitting remaining messages.

        Each message must be a dict with ``"role"`` and ``"content"`` keys.
        """
        limit = max_tokens if max_tokens is not None else self._max_tokens
        system = [m for m in messages if m.get("role") == "system"]
        others = [m for m in messages if m.get("role") != "system"]
        system_tokens = sum(self.count_chars(m["content"]) for m in system)
        budget = limit - (system_tokens if keep_system else 0)
        if budget <= 0:
            # System messages alone exhaust the budget
            return list(system) if keep_system else []
        result: List[Dict[str, str]] = []
        used = 0
        for msg in reversed(others):
            t = self.count_chars(msg["content"])
            if used + t <= budget:
                result.insert(0, msg)
                used += t
            else:
                # Stop: keeping a gap in the history would produce incoherent context
                break
        return (list(system) if keep_system else []) + result

    # ------------------------------------------------------------------
    # Splitting
    # ------------------------------------------------------------------

    def split(self, text: str, max_tokens: Optional[int] = None) -> List[str]:
        """Split *text* into chunks each fitting within *max_tokens*.

        Returns an empty list for empty input.
        """
        if not text:
            return []
        limit = max_tokens if max_tokens is not None else self._max_tokens
        max_chars = limit * CHARS_PER_TOKEN
        if len(text) <= max_chars:
            return [text]
        chunks: List[str] = []
        while text:
            chunks.append(text[:max_chars])
            text = text[max_chars:]
        return chunks

    # ------------------------------------------------------------------
    # Sliding window
    # ------------------------------------------------------------------

    def sliding_window(
        self,
        parts: List[str],
        max_tokens: Optional[int] = None,
    ) -> List[str]:
        """Return the most recent *parts* that fit within the token budget.

        Iterates from newest to oldest; stops as soon as adding a part would
        exceed the budget, preserving conversational contiguity.
        """
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
