"""Context window packer — truncation, splitting, chat packing, sliding window."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

DEFAULT_MAX_TOKENS: int = 8192
CHARS_PER_TOKEN: int = 4  # standard heuristic (1 token ≈ 4 characters)


class Contextpacker:
    """Pack and manage content for LLM prompt context windows.

    Provides token-aware utilities for truncating, selecting, and assembling
    heterogeneous content (chat history, retrieved documents, system instructions)
    so the resulting prompt fits within a model's token budget.

    Token counting uses character-based heuristics (``CHARS_PER_TOKEN = 4``) that
    avoid a hard dependency on any specific tokenizer.  The public :meth:`count`
    method offers a word-aware variant that may be more accurate for plain prose,
    while all internal budget arithmetic uses :meth:`count_chars` for consistency
    with the character-slice truncation operations.

    Parameters
    ----------
    max_tokens : int
        Default token budget applied when a method is called without an explicit
        *max_tokens* argument.  Must be a positive integer.
    separator : str
        String used to join multiple text parts in :meth:`pack` and
        :meth:`pack_priority`.

    Examples
    --------
    >>> cp = Contextpacker(max_tokens=4096)
    >>> packed = cp.pack(["system prompt", "user message", "retrieved doc"])
    >>> cp.count(packed)
    5
    """

    def __init__(
        self,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        separator: str = "\n\n",
    ) -> None:
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            raise ValueError(f"max_tokens must be a positive integer; got {max_tokens!r}")
        self._max_tokens = max_tokens
        self._separator = separator

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def max_tokens(self) -> int:
        """Default token budget for this packer instance."""
        return self._max_tokens

    @property
    def separator(self) -> str:
        """Separator string used when joining multiple text parts."""
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

        Multiplies the word count by 1.3 to account for sub-word tokenisation.
        Returns 0 for empty or whitespace-only input.

        Parameters
        ----------
        text : str
            Input text to estimate.

        Returns
        -------
        int
            Estimated token count (≥ 0).

        Notes
        -----
        This method is exposed for user-facing estimates.  All internal budget
        arithmetic uses :meth:`count_chars` to stay consistent with character-
        based truncation.
        """
        if not text or not text.strip():
            return 0
        words = text.split()
        return round(len(words) * 1.3)

    def count_chars(self, text: str) -> int:
        """Approximate token count using a character-based heuristic (chars / 4).

        Returns 0 for empty input.  This is the method used internally by all
        packing and selection operations so that budget arithmetic remains
        consistent with character-slice truncation.

        Parameters
        ----------
        text : str
            Input text to estimate.

        Returns
        -------
        int
            Estimated token count (≥ 0).
        """
        if not text:
            return 0
        return max(1, len(text) // CHARS_PER_TOKEN)

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    def _resolve_limit(self, max_tokens: Optional[int]) -> int:
        """Return *max_tokens* if given, else the instance default."""
        if max_tokens is None:
            return self._max_tokens
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            raise ValueError(f"max_tokens must be a positive integer; got {max_tokens!r}")
        return max_tokens

    # ------------------------------------------------------------------
    # Truncation
    # ------------------------------------------------------------------

    def truncate(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Truncate text to fit within a token budget, keeping the beginning.

        Parameters
        ----------
        text : str
            Text to truncate.
        max_tokens : int, optional
            Token limit.  Defaults to the instance ``max_tokens``.

        Returns
        -------
        str
            The (possibly truncated) text.
        """
        limit = self._resolve_limit(max_tokens)
        max_chars = limit * CHARS_PER_TOKEN
        return text[:max_chars] if len(text) > max_chars else text

    def truncate_start(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Truncate text to fit within a token budget, keeping the END.

        Useful for dropping the oldest portion of a long transcript while
        retaining the most recent context.

        Parameters
        ----------
        text : str
            Text to truncate.
        max_tokens : int, optional
            Token limit.  Defaults to the instance ``max_tokens``.

        Returns
        -------
        str
            The (possibly truncated) text, taken from the end.
        """
        limit = self._resolve_limit(max_tokens)
        max_chars = limit * CHARS_PER_TOKEN
        return text[-max_chars:] if len(text) > max_chars else text

    # ------------------------------------------------------------------
    # Packing
    # ------------------------------------------------------------------

    def pack(self, parts: List[str], max_tokens: Optional[int] = None) -> str:
        """Join text parts with the instance separator and truncate to fit.

        Empty strings in *parts* are silently skipped before joining.

        Parameters
        ----------
        parts : list of str
            Text segments to combine.
        max_tokens : int, optional
            Token limit.  Defaults to the instance ``max_tokens``.

        Returns
        -------
        str
            Combined (and possibly truncated) text.
        """
        limit = self._resolve_limit(max_tokens)
        joined = self._separator.join(p for p in parts if p)
        return self.truncate(joined, limit)

    def pack_priority(
        self,
        parts: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
    ) -> str:
        """Select and pack parts by priority score, preserving document order.

        Parts are selected greedily from highest to lowest priority until the
        token budget is exhausted.  The selected parts are then joined in their
        **original input order** (not priority order), so the semantic structure
        of the document is maintained.

        Parameters
        ----------
        parts : list of dict
            Each dict must contain:

            - ``"text"`` (*str*): the content to include.
            - ``"priority"`` (*int* or *float*, optional): higher values are
              retained preferentially.  Defaults to ``0``.

        max_tokens : int, optional
            Token limit.  Defaults to the instance ``max_tokens``.

        Returns
        -------
        str
            Selected parts joined by the instance separator in original order.
        """
        limit = self._resolve_limit(max_tokens)
        # Select greedily by descending priority
        indexed = sorted(
            enumerate(parts),
            key=lambda x: x[1].get("priority", 0),
            reverse=True,
        )
        selected_indices: set = set()
        used = 0
        for idx, part in indexed:
            text = part.get("text", "")
            tokens = self.count_chars(text)
            if used + tokens <= limit:
                selected_indices.add(idx)
                used += tokens
        # Emit in original document order
        return self._separator.join(
            parts[i].get("text", "")
            for i in range(len(parts))
            if i in selected_indices
        )

    def pack_chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        keep_system: bool = True,
    ) -> List[Dict[str, str]]:
        """Fit a list of chat messages within a token budget.

        Iterates from the most-recent message backwards, accumulating messages
        until the budget is exhausted.  This preserves a contiguous window of
        the most recent conversation.  System messages are handled separately
        and, when *keep_system* is ``True``, are always prepended to the result
        regardless of budget pressure.

        Parameters
        ----------
        messages : list of dict
            Each dict must contain:

            - ``"role"`` (*str*): e.g. ``"system"``, ``"user"``, ``"assistant"``.
            - ``"content"`` (*str*): the message text.

        max_tokens : int, optional
            Token limit.  Defaults to the instance ``max_tokens``.
        keep_system : bool
            When ``True`` (default), system messages are preserved and their
            token cost is deducted from the budget available to other messages.

        Returns
        -------
        list of dict
            Subset of *messages* that fits within the budget, with system
            messages prepended when *keep_system* is ``True``.
        """
        limit = self._resolve_limit(max_tokens)
        system = [m for m in messages if m.get("role") == "system"]
        others = [m for m in messages if m.get("role") != "system"]
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
        """Split text into chunks that each fit within the token budget.

        Parameters
        ----------
        text : str
            Text to split.
        max_tokens : int, optional
            Per-chunk token limit.  Defaults to the instance ``max_tokens``.

        Returns
        -------
        list of str
            Non-overlapping chunks, each at most *max_tokens* tokens.  Returns
            a list containing the original text when it already fits.
        """
        limit = self._resolve_limit(max_tokens)
        max_chars = limit * CHARS_PER_TOKEN
        if not text or len(text) <= max_chars:
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

        Iterates *parts* from the end, accumulating items until the budget is
        exhausted.  Older items that do not fit are dropped entirely.

        Parameters
        ----------
        parts : list of str
            Ordered sequence of text segments (oldest first).
        max_tokens : int, optional
            Token limit.  Defaults to the instance ``max_tokens``.

        Returns
        -------
        list of str
            Suffix of *parts* (in original order) that fits within the budget.
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
