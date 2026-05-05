"""Context window packer — truncation, splitting, chat packing, sliding window."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

DEFAULT_MAX_TOKENS: int = 8192
CHARS_PER_TOKEN: int = 4  # standard heuristic (≈ GPT-style tokenisation)


class Contextpacker:
    """Pack and manage context for LLM prompts.

    All methods that accept a *max_tokens* parameter use ``self.max_tokens``
    as a default, so the object can be configured once and reused across many
    calls.

    Parameters
    ----------
    max_tokens : int
        Default token budget for all operations.  Must be a positive integer.
    separator : str
        String inserted between parts when joining text fragments.

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
        if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or max_tokens <= 0:
            raise ValueError(
                f"max_tokens must be a positive integer, got {max_tokens!r}"
            )
        self._max_tokens: int = max_tokens
        self._separator: str = separator

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def max_tokens(self) -> int:
        """Default token budget used when no per-call override is supplied."""
        return self._max_tokens

    @property
    def separator(self) -> str:
        """String inserted between parts during packing."""
        return self._separator

    def __repr__(self) -> str:
        return (
            f"Contextpacker(max_tokens={self._max_tokens!r}, "
            f"separator={self._separator!r})"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_limit(self, max_tokens: Optional[int]) -> int:
        """Return per-call limit or fall back to the instance default."""
        if max_tokens is None:
            return self._max_tokens
        if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or max_tokens <= 0:
            raise ValueError(
                f"max_tokens must be a positive integer, got {max_tokens!r}"
            )
        return max_tokens

    # ------------------------------------------------------------------
    # Token counting
    # ------------------------------------------------------------------

    def count(self, text: str) -> int:
        """Approximate token count using a word-aware heuristic.

        Counts whitespace-separated words and multiplies by 1.3 to account
        for sub-word tokenisation.  Returns 0 for empty or whitespace-only
        strings.

        Parameters
        ----------
        text : str
            Input text.

        Returns
        -------
        int
            Estimated token count (>= 0).
        """
        words = text.split()
        return round(len(words) * 1.3)

    def count_chars(self, text: str) -> int:
        """Character-based token estimate (``len(text) // CHARS_PER_TOKEN``).

        Uses the widely-cited 4-characters-per-token heuristic.  Returns 0
        for strings shorter than *CHARS_PER_TOKEN* characters, including
        empty strings.  Used internally for all budget arithmetic.

        Parameters
        ----------
        text : str
            Input text.

        Returns
        -------
        int
            Estimated token count (>= 0).
        """
        return len(text) // CHARS_PER_TOKEN

    # ------------------------------------------------------------------
    # Truncation
    # ------------------------------------------------------------------

    def truncate(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Truncate *text* from the end to fit within *max_tokens*.

        Keeps the **beginning** of *text*; the excess tail is discarded.
        Use :meth:`truncate_start` to instead keep the tail.

        Parameters
        ----------
        text : str
            Text to truncate.
        max_tokens : int, optional
            Token limit.  Defaults to ``self.max_tokens``.

        Returns
        -------
        str
            Truncated (or unchanged) text.
        """
        limit = self._resolve_limit(max_tokens)
        max_chars = limit * CHARS_PER_TOKEN
        return text[:max_chars]

    def truncate_start(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Truncate *text* from the beginning to fit within *max_tokens*.

        Keeps the **end** of *text*, discarding the oldest (leading) content.
        Useful for chat history where the most-recent content is at the tail.

        Parameters
        ----------
        text : str
            Text to truncate.
        max_tokens : int, optional
            Token limit.  Defaults to ``self.max_tokens``.

        Returns
        -------
        str
            Truncated (or unchanged) text.
        """
        limit = self._resolve_limit(max_tokens)
        max_chars = limit * CHARS_PER_TOKEN
        return text[-max_chars:] if len(text) > max_chars else text

    # ------------------------------------------------------------------
    # Packing
    # ------------------------------------------------------------------

    def pack(self, parts: List[str], max_tokens: Optional[int] = None) -> str:
        """Join *parts* with the instance separator and truncate to fit.

        Empty strings in *parts* are silently ignored before joining.

        Parameters
        ----------
        parts : list of str
            Text fragments to concatenate.
        max_tokens : int, optional
            Token limit.  Defaults to ``self.max_tokens``.

        Returns
        -------
        str
            Packed (and possibly truncated) text.
        """
        limit = self._resolve_limit(max_tokens)
        joined = self._separator.join(p for p in parts if p)
        return self.truncate(joined, limit)

    def pack_priority(
        self,
        parts: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
    ) -> str:
        """Pack parts with priority scores, dropping lowest-priority first.

        Greedily selects parts in descending priority order until the token
        budget is exhausted.  The output joins the selected parts ordered by
        priority (highest first).

        Parameters
        ----------
        parts : list of dict
            Each element must have the keys:

            - ``"text"`` (str) — the text fragment.
            - ``"priority"`` (int) — higher values are retained when the
              budget is tight.

        max_tokens : int, optional
            Token limit.  Defaults to ``self.max_tokens``.

        Returns
        -------
        str
            Selected parts joined by the instance separator, in descending
            priority order.
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

        System messages are handled separately and (optionally) always
        retained.  Among the remaining messages the **most recent** are
        preferred: the algorithm walks backward through the list and stops
        as soon as adding the next (older) message would exceed the budget,
        yielding a contiguous most-recent window.

        Parameters
        ----------
        messages : list of dict
            Each element must contain:

            - ``"role"`` (str) — e.g. ``"system"``, ``"user"``,
              ``"assistant"``.
            - ``"content"`` (str) — message text.

        max_tokens : int, optional
            Token limit.  Defaults to ``self.max_tokens``.
        keep_system : bool
            When *True* (default), system messages are prepended to the
            result and their token cost is deducted from the budget before
            selecting non-system messages.

        Returns
        -------
        list of dict
            A filtered subset of *messages* in their original order.
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
        """Split *text* into chunks that each fit within *max_tokens*.

        The split is purely character-based with no attempt to align to
        word or sentence boundaries.  An empty *text* is returned as a
        single-element list containing the empty string.

        Parameters
        ----------
        text : str
            Text to split.
        max_tokens : int, optional
            Per-chunk token limit.  Defaults to ``self.max_tokens``.

        Returns
        -------
        list of str
            List of chunks, each at most ``max_tokens * CHARS_PER_TOKEN``
            characters long.
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
        """Return the most recent *parts* that fit within the token budget.

        Iterates *parts* in reverse order (newest first) and accumulates
        items until the next item would overflow the budget.  The result is
        a **contiguous suffix** of *parts* in their original order.

        Parameters
        ----------
        parts : list of str
            Ordered list of text fragments (oldest first).
        max_tokens : int, optional
            Token budget.  Defaults to ``self.max_tokens``.

        Returns
        -------
        list of str
            A (possibly empty) contiguous suffix of *parts*.
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
