"""Context window packer — truncation, splitting, chat packing, sliding window."""
from typing import Any, Dict, List, Optional

DEFAULT_MAX_TOKENS = 8192
CHARS_PER_TOKEN = 4  # standard heuristic (GPT-family average)


class Contextpacker:
    """Pack and manage content for LLM context windows.

    Token counting uses two heuristics:
    - ``count()``       — word-based  (~1.3 tokens per word, English prose)
    - ``count_chars()`` — char-based  (chars / 4, language-agnostic fallback)

    Internal budget arithmetic uses ``count_chars`` so that truncation and
    packing behave identically regardless of the text's word structure.
    """

    def __init__(self, max_tokens: int = DEFAULT_MAX_TOKENS,
                 separator: str = "\n\n") -> None:
        if not isinstance(max_tokens, int):
            raise TypeError(
                f"max_tokens must be an int, got {type(max_tokens).__name__!r}"
            )
        if max_tokens < 1:
            raise ValueError(
                f"max_tokens must be a positive integer, got {max_tokens!r}"
            )
        self._max_tokens = max_tokens
        self._separator = separator

    def __repr__(self) -> str:
        return (
            f"Contextpacker(max_tokens={self._max_tokens!r}, "
            f"separator={self._separator!r})"
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def max_tokens(self) -> int:
        """Token budget used when no per-call limit is supplied."""
        return self._max_tokens

    @property
    def separator(self) -> str:
        """String inserted between parts when joining."""
        return self._separator

    # ------------------------------------------------------------------
    # Token counting
    # ------------------------------------------------------------------

    def count(self, text: str) -> int:
        """Word-aware token estimate (~1.3 tokens per whitespace-delimited word).

        Returns 0 for empty strings.
        """
        if not isinstance(text, str):
            raise TypeError(f"text must be str, got {type(text).__name__!r}")
        if not text:
            return 0
        return round(len(text.split()) * 1.3)

    def count_chars(self, text: str) -> int:
        """Character-based token estimate (chars / 4, language-agnostic).

        Returns 0 for empty strings.
        """
        if not isinstance(text, str):
            raise TypeError(f"text must be str, got {type(text).__name__!r}")
        if not text:
            return 0
        return max(1, len(text) // CHARS_PER_TOKEN)

    # ------------------------------------------------------------------
    # Truncation
    # ------------------------------------------------------------------

    def truncate(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Return the *beginning* of ``text`` clipped to the token budget.

        Uses the char-based heuristic (1 token ≈ 4 chars) so that the
        character limit is deterministic regardless of word boundaries.
        """
        if not isinstance(text, str):
            raise TypeError(f"text must be str, got {type(text).__name__!r}")
        limit = max_tokens if max_tokens is not None else self._max_tokens
        if limit < 1:
            raise ValueError(f"max_tokens must be >= 1, got {limit!r}")
        max_chars = limit * CHARS_PER_TOKEN
        return text[:max_chars] if len(text) > max_chars else text

    def truncate_start(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Return the *end* of ``text`` clipped to the token budget.

        Useful for chat history where the most recent context (at the end)
        is most important and old content should be dropped first.
        """
        if not isinstance(text, str):
            raise TypeError(f"text must be str, got {type(text).__name__!r}")
        limit = max_tokens if max_tokens is not None else self._max_tokens
        if limit < 1:
            raise ValueError(f"max_tokens must be >= 1, got {limit!r}")
        max_chars = limit * CHARS_PER_TOKEN
        return text[-max_chars:] if len(text) > max_chars else text

    # ------------------------------------------------------------------
    # Packing
    # ------------------------------------------------------------------

    def pack(self, parts: List[str], max_tokens: Optional[int] = None) -> str:
        """Join non-empty ``parts`` with the separator and truncate to budget.

        Parts are joined in the order given; the result is front-truncated
        to fit within ``max_tokens``.
        """
        if not isinstance(parts, list):
            raise TypeError(f"parts must be a list, got {type(parts).__name__!r}")
        limit = max_tokens if max_tokens is not None else self._max_tokens
        joined = self._separator.join(p for p in parts if p)
        return self.truncate(joined, limit)

    def pack_priority(self, parts: List[Dict[str, Any]],
                      max_tokens: Optional[int] = None) -> str:
        """Greedily select parts by priority, then return them in insertion order.

        Each element of ``parts`` must be a dict with keys:

        * ``"text"``     (str)  — the content to include
        * ``"priority"`` (int)  — higher value means kept longer when budget
          is tight; defaults to 0 if missing

        Parts are selected greedily from highest to lowest priority until the
        token budget is exhausted.  The output preserves the **original
        insertion order** of the selected items so that the assembled text
        reads naturally.
        """
        if not isinstance(parts, list):
            raise TypeError(f"parts must be a list, got {type(parts).__name__!r}")
        limit = max_tokens if max_tokens is not None else self._max_tokens

        # Sort by priority descending to decide which items to keep, but track
        # each item's original index so we can restore insertion order later.
        indexed = sorted(
            enumerate(parts),
            key=lambda ip: ip[1].get("priority", 0),
            reverse=True,
        )

        selected_indices: List[int] = []
        used = 0
        for idx, part in indexed:
            text = part.get("text", "")
            tokens = self.count_chars(text)
            if used + tokens <= limit:
                selected_indices.append(idx)
                used += tokens

        # Restore original insertion order.
        selected_indices.sort()
        texts = [parts[i].get("text", "") for i in selected_indices]
        return self._separator.join(t for t in texts if t)

    def pack_chat(self, messages: List[Dict[str, str]],
                  max_tokens: Optional[int] = None,
                  keep_system: bool = True) -> List[Dict[str, str]]:
        """Fit a chat message list within a token budget.

        Messages are retained from most-recent to oldest; the oldest
        non-system messages are dropped first when the budget is tight.

        Each element of ``messages`` must be a dict with keys:

        * ``"role"``    (str) — e.g. ``"system"``, ``"user"``, ``"assistant"``
        * ``"content"`` (str) — the message body

        Parameters
        ----------
        messages:
            Ordered list of chat messages (oldest first).
        max_tokens:
            Token budget; defaults to the instance ``max_tokens``.
        keep_system:
            When ``True`` (default), system messages are always included and
            their tokens are reserved from the budget before fitting
            non-system messages.
        """
        if not isinstance(messages, list):
            raise TypeError(
                f"messages must be a list, got {type(messages).__name__!r}"
            )
        limit = max_tokens if max_tokens is not None else self._max_tokens

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
        """Split ``text`` into sequential chunks each within the token budget.

        The final chunk may be shorter than the budget.  Returns a
        single-element list when the whole text already fits.
        """
        if not isinstance(text, str):
            raise TypeError(f"text must be str, got {type(text).__name__!r}")
        limit = max_tokens if max_tokens is not None else self._max_tokens
        if limit < 1:
            raise ValueError(f"max_tokens must be >= 1, got {limit!r}")
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

    def sliding_window(self, parts: List[str],
                       max_tokens: Optional[int] = None) -> List[str]:
        """Return the most-recent contiguous suffix of ``parts`` that fits the budget.

        Iterates from the last element backwards, accumulating parts until
        adding the next would exceed ``max_tokens``.  This preserves a
        contiguous recency window — older parts that would not fit are
        dropped as a block, matching the typical LLM chat-history pattern.
        """
        if not isinstance(parts, list):
            raise TypeError(f"parts must be a list, got {type(parts).__name__!r}")
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
