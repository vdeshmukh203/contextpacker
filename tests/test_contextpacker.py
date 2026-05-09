"""Tests for contextpacker — covers public API, edge cases, and error paths."""
import math
import pytest

from contextpacker import Contextpacker
from contextpacker.packer import DEFAULT_MAX_TOKENS, CHARS_PER_TOKEN


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cp():
    return Contextpacker()


@pytest.fixture
def cp_small():
    return Contextpacker(max_tokens=10)


# ---------------------------------------------------------------------------
# Construction & properties
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_defaults(self):
        cp = Contextpacker()
        assert cp.max_tokens == DEFAULT_MAX_TOKENS
        assert cp.separator == "\n\n"

    def test_custom_values(self):
        cp = Contextpacker(max_tokens=512, separator=" | ")
        assert cp.max_tokens == 512
        assert cp.separator == " | "

    def test_repr(self):
        cp = Contextpacker(max_tokens=100, separator="\n")
        r = repr(cp)
        assert "100" in r
        assert "Contextpacker" in r

    def test_invalid_max_tokens_zero(self):
        with pytest.raises(ValueError):
            Contextpacker(max_tokens=0)

    def test_invalid_max_tokens_negative(self):
        with pytest.raises(ValueError):
            Contextpacker(max_tokens=-1)

    def test_invalid_max_tokens_float(self):
        with pytest.raises(TypeError):
            Contextpacker(max_tokens=8.5)  # type: ignore[arg-type]

    def test_invalid_max_tokens_bool(self):
        # bool is a subclass of int but should be rejected
        with pytest.raises(TypeError):
            Contextpacker(max_tokens=True)  # type: ignore[arg-type]

    def test_invalid_separator_type(self):
        with pytest.raises(TypeError):
            Contextpacker(separator=None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------

class TestCount:
    def test_empty_returns_zero(self, cp):
        assert cp.count("") == 0

    def test_single_word(self, cp):
        # 1 word * 1.3 = 1.3 → ceil → 2, but max(1, …) so at least 1
        result = cp.count("hello")
        assert result >= 1

    def test_multiple_words(self, cp):
        result = cp.count("hello world foo bar")
        assert result == math.ceil(4 * 1.3)

    def test_whitespace_only_empty(self, cp):
        # split() on whitespace-only returns []
        assert cp.count("   ") == 0

    def test_count_grows_with_text(self, cp):
        assert cp.count("a b c") < cp.count("a b c d e f g h i j")

    def test_invalid_type(self, cp):
        with pytest.raises(TypeError):
            cp.count(123)  # type: ignore[arg-type]


class TestCountChars:
    def test_empty_returns_zero(self, cp):
        assert cp.count_chars("") == 0

    def test_exact_multiple(self, cp):
        # 8 chars → 8 // 4 = 2
        assert cp.count_chars("a" * 8) == 2

    def test_rounding_down(self, cp):
        # 9 chars → 9 // 4 = 2
        assert cp.count_chars("a" * 9) == 2

    def test_less_than_one_token(self, cp):
        # 3 chars → 3 // 4 = 0
        assert cp.count_chars("abc") == 0

    def test_unicode_counted_by_len(self, cp):
        # Multi-byte chars: Python len() counts code points
        text = "こんにちは"  # 5 chars (each 3 bytes in UTF-8)
        assert cp.count_chars(text) == len(text) // CHARS_PER_TOKEN

    def test_invalid_type(self, cp):
        with pytest.raises(TypeError):
            cp.count_chars(42)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------

class TestTruncate:
    def test_short_text_unchanged(self):
        cp = Contextpacker(max_tokens=1000)
        assert cp.truncate("hello") == "hello"

    def test_empty_string(self, cp):
        assert cp.truncate("") == ""

    def test_exact_boundary(self):
        cp = Contextpacker(max_tokens=5)
        text = "a" * (5 * CHARS_PER_TOKEN)
        assert cp.truncate(text) == text

    def test_one_over_boundary(self):
        cp = Contextpacker(max_tokens=5)
        text = "a" * (5 * CHARS_PER_TOKEN + 1)
        result = cp.truncate(text)
        assert len(result) == 5 * CHARS_PER_TOKEN

    def test_long_text_truncated_from_end(self):
        cp = Contextpacker(max_tokens=10)
        result = cp.truncate("a" * 200)
        assert len(result) == 10 * CHARS_PER_TOKEN

    def test_override_max_tokens(self):
        cp = Contextpacker(max_tokens=1000)
        result = cp.truncate("a" * 200, max_tokens=5)
        assert len(result) == 5 * CHARS_PER_TOKEN

    def test_invalid_max_tokens_override(self, cp):
        with pytest.raises(ValueError):
            cp.truncate("hello", max_tokens=0)

    def test_invalid_text_type(self, cp):
        with pytest.raises(TypeError):
            cp.truncate(42)  # type: ignore[arg-type]


class TestTruncateStart:
    def test_short_text_unchanged(self):
        cp = Contextpacker(max_tokens=1000)
        assert cp.truncate_start("hello") == "hello"

    def test_empty_string(self, cp):
        assert cp.truncate_start("") == ""

    def test_keeps_end(self):
        cp = Contextpacker(max_tokens=5)
        text = "START" + "x" * 100
        result = cp.truncate_start(text)
        assert result.endswith("x")
        assert not result.startswith("S")

    def test_exact_boundary_unchanged(self):
        cp = Contextpacker(max_tokens=5)
        text = "z" * (5 * CHARS_PER_TOKEN)
        assert cp.truncate_start(text) == text

    def test_complement_of_truncate(self):
        cp = Contextpacker(max_tokens=5)
        max_chars = 5 * CHARS_PER_TOKEN
        # Text that is exactly 2*max_chars long partitions cleanly
        text = "a" * max_chars + "b" * max_chars
        head = cp.truncate(text)
        tail = cp.truncate_start(text)
        assert head == "a" * max_chars
        assert tail == "b" * max_chars
        assert head + tail == text


# ---------------------------------------------------------------------------
# Packing
# ---------------------------------------------------------------------------

class TestPack:
    def test_small_parts_fit(self):
        cp = Contextpacker(max_tokens=1000)
        result = cp.pack(["part1", "part2"])
        assert "part1" in result
        assert "part2" in result

    def test_empty_parts_skipped(self, cp):
        result = cp.pack(["hello", "", "world"])
        assert "hello" in result
        assert "world" in result

    def test_all_empty_parts(self, cp):
        assert cp.pack([]) == ""
        assert cp.pack(["", ""]) == ""

    def test_separator_inserted(self):
        cp = Contextpacker(max_tokens=1000, separator="---")
        result = cp.pack(["a", "b"])
        assert "---" in result

    def test_truncates_to_budget(self):
        cp = Contextpacker(max_tokens=5)
        result = cp.pack(["a" * 100, "b" * 100])
        assert len(result) <= 5 * CHARS_PER_TOKEN

    def test_invalid_parts_type(self, cp):
        with pytest.raises(TypeError):
            cp.pack("not a list")  # type: ignore[arg-type]


class TestPackPriority:
    def test_keeps_highest_priority(self):
        cp = Contextpacker(max_tokens=20)
        parts = [
            {"text": "low priority text", "priority": 1},
            {"text": "IMPORTANT", "priority": 10},
        ]
        result = cp.pack_priority(parts)
        assert "IMPORTANT" in result

    def test_drops_lowest_when_over_budget(self):
        cp = Contextpacker(max_tokens=5)
        parts = [
            {"text": "a" * 100, "priority": 1},  # too big if only one fits
            {"text": "hi", "priority": 10},
        ]
        result = cp.pack_priority(parts)
        assert "hi" in result
        # The big low-priority part must not appear if it overflows budget
        budget_chars = 5 * CHARS_PER_TOKEN
        assert len(result) <= budget_chars

    def test_empty_parts(self, cp):
        assert cp.pack_priority([]) == ""

    def test_missing_priority_defaults_to_zero(self, cp):
        parts = [{"text": "hello"}]
        result = cp.pack_priority(parts)
        assert "hello" in result

    def test_missing_text_key(self, cp):
        # Should not raise; text defaults to ""
        parts = [{"priority": 5}]
        result = cp.pack_priority(parts)
        assert result == ""

    def test_invalid_parts_type(self, cp):
        with pytest.raises(TypeError):
            cp.pack_priority("not a list")  # type: ignore[arg-type]

    def test_output_highest_priority_first(self):
        cp = Contextpacker(max_tokens=200)
        parts = [
            {"text": "low", "priority": 1},
            {"text": "high", "priority": 99},
            {"text": "mid", "priority": 50},
        ]
        result = cp.pack_priority(parts)
        assert result.index("high") < result.index("mid") < result.index("low")


class TestPackChat:
    def test_all_fit(self):
        cp = Contextpacker(max_tokens=1000)
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        result = cp.pack_chat(msgs)
        assert len(result) == 2

    def test_drops_oldest_non_system(self):
        cp = Contextpacker(max_tokens=5)
        msgs = [
            {"role": "user", "content": "old message that is very long indeed"},
            {"role": "assistant", "content": "hi"},
        ]
        result = cp.pack_chat(msgs)
        assert any(m["content"] == "hi" for m in result)

    def test_keeps_system_first(self):
        cp = Contextpacker(max_tokens=1000)
        msgs = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "hello"},
        ]
        result = cp.pack_chat(msgs)
        assert result[0]["role"] == "system"

    def test_keep_system_false(self):
        cp = Contextpacker(max_tokens=1000)
        msgs = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hello"},
        ]
        result = cp.pack_chat(msgs, keep_system=False)
        assert all(m["role"] != "system" for m in result)

    def test_empty_message_list(self, cp):
        assert cp.pack_chat([]) == []

    def test_only_system_messages(self):
        cp = Contextpacker(max_tokens=1000)
        msgs = [{"role": "system", "content": "You are an AI."}]
        result = cp.pack_chat(msgs)
        assert len(result) == 1
        assert result[0]["role"] == "system"

    def test_system_budget_overflow_gives_empty_others(self):
        # System message alone exceeds budget; others list should be empty
        cp = Contextpacker(max_tokens=1)
        msgs = [
            {"role": "system", "content": "a" * 1000},
            {"role": "user", "content": "hello world foo"},  # > 4 chars → at least 1 token
        ]
        result = cp.pack_chat(msgs)
        # System is always kept; no room for user
        assert all(m["role"] == "system" for m in result)

    def test_missing_content_key(self, cp):
        msgs = [{"role": "user"}]
        result = cp.pack_chat(msgs)
        assert len(result) == 1

    def test_invalid_messages_type(self, cp):
        with pytest.raises(TypeError):
            cp.pack_chat("not a list")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Splitting
# ---------------------------------------------------------------------------

class TestSplit:
    def test_short_text_single_chunk(self):
        cp = Contextpacker(max_tokens=100)
        assert cp.split("hello") == ["hello"]

    def test_empty_string_returns_empty_list(self, cp):
        assert cp.split("") == []

    def test_chunks_respect_budget(self):
        cp = Contextpacker(max_tokens=10)
        chunks = cp.split("a" * 200)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 10 * CHARS_PER_TOKEN

    def test_chunks_reconstruct_original(self):
        cp = Contextpacker(max_tokens=10)
        text = "abcdefghijklmnopqrstuvwxyz" * 5
        chunks = cp.split(text)
        assert "".join(chunks) == text

    def test_exact_boundary_single_chunk(self):
        cp = Contextpacker(max_tokens=5)
        text = "a" * (5 * CHARS_PER_TOKEN)
        chunks = cp.split(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_override_max_tokens(self):
        cp = Contextpacker(max_tokens=1000)
        chunks = cp.split("a" * 200, max_tokens=5)
        for chunk in chunks:
            assert len(chunk) <= 5 * CHARS_PER_TOKEN

    def test_invalid_text_type(self, cp):
        with pytest.raises(TypeError):
            cp.split(42)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Sliding window
# ---------------------------------------------------------------------------

class TestSlidingWindow:
    def test_all_fit(self):
        cp = Contextpacker(max_tokens=1000)
        parts = ["a", "b", "c"]
        result = cp.sliding_window(parts)
        assert result == parts

    def test_keeps_most_recent(self):
        cp = Contextpacker(max_tokens=10)
        parts = ["old " * 20, "middle " * 20, "recent"]
        result = cp.sliding_window(parts)
        assert "recent" in result

    def test_empty_list(self, cp):
        assert cp.sliding_window([]) == []

    def test_preserves_order(self):
        cp = Contextpacker(max_tokens=1000)
        parts = ["first", "second", "third"]
        result = cp.sliding_window(parts)
        assert result == parts

    def test_skips_non_str(self, cp):
        parts = ["hello", 42, "world"]  # type: ignore[list-item]
        result = cp.sliding_window(parts)
        assert 42 not in result

    def test_invalid_parts_type(self, cp):
        with pytest.raises(TypeError):
            cp.sliding_window("not a list")  # type: ignore[arg-type]

    def test_override_max_tokens(self):
        cp = Contextpacker(max_tokens=1000)
        parts = ["a" * 100, "recent"]
        result = cp.sliding_window(parts, max_tokens=1)
        assert result == ["recent"]
