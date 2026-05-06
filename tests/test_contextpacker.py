"""Tests for contextpacker."""
import pytest
from contextpacker import Contextpacker


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
    assert cp.count("   \n\t  ") == 0


def test_count_chars_empty():
    cp = Contextpacker()
    assert cp.count_chars("") == 0


def test_count_chars_basic():
    cp = Contextpacker()
    # 8 chars → 2 tokens (8 // 4)
    assert cp.count_chars("abcdefgh") == 2


def test_count_chars_short():
    cp = Contextpacker()
    # 3 chars → max(1, 0) = 1
    assert cp.count_chars("abc") == 1


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------

def test_negative_max_tokens_raises():
    with pytest.raises(ValueError):
        Contextpacker(max_tokens=-1)


def test_zero_max_tokens_ok():
    cp = Contextpacker(max_tokens=0)
    assert cp.max_tokens == 0


def test_properties():
    cp = Contextpacker(max_tokens=512, separator=" | ")
    assert cp.max_tokens == 512
    assert cp.separator == " | "


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------

def test_truncate_short():
    cp = Contextpacker(max_tokens=1000)
    assert cp.truncate("hello") == "hello"


def test_truncate_long():
    cp = Contextpacker(max_tokens=10)
    result = cp.truncate("a" * 200)
    assert len(result) == 40  # 10 tokens * 4 chars


def test_truncate_empty():
    cp = Contextpacker(max_tokens=10)
    assert cp.truncate("") == ""


def test_truncate_start():
    cp = Contextpacker(max_tokens=5)
    text = "START" + "x" * 100
    result = cp.truncate_start(text)
    assert result.endswith("x" * 20)
    assert not result.startswith("START")


def test_truncate_start_short():
    cp = Contextpacker(max_tokens=1000)
    assert cp.truncate_start("hello") == "hello"


def test_truncate_override():
    cp = Contextpacker(max_tokens=1000)
    result = cp.truncate("a" * 100, max_tokens=5)
    assert len(result) == 20


def test_truncate_negative_limit_raises():
    cp = Contextpacker()
    with pytest.raises(ValueError):
        cp.truncate("hello", max_tokens=-1)


# ---------------------------------------------------------------------------
# Pack
# ---------------------------------------------------------------------------

def test_pack_basic():
    cp = Contextpacker(max_tokens=1000)
    result = cp.pack(["part1", "part2"])
    assert "part1" in result and "part2" in result


def test_pack_truncates():
    cp = Contextpacker(max_tokens=5)
    result = cp.pack(["a" * 100, "b" * 100])
    assert len(result) <= 20


def test_pack_empty_parts_ignored():
    cp = Contextpacker(max_tokens=1000)
    result = cp.pack(["hello", "", "world"])
    assert "hello" in result and "world" in result
    assert result == "hello\n\nworld"


def test_pack_all_empty():
    cp = Contextpacker(max_tokens=1000)
    assert cp.pack([]) == ""
    assert cp.pack(["", "", ""]) == ""


# ---------------------------------------------------------------------------
# Pack priority
# ---------------------------------------------------------------------------

def test_pack_priority_keeps_high():
    cp = Contextpacker(max_tokens=20)
    parts = [
        {"text": "low priority text here", "priority": 1},
        {"text": "IMPORTANT", "priority": 10},
    ]
    result = cp.pack_priority(parts)
    assert "IMPORTANT" in result


def test_pack_priority_drops_low_when_budget_tight():
    cp = Contextpacker(max_tokens=3)  # 12 chars
    parts = [
        {"text": "drop me please yes", "priority": 1},   # >12 chars
        {"text": "keep", "priority": 10},                 # 4 chars → 1 token
    ]
    result = cp.pack_priority(parts)
    assert "keep" in result
    assert "drop" not in result


def test_pack_priority_empty():
    cp = Contextpacker(max_tokens=100)
    assert cp.pack_priority([]) == ""


# ---------------------------------------------------------------------------
# Pack chat
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
        {"role": "user", "content": "old message that is very long indeed"},
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


def test_pack_chat_system_not_kept():
    cp = Contextpacker(max_tokens=1000)
    msgs = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "hello"},
    ]
    result = cp.pack_chat(msgs, keep_system=False)
    assert all(m["role"] != "system" for m in result)


def test_pack_chat_system_larger_than_limit():
    # System messages consume entire budget; no non-system messages should appear.
    cp = Contextpacker(max_tokens=1)
    msgs = [
        {"role": "system", "content": "A" * 200},
        {"role": "user", "content": "hello"},
    ]
    result = cp.pack_chat(msgs)
    assert any(m["role"] == "system" for m in result)
    # budget is 0 after system; "hello" must not appear
    assert not any(m["role"] == "user" for m in result)


def test_pack_chat_empty():
    cp = Contextpacker(max_tokens=1000)
    assert cp.pack_chat([]) == []


# ---------------------------------------------------------------------------
# Split
# ---------------------------------------------------------------------------

def test_split_basic():
    cp = Contextpacker(max_tokens=10)
    chunks = cp.split("a" * 200)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 40  # 10 tokens * 4 chars


def test_split_short():
    cp = Contextpacker(max_tokens=1000)
    assert cp.split("hello") == ["hello"]


def test_split_empty():
    cp = Contextpacker(max_tokens=10)
    assert cp.split("") == []


def test_split_exact_boundary():
    cp = Contextpacker(max_tokens=5)  # 20 chars per chunk
    text = "a" * 40
    chunks = cp.split(text)
    assert len(chunks) == 2
    assert all(len(c) == 20 for c in chunks)


# ---------------------------------------------------------------------------
# Sliding window
# ---------------------------------------------------------------------------

def test_sliding_window_basic():
    cp = Contextpacker(max_tokens=10)
    parts = ["old " * 20, "middle " * 20, "recent"]
    result = cp.sliding_window(parts)
    assert "recent" in result


def test_sliding_window_all_fit():
    cp = Contextpacker(max_tokens=10000)
    parts = ["a", "b", "c"]
    assert cp.sliding_window(parts) == ["a", "b", "c"]


def test_sliding_window_empty():
    cp = Contextpacker(max_tokens=100)
    assert cp.sliding_window([]) == []


def test_sliding_window_order_preserved():
    cp = Contextpacker(max_tokens=5)  # 20 chars
    parts = ["old_part_that_is_long_enough_to_not_fit_at_all", "short"]
    result = cp.sliding_window(parts)
    assert result == ["short"]
