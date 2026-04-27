"""Tests for contextpacker."""
import pytest
from contextpacker import Contextpacker


# ──────────────────────────────────────────────────────────────
# Construction & properties
# ──────────────────────────────────────────────────────────────

def test_repr():
    cp = Contextpacker(max_tokens=512, separator="||")
    assert "512" in repr(cp)
    assert "||" in repr(cp)


def test_max_tokens_property():
    cp = Contextpacker(max_tokens=1024)
    assert cp.max_tokens == 1024


def test_separator_property():
    cp = Contextpacker(separator="---")
    assert cp.separator == "---"


def test_invalid_max_tokens_raises():
    with pytest.raises(ValueError):
        Contextpacker(max_tokens=0)
    with pytest.raises(ValueError):
        Contextpacker(max_tokens=-1)
    with pytest.raises(TypeError):
        Contextpacker(max_tokens="big")  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────
# Token counting
# ──────────────────────────────────────────────────────────────

def test_count_basic():
    cp = Contextpacker()
    assert cp.count("hello world") >= 1


def test_count_empty():
    cp = Contextpacker()
    assert cp.count("") == 0


def test_count_chars_empty():
    cp = Contextpacker()
    assert cp.count_chars("") == 0


def test_count_type_error():
    cp = Contextpacker()
    with pytest.raises(TypeError):
        cp.count(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        cp.count_chars(42)  # type: ignore[arg-type]


def test_count_chars_positive():
    cp = Contextpacker()
    assert cp.count_chars("a" * 100) == 25


# ──────────────────────────────────────────────────────────────
# Truncation
# ──────────────────────────────────────────────────────────────

def test_truncate_short():
    cp = Contextpacker(max_tokens=1000)
    assert cp.truncate("hello") == "hello"


def test_truncate_long():
    cp = Contextpacker(max_tokens=10)
    result = cp.truncate("a" * 200)
    assert len(result) == 40


def test_truncate_exact_boundary():
    cp = Contextpacker(max_tokens=5)
    text = "x" * 20  # exactly 5 tokens @ 4 chars/token
    assert cp.truncate(text) == text


def test_truncate_start():
    cp = Contextpacker(max_tokens=5)
    text = "START" + "x" * 100
    result = cp.truncate_start(text)
    assert result.endswith("x" * 20)
    assert not result.startswith("START")


def test_truncate_empty():
    cp = Contextpacker(max_tokens=10)
    assert cp.truncate("") == ""
    assert cp.truncate_start("") == ""


def test_truncate_type_error():
    cp = Contextpacker()
    with pytest.raises(TypeError):
        cp.truncate(123)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        cp.truncate_start(None)  # type: ignore[arg-type]


def test_truncate_per_call_limit():
    cp = Contextpacker(max_tokens=1000)
    result = cp.truncate("a" * 200, max_tokens=10)
    assert len(result) == 40


# ──────────────────────────────────────────────────────────────
# Pack
# ──────────────────────────────────────────────────────────────

def test_pack():
    cp = Contextpacker(max_tokens=1000)
    result = cp.pack(["part1", "part2"])
    assert "part1" in result and "part2" in result


def test_pack_truncates():
    cp = Contextpacker(max_tokens=5)
    result = cp.pack(["a" * 100, "b" * 100])
    assert len(result) <= 20


def test_pack_filters_empty_parts():
    cp = Contextpacker(max_tokens=1000)
    result = cp.pack(["hello", "", "world"])
    assert "hello" in result and "world" in result


def test_pack_custom_separator():
    cp = Contextpacker(max_tokens=1000, separator=" | ")
    result = cp.pack(["a", "b"])
    assert " | " in result


def test_pack_type_error():
    cp = Contextpacker()
    with pytest.raises(TypeError):
        cp.pack("not a list")  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────
# Priority pack
# ──────────────────────────────────────────────────────────────

def test_pack_priority_includes_high_priority():
    cp = Contextpacker(max_tokens=20)
    parts = [
        {"text": "low priority text", "priority": 1},
        {"text": "IMPORTANT", "priority": 10},
    ]
    result = cp.pack_priority(parts)
    assert "IMPORTANT" in result


def test_pack_priority_preserves_insertion_order():
    """Selected items must appear in their original order, not priority order."""
    cp = Contextpacker(max_tokens=1000)
    parts = [
        {"text": "first", "priority": 5},
        {"text": "second", "priority": 10},
        {"text": "third", "priority": 1},
    ]
    result = cp.pack_priority(parts)
    assert result.index("first") < result.index("second") < result.index("third")


def test_pack_priority_drops_low_priority_when_tight():
    cp = Contextpacker(max_tokens=4)  # 16 chars
    parts = [
        {"text": "keep this!", "priority": 10},  # 10 chars
        {"text": "drop me please now!", "priority": 1},  # 19 chars — won't fit
    ]
    result = cp.pack_priority(parts)
    assert "keep this!" in result
    assert "drop me please now!" not in result


def test_pack_priority_missing_priority_defaults_to_zero():
    cp = Contextpacker(max_tokens=1000)
    parts = [{"text": "no priority key"}]
    result = cp.pack_priority(parts)
    assert "no priority key" in result


def test_pack_priority_type_error():
    cp = Contextpacker()
    with pytest.raises(TypeError):
        cp.pack_priority("not a list")  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────
# Chat pack
# ──────────────────────────────────────────────────────────────

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


def test_pack_chat_system_first_in_output():
    cp = Contextpacker(max_tokens=1000)
    msgs = [
        {"role": "user", "content": "hi"},
        {"role": "system", "content": "sys"},
        {"role": "assistant", "content": "hey"},
    ]
    result = cp.pack_chat(msgs)
    assert result[0]["role"] == "system"


def test_pack_chat_missing_content_does_not_raise():
    """Messages with no 'content' key should not raise KeyError."""
    cp = Contextpacker(max_tokens=1000)
    msgs = [{"role": "user"}]  # missing 'content'
    result = cp.pack_chat(msgs)
    assert isinstance(result, list)


def test_pack_chat_no_system():
    cp = Contextpacker(max_tokens=1000)
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
    ]
    result = cp.pack_chat(msgs, keep_system=False)
    assert all(m["role"] != "system" for m in result)


def test_pack_chat_type_error():
    cp = Contextpacker()
    with pytest.raises(TypeError):
        cp.pack_chat("not a list")  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────
# Split
# ──────────────────────────────────────────────────────────────

def test_split_short():
    cp = Contextpacker(max_tokens=100)
    chunks = cp.split("short text")
    assert chunks == ["short text"]


def test_split_long():
    cp = Contextpacker(max_tokens=10)
    chunks = cp.split("a" * 200)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 40


def test_split_exact_boundary():
    cp = Contextpacker(max_tokens=5)
    text = "x" * 20  # exactly 5 tokens
    assert cp.split(text) == [text]


def test_split_empty():
    cp = Contextpacker(max_tokens=10)
    assert cp.split("") == [""]


def test_split_type_error():
    cp = Contextpacker()
    with pytest.raises(TypeError):
        cp.split(None)  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────
# Sliding window
# ──────────────────────────────────────────────────────────────

def test_sliding_window_keeps_recent():
    cp = Contextpacker(max_tokens=10)
    parts = ["old " * 20, "middle " * 20, "recent"]
    result = cp.sliding_window(parts)
    assert "recent" in result


def test_sliding_window_empty_parts():
    cp = Contextpacker(max_tokens=10)
    assert cp.sliding_window([]) == []


def test_sliding_window_all_fit():
    cp = Contextpacker(max_tokens=1000)
    parts = ["a", "b", "c"]
    assert cp.sliding_window(parts) == parts


def test_sliding_window_type_error():
    cp = Contextpacker()
    with pytest.raises(TypeError):
        cp.sliding_window("not a list")  # type: ignore[arg-type]
