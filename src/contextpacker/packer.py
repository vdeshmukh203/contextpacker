"""Context window packer — truncation, splitting, chat packing, sliding window."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

DEFAULT_MAX_TOKENS = 8192
CHARS_PER_TOKEN = 4  # ~4 chars per token for English text (standard heuristic)


class Contextpacker:
    """Pack and manage content for LLM prompts within a token budget.

    Parameters
    ----------
    max_tokens:
        Default token budget used when individual method calls omit
        *max_tokens*.  Must be non-negative.
    separator:
        String inserted between joined text parts (default: blank line).
    """

    def __init__(
        self,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        separator: str = "\n\n",
    ) -> None:
        if max_tokens < 0:
            raise ValueError(f"max_tokens must be non-negative, got {max_tokens}")
        self._max_tokens = max_tokens
        self._separator = separator

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def max_tokens(self) -> int:
        """Default token budget for this instance."""
        return self._max_tokens

    @property
    def separator(self) -> str:
        """Separator string used between joined parts."""
        return self._separator

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_limit(self, max_tokens: Optional[int]) -> int:
        """Return the effective token limit (caller override or instance default)."""
        limit = max_tokens if max_tokens is not None else self._max_tokens
        if limit < 0:
            raise ValueError(f"max_tokens must be non-negative, got {limit}")
        return limit

    # ------------------------------------------------------------------
    # Token counting
    # ------------------------------------------------------------------

    def count(self, text: str) -> int:
        """Approximate token count using a word-aware heuristic.

        Uses a 1.3× word-count multiplier calibrated for English text.
        Returns 0 for empty or whitespace-only strings.

        Parameters
        ----------
        text:
            Input string to count.

        Returns
        -------
        int
            Estimated token count (>= 0).
        """
        if not text or not text.strip():
            return 0
        words = text.split()
        return max(1, round(len(words) * 1.3))

    def count_chars(self, text: str) -> int:
        """Character-based token count (``len(text) // CHARS_PER_TOKEN``).

        Returns 0 for empty strings.  Used internally for all budget
        arithmetic so that truncation and counting are consistent.

        Parameters
        ----------
        text:
            Input string to count.

        Returns
        -------
        int
            Estimated token count (>= 0).
        """
        if not text:
            return 0
        return max(1, len(text) // CHARS_PER_TOKEN)

    # ------------------------------------------------------------------
    # Truncation
    # ------------------------------------------------------------------

    def truncate(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Truncate *text* from the end to fit within *max_tokens*.

        Keeps the beginning of the string (drops the tail).

        Parameters
        ----------
        text:
            String to truncate.
        max_tokens:
            Token budget.  Defaults to the instance *max_tokens*.

        Returns
        -------
        str
            Truncated string no longer than ``max_tokens * CHARS_PER_TOKEN``
            characters.
        """
        limit = self._resolve_limit(max_tokens)
        max_chars = limit * CHARS_PER_TOKEN
        return text[:max_chars] if len(text) > max_chars else text

    def truncate_start(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Keep the END of *text*, dropping oldest content first.

        Useful when the most recent context (tail of the string) is the
        most important part to preserve.

        Parameters
        ----------
        text:
            String to truncate.
        max_tokens:
            Token budget.  Defaults to the instance *max_tokens*.

        Returns
        -------
        str
            Tail of the string no longer than ``max_tokens * CHARS_PER_TOKEN``
            characters.
        """
        limit = self._resolve_limit(max_tokens)
        max_chars = limit * CHARS_PER_TOKEN
        return text[-max_chars:] if len(text) > max_chars else text

    # ------------------------------------------------------------------
    # Packing
    # ------------------------------------------------------------------

    def pack(self, parts: List[str], max_tokens: Optional[int] = None) -> str:
        """Join *parts* with the instance separator then truncate to budget.

        Empty strings in *parts* are ignored.

        Parameters
        ----------
        parts:
            Text segments to join.
        max_tokens:
            Token budget.  Defaults to the instance *max_tokens*.

        Returns
        -------
        str
            Joined and truncated string.
        """
        limit = self._resolve_limit(max_tokens)
        joined = self._separator.join(p for p in parts if p)
        return self.truncate(joined, limit)

    def pack_priority(
        self,
        parts: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
    ) -> str:
        """Pack parts with priority scores; drop lowest-priority items first.

        Iterates parts in descending priority order, greedily accumulating
        items that fit within the budget, then re-sorts the selected items
        back into descending-priority order before joining.

        Parameters
        ----------
        parts:
            List of ``{"text": str, "priority": int}`` dicts.
            Higher *priority* values are retained first.
        max_tokens:
            Token budget.  Defaults to the instance *max_tokens*.

        Returns
        -------
        str
            Selected parts joined by the instance separator, ordered by
            descending priority.
        """
        limit = self._resolve_limit(max_tokens)
        sorted_parts = sorted(parts, key=lambda p: p.get("priority", 0), reverse=True)
        selected: List[Tuple[int, str]] = []
        used = 0
        for part in sorted_parts:
            text = part.get("text", "")
            tokens = self.count_chars(text)
            if used + tokens <= limit:
                selected.append((part.get("priority", 0), text))
                used += tokens
        selected.sort(key=lambda x: x[0], reverse=True)
        return self._separator.join(t for _, t in selected)

    def pack_chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        keep_system: bool = True,
    ) -> List[Dict[str, str]]:
        """Fit a list of chat messages within a token budget.

        Iterates from the most-recent to the oldest non-system message,
        accumulating messages until the budget is exhausted.  Stops as
        soon as a message does not fit to preserve conversational
        continuity (no gaps in the chat history).

        Parameters
        ----------
        messages:
            List of ``{"role": str, "content": str}`` dicts in
            chronological order.
        max_tokens:
            Token budget.  Defaults to the instance *max_tokens*.
        keep_system:
            When ``True`` (default), system messages are always prepended
            to the result and their token cost is deducted from the budget.

        Returns
        -------
        List[Dict[str, str]]
            Subset of *messages* that fits within the budget, in
            chronological order.
        """
        limit = self._resolve_limit(max_tokens)
        system = [m for m in messages if m.get("role") == "system"]
        others = [m for m in messages if m.get("role") != "system"]
        system_tokens = (
            sum(self.count_chars(m["content"]) for m in system) if keep_system else 0
        )
        budget = max(0, limit - system_tokens)
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
        """Split *text* into chunks that each fit within *max_tokens*.

        The last chunk may be shorter than the limit.  Returns an empty
        list for an empty *text*.

        Parameters
        ----------
        text:
            String to split.
        max_tokens:
            Maximum tokens per chunk.  Defaults to the instance
            *max_tokens*.

        Returns
        -------
        List[str]
            List of chunks, each at most ``max_tokens * CHARS_PER_TOKEN``
            characters long.
        """
        limit = self._resolve_limit(max_tokens)
        if not text:
            return []
        max_chars = max(1, limit * CHARS_PER_TOKEN)
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
        """Return the most-recent contiguous parts that fit within the budget.

        Iterates *parts* from the end (most recent) backwards, accumulating
        items until the next item would exceed the budget.

        Parameters
        ----------
        parts:
            Ordered list of text segments (oldest first).
        max_tokens:
            Token budget.  Defaults to the instance *max_tokens*.

        Returns
        -------
        List[str]
            Contiguous tail of *parts* that fits within the budget.
        """
        limit = self._resolve_limit(max_tokens)
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
