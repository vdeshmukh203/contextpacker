"""Context window packer — truncation, splitting, chat packing, sliding window."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

DEFAULT_MAX_TOKENS = 8192
CHARS_PER_TOKEN = 4  # standard heuristic: ~4 chars per token


class Contextpacker:
    """Pack and manage context for LLM prompts within a fixed token budget.

    Parameters
    ----------
    max_tokens:
        Default token budget used by all methods when no per-call limit is given.
    separator:
        String inserted between parts when joining them (default ``"\\n\\n"``).

    Raises
    ------
    ValueError
        If *max_tokens* is not a positive integer.
    """

    def __init__(
        self,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        separator: str = "\n\n",
    ) -> None:
        if not isinstance(max_tokens, int) or max_tokens < 1:
            raise ValueError(f"max_tokens must be a positive integer, got {max_tokens!r}")
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
        """Separator string inserted between packed parts."""
        return self._separator

    def __repr__(self) -> str:
        return (
            f"Contextpacker(max_tokens={self._max_tokens!r}, "
            f"separator={self._separator!r})"
        )

    # ------------------------------------------------------------------
    # Token counting
    # ------------------------------------------------------------------

    def count(self, text: str) -> int:
        """Approximate token count using a word-aware heuristic.

        Multiplies the word count by 1.3 to account for subword tokenization.
        Returns 0 for empty or whitespace-only strings.

        Parameters
        ----------
        text:
            Input string.

        Returns
        -------
        int
            Estimated token count (>= 0).
        """
        words = text.split()
        if not words:
            return 0
        return round(len(words) * 1.3)

    def count_chars(self, text: str) -> int:
        """Character-based token count fallback (``len(text) // 4``).

        Returns 0 for empty strings; otherwise at least 1 for any non-empty
        string, since even a single character represents some model attention.

        Parameters
        ----------
        text:
            Input string.

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
        """Truncate *text* from the end to fit within a token limit.

        Uses a character-based heuristic (``CHARS_PER_TOKEN`` chars per token).
        Returns *text* unchanged when it already fits.

        Parameters
        ----------
        text:
            Text to truncate.
        max_tokens:
            Token limit; falls back to the instance default when omitted.

        Returns
        -------
        str
            Truncated (or unchanged) text.
        """
        limit = max_tokens if max_tokens is not None else self._max_tokens
        max_chars = limit * CHARS_PER_TOKEN
        return text[:max_chars] if len(text) > max_chars else text

    def truncate_start(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Keep the END of *text*, dropping the oldest (leftmost) content first.

        Useful for preserving the most recent assistant turns in a conversation.

        Parameters
        ----------
        text:
            Text to truncate.
        max_tokens:
            Token limit; falls back to the instance default when omitted.

        Returns
        -------
        str
            Truncated (or unchanged) text.
        """
        limit = max_tokens if max_tokens is not None else self._max_tokens
        max_chars = limit * CHARS_PER_TOKEN
        return text[-max_chars:] if len(text) > max_chars else text

    # ------------------------------------------------------------------
    # Packing
    # ------------------------------------------------------------------

    def pack(self, parts: List[str], max_tokens: Optional[int] = None) -> str:
        """Join *parts* with the instance separator and truncate to fit.

        Empty strings within *parts* are ignored. The joined result is
        truncated from the end when it exceeds the token budget.

        Parameters
        ----------
        parts:
            Sequence of text strings to pack.
        max_tokens:
            Token limit; falls back to the instance default when omitted.

        Returns
        -------
        str
            Packed (and possibly truncated) text.
        """
        limit = max_tokens if max_tokens is not None else self._max_tokens
        joined = self._separator.join(p for p in parts if p)
        return self.truncate(joined, limit)

    def pack_priority(
        self,
        parts: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
    ) -> str:
        """Greedily pack parts by priority, then restore original order.

        Parts with higher ``"priority"`` values are selected first when the
        budget is tight. The final output preserves the original input order
        of the selected parts so that logical flow is maintained.

        Parameters
        ----------
        parts:
            List of dicts with keys ``"text"`` (str) and ``"priority"`` (int,
            higher = kept longer). Missing keys default to ``""`` / ``0``.
        max_tokens:
            Token limit; falls back to the instance default when omitted.

        Returns
        -------
        str
            Joined text of the selected parts in their original order.
        """
        limit = max_tokens if max_tokens is not None else self._max_tokens
        indexed = list(enumerate(parts))
        sorted_by_priority = sorted(
            indexed,
            key=lambda x: x[1].get("priority", 0),
            reverse=True,
        )
        selected_indices: List[int] = []
        used = 0
        for orig_idx, part in sorted_by_priority:
            text = part.get("text", "")
            if not text:
                continue
            tokens = self.count_chars(text)
            if used + tokens <= limit:
                selected_indices.append(orig_idx)
                used += tokens
        selected_indices.sort()  # restore original order
        return self._separator.join(parts[i].get("text", "") for i in selected_indices)

    def pack_proportional(
        self,
        parts: List[str],
        max_tokens: Optional[int] = None,
    ) -> str:
        """Pack parts with a proportional token allocation per part.

        Unlike :meth:`pack` (which truncates the concatenation from the end),
        this method gives each part a character budget proportional to its
        original length relative to all parts combined. This preserves some
        content from *every* part even when the total exceeds the budget.

        Parameters
        ----------
        parts:
            Sequence of text strings to pack.
        max_tokens:
            Token limit; falls back to the instance default when omitted.

        Returns
        -------
        str
            Joined text where each part is truncated proportionally.
        """
        limit = max_tokens if max_tokens is not None else self._max_tokens
        non_empty = [p for p in parts if p]
        if not non_empty:
            return ""
        total_chars = sum(len(p) for p in non_empty)
        # Reserve character budget for separators between parts.
        sep_chars = (len(non_empty) - 1) * len(self._separator)
        content_budget = max(0, limit * CHARS_PER_TOKEN - sep_chars)
        if total_chars <= content_budget:
            return self._separator.join(non_empty)
        result_parts = []
        for part in non_empty:
            share = len(part) / total_chars
            alloc = max(1, round(share * content_budget))
            result_parts.append(part[:alloc])
        return self._separator.join(result_parts)

    def pack_chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        keep_system: bool = True,
    ) -> List[Dict[str, str]]:
        """Fit a chat message list within a token budget.

        Iterates from the most recent message backwards, accumulating messages
        until the budget is exhausted or a message does not fit. This produces
        a **contiguous** recent window — no gaps in conversation history.

        System messages are always placed first in the returned list when
        *keep_system* is ``True`` (the default).

        Parameters
        ----------
        messages:
            List of dicts with ``"role"`` and ``"content"`` keys.
        max_tokens:
            Token limit; falls back to the instance default when omitted.
        keep_system:
            When ``True``, system messages are preserved and their token cost
            is deducted from the budget before fitting non-system messages.

        Returns
        -------
        list[dict[str, str]]
            Filtered message list that fits within the budget.
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
        """Split *text* into chunks that each fit within *max_tokens*.

        Splitting is performed on character boundaries (not word boundaries).
        Returns a single-element list when *text* already fits.

        Parameters
        ----------
        text:
            Text to split.
        max_tokens:
            Chunk size limit; falls back to the instance default when omitted.

        Returns
        -------
        list[str]
            List of chunks, each no longer than ``max_tokens * CHARS_PER_TOKEN``
            characters.
        """
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
        """Return the most recent contiguous parts that fit within the budget.

        Iterates from the last element backwards, accumulating parts until the
        next part would exceed the budget. The result is a contiguous suffix of
        the input list (no gaps).

        Parameters
        ----------
        parts:
            Ordered sequence of text strings (oldest first).
        max_tokens:
            Token limit; falls back to the instance default when omitted.

        Returns
        -------
        list[str]
            The most recent subset of *parts* that fits, in original order.
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
