"""Context window packer — truncation, splitting, chat packing, sliding window.

``CHARS_PER_TOKEN = 4`` is the industry-standard heuristic for English prose
(GPT-2/3 tokenisers average ~4 characters per token).  All budget enforcement
uses this constant for speed and consistency.  :meth:`Contextpacker.count` uses
a complementary word-based heuristic and is provided for informational display
only; it is *not* used internally for budget arithmetic.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

DEFAULT_MAX_TOKENS: int = 8192
CHARS_PER_TOKEN: int = 4  # chars per token (standard heuristic for English)


class Contextpacker:
    """Pack and manage context for LLM prompts within a token budget.

    All budget enforcement is character-based using the rule
    ``token_estimate = len(text) // CHARS_PER_TOKEN`` (where
    ``CHARS_PER_TOKEN = 4``).  This makes arithmetic fast, deterministic, and
    independent of any external tokeniser library.

    Parameters
    ----------
    max_tokens:
        Default token budget applied when individual method calls do not
        supply their own *max_tokens* argument.  Must be a positive integer.
    separator:
        String inserted between parts when joining text (default ``"\\n\\n"``).

    Raises
    ------
    ValueError
        If *max_tokens* is not a positive integer.

    Examples
    --------
    >>> cp = Contextpacker(max_tokens=4096)
    >>> cp.pack(["system prompt", "user message", "assistant reply"])
    'system prompt\\n\\nuser message\\n\\nassistant reply'
    """

    def __init__(self, max_tokens: int = DEFAULT_MAX_TOKENS, separator: str = "\n\n") -> None:
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            raise ValueError(f"max_tokens must be a positive integer, got {max_tokens!r}")
        self._max_tokens: int = max_tokens
        self._separator: str = separator

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def max_tokens(self) -> int:
        """Default token budget for this instance."""
        return self._max_tokens

    @property
    def separator(self) -> str:
        """Separator string used when joining packed parts."""
        return self._separator

    # ------------------------------------------------------------------
    # Token counting
    # ------------------------------------------------------------------

    def count(self, text: str) -> int:
        """Approximate token count using a word-aware heuristic.

        Applies the rule-of-thumb that an English word produces ~1.3 tokens
        on average.  Suitable for rough estimates and display; use
        :meth:`count_chars` for budget enforcement, which is faster and
        consistent with all truncation operations.

        Parameters
        ----------
        text:
            Input string to count.

        Returns
        -------
        int
            Estimated token count; ``0`` for an empty string.
        """
        if not text:
            return 0
        words = text.split()
        return max(1, round(len(words) * 1.3))

    def count_chars(self, text: str) -> int:
        """Char-based token estimate: ``len(text) // CHARS_PER_TOKEN``.

        This is the method used internally by all budget-enforcement
        operations (truncation, packing, splitting, sliding window).

        Parameters
        ----------
        text:
            Input string to count.

        Returns
        -------
        int
            Estimated token count; ``0`` for an empty string.
        """
        if not text:
            return 0
        return max(1, len(text) // CHARS_PER_TOKEN)

    # ------------------------------------------------------------------
    # Truncation
    # ------------------------------------------------------------------

    def truncate(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Truncate *text* from the end to fit within *max_tokens*.

        Parameters
        ----------
        text:
            Text to truncate.
        max_tokens:
            Token limit; uses the instance default when ``None``.

        Returns
        -------
        str
            Possibly-truncated text (unchanged when already within budget).

        Raises
        ------
        ValueError
            If the resolved *max_tokens* is not a positive integer.
        """
        limit = self._resolve_limit(max_tokens)
        max_chars = limit * CHARS_PER_TOKEN
        return text[:max_chars] if len(text) > max_chars else text

    def truncate_start(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Keep the END of *text*, dropping the oldest content first.

        Useful for retaining the most-recent portion of a long context when
        the beginning (e.g. old conversation turns) is less important.

        Parameters
        ----------
        text:
            Text to truncate.
        max_tokens:
            Token limit; uses the instance default when ``None``.

        Returns
        -------
        str
            Tail of *text* that fits within the budget (unchanged when
            already within budget).

        Raises
        ------
        ValueError
            If the resolved *max_tokens* is not a positive integer.
        """
        limit = self._resolve_limit(max_tokens)
        max_chars = limit * CHARS_PER_TOKEN
        return text[-max_chars:] if len(text) > max_chars else text

    # ------------------------------------------------------------------
    # Packing
    # ------------------------------------------------------------------

    def pack(self, parts: List[str], max_tokens: Optional[int] = None) -> str:
        """Join *parts* with the separator and truncate to fit the budget.

        Empty strings in *parts* are silently ignored before joining.

        Parameters
        ----------
        parts:
            List of text segments to join.
        max_tokens:
            Token limit; uses the instance default when ``None``.

        Returns
        -------
        str
            Joined and possibly-truncated text.

        Raises
        ------
        ValueError
            If the resolved *max_tokens* is not a positive integer.
        """
        limit = self._resolve_limit(max_tokens)
        joined = self._separator.join(p for p in parts if p)
        return self.truncate(joined, limit)

    def pack_priority(
        self,
        parts: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
    ) -> str:
        """Pack parts by priority score, dropping the lowest-priority first.

        Parts are selected greedily from highest to lowest priority until
        the budget is exhausted.  Parts that share the same priority are
        included in their original list order (stable sort).  The final
        output also preserves the original list order of all selected parts,
        so structure is deterministic regardless of priority values.

        Parameters
        ----------
        parts:
            List of dicts, each containing:

            * ``"text"`` (*str*) — content to include.
            * ``"priority"`` (*int* or *float*, optional, default ``0``) —
              higher values are selected preferentially.

        max_tokens:
            Token limit; uses the instance default when ``None``.

        Returns
        -------
        str
            Selected parts joined by the separator, in original list order.

        Raises
        ------
        ValueError
            If the resolved *max_tokens* is not a positive integer.
        """
        limit = self._resolve_limit(max_tokens)
        # Pair each part with its original index for stable ordering later.
        indexed = sorted(
            enumerate(parts),
            key=lambda ip: ip[1].get("priority", 0),
            reverse=True,
        )
        selected_indices: List[int] = []
        used = 0
        for original_idx, part in indexed:
            text = part.get("text", "")
            tokens = self.count_chars(text)
            if used + tokens <= limit:
                selected_indices.append(original_idx)
                used += tokens
        # Restore original list order before joining.
        selected_indices.sort()
        return self._separator.join(parts[i].get("text", "") for i in selected_indices)

    def pack_chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        keep_system: bool = True,
    ) -> List[Dict[str, str]]:
        """Fit a chat message list within a token budget.

        Removes the oldest non-system messages first until the conversation
        fits within *max_tokens*.  System messages (``"role": "system"``) are
        always preserved at the front of the result when *keep_system* is
        ``True``.

        Parameters
        ----------
        messages:
            List of message dicts with ``"role"`` and ``"content"`` keys.
            Missing keys are treated as empty strings.
        max_tokens:
            Token limit; uses the instance default when ``None``.
        keep_system:
            When ``True`` (default), system messages are always included and
            their token cost is subtracted from the budget before fitting
            non-system messages.

        Returns
        -------
        List[Dict[str, str]]
            Trimmed message list; system messages appear first.

        Raises
        ------
        ValueError
            If the resolved *max_tokens* is not a positive integer.
        """
        limit = self._resolve_limit(max_tokens)
        system: List[Dict[str, str]] = [m for m in messages if m.get("role") == "system"]
        others: List[Dict[str, str]] = [m for m in messages if m.get("role") != "system"]
        system_tokens = sum(self.count_chars(m.get("content", "")) for m in system)
        budget = limit - (system_tokens if keep_system else 0)
        result: List[Dict[str, str]] = []
        used = 0
        for msg in reversed(others):
            t = self.count_chars(msg.get("content", ""))
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

        Splitting is character-based; chunks may fall in the middle of a word.
        If *text* already fits within the budget it is returned as a
        single-element list.

        Parameters
        ----------
        text:
            Text to split.
        max_tokens:
            Maximum tokens per chunk; uses the instance default when ``None``.

        Returns
        -------
        List[str]
            Ordered list of chunks.

        Raises
        ------
        ValueError
            If the resolved *max_tokens* is not a positive integer.
        """
        limit = self._resolve_limit(max_tokens)
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
        """Return the most-recent parts that fit within the token budget.

        Iterates *parts* from newest (last) to oldest (first), accumulating
        parts until the budget is exhausted.  Stops as soon as one part does
        not fit, so the result is always a contiguous suffix of *parts*.

        Parameters
        ----------
        parts:
            Ordered list of text segments (oldest first).
        max_tokens:
            Token limit; uses the instance default when ``None``.

        Returns
        -------
        List[str]
            The most-recent contiguous suffix of *parts* that fits within
            the budget, preserving original order.

        Raises
        ------
        ValueError
            If the resolved *max_tokens* is not a positive integer.
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_limit(self, max_tokens: Optional[int]) -> int:
        """Return a validated token limit.

        Uses *max_tokens* when provided, otherwise falls back to the instance
        default.  Raises :exc:`ValueError` for non-positive values.
        """
        limit = max_tokens if max_tokens is not None else self._max_tokens
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError(f"max_tokens must be a positive integer, got {limit!r}")
        return limit
