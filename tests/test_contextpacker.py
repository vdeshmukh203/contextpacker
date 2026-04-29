"""Tests for contextpacker."""
import pytest

from contextpacker import Contextpacker
from contextpacker.packer import CHARS_PER_TOKEN, DEFAULT_MAX_TOKENS


# ---------------------------------------------------------------------------
# Construction & properties
# ---------------------------------------------------------------------------

class TestInit:
    def test_defaults(self):
        cp = Contextpacker()
        assert cp.max_tokens == DEFAULT_MAX_TOKENS
        assert cp.separator == "\n\n"

    def test_custom_values(self):
        cp = Contextpacker(max_tokens=512, separator=" | ")
        assert cp.max_tokens == 512
        assert cp.separator == " | "

    def test_zero_max_tokens_raises(self):
        with pytest.raises(ValueError, match="max_tokens"):
            Contextpacker(max_tokens=0)

    def test_negative_max_tokens_raises(self):
        with pytest.raises(ValueError, match="max_tokens"):
            Contextpacker(max_tokens=-1)

    def test_float_max_tokens_raises(self):
        with pytest.raises(ValueError, match="max_tokens"):
            Contextpacker(max_tokens=100.0)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------

class TestCount:
    def test_non_empty(self):
        cp = Contextpacker()
        assert cp.count("hello world") >= 1

    def test_empty_string(self):
        cp = Contextpacker()
        assert cp.count("") == 0

    def test_single_word(self):
        cp = Contextpacker()
        assert cp.count("hello") == 1

    def test_scales_with_length(self):
        cp = Contextpacker()
        short = cp.count("hello world")
        long_ = cp.count("hello world " * 10)
        assert long_ > short


class TestCountChars:
    def test_empty_string(self):
        cp = Contextpacker()
        assert cp.count_chars("") == 0

    def test_exact_multiple(self):
        cp = Contextpacker()
        # 40 chars → 10 tokens
        assert cp.count_chars("a" * 40) == 10

    def test_below_one_token(self):
        # len("abc") // 4 == 0 → clamped to 1
        cp = Contextpacker()
        assert cp.count_chars("abc") == 1

    def test_consistent_with_truncate(self):
        cp = Contextpacker(max_tokens=10)
        text = "a" * (10 * CHARS_PER_TOKEN)
        truncated = cp.truncate(text, max_tokens=10)
        assert cp.count_chars(truncated) <= 10


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------

class TestTruncate:
    def test_short_text_unchanged(self):
        cp = Contextpacker(max_tokens=1000)
        assert cp.truncate("hello") == "hello"

    def test_exact_limit_unchanged(self):
        cp = Contextpacker(max_tokens=10)
        text = "a" * 40  # exactly 10 tokens
        assert cp.truncate(text) == text

    def test_long_text_truncated(self):
        cp = Contextpacker(max_tokens=10)
        result = cp.truncate("a" * 200)
        assert len(result) == 40

    def test_override_limit(self):
        cp = Contextpacker(max_tokens=1000)
        result = cp.truncate("a" * 200, max_tokens=10)
        assert len(result) == 40

    def test_invalid_limit_raises(self):
        cp = Contextpacker()
        with pytest.raises(ValueError, match="max_tokens"):
            cp.truncate("text", max_tokens=0)

    def test_empty_string(self):
        cp = Contextpacker(max_tokens=10)
        assert cp.truncate("") == ""


class TestTruncateStart:
    def test_short_text_unchanged(self):
        cp = Contextpacker(max_tokens=1000)
        assert cp.truncate_start("hello") == "hello"

    def test_keeps_end(self):
        cp = Contextpacker(max_tokens=5)
        text = "START" + "x" * 100
        result = cp.truncate_start(text)
        assert result.endswith("x" * 20)
        assert not result.startswith("START")

    def test_length_bounded(self):
        cp = Contextpacker(max_tokens=10)
        result = cp.truncate_start("b" * 200)
        assert len(result) == 40


# ---------------------------------------------------------------------------
# Packing
# ---------------------------------------------------------------------------

class TestPack:
    def test_parts_joined(self):
        cp = Contextpacker(max_tokens=1000)
        result = cp.pack(["part1", "part2"])
        assert "part1" in result
        assert "part2" in result

    def test_separator_used(self):
        cp = Contextpacker(max_tokens=1000, separator=" | ")
        result = cp.pack(["a", "b"])
        assert " | " in result

    def test_empty_parts_ignored(self):
        cp = Contextpacker(max_tokens=1000)
        result = cp.pack(["a", "", "b"])
        assert result == "a\n\nb"

    def test_all_empty_parts(self):
        cp = Contextpacker(max_tokens=1000)
        assert cp.pack(["", ""]) == ""

    def test_truncates_to_budget(self):
        cp = Contextpacker(max_tokens=5)
        result = cp.pack(["a" * 100, "b" * 100])
        assert len(result) <= 20

    def test_empty_list(self):
        cp = Contextpacker(max_tokens=1000)
        assert cp.pack([]) == ""


class TestPackPriority:
    def test_high_priority_included(self):
        cp = Contextpacker(max_tokens=20)
        parts = [
            {"text": "low priority text", "priority": 1},
            {"text": "IMPORTANT", "priority": 10},
        ]
        result = cp.pack_priority(parts)
        assert "IMPORTANT" in result

    def test_low_priority_dropped_when_over_budget(self):
        cp = Contextpacker(max_tokens=5)
        parts = [
            {"text": "a" * 30, "priority": 1},   # ~7 tokens, low priority
            {"text": "HIGH", "priority": 100},    # ~1 token, high priority
        ]
        result = cp.pack_priority(parts)
        assert "HIGH" in result
        assert "a" * 30 not in result

    def test_original_order_preserved(self):
        # Parts selected should appear in their original list order, not
        # sorted by priority in the output.
        cp = Contextpacker(max_tokens=1000)
        parts = [
            {"text": "first", "priority": 1},
            {"text": "second", "priority": 10},
            {"text": "third", "priority": 5},
        ]
        result = cp.pack_priority(parts)
        assert result.index("first") < result.index("second") < result.index("third")

    def test_missing_priority_defaults_to_zero(self):
        cp = Contextpacker(max_tokens=1000)
        parts = [{"text": "no priority key"}]
        assert cp.pack_priority(parts) == "no priority key"

    def test_missing_text_key(self):
        cp = Contextpacker(max_tokens=1000)
        parts = [{"priority": 5}]
        assert cp.pack_priority(parts) == ""

    def test_empty_parts_list(self):
        cp = Contextpacker(max_tokens=1000)
        assert cp.pack_priority([]) == ""


class TestPackChat:
    def test_all_fit(self):
        cp = Contextpacker(max_tokens=1000)
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        assert cp.pack_chat(msgs) == msgs

    def test_drops_oldest(self):
        cp = Contextpacker(max_tokens=5)
        msgs = [
            {"role": "user", "content": "old message that is very long"},
            {"role": "assistant", "content": "hi"},
        ]
        result = cp.pack_chat(msgs)
        assert any(m["content"] == "hi" for m in result)

    def test_system_kept_first(self):
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

    def test_missing_content_key(self):
        # Should not raise; missing key treated as empty string.
        cp = Contextpacker(max_tokens=1000)
        msgs = [{"role": "user"}]
        result = cp.pack_chat(msgs)
        assert result == msgs

    def test_empty_message_list(self):
        cp = Contextpacker(max_tokens=1000)
        assert cp.pack_chat([]) == []


# ---------------------------------------------------------------------------
# Splitting
# ---------------------------------------------------------------------------

class TestSplit:
    def test_short_text_single_chunk(self):
        cp = Contextpacker(max_tokens=1000)
        chunks = cp.split("hello")
        assert chunks == ["hello"]

    def test_long_text_multiple_chunks(self):
        cp = Contextpacker(max_tokens=10)
        chunks = cp.split("a" * 200)
        assert len(chunks) > 1

    def test_chunk_size_bounded(self):
        cp = Contextpacker(max_tokens=10)
        for chunk in cp.split("a" * 200):
            assert len(chunk) <= 40

    def test_chunks_reconstruct_original(self):
        cp = Contextpacker(max_tokens=10)
        text = "a" * 200
        assert "".join(cp.split(text)) == text

    def test_exact_boundary(self):
        cp = Contextpacker(max_tokens=10)
        text = "a" * 40  # exactly one chunk
        assert cp.split(text) == [text]

    def test_empty_string(self):
        cp = Contextpacker(max_tokens=10)
        assert cp.split("") == [""]


# ---------------------------------------------------------------------------
# Sliding window
# ---------------------------------------------------------------------------

class TestSlidingWindow:
    def test_recent_part_included(self):
        cp = Contextpacker(max_tokens=10)
        parts = ["old " * 20, "middle " * 20, "recent"]
        result = cp.sliding_window(parts)
        assert "recent" in result

    def test_old_part_excluded_when_over_budget(self):
        cp = Contextpacker(max_tokens=5)
        parts = ["a" * 100, "b" * 5]
        result = cp.sliding_window(parts)
        assert "a" * 100 not in result

    def test_order_preserved(self):
        cp = Contextpacker(max_tokens=1000)
        parts = ["alpha", "beta", "gamma"]
        result = cp.sliding_window(parts)
        assert result == parts

    def test_all_fit(self):
        cp = Contextpacker(max_tokens=1000)
        parts = ["x", "y", "z"]
        assert cp.sliding_window(parts) == parts

    def test_empty_parts(self):
        cp = Contextpacker(max_tokens=10)
        assert cp.sliding_window([]) == []
