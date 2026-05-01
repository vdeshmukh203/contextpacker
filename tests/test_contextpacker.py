"""Tests for contextpacker."""
import pytest
from contextpacker import Contextpacker


# ------------------------------------------------------------------
# Constructor
# ------------------------------------------------------------------

def test_constructor_default():
    cp = Contextpacker()
    assert cp.max_tokens == 8192
    assert cp.separator == "\n\n"


def test_constructor_custom():
    cp = Contextpacker(max_tokens=512, separator="---")
    assert cp.max_tokens == 512
    assert cp.separator == "---"


def test_constructor_rejects_zero_max_tokens():
    with pytest.raises(ValueError):
        Contextpacker(max_tokens=0)


def test_constructor_rejects_negative_max_tokens():
    with pytest.raises(ValueError):
        Contextpacker(max_tokens=-1)


# ------------------------------------------------------------------
# Token counting
# ------------------------------------------------------------------

def test_count():
    cp = Contextpacker()
    assert cp.count("hello world") >= 1


def test_count_empty_string():
    cp = Contextpacker()
    assert cp.count("") == 0


def test_count_single_word():
    cp = Contextpacker()
    assert cp.count("hello") >= 1


def test_count_chars_empty_string():
    cp = Contextpacker()
    assert cp.count_chars("") == 0


def test_count_chars_nonempty():
    cp = Contextpacker()
    assert cp.count_chars("hello world") >= 1


# ------------------------------------------------------------------
# Truncation
# ------------------------------------------------------------------

def test_truncate_short():
    cp = Contextpacker(max_tokens=1000)
    assert cp.truncate("hello") == "hello"


def test_truncate_long():
    cp = Contextpacker(max_tokens=10)
    result = cp.truncate("a" * 200)
    assert len(result) == 40


def test_truncate_start():
    cp = Contextpacker(max_tokens=5)
    text = "START" + "x" * 100
    result = cp.truncate_start(text)
    assert result.endswith("x" * 20)
    assert not result.startswith("START")


def test_truncate_exact_boundary():
    cp = Contextpacker(max_tokens=10)
    text = "a" * 40  # exactly 10 tokens
    assert cp.truncate(text) == text


# ------------------------------------------------------------------
# Packing
# ------------------------------------------------------------------

def test_pack():
    cp = Contextpacker(max_tokens=1000)
    result = cp.pack(["part1", "part2"])
    assert "part1" in result and "part2" in result


def test_pack_uses_separator():
    cp = Contextpacker(max_tokens=1000, separator="|||")
    result = cp.pack(["a", "b"])
    assert "|||" in result


def test_pack_truncates():
    cp = Contextpacker(max_tokens=5)
    result = cp.pack(["a" * 100, "b" * 100])
    assert len(result) <= 20


def test_pack_skips_empty_parts():
    cp = Contextpacker(max_tokens=1000)
    result = cp.pack(["hello", "", "world"])
    assert "hello" in result and "world" in result
    # empty part not joined as a blank line between the two
    assert "\n\n\n\n" not in result


# ------------------------------------------------------------------
# Priority packing
# ------------------------------------------------------------------

def test_pack_priority_includes_important():
    cp = Contextpacker(max_tokens=20)
    parts = [
        {"text": "low priority text", "priority": 1},
        {"text": "IMPORTANT", "priority": 10},
    ]
    result = cp.pack_priority(parts)
    assert "IMPORTANT" in result


def test_pack_priority_preserves_original_order():
    cp = Contextpacker(max_tokens=500)
    parts = [
        {"text": "first item", "priority": 1},
        {"text": "second item", "priority": 10},
        {"text": "third item", "priority": 5},
    ]
    result = cp.pack_priority(parts)
    # All three fit; output must appear in document order, not priority order
    assert result.index("first") < result.index("second") < result.index("third")


def test_pack_priority_drops_low_priority_when_tight():
    cp = Contextpacker(max_tokens=5)
    parts = [
        {"text": "x" * 100, "priority": 1},
        {"text": "hi", "priority": 10},
    ]
    result = cp.pack_priority(parts)
    assert "hi" in result
    assert "x" * 100 not in result


def test_pack_priority_empty_list():
    cp = Contextpacker(max_tokens=100)
    assert cp.pack_priority([]) == ""


# ------------------------------------------------------------------
# Chat packing
# ------------------------------------------------------------------

def test_pack_chat_fits():
    cp = Contextpacker(max_tokens=1000)
    msgs = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
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


def test_pack_chat_budget_exhausted_by_system():
    """When system tokens leave no budget, only system messages are returned."""
    cp = Contextpacker(max_tokens=2)
    msgs = [
        {"role": "system", "content": "you are a very helpful assistant with lots of instructions"},
        {"role": "user", "content": "hello"},
    ]
    result = cp.pack_chat(msgs)
    assert all(m["role"] == "system" for m in result)


def test_pack_chat_keep_system_false():
    cp = Contextpacker(max_tokens=1000)
    msgs = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "hello"},
    ]
    result = cp.pack_chat(msgs, keep_system=False)
    assert all(m["role"] != "system" for m in result)


# ------------------------------------------------------------------
# Splitting
# ------------------------------------------------------------------

def test_split():
    cp = Contextpacker(max_tokens=10)
    chunks = cp.split("a" * 200)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 40


def test_split_short_text():
    cp = Contextpacker(max_tokens=100)
    assert cp.split("hello") == ["hello"]


def test_split_empty_string():
    cp = Contextpacker(max_tokens=10)
    assert cp.split("") == []


def test_split_chunks_cover_input():
    cp = Contextpacker(max_tokens=10)
    text = "a" * 120
    chunks = cp.split(text)
    assert "".join(chunks) == text


# ------------------------------------------------------------------
# Sliding window
# ------------------------------------------------------------------

def test_sliding_window():
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
    assert cp.sliding_window(parts) == ["a", "b", "c"]


def test_sliding_window_preserves_order():
    cp = Contextpacker(max_tokens=50)
    parts = ["alpha", "beta", "gamma"]
    result = cp.sliding_window(parts)
    # Result must be a tail of parts in original order
    assert result == parts[-len(result):]
