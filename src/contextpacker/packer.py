"""Context window packer — truncation, splitting, chat packing, sliding window."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

DEFAULT_MAX_TOKENS: int = 8192
CHARS_PER_TOKEN: int = 4  # standard English-text heuristic (1 token ≈ 4 chars)


class Contextpacker:
    """Pack and manage content for LLM context windows.

    All operations share a single char-based token estimate
    (``len(text) // CHARS_PER_TOKEN``) so that ``count()``, ``truncate()``,
    ``pack()``, and the rest of the API report *consistent* numbers.

    Parameters
    ----------
    max_tokens : int, optional
        Default token budget for all operations, by default 8192.
    separator : str, optional
        String used to join parts when packing, by default ``"\\n\\n"``.

    Raises
    ------
    ValueError
        If *max_tokens* is not a positive integer.

    Examples
    --------
    >>> cp = Contextpacker(max_tokens=4096)
    >>> packed = cp.pack(["system prompt", "user message", "reply"])
    >>> cp.count(packed)
    10
    """

    def __init__(
        self,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        separator: str = "\n\n",
    ) -> None:
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            raise ValueError(
                f"max_tokens must be a positive integer, got {max_tokens!r}"
            )
        if not isinstance(separator, str):
            raise TypeError(
                f"separator must be a str, got {type(separator).__name__}"
            )
        self._max_tokens = max_tokens
        self._separator = separator

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def max_tokens(self) -> int:
        """Default token budget for this instance."""
        return self._max_tokens

    @max_tokens.setter
    def max_tokens(self, value: int) -> None:
        if not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"max_tokens must be a positive integer, got {value!r}"
            )
        self._max_tokens = value

    @property
    def separator(self) -> str:
        """Part separator used when joining packed content."""
        return self._separator

    @separator.setter
    def separator(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError(
                f"separator must be a str, got {type(value).__name__}"
            )
        self._separator = value

    def __repr__(self) -> str:
        return (
            f"Contextpacker(max_tokens={self._max_tokens!r}, "
            f"separator={self._separator!r})"
        )

    # ------------------------------------------------------------------
    # Token counting
    # ------------------------------------------------------------------

    def count(self, text: str) -> int:
        """Estimate token count using a character-based heuristic.

        Uses the standard approximation of one token per four characters,
        consistent with all budget arithmetic in this library.  Returns
        ``0`` for empty input.

        Parameters
        ----------
        text : str
            Input text to estimate.

        Returns
        -------
        int
            Estimated token count (>= 0).

        Examples
        --------
        >>> Contextpacker().count("Hello, world!")
        3
        """
        if not text:
            return 0
        return len(text) // CHARS_PER_TOKEN

    def count_chars(self, text: str) -> int:
        """Character-based token count — alias for :meth:`count`.

        Kept for backward compatibility.

        Parameters
        ----------
        text : str
            Input text to estimate.

        Returns
        -------
        int
            Estimated token count (>= 0).
        """
        return self.count(text)

    def count_words(self, text: str) -> int:
        """Estimate token count using a word-aware heuristic (words × 1.3).

        More accurate than :meth:`count` for natural prose; less reliable
        for repetitive or non-alphabetic content.  Returns ``0`` for
        empty input.

        Parameters
        ----------
        text : str
            Input text to estimate.

        Returns
        -------
        int
            Estimated token count (>= 0).
        """
        if not text:
            return 0
        words = text.split()
        return max(1, round(len(words) * 1.3)) if words else 0

    def fits(self, text: str, max_tokens: Optional[int] = None) -> bool:
        """Return ``True`` if *text* fits within the token budget.

        Parameters
        ----------
        text : str
            Text to test.
        max_tokens : int, optional
            Token budget; defaults to instance ``max_tokens``.

        Returns
        -------
        bool
        """
        limit = self._resolve_limit(max_tokens)
        return self.count(text) <= limit

    # ------------------------------------------------------------------
    # Truncation
    # ------------------------------------------------------------------

    def truncate(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Truncate *text* from the end to fit within a token limit.

        Parameters
        ----------
        text : str
            Text to truncate.
        max_tokens : int, optional
            Token limit; defaults to instance ``max_tokens``.

        Returns
        -------
        str
            Truncated text (never longer than the input).

        Raises
        ------
        ValueError
            If *max_tokens* is provided but is not a positive integer.

        Examples
        --------
        >>> cp = Contextpacker(max_tokens=5)
        >>> len(cp.truncate("a" * 100))
        20
        """
        limit = self._resolve_limit(max_tokens)
        max_chars = limit * CHARS_PER_TOKEN
        return text[:max_chars] if len(text) > max_chars else text

    def truncate_start(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Truncate *text* from the start, keeping the most recent content.

        Parameters
        ----------
        text : str
            Text to truncate.
        max_tokens : int, optional
            Token limit; defaults to instance ``max_tokens``.

        Returns
        -------
        str
            Tail portion of *text* that fits within the budget.

        Raises
        ------
        ValueError
            If *max_tokens* is provided but is not a positive integer.
        """
        limit = self._resolve_limit(max_tokens)
        max_chars = limit * CHARS_PER_TOKEN
        return text[-max_chars:] if len(text) > max_chars else text

    # ------------------------------------------------------------------
    # Packing
    # ------------------------------------------------------------------

    def pack(self, parts: List[str], max_tokens: Optional[int] = None) -> str:
        """Join text parts and truncate the result to fit the token budget.

        Empty and falsy parts are skipped before joining.  If all parts
        fit within the budget the joined string is returned unchanged.

        Parameters
        ----------
        parts : list of str
            Text fragments to pack.
        max_tokens : int, optional
            Token limit; defaults to instance ``max_tokens``.

        Returns
        -------
        str
            Joined and possibly-truncated text.

        Raises
        ------
        ValueError
            If *max_tokens* is provided but is not a positive integer.
        """
        limit = self._resolve_limit(max_tokens)
        joined = self._separator.join(p for p in parts if p)
        return self.truncate(joined, limit)

    def pack_priority(
        self,
        parts: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
        preserve_order: bool = False,
    ) -> str:
        """Pack parts greedily by priority, dropping lowest-priority first.

        Iterates parts from highest to lowest ``"priority"`` value, adding
        each part when it fits within the remaining budget.  By default the
        output is emitted in priority-descending order; set
        *preserve_order* to ``True`` to restore the original list order.

        Parameters
        ----------
        parts : list of dict
            Each element must have a ``"text"`` key (str) and may have a
            ``"priority"`` key (int or float; higher = kept first).
            Entries without ``"priority"`` default to ``0``.
        max_tokens : int, optional
            Token limit; defaults to instance ``max_tokens``.
        preserve_order : bool, optional
            When ``True``, selected parts are emitted in their original
            list order rather than priority order.

        Returns
        -------
        str
            Packed text built from the highest-priority parts that fit.

        Raises
        ------
        ValueError
            If any element of *parts* is missing a ``"text"`` key, or if
            *max_tokens* is provided but is not a positive integer.

        Examples
        --------
        >>> cp = Contextpacker(max_tokens=20)
        >>> parts = [{"text": "low", "priority": 1},
        ...          {"text": "IMPORTANT", "priority": 10}]
        >>> cp.pack_priority(parts)
        'IMPORTANT\\n\\nlow'
        """
        limit = self._resolve_limit(max_tokens)
        for i, part in enumerate(parts):
            if "text" not in part:
                raise ValueError(f"parts[{i}] is missing required key 'text'")

        indexed = list(enumerate(parts))
        sorted_parts = sorted(
            indexed, key=lambda x: x[1].get("priority", 0), reverse=True
        )

        selected_indices: List[int] = []
        used = 0
        for idx, part in sorted_parts:
            text = part["text"]
            tokens = self.count(text)
            if used + tokens <= limit:
                selected_indices.append(idx)
                used += tokens

        if preserve_order:
            selected_indices.sort()

        texts = [parts[i]["text"] for i in selected_indices]
        return self._separator.join(t for t in texts if t)

    def pack_chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        keep_system: bool = True,
    ) -> List[Dict[str, str]]:
        """Fit a chat message list within a token budget.

        System messages are always placed first when *keep_system* is
        ``True``, and their token cost is reserved from the budget.  The
        most recent non-system messages are retained; oldest ones are
        dropped until the total fits.

        Parameters
        ----------
        messages : list of dict
            Each element must have ``"role"`` and ``"content"`` keys.
        max_tokens : int, optional
            Token limit; defaults to instance ``max_tokens``.
        keep_system : bool, optional
            When ``True`` (default), system messages are unconditionally
            retained and their tokens are deducted from the budget.

        Returns
        -------
        list of dict
            A subset of *messages* that fits within the token budget,
            preserving the original ordering.

        Raises
        ------
        ValueError
            If any element of *messages* is missing ``"role"`` or
            ``"content"`` keys, or if *max_tokens* is invalid.
        """
        limit = self._resolve_limit(max_tokens)
        for i, msg in enumerate(messages):
            if "role" not in msg or "content" not in msg:
                raise ValueError(
                    f"messages[{i}] must have both 'role' and 'content' keys"
                )

        system = [m for m in messages if m.get("role") == "system"]
        others = [m for m in messages if m.get("role") != "system"]
        system_tokens = sum(self.count(m["content"]) for m in system)
        budget = limit - (system_tokens if keep_system else 0)

        result: List[Dict[str, str]] = []
        used = 0
        for msg in reversed(others):
            t = self.count(msg["content"])
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
        """Split *text* into chunks that each fit within the token limit.

        Splits are made at character boundaries.  For word- or
        sentence-boundary-aware chunking, pre-process the text with an
        external splitter before calling this method.

        Parameters
        ----------
        text : str
            Text to split.
        max_tokens : int, optional
            Maximum tokens per chunk; defaults to instance ``max_tokens``.

        Returns
        -------
        list of str
            Non-empty chunks each within the token limit.  Returns an
            empty list when *text* is empty or falsy.

        Raises
        ------
        ValueError
            If *max_tokens* is provided but is not a positive integer.
        """
        limit = self._resolve_limit(max_tokens)
        max_chars = limit * CHARS_PER_TOKEN
        if not text:
            return []
        if len(text) <= max_chars:
            return [text]
        return [text[i: i + max_chars] for i in range(0, len(text), max_chars)]

    # ------------------------------------------------------------------
    # Sliding window
    # ------------------------------------------------------------------

    def sliding_window(
        self,
        parts: List[str],
        max_tokens: Optional[int] = None,
    ) -> List[str]:
        """Return the most-recent parts that fit within the token budget.

        Iterates *parts* from newest to oldest, accumulating items until
        the budget is exhausted or a part that cannot fit is encountered.
        The returned list preserves the original order of *parts*.

        Parameters
        ----------
        parts : list of str
            Ordered text fragments, oldest first.
        max_tokens : int, optional
            Token limit; defaults to instance ``max_tokens``.

        Returns
        -------
        list of str
            Tail of *parts* that fits within the budget.

        Raises
        ------
        ValueError
            If *max_tokens* is provided but is not a positive integer.
        """
        limit = self._resolve_limit(max_tokens)
        result: List[str] = []
        used = 0
        for part in reversed(parts):
            t = self.count(part)
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
        """Return *max_tokens* if given, otherwise the instance default.

        Raises
        ------
        ValueError
            If *max_tokens* is provided but is not a positive integer.
        """
        if max_tokens is None:
            return self._max_tokens
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            raise ValueError(
                f"max_tokens must be a positive integer, got {max_tokens!r}"
            )
        return max_tokens
