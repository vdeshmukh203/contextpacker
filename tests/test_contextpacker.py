"""Tests for contextpacker."""
import pytest
from contextpacker import Contextpacker
from contextpacker.packer import CHARS_PER_TOKEN, DEFAULT_MAX_TOKENS


# ---------------------------------------------------------------------------
# Construction & properties
# ---------------------------------------------------------------------------

def test_default_construction():
    cp = Contextpacker()
    assert cp.max_tokens == DEFAULT_MAX_TOKENS
    assert cp.separator == "\n\n"


def test_custom_construction():
    cp = Contextpacker(max_tokens=512, separator=" | ")
    assert cp.max_tokens == 512
    assert cp.separator == " | "


def test_repr():
    cp = Contextpacker(max_tokens=100, separator="\n")
    r = repr(cp)
    assert "100" in r
    assert "Contextpacker" in r


def test_invalid_max_tokens_zero():
    with pytest.raises(ValueError):
        Contextpacker(max_tokens=0)


def test_invalid_max_tokens_negative():
    with pytest.raises(ValueError):
        Contextpacker(max_tokens=-1)


def test_invalid_max_tokens_string():
    with pytest.raises(ValueError):
        Contextpacker(max_tokens="big")  # type: ignore[arg-type]


def test_invalid_max_tokens_bool():
    with pytest.raises(ValueError):
        Contextpacker(max_tokens=True)


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------

def test_count_basic():
    cp = Contextpacker()
    assert cp.count("hello world") >= 1


def test_count_empty():
    cp = Contextpacker()
    assert cp.count("") == 0


def test_count_single_word():
    cp = Contextpacker()
    assert cp.count("hello") == 1


def test_count_chars_basic():
    cp = Contextpacker()
    text = "a" * 40
    assert cp.count_chars(text) == 10


def test_count_chars_empty():
    cp = Contextpacker()
    assert cp.count_chars("") == 0


def test_count_chars_short():
    cp = Contextpacker()
    assert cp.count_chars("ab") == 0


def test_count_chars_exactly_four():
    cp = Contextpacker()
    assert cp.count_chars("abcd") == 1


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------

def test_truncate_short_unchanged():
    cp = Contextpacker(max_tokens=1000)
    assert cp.truncate("hello") == "hello"


def test_truncate_long():
    cp = Contextpacker(max_tokens=10)
    result = cp.truncate("a" * 200)
    assert len(result) == 10 * CHARS_PER_TOKEN


def test_truncate_empty():
    cp = Contextpacker(max_tokens=10)
    assert cp.truncate("") == ""


def test_truncate_exact_boundary():
    cp = Contextpacker(max_tokens=5)
    text = "a" * (5 * CHARS_PER_TOKEN)
    assert cp.truncate(text) == text


def test_truncate_start_keeps_end():
    cp = Contextpacker(max_tokens=5)
    text = "START" + "x" * 100
    result = cp.truncate_start(text)
    assert result.endswith("x" * 20)
    assert not result.startswith("START")


def test_truncate_start_short_unchanged():
    cp = Contextpacker(max_tokens=1000)
    assert cp.truncate_start("hello") == "hello"


def test_truncate_per_call_override():
    cp = Contextpacker(max_tokens=1000)
    result = cp.truncate("a" * 200, max_tokens=10)
    assert len(result) == 40


# ---------------------------------------------------------------------------
# Packing
# ---------------------------------------------------------------------------

def test_pack_basic():
    cp = Contextpacker(max_tokens=1000)
    result = cp.pack(["part1", "part2"])
    assert "part1" in result and "part2" in result


def test_pack_uses_separator():
    cp = Contextpacker(max_tokens=1000, separator=" | ")
    result = cp.pack(["A", "B"])
    assert result == "A | B"


def test_pack_ignores_empty_strings():
    cp = Contextpacker(max_tokens=1000)
    result = cp.pack(["A", "", "B"])
    assert result == "A\n\nB"


def test_pack_truncates_to_limit():
    cp = Contextpacker(max_tokens=5)
    result = cp.pack(["a" * 100, "b" * 100])
    assert len(result) <= 5 * CHARS_PER_TOKEN


def test_pack_empty_list():
    cp = Contextpacker(max_tokens=100)
    assert cp.pack([]) == ""


# ---------------------------------------------------------------------------
# Priority packing
# ---------------------------------------------------------------------------

def test_pack_priority_keeps_high_priority():
    cp = Contextpacker(max_tokens=20)
    parts = [
        {"text": "low priority text", "priority": 1},
        {"text": "IMPORTANT", "priority": 10},
    ]
    result = cp.pack_priority(parts)
    assert "IMPORTANT" in result


def test_pack_priority_drops_low_priority():
    cp = Contextpacker(max_tokens=5)
    parts = [
        {"text": "a" * 30, "priority": 1},
        {"text": "KEEP", "priority": 99},
    ]
    result = cp.pack_priority(parts)
    assert "KEEP" in result
    assert "a" * 30 not in result


def test_pack_priority_all_fit():
    cp = Contextpacker(max_tokens=10000)
    parts = [
        {"text": "first", "priority": 2},
        {"text": "second", "priority": 1},
    ]
    result = cp.pack_priority(parts)
    assert "first" in result and "second" in result


def test_pack_priority_empty():
    cp = Contextpacker(max_tokens=100)
    assert cp.pack_priority([]) == ""


# ---------------------------------------------------------------------------
# Chat packing
# ---------------------------------------------------------------------------

def test_pack_chat_all_fit():
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


def test_pack_chat_keeps_system_first():
    cp = Contextpacker(max_tokens=1000)
    msgs = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "hello"},
    ]
    result = cp.pack_chat(msgs)
    assert result[0]["role"] == "system"


def test_pack_chat_keep_system_false():
    cp = Contextpacker(max_tokens=1000)
    msgs = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "hello"},
    ]
    result = cp.pack_chat(msgs, keep_system=False)
    assert all(m["role"] != "system" for m in result)


def test_pack_chat_preserves_order():
    cp = Contextpacker(max_tokens=10000)
    msgs = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "second"},
        {"role": "user", "content": "third"},
    ]
    result = cp.pack_chat(msgs)
    contents = [m["content"] for m in result]
    assert contents == ["first", "second", "third"]


def test_pack_chat_empty():
    cp = Contextpacker(max_tokens=100)
    assert cp.pack_chat([]) == []


# ---------------------------------------------------------------------------
# Splitting
# ---------------------------------------------------------------------------

def test_split_short_text_single_chunk():
    cp = Contextpacker(max_tokens=1000)
    result = cp.split("hello world")
    assert result == ["hello world"]


def test_split_long_text_multiple_chunks():
    cp = Contextpacker(max_tokens=10)
    chunks = cp.split("a" * 200)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 10 * CHARS_PER_TOKEN


def test_split_exact_boundary():
    cp = Contextpacker(max_tokens=5)
    text = "a" * (5 * CHARS_PER_TOKEN)
    chunks = cp.split(text)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_split_empty_text():
    cp = Contextpacker(max_tokens=10)
    assert cp.split("") == [""]


def test_split_chunks_cover_full_text():
    cp = Contextpacker(max_tokens=10)
    text = "a" * 200
    chunks = cp.split(text)
    assert "".join(chunks) == text


# ---------------------------------------------------------------------------
# Sliding window
# ---------------------------------------------------------------------------

def test_sliding_window_keeps_recent():
    cp = Contextpacker(max_tokens=10)
    parts = ["old " * 20, "middle " * 20, "recent"]
    result = cp.sliding_window(parts)
    assert "recent" in result


def test_sliding_window_empty_list():
    cp = Contextpacker(max_tokens=100)
    assert cp.sliding_window([]) == []


def test_sliding_window_all_fit():
    cp = Contextpacker(max_tokens=10000)
    parts = ["alpha", "beta", "gamma"]
    result = cp.sliding_window(parts)
    assert result == parts


def test_sliding_window_contiguous_suffix():
    cp = Contextpacker(max_tokens=5)
    parts = ["a" * 80, "b" * 8, "c" * 8]
    result = cp.sliding_window(parts)
    if result:
        assert result == parts[len(parts) - len(result):]
