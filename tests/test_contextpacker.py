"""Tests for contextpacker."""
import pytest
from contextpacker import Contextpacker


# ---------------------------------------------------------------------------
# Construction and properties
# ---------------------------------------------------------------------------

def test_default_construction():
    cp = Contextpacker()
    assert cp.max_tokens == 8192
    assert cp.separator == "\n\n"


def test_custom_construction():
    cp = Contextpacker(max_tokens=512, separator=" | ")
    assert cp.max_tokens == 512
    assert cp.separator == " | "


def test_invalid_max_tokens_zero():
    with pytest.raises(ValueError):
        Contextpacker(max_tokens=0)


def test_invalid_max_tokens_negative():
    with pytest.raises(ValueError):
        Contextpacker(max_tokens=-1)


def test_invalid_max_tokens_float():
    with pytest.raises(ValueError):
        Contextpacker(max_tokens=1.5)  # type: ignore[arg-type]


def test_repr():
    cp = Contextpacker(max_tokens=100, separator="\n")
    r = repr(cp)
    assert "100" in r
    assert "Contextpacker" in r


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------

def test_count_basic():
    cp = Contextpacker()
    assert cp.count("hello world") >= 1


def test_count_empty_string():
    cp = Contextpacker()
    assert cp.count("") == 0


def test_count_whitespace_only():
    cp = Contextpacker()
    assert cp.count("   \t\n  ") == 0


def test_count_single_word():
    cp = Contextpacker()
    assert cp.count("hello") >= 1


def test_count_chars_basic():
    cp = Contextpacker()
    # "hello world" = 11 chars → 11 // 4 = 2 tokens
    assert cp.count_chars("hello world") == 2


def test_count_chars_empty():
    cp = Contextpacker()
    assert cp.count_chars("") == 0


def test_count_chars_short():
    cp = Contextpacker()
    # 3 chars is less than 4, but count_chars returns max(1, 3//4) = max(1,0) = 1
    assert cp.count_chars("abc") == 1


def test_count_chars_exact_boundary():
    cp = Contextpacker()
    assert cp.count_chars("a" * 8) == 2


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


def test_truncate_exact_limit():
    cp = Contextpacker(max_tokens=10)
    text = "a" * 40
    assert cp.truncate(text) == text  # fits exactly


def test_truncate_empty():
    cp = Contextpacker(max_tokens=10)
    assert cp.truncate("") == ""


def test_truncate_override_limit():
    cp = Contextpacker(max_tokens=100)
    result = cp.truncate("a" * 200, max_tokens=5)
    assert len(result) == 20  # 5 * 4


def test_truncate_invalid_limit():
    cp = Contextpacker()
    with pytest.raises(ValueError):
        cp.truncate("hello", max_tokens=-1)


def test_truncate_start_short():
    cp = Contextpacker(max_tokens=1000)
    assert cp.truncate_start("hello") == "hello"


def test_truncate_start_long():
    cp = Contextpacker(max_tokens=5)
    text = "START" + "x" * 100
    result = cp.truncate_start(text)
    assert result.endswith("x" * 20)
    assert not result.startswith("START")


def test_truncate_start_keeps_end():
    cp = Contextpacker(max_tokens=5)
    text = "A" * 80 + "END"
    result = cp.truncate_start(text)
    assert result.endswith("END")


def test_truncate_start_empty():
    cp = Contextpacker(max_tokens=10)
    assert cp.truncate_start("") == ""


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


def test_pack_truncates():
    cp = Contextpacker(max_tokens=5)
    result = cp.pack(["a" * 100, "b" * 100])
    assert len(result) <= 20  # 5 tokens * 4 chars


def test_pack_skips_empty_parts():
    cp = Contextpacker(max_tokens=1000)
    result = cp.pack(["hello", "", "world"])
    assert "hello" in result and "world" in result
    assert "  " not in result  # double separator not present


def test_pack_empty_list():
    cp = Contextpacker(max_tokens=1000)
    assert cp.pack([]) == ""


def test_pack_single_part():
    cp = Contextpacker(max_tokens=1000)
    assert cp.pack(["only"]) == "only"


# ---------------------------------------------------------------------------
# Priority packing
# ---------------------------------------------------------------------------

def test_pack_priority_keeps_high_priority():
    cp = Contextpacker(max_tokens=20)
    parts = [
        {"text": "low priority text here", "priority": 1},
        {"text": "IMPORTANT", "priority": 10},
    ]
    result = cp.pack_priority(parts)
    assert "IMPORTANT" in result


def test_pack_priority_preserves_document_order():
    cp = Contextpacker(max_tokens=100)
    parts = [
        {"text": "first", "priority": 5},
        {"text": "second", "priority": 10},
        {"text": "third", "priority": 1},
    ]
    result = cp.pack_priority(parts)
    # All fit; original order must be preserved
    assert result.index("first") < result.index("second") < result.index("third")


def test_pack_priority_drops_low_priority_when_tight():
    # Budget = 3 tokens (12 chars).
    # "y"*8 costs 2 tokens (high priority, selected first).
    # "x"*12 costs 3 tokens (low priority); 2+3=5 > 3 → excluded.
    cp = Contextpacker(max_tokens=3)
    parts = [
        {"text": "x" * 12, "priority": 1},
        {"text": "y" * 8, "priority": 10},
    ]
    result = cp.pack_priority(parts)
    assert "y" * 8 in result
    assert "x" * 12 not in result


def test_pack_priority_empty_parts():
    cp = Contextpacker(max_tokens=100)
    assert cp.pack_priority([]) == ""


def test_pack_priority_default_priority():
    cp = Contextpacker(max_tokens=100)
    parts = [{"text": "no priority key"}]
    result = cp.pack_priority(parts)
    assert result == "no priority key"


# ---------------------------------------------------------------------------
# Chat packing
# ---------------------------------------------------------------------------

def test_pack_chat_fits():
    cp = Contextpacker(max_tokens=1000)
    msgs = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
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


def test_pack_chat_system_always_first():
    cp = Contextpacker(max_tokens=1000)
    msgs = [
        {"role": "user", "content": "hi"},
        {"role": "system", "content": "Be concise."},
        {"role": "assistant", "content": "hello"},
    ]
    result = cp.pack_chat(msgs)
    assert result[0]["role"] == "system"


def test_pack_chat_no_system():
    cp = Contextpacker(max_tokens=1000)
    msgs = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
    result = cp.pack_chat(msgs, keep_system=False)
    assert not any(m["role"] == "system" for m in result)


def test_pack_chat_empty():
    cp = Contextpacker(max_tokens=1000)
    assert cp.pack_chat([]) == []


def test_pack_chat_only_system_with_keep():
    cp = Contextpacker(max_tokens=1000)
    msgs = [{"role": "system", "content": "instructions"}]
    result = cp.pack_chat(msgs)
    assert len(result) == 1
    assert result[0]["role"] == "system"


# ---------------------------------------------------------------------------
# Splitting
# ---------------------------------------------------------------------------

def test_split_short():
    cp = Contextpacker(max_tokens=1000)
    chunks = cp.split("hello world")
    assert chunks == ["hello world"]


def test_split_long():
    cp = Contextpacker(max_tokens=10)
    chunks = cp.split("a" * 200)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 40  # 10 tokens * 4 chars


def test_split_exact_boundary():
    cp = Contextpacker(max_tokens=10)
    text = "a" * 40
    chunks = cp.split(text)
    assert chunks == [text]


def test_split_empty():
    cp = Contextpacker(max_tokens=10)
    chunks = cp.split("")
    assert chunks == [""]


def test_split_chunks_cover_input():
    cp = Contextpacker(max_tokens=10)
    text = "x" * 83
    chunks = cp.split(text)
    assert "".join(chunks) == text


# ---------------------------------------------------------------------------
# Sliding window
# ---------------------------------------------------------------------------

def test_sliding_window_all_fit():
    cp = Contextpacker(max_tokens=1000)
    parts = ["alpha", "beta", "gamma"]
    result = cp.sliding_window(parts)
    assert result == parts


def test_sliding_window_keeps_recent():
    cp = Contextpacker(max_tokens=10)
    parts = ["old " * 20, "middle " * 20, "recent"]
    result = cp.sliding_window(parts)
    assert "recent" in result


def test_sliding_window_drops_oldest():
    cp = Contextpacker(max_tokens=10)
    # Each part is 4 tokens (16 chars); budget only fits 2
    parts = ["a" * 16, "b" * 16, "c" * 16]
    result = cp.sliding_window(parts)
    assert parts[0] not in result
    assert parts[2] in result


def test_sliding_window_empty():
    cp = Contextpacker(max_tokens=10)
    assert cp.sliding_window([]) == []


def test_sliding_window_single_fits():
    cp = Contextpacker(max_tokens=100)
    assert cp.sliding_window(["hello"]) == ["hello"]


def test_sliding_window_single_too_large():
    cp = Contextpacker(max_tokens=1)
    # count_chars("a"*100) = 25 > 1, so nothing fits
    result = cp.sliding_window(["a" * 100])
    assert result == []
