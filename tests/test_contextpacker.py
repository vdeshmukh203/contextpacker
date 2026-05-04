"""Tests for contextpacker."""
import pytest

from contextpacker import Contextpacker


# ---------------------------------------------------------------------------
# Construction & properties
# ---------------------------------------------------------------------------

def test_repr():
    cp = Contextpacker(max_tokens=512, separator=" | ")
    assert "512" in repr(cp)
    assert " | " in repr(cp)


def test_separator_property():
    cp = Contextpacker(separator="---")
    assert cp.separator == "---"


def test_max_tokens_property():
    cp = Contextpacker(max_tokens=1024)
    assert cp.max_tokens == 1024


def test_invalid_max_tokens_zero():
    with pytest.raises(ValueError):
        Contextpacker(max_tokens=0)


def test_invalid_max_tokens_negative():
    with pytest.raises(ValueError):
        Contextpacker(max_tokens=-1)


def test_invalid_max_tokens_float():
    with pytest.raises(ValueError):
        Contextpacker(max_tokens=8.5)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------

def test_count_basic():
    cp = Contextpacker()
    assert cp.count("hello world") >= 1


def test_count_empty():
    cp = Contextpacker()
    assert cp.count("") == 0


def test_count_whitespace_only():
    cp = Contextpacker()
    assert cp.count("   \t\n  ") == 0


def test_count_chars_basic():
    cp = Contextpacker()
    # 8 chars / 4 = 2 tokens
    assert cp.count_chars("abcdefgh") == 2


def test_count_chars_empty():
    cp = Contextpacker()
    assert cp.count_chars("") == 0


def test_count_chars_short_nonempty():
    cp = Contextpacker()
    # Fewer than CHARS_PER_TOKEN chars → at least 1 token
    assert cp.count_chars("hi") == 1


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------

def test_truncate_short():
    cp = Contextpacker(max_tokens=1000)
    assert cp.truncate("hello") == "hello"


def test_truncate_long():
    cp = Contextpacker(max_tokens=10)
    result = cp.truncate("a" * 200)
    assert len(result) == 40


def test_truncate_exact_boundary():
    cp = Contextpacker(max_tokens=5)
    text = "a" * 20  # exactly 5 tokens (5*4)
    assert cp.truncate(text) == text


def test_truncate_start():
    cp = Contextpacker(max_tokens=5)
    text = "START" + "x" * 100
    result = cp.truncate_start(text)
    assert result.endswith("x" * 20)
    assert not result.startswith("START")


def test_truncate_start_short():
    cp = Contextpacker(max_tokens=1000)
    assert cp.truncate_start("hello") == "hello"


# ---------------------------------------------------------------------------
# Packing — basic
# ---------------------------------------------------------------------------

def test_pack_fits():
    cp = Contextpacker(max_tokens=1000)
    result = cp.pack(["part1", "part2"])
    assert "part1" in result and "part2" in result


def test_pack_truncates():
    cp = Contextpacker(max_tokens=5)
    result = cp.pack(["a" * 100, "b" * 100])
    assert len(result) <= 20


def test_pack_skips_empty_parts():
    cp = Contextpacker(max_tokens=1000)
    result = cp.pack(["hello", "", "world"])
    assert result == "hello\n\nworld"


def test_pack_all_empty():
    cp = Contextpacker(max_tokens=1000)
    assert cp.pack(["", "", ""]) == ""


def test_pack_custom_separator():
    cp = Contextpacker(max_tokens=1000, separator=" | ")
    result = cp.pack(["a", "b", "c"])
    assert result == "a | b | c"


# ---------------------------------------------------------------------------
# Packing — priority
# ---------------------------------------------------------------------------

def test_pack_priority_keeps_important():
    cp = Contextpacker(max_tokens=20)
    parts = [
        {"text": "low priority text", "priority": 1},
        {"text": "IMPORTANT", "priority": 10},
    ]
    result = cp.pack_priority(parts)
    assert "IMPORTANT" in result


def test_pack_priority_preserves_order():
    cp = Contextpacker(max_tokens=1000)
    parts = [
        {"text": "first", "priority": 1},
        {"text": "second", "priority": 5},
        {"text": "third", "priority": 3},
    ]
    result = cp.pack_priority(parts)
    assert result.index("first") < result.index("second") < result.index("third")


def test_pack_priority_drops_lowest():
    # max_tokens=3 → 3-token budget; each 8-char part costs 2 tokens.
    # High-priority "A"*8 is selected first (2 tokens used).
    # Low-priority "B"*8 would take budget to 4 > 3 → dropped.
    cp = Contextpacker(max_tokens=3)
    parts = [
        {"text": "A" * 8, "priority": 10},
        {"text": "B" * 8, "priority": 1},
    ]
    result = cp.pack_priority(parts)
    assert "A" * 8 in result
    assert "B" * 8 not in result


def test_pack_priority_skips_empty_text():
    cp = Contextpacker(max_tokens=1000)
    parts = [
        {"text": "", "priority": 99},
        {"text": "real content", "priority": 1},
    ]
    result = cp.pack_priority(parts)
    assert "real content" in result
    assert result.count(cp.separator) == 0  # only one part selected


# ---------------------------------------------------------------------------
# Packing — proportional
# ---------------------------------------------------------------------------

def test_pack_proportional_fits():
    cp = Contextpacker(max_tokens=1000)
    result = cp.pack_proportional(["hello", "world"])
    assert result == "hello\n\nworld"


def test_pack_proportional_truncates_all():
    cp = Contextpacker(max_tokens=4)  # 16 chars content budget (minus separators)
    parts = ["a" * 100, "b" * 100]
    result = cp.pack_proportional(parts)
    # Both parts should appear
    assert "a" in result
    assert "b" in result
    # Total length should be within budget + separator
    sep_len = len("\n\n")
    assert len(result) <= 4 * 4 + sep_len


def test_pack_proportional_empty_parts():
    cp = Contextpacker(max_tokens=1000)
    assert cp.pack_proportional(["", "", ""]) == ""


def test_pack_proportional_larger_part_gets_more():
    cp = Contextpacker(max_tokens=10)  # 40 chars
    big = "B" * 80
    small = "s" * 20
    result = cp.pack_proportional([big, small])
    # big is 80/(80+20)=80% of total; should get ~80% of budget
    parts_out = result.split("\n\n")
    assert len(parts_out[0]) > len(parts_out[1])


# ---------------------------------------------------------------------------
# Chat packing
# ---------------------------------------------------------------------------

def test_pack_chat_fits():
    cp = Contextpacker(max_tokens=1000)
    msgs = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
    result = cp.pack_chat(msgs)
    assert len(result) == 2


def test_pack_chat_drops_oldest():
    cp = Contextpacker(max_tokens=5)
    msgs = [
        {"role": "user", "content": "old message that is very long"},
        {"role": "assistant", "content": "hi"},
    ]
    result = cp.pack_chat(msgs)
    assert any(m["content"] == "hi" for m in result)


def test_pack_chat_keeps_system():
    cp = Contextpacker(max_tokens=1000)
    msgs = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "hello"},
    ]
    result = cp.pack_chat(msgs)
    assert result[0]["role"] == "system"


def test_pack_chat_no_system_when_disabled():
    cp = Contextpacker(max_tokens=1000)
    msgs = [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "hello"},
    ]
    result = cp.pack_chat(msgs, keep_system=False)
    assert all(m["role"] != "system" for m in result)


# ---------------------------------------------------------------------------
# Splitting
# ---------------------------------------------------------------------------

def test_split_fits():
    cp = Contextpacker(max_tokens=1000)
    chunks = cp.split("short text")
    assert chunks == ["short text"]


def test_split_multiple():
    cp = Contextpacker(max_tokens=10)
    chunks = cp.split("a" * 200)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 40


def test_split_exact_boundary():
    cp = Contextpacker(max_tokens=10)
    text = "a" * 40  # exactly one chunk
    chunks = cp.split(text)
    assert len(chunks) == 1 and chunks[0] == text


# ---------------------------------------------------------------------------
# Sliding window
# ---------------------------------------------------------------------------

def test_sliding_window_keeps_recent():
    cp = Contextpacker(max_tokens=10)
    parts = ["old " * 20, "middle " * 20, "recent"]
    result = cp.sliding_window(parts)
    assert "recent" in result


def test_sliding_window_all_fit():
    cp = Contextpacker(max_tokens=1000)
    parts = ["short", "pieces", "here"]
    result = cp.sliding_window(parts)
    assert result == parts


def test_sliding_window_empty_list():
    cp = Contextpacker(max_tokens=100)
    assert cp.sliding_window([]) == []
