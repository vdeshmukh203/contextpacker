"""Context window packer — truncation, splitting, chat packing, sliding window."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

try:
    from typing import TypedDict
except ImportError:  # Python 3.7 compat shim (not needed for >=3.9 but harmless)
    from typing_extensions import TypedDict  # type: ignore[no-redef]

DEFAULT_MAX_TOKENS: int = 8192
CHARS_PER_TOKEN: int = 4  # standard heuristic: ~4 chars per BPE token


class MessageDict(TypedDict, total=False):
    """Shape of a single chat message."""

    role: str
    content: str


class PriorityPart(TypedDict, total=False):
    """Shape of a priority-annotated text part."""

    text: str
    priority: int


def _require_positive_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer, got {type(value).__name__}")
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer, got {value!r}")


def _require_str(value: object, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str, got {type(value).__name__}")


class Contextpacker:
    """Pack and manage context for LLM prompts.

    Parameters
    ----------
    max_tokens:
        Default token budget used by all methods when their own ``max_tokens``
        argument is omitted.  Must be a positive integer.
    separator:
        String inserted between parts when joining them (default ``"\\n\\n"``).

    Examples
    --------
    >>> cp = Contextpacker(max_tokens=512)
    >>> cp.truncate("some very long document ...")
    'some very long document ...'
    """

    def __init__(
        self,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        separator: str = "\n\n",
    ) -> None:
        _require_positive_int(max_tokens, "max_tokens")
        _require_str(separator, "separator")
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
        """String used to join multiple text parts."""
        return self._separator

    def __repr__(self) -> str:
        return (
            f"Contextpacker(max_tokens={self._max_tokens!r}, "
            f"separator={self._separator!r})"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_limit(self, max_tokens: Optional[int]) -> int:
        if max_tokens is None:
            return self._max_tokens
        _require_positive_int(max_tokens, "max_tokens")
        return max_tokens

    # ------------------------------------------------------------------
    # Token counting
    # ------------------------------------------------------------------

    def count(self, text: str) -> int:
        """Return an approximate token count using a word-aware heuristic.

        The estimate multiplies the whitespace-delimited word count by 1.3 to
        account for sub-word tokenisation (punctuation, numbers, etc.).  Empty
        text returns 0.

        Parameters
        ----------
        text:
            The input string to measure.

        Returns
        -------
        int
            Non-negative estimated token count.
        """
        _require_str(text, "text")
        words = text.split()
        if not words:
            return 0
        return max(1, math.ceil(len(words) * 1.3))

    def count_chars(self, text: str) -> int:
        """Return a character-based token estimate (``len(text) // CHARS_PER_TOKEN``).

        This is used internally for all budget calculations because it is O(1)
        and deterministic.  Empty text returns 0.

        Parameters
        ----------
        text:
            The input string to measure.

        Returns
        -------
        int
            Non-negative estimated token count.
        """
        _require_str(text, "text")
        return len(text) // CHARS_PER_TOKEN

    # ------------------------------------------------------------------
    # Truncation
    # ------------------------------------------------------------------

    def truncate(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Truncate *text* so it fits within *max_tokens*, keeping the beginning.

        Parameters
        ----------
        text:
            Source text to truncate.
        max_tokens:
            Token budget.  Defaults to the instance's ``max_tokens``.

        Returns
        -------
        str
            A prefix of *text* whose character length does not exceed
            ``max_tokens * CHARS_PER_TOKEN``.
        """
        _require_str(text, "text")
        limit = self._resolve_limit(max_tokens)
        max_chars = limit * CHARS_PER_TOKEN
        return text[:max_chars]

    def truncate_start(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Keep the *end* of *text*, dropping the beginning (oldest context first).

        Useful for trimming chat history where the most recent content is most
        relevant.

        Parameters
        ----------
        text:
            Source text to truncate.
        max_tokens:
            Token budget.  Defaults to the instance's ``max_tokens``.

        Returns
        -------
        str
            A suffix of *text* whose character length does not exceed
            ``max_tokens * CHARS_PER_TOKEN``.
        """
        _require_str(text, "text")
        limit = self._resolve_limit(max_tokens)
        max_chars = limit * CHARS_PER_TOKEN
        if len(text) <= max_chars:
            return text
        return text[-max_chars:]

    # ------------------------------------------------------------------
    # Packing
    # ------------------------------------------------------------------

    def pack(self, parts: List[str], max_tokens: Optional[int] = None) -> str:
        """Join *parts* with the instance separator and truncate to the budget.

        Parts that are empty strings are silently skipped.

        Parameters
        ----------
        parts:
            Ordered list of text fragments to combine.
        max_tokens:
            Token budget.  Defaults to the instance's ``max_tokens``.

        Returns
        -------
        str
            Joined and possibly truncated text.
        """
        if not isinstance(parts, list):
            raise TypeError(f"parts must be a list, got {type(parts).__name__}")
        limit = self._resolve_limit(max_tokens)
        joined = self._separator.join(p for p in parts if isinstance(p, str) and p)
        return self.truncate(joined, limit)

    def pack_priority(
        self,
        parts: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
    ) -> str:
        """Select and join parts by descending priority, dropping the lowest first.

        Parts are selected in priority order until the budget is exhausted.  The
        output text preserves the same descending-priority order (highest first)
        so that the most important content appears at the top.

        Parameters
        ----------
        parts:
            List of dicts, each with at least a ``"text"`` key (str) and an
            optional ``"priority"`` key (numeric, higher = more important).
        max_tokens:
            Token budget.  Defaults to the instance's ``max_tokens``.

        Returns
        -------
        str
            Separator-joined text of the selected parts.
        """
        if not isinstance(parts, list):
            raise TypeError(f"parts must be a list, got {type(parts).__name__}")
        limit = self._resolve_limit(max_tokens)

        ranked = sorted(parts, key=lambda p: p.get("priority", 0), reverse=True)
        selected: List[tuple[int, str]] = []
        used = 0
        for part in ranked:
            text = str(part.get("text", ""))
            tokens = self.count_chars(text)
            if used + tokens <= limit:
                selected.append((part.get("priority", 0), text))
                used += tokens

        # Emit in descending priority order
        selected.sort(key=lambda x: x[0], reverse=True)
        return self._separator.join(t for _, t in selected if t)

    def pack_chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        keep_system: bool = True,
    ) -> List[Dict[str, str]]:
        """Fit a chat message list within a token budget.

        System messages are optionally preserved at the front of the returned
        list.  Oldest non-system messages are dropped first when the budget
        would be exceeded.

        Parameters
        ----------
        messages:
            Ordered list of message dicts, each with ``"role"`` and
            ``"content"`` keys.
        max_tokens:
            Token budget.  Defaults to the instance's ``max_tokens``.
        keep_system:
            When ``True`` (default), system messages are always included and
            their token cost is subtracted from the budget before fitting the
            remaining messages.

        Returns
        -------
        list[dict]
            Filtered list of messages that fit within the budget, with system
            messages (if kept) prepended.
        """
        if not isinstance(messages, list):
            raise TypeError(
                f"messages must be a list, got {type(messages).__name__}"
            )
        limit = self._resolve_limit(max_tokens)

        system = [m for m in messages if m.get("role") == "system"]
        others = [m for m in messages if m.get("role") != "system"]

        system_tokens = sum(
            self.count_chars(m.get("content", "")) for m in system
        )
        budget = limit - (system_tokens if keep_system else 0)
        if budget < 0:
            budget = 0

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

        Splits are made on character boundaries.  For production use with
        natural-language text, consider splitting on sentence or paragraph
        boundaries and then calling this method on each segment.

        Parameters
        ----------
        text:
            Source text to split.
        max_tokens:
            Maximum tokens per chunk.  Defaults to the instance's
            ``max_tokens``.

        Returns
        -------
        list[str]
            Ordered list of non-empty string chunks.
        """
        _require_str(text, "text")
        limit = self._resolve_limit(max_tokens)
        max_chars = limit * CHARS_PER_TOKEN
        if not text:
            return []
        if len(text) <= max_chars:
            return [text]
        return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]

    # ------------------------------------------------------------------
    # Sliding window
    # ------------------------------------------------------------------

    def sliding_window(
        self,
        parts: List[str],
        max_tokens: Optional[int] = None,
    ) -> List[str]:
        """Return the most recent *parts* that fit within the token budget.

        Iterates *parts* from newest to oldest, accumulating until the budget
        is reached.  Once a part would exceed the budget, iteration stops, so
        parts that do not individually fit are excluded even if there is
        remaining capacity.

        Parameters
        ----------
        parts:
            Ordered list of text fragments (oldest → newest).
        max_tokens:
            Token budget.  Defaults to the instance's ``max_tokens``.

        Returns
        -------
        list[str]
            Suffix of *parts* that fits within the budget, preserving original
            order.
        """
        if not isinstance(parts, list):
            raise TypeError(f"parts must be a list, got {type(parts).__name__}")
        limit = self._resolve_limit(max_tokens)
        result: List[str] = []
        used = 0
        for part in reversed(parts):
            if not isinstance(part, str):
                continue
            t = self.count_chars(part)
            if used + t <= limit:
                result.insert(0, part)
                used += t
            else:
                break
        return result
