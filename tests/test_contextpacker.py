"""Tests for contextpacker."""
import pytest
from contextpacker import Contextpacker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cp():
    return Contextpacker(max_tokens=1000)


@pytest.fixture
def cp_small():
    return Contextpacker(max_tokens=5)


# ---------------------------------------------------------------------------
# Contextpacker.__init__
# ---------------------------------------------------------------------------

class TestInit:
    def test_default_max_tokens(self):
        cp = Contextpacker()
        assert cp.max_tokens == 8192

    def test_custom_max_tokens(self):
        cp = Contextpacker(max_tokens=512)
        assert cp.max_tokens == 512

    def test_custom_separator(self):
        cp = Contextpacker(separator=" | ")
        assert cp.separator == " | "

    def test_invalid_max_tokens_zero(self):
        with pytest.raises(ValueError, match="positive integer"):
            Contextpacker(max_tokens=0)

    def test_invalid_max_tokens_negative(self):
        with pytest.raises(ValueError, match="positive integer"):
            Contextpacker(max_tokens=-1)

    def test_invalid_max_tokens_float(self):
        with pytest.raises(ValueError):
            Contextpacker(max_tokens=3.5)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# count / count_chars
# ---------------------------------------------------------------------------

class TestCount:
    def test_count_empty(self, cp):
        assert cp.count("") == 0

    def test_count_whitespace_only(self, cp):
        assert cp.count("   \n  ") == 0

    def test_count_single_word(self, cp):
        assert cp.count("hello") == 1  # round(1 * 1.3) = 1

    def test_count_two_words(self, cp):
        assert cp.count("hello world") == 3  # round(2 * 1.3) = 3

    def test_count_returns_int(self, cp):
        assert isinstance(cp.count("some text"), int)

    def test_count_chars_empty(self, cp):
        assert cp.count_chars("") == 0

    def test_count_chars_four_chars(self, cp):
        assert cp.count_chars("abcd") == 1

    def test_count_chars_eight_chars(self, cp):
        assert cp.count_chars("abcdefgh") == 2

    def test_count_chars_less_than_four(self, cp):
        # integer division: 3 // 4 = 0
        assert cp.count_chars("abc") == 0

    def test_count_chars_returns_int(self, cp):
        assert isinstance(cp.count_chars("some text"), int)


# ---------------------------------------------------------------------------
# truncate
# ---------------------------------------------------------------------------

class TestTruncate:
    def test_short_text_unchanged(self, cp):
        assert cp.truncate("hello") == "hello"

    def test_exact_limit_unchanged(self):
        cp = Contextpacker(max_tokens=10)
        text = "a" * 40  # exactly 10 tokens (40 chars / 4)
        assert cp.truncate(text) == text

    def test_long_text_clipped(self):
        cp = Contextpacker(max_tokens=10)
        result = cp.truncate("a" * 200)
        assert len(result) == 40  # 10 tokens * 4 chars

    def test_keeps_start(self):
        cp = Contextpacker(max_tokens=5)
        text = "START" + "x" * 100
        result = cp.truncate(text)
        assert result.startswith("START")

    def test_custom_limit_override(self, cp):
        result = cp.truncate("a" * 200, max_tokens=10)
        assert len(result) == 40

    def test_empty_text(self, cp):
        assert cp.truncate("") == ""


# ---------------------------------------------------------------------------
# truncate_start
# ---------------------------------------------------------------------------

class TestTruncateStart:
    def test_short_text_unchanged(self, cp):
        assert cp.truncate_start("hello") == "hello"

    def test_keeps_end(self):
        cp = Contextpacker(max_tokens=5)
        text = "x" * 100 + "END"
        result = cp.truncate_start(text)
        assert result.endswith("END")

    def test_drops_start(self):
        cp = Contextpacker(max_tokens=5)
        text = "START" + "x" * 100
        result = cp.truncate_start(text)
        assert not result.startswith("START")

    def test_length_respected(self):
        cp = Contextpacker(max_tokens=10)
        result = cp.truncate_start("a" * 200)
        assert len(result) == 40


# ---------------------------------------------------------------------------
# pack
# ---------------------------------------------------------------------------

class TestPack:
    def test_joins_parts(self, cp):
        result = cp.pack(["part1", "part2"])
        assert "part1" in result and "part2" in result

    def test_separator_used(self):
        cp = Contextpacker(separator=" | ")
        result = cp.pack(["A", "B"])
        assert result == "A | B"

    def test_skips_empty_parts(self, cp):
        result = cp.pack(["A", "", "B"])
        assert "A" in result and "B" in result
        assert "  " not in result  # no double separator artefact from empty

    def test_truncates_when_over_budget(self):
        cp = Contextpacker(max_tokens=5)
        result = cp.pack(["a" * 100, "b" * 100])
        assert len(result) <= 20  # 5 tokens * 4 chars

    def test_custom_limit_override(self, cp):
        result = cp.pack(["a" * 100, "b" * 100], max_tokens=5)
        assert len(result) <= 20

    def test_empty_list(self, cp):
        assert cp.pack([]) == ""


# ---------------------------------------------------------------------------
# pack_priority
# ---------------------------------------------------------------------------

class TestPackPriority:
    def test_includes_high_priority(self):
        cp = Contextpacker(max_tokens=20)
        parts = [
            {"text": "low priority text that is fairly long", "priority": 1},
            {"text": "IMPORTANT", "priority": 10},
        ]
        result = cp.pack_priority(parts)
        assert "IMPORTANT" in result

    def test_drops_lowest_priority_when_tight(self):
        cp = Contextpacker(max_tokens=5)
        parts = [
            {"text": "low " * 20, "priority": 1},
            {"text": "hi", "priority": 99},
        ]
        result = cp.pack_priority(parts)
        assert "hi" in result
        assert "low" not in result

    def test_preserves_original_order_in_output(self):
        """Selected parts must appear in their original input order."""
        cp = Contextpacker(max_tokens=100)
        parts = [
            {"text": "first", "priority": 3},
            {"text": "second", "priority": 5},
            {"text": "third", "priority": 1},
        ]
        result = cp.pack_priority(parts)
        # All three fit, so order must match input: first, second, third
        idx_first = result.index("first")
        idx_second = result.index("second")
        idx_third = result.index("third")
        assert idx_first < idx_second < idx_third

    def test_missing_text_key_defaults_to_empty(self):
        cp = Contextpacker(max_tokens=100)
        parts = [{"priority": 5}]  # no "text" key
        result = cp.pack_priority(parts)
        assert result == ""

    def test_missing_priority_key_defaults_to_zero(self):
        cp = Contextpacker(max_tokens=100)
        parts = [{"text": "hello"}]  # no "priority" key
        result = cp.pack_priority(parts)
        assert result == "hello"

    def test_empty_parts_list(self, cp):
        assert cp.pack_priority([]) == ""


# ---------------------------------------------------------------------------
# pack_chat
# ---------------------------------------------------------------------------

class TestPackChat:
    def test_all_fit(self, cp):
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        result = cp.pack_chat(msgs)
        assert len(result) == 2

    def test_drops_oldest_non_system(self):
        cp = Contextpacker(max_tokens=5)
        msgs = [
            {"role": "user", "content": "old message that is very long and won't fit"},
            {"role": "assistant", "content": "hi"},
        ]
        result = cp.pack_chat(msgs)
        assert any(m["content"] == "hi" for m in result)
        assert not any("old message" in m["content"] for m in result)

    def test_keeps_system_message(self, cp):
        msgs = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "hello"},
        ]
        result = cp.pack_chat(msgs)
        assert result[0]["role"] == "system"

    def test_system_first_in_output(self, cp):
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "system", "content": "You are helpful."},
        ]
        result = cp.pack_chat(msgs)
        assert result[0]["role"] == "system"

    def test_keep_system_false(self):
        cp = Contextpacker(max_tokens=100)
        msgs = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "hello"},
        ]
        result = cp.pack_chat(msgs, keep_system=False)
        assert all(m["role"] != "system" for m in result)

    def test_missing_content_key_does_not_crash(self, cp):
        """Malformed messages without 'content' must not raise KeyError."""
        msgs = [{"role": "user"}]
        result = cp.pack_chat(msgs)
        assert isinstance(result, list)

    def test_empty_messages_list(self, cp):
        assert cp.pack_chat([]) == []

    def test_only_system_messages(self, cp):
        msgs = [{"role": "system", "content": "Instruction."}]
        result = cp.pack_chat(msgs)
        assert len(result) == 1 and result[0]["role"] == "system"


# ---------------------------------------------------------------------------
# split
# ---------------------------------------------------------------------------

class TestSplit:
    def test_short_text_single_chunk(self, cp):
        chunks = cp.split("hello")
        assert len(chunks) == 1
        assert chunks[0] == "hello"

    def test_long_text_multiple_chunks(self):
        cp = Contextpacker(max_tokens=10)
        chunks = cp.split("a" * 200)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 40  # 10 tokens * 4 chars

    def test_all_chars_preserved(self):
        cp = Contextpacker(max_tokens=10)
        text = "a" * 200
        chunks = cp.split(text)
        assert "".join(chunks) == text

    def test_empty_string(self, cp):
        chunks = cp.split("")
        assert chunks == [""]

    def test_exact_chunk_boundary(self):
        cp = Contextpacker(max_tokens=10)
        text = "a" * 40  # exactly one chunk
        chunks = cp.split(text)
        assert len(chunks) == 1


# ---------------------------------------------------------------------------
# sliding_window
# ---------------------------------------------------------------------------

class TestSlidingWindow:
    def test_recent_part_included(self):
        cp = Contextpacker(max_tokens=10)
        parts = ["old " * 20, "middle " * 20, "recent"]
        result = cp.sliding_window(parts)
        assert "recent" in result

    def test_old_part_excluded_when_tight(self):
        cp = Contextpacker(max_tokens=5)
        parts = ["old " * 20, "new"]
        result = cp.sliding_window(parts)
        assert result == ["new"]

    def test_preserves_order(self):
        cp = Contextpacker(max_tokens=100)
        parts = ["a", "b", "c"]
        result = cp.sliding_window(parts)
        assert result == ["a", "b", "c"]

    def test_empty_list(self, cp):
        assert cp.sliding_window([]) == []

    def test_all_fit(self, cp):
        parts = ["short", "also short", "tiny"]
        result = cp.sliding_window(parts)
        assert result == parts
