"""Context window packer — truncation, splitting, chat packing, sliding window."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

DEFAULT_MAX_TOKENS = 8192
CHARS_PER_TOKEN = 4  # widely-used heuristic: ~4 UTF-8 characters per token


class Contextpacker:
    """Pack and manage content for LLM prompts within a token budget.

    All token counts are *estimates* based on lightweight character- or
    word-level heuristics and will differ from the exact counts produced by
    a model-specific tokenizer (e.g. tiktoken or HuggingFace tokenizers).
    The heuristics are calibrated for English prose; adjust ``max_tokens``
    conservatively for other languages or heavily formatted text.

    Parameters
    ----------
    max_tokens : int
        Default token budget applied by every method that accepts
        ``max_tokens``. Must be a positive integer.
    separator : str
        String used to join parts in :meth:`pack` and
        :meth:`pack_priority`. Defaults to ``"\\n\\n"``.

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
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            raise ValueError(
                f"max_tokens must be a positive integer, got {max_tokens!r}"
            )
        self._max_tokens = max_tokens
        self._separator = separator

    # ------------------------------------------------------------------
    # Token counting
    # ------------------------------------------------------------------

    def count(self, text: str) -> int:
        """Approximate token count using a word-aware heuristic.

        Estimates tokens as ``round(word_count * 1.3)``, which accounts for
        sub-word tokenization common in BPE-based models (e.g. GPT-4, LLaMA).
        Returns 0 for empty or whitespace-only text.

        Parameters
        ----------
        text : str
            Input text.

        Returns
        -------
        int
            Estimated token count (≥ 0).

        Examples
        --------
        >>> packer = Contextpacker()
        >>> packer.count("Hello world")
        3
        >>> packer.count("")
        0
        """
        if not text or not text.strip():
            return 0
        return round(len(text.split()) * 1.3)

    def count_chars(self, text: str) -> int:
        """Character-based token count (``len(text) // 4``).

        A lightweight alternative to :meth:`count` that avoids word-splitting.
        The 4-characters-per-token constant is the standard rule of thumb used
        by OpenAI and other providers for English text. Returns 0 for empty
        text.

        Parameters
        ----------
        text : str
            Input text.

        Returns
        -------
        int
            Estimated token count (≥ 0).
        """
        if not text:
            return 0
        return len(text) // CHARS_PER_TOKEN

    # ------------------------------------------------------------------
    # Truncation
    # ------------------------------------------------------------------

    def truncate(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Truncate text from the end to fit within a token limit.

        Keeps the *beginning* of the text. To retain the newest content
        (i.e. keep the *end*), use :meth:`truncate_start`.

        Parameters
        ----------
        text : str
            Input text.
        max_tokens : int, optional
            Token limit; defaults to :attr:`max_tokens`.

        Returns
        -------
        str
            Text clipped to at most *max_tokens* tokens.
        """
        limit = self._resolve_limit(max_tokens)
        max_chars = limit * CHARS_PER_TOKEN
        return text[:max_chars] if len(text) > max_chars else text

    def truncate_start(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Keep the end of text, dropping the oldest content first.

        Useful when ``text`` is an ordered sequence where the most recent
        content appears at the end (e.g. a serialised conversation).

        Parameters
        ----------
        text : str
            Input text.
        max_tokens : int, optional
            Token limit; defaults to :attr:`max_tokens`.

        Returns
        -------
        str
            Tail of *text* fitting within *max_tokens* tokens.
        """
        limit = self._resolve_limit(max_tokens)
        max_chars = limit * CHARS_PER_TOKEN
        return text[-max_chars:] if len(text) > max_chars else text

    # ------------------------------------------------------------------
    # Packing
    # ------------------------------------------------------------------

    def pack(self, parts: List[str], max_tokens: Optional[int] = None) -> str:
        """Join text parts with the separator and truncate to fit token limit.

        Empty strings within *parts* are skipped. Parts are joined in the
        order provided; the joined string is then truncated if necessary.

        Parameters
        ----------
        parts : list of str
            Text fragments to join.
        max_tokens : int, optional
            Token limit; defaults to :attr:`max_tokens`.

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
        """Select parts by priority, returning them in their original order.

        Parts are selected greedily from highest to lowest priority until
        the token budget is exhausted. The output preserves the *original
        ordering* of the input list so that document structure is
        maintained — only content selection is governed by priority, not
        the output order.

        Parameters
        ----------
        parts : list of dict
            Each dict should contain:

            * ``"text"`` (*str*) — the content to include.
            * ``"priority"`` (*numeric*, optional, default ``0``) — higher
              values are kept first when the budget is tight.

            Missing keys default to ``""`` / ``0`` rather than raising.
        max_tokens : int, optional
            Token limit; defaults to :attr:`max_tokens`.

        Returns
        -------
        str
            Selected parts joined by the configured separator, in
            original input order.

        Examples
        --------
        >>> packer = Contextpacker(max_tokens=20)
        >>> parts = [
        ...     {"text": "Background info", "priority": 1},
        ...     {"text": "Critical fact",   "priority": 10},
        ... ]
        >>> packer.pack_priority(parts)
        'Background info\\n\\nCritical fact'
        """
        limit = self._resolve_limit(max_tokens)

        # Pair each part with its original index for stable ordering later.
        indexed: List[Tuple[int, Dict[str, Any]]] = list(enumerate(parts))
        # Select in priority order (highest first) to respect the budget.
        by_priority = sorted(
            indexed, key=lambda x: x[1].get("priority", 0), reverse=True
        )

        selected: Set[int] = set()
        used = 0
        for idx, part in by_priority:
            text = part.get("text", "")
            tokens = self.count_chars(text)
            if used + tokens <= limit:
                selected.add(idx)
                used += tokens

        # Emit in original input order so callers get predictable output.
        return self._separator.join(
            parts[i].get("text", "") for i in sorted(selected)
        )

    def pack_chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        keep_system: bool = True,
    ) -> List[Dict[str, str]]:
        """Fit a chat message list within a token budget.

        System messages are collected first and placed at the head of the
        result (when *keep_system* is ``True``). Non-system messages are
        then added in *reverse* chronological order (newest first) until
        the remaining budget is exhausted.

        Parameters
        ----------
        messages : list of dict
            OpenAI-compatible message dicts.  Each dict should have
            ``"role"`` (*str*) and ``"content"`` (*str*) keys. A missing
            ``"content"`` key is treated as an empty string rather than
            raising a ``KeyError``.
        max_tokens : int, optional
            Token limit; defaults to :attr:`max_tokens`.
        keep_system : bool
            When ``True`` (default), system messages are always included
            and their token cost is subtracted from the budget before
            non-system messages are added.

        Returns
        -------
        list of dict
            Subset of *messages* that fits within the token budget, with
            system messages at the front.
        """
        limit = self._resolve_limit(max_tokens)
        system = [m for m in messages if m.get("role") == "system"]
        others = [m for m in messages if m.get("role") != "system"]

        # Use .get() with a default to avoid KeyError on malformed dicts.
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
        """Split text into chunks that each fit within *max_tokens*.

        Chunking is character-based and does not respect word or sentence
        boundaries. For an empty string, a one-element list containing the
        empty string is returned.

        Parameters
        ----------
        text : str
            Input text to split.
        max_tokens : int, optional
            Per-chunk token limit; defaults to :attr:`max_tokens`.

        Returns
        -------
        list of str
            Ordered list of chunks, each at most *max_tokens* tokens long.
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
        """Return the most recent parts that fit within the token budget.

        Iterates *parts* from newest to oldest, accumulating items until
        the budget is exhausted. The returned list preserves the original
        order of the selected parts.

        Parameters
        ----------
        parts : list of str
            Ordered text fragments (oldest first, newest last).
        max_tokens : int, optional
            Token limit; defaults to :attr:`max_tokens`.

        Returns
        -------
        list of str
            Tail of *parts* that fits within the budget, in original order.
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
    # Properties and helpers
    # ------------------------------------------------------------------

    @property
    def max_tokens(self) -> int:
        """Default token budget for this packer instance."""
        return self._max_tokens

    @property
    def separator(self) -> str:
        """Separator string used to join parts."""
        return self._separator

    def _resolve_limit(self, max_tokens: Optional[int]) -> int:
        """Return *max_tokens* if provided and valid, else :attr:`max_tokens`."""
        limit = max_tokens if max_tokens is not None else self._max_tokens
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError(
                f"max_tokens must be a positive integer, got {limit!r}"
            )
        return limit
