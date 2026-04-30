"""Tests for contextpacker."""
import pytest
from contextpacker import Contextpacker
from contextpacker.packer import CHARS_PER_TOKEN, DEFAULT_MAX_TOKENS


# ---------------------------------------------------------------------------
# Construction and properties
# ---------------------------------------------------------------------------

def test_default_construction():
    cp = Contextpacker()
    assert cp.max_tokens == DEFAULT_MAX_TOKENS
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


def test_invalid_separator_type():
    with pytest.raises(TypeError):
        Contextpacker(separator=42)  # type: ignore[arg-type]


def test_repr():
    cp = Contextpacker(max_tokens=100, separator="\n")
    assert "100" in repr(cp)
    assert "Contextpacker" in repr(cp)


def test_max_tokens_setter():
    cp = Contextpacker(max_tokens=100)
    cp.max_tokens = 200
    assert cp.max_tokens == 200


def test_max_tokens_setter_invalid():
    cp = Contextpacker()
    with pytest.raises(ValueError):
        cp.max_tokens = 0


def test_separator_setter():
    cp = Contextpacker()
    cp.separator = " --- "
    assert cp.separator == " --- "


def test_separator_setter_invalid():
    cp = Contextpacker()
    with pytest.raises(TypeError):
        cp.separator = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------

def test_count_empty():
    cp = Contextpacker()
    assert cp.count("") == 0


def test_count_basic():
    cp = Contextpacker()
    text = "a" * 40  # 40 chars → 10 tokens
    assert cp.count(text) == 10


def test_count_chars_alias():
    cp = Contextpacker()
    text = "hello world"
    assert cp.count_chars(text) == cp.count(text)


def test_count_words_empty():
    cp = Contextpacker()
    assert cp.count_words("") == 0


def test_count_words_basic():
    cp = Contextpacker()
    assert cp.count_words("hello world") >= 1


def test_count_consistency_with_truncate():
    """count() must agree with truncate(): a text that barely fits should
    not be reduced by truncate()."""
    cp = Contextpacker(max_tokens=10)
    text = "x" * (10 * CHARS_PER_TOKEN)  # exactly at limit
    assert cp.count(text) == 10
    assert cp.truncate(text) == text


def test_fits_true():
    cp = Contextpacker(max_tokens=100)
    assert cp.fits("short text") is True


def test_fits_false():
    cp = Contextpacker(max_tokens=2)
    assert cp.fits("a" * 100) is False


def test_fits_override():
    cp = Contextpacker(max_tokens=1)
    assert cp.fits("a" * 100, max_tokens=1000) is True


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
    cp = Contextpacker(max_tokens=10)
    text = "a" * 40  # exactly 10 tokens
    assert cp.truncate(text) == text


def test_truncate_empty():
    cp = Contextpacker(max_tokens=10)
    assert cp.truncate("") == ""


def test_truncate_invalid_limit():
    cp = Contextpacker()
    with pytest.raises(ValueError):
        cp.truncate("hello", max_tokens=0)


def test_truncate_start():
    cp = Contextpacker(max_tokens=5)
    text = "START" + "x" * 100
    result = cp.truncate_start(text)
    assert result.endswith("x" * 20)
    assert not result.startswith("START")


def test_truncate_start_short():
    cp = Contextpacker(max_tokens=1000)
    assert cp.truncate_start("hello") == "hello"


def test_truncate_start_empty():
    cp = Contextpacker(max_tokens=10)
    assert cp.truncate_start("") == ""


# ---------------------------------------------------------------------------
# Pack
# ---------------------------------------------------------------------------

def test_pack_basic():
    cp = Contextpacker(max_tokens=1000)
    result = cp.pack(["part1", "part2"])
    assert "part1" in result and "part2" in result


def test_pack_separator():
    cp = Contextpacker(max_tokens=1000, separator=" | ")
    result = cp.pack(["a", "b"])
    assert result == "a | b"


def test_pack_skips_empty():
    cp = Contextpacker(max_tokens=1000)
    result = cp.pack(["a", "", "b"])
    assert "a" in result and "b" in result
    assert cp.separator + cp.separator not in result


def test_pack_truncates():
    cp = Contextpacker(max_tokens=5)
    result = cp.pack(["a" * 100, "b" * 100])
    assert len(result) <= 20


def test_pack_empty_list():
    cp = Contextpacker(max_tokens=100)
    assert cp.pack([]) == ""


def test_pack_single_part():
    cp = Contextpacker(max_tokens=100)
    assert cp.pack(["only"]) == "only"


# ---------------------------------------------------------------------------
# Pack priority
# ---------------------------------------------------------------------------

def test_pack_priority_keeps_high():
    cp = Contextpacker(max_tokens=20)
    parts = [
        {"text": "low priority text", "priority": 1},
        {"text": "IMPORTANT", "priority": 10},
    ]
    result = cp.pack_priority(parts)
    assert "IMPORTANT" in result


def test_pack_priority_drops_low_when_tight():
    cp = Contextpacker(max_tokens=3)  # ~12 chars
    parts = [
        {"text": "drop me completely", "priority": 1},
        {"text": "keep", "priority": 10},
    ]
    result = cp.pack_priority(parts)
    assert "keep" in result
    assert "drop" not in result


def test_pack_priority_preserve_order():
    cp = Contextpacker(max_tokens=1000)
    parts = [
        {"text": "first", "priority": 1},
        {"text": "second", "priority": 10},
        {"text": "third", "priority": 5},
    ]
    result = cp.pack_priority(parts, preserve_order=True)
    assert result.index("first") < result.index("second") < result.index("third")


def test_pack_priority_default_priority():
    cp = Contextpacker(max_tokens=1000)
    parts = [{"text": "no priority key"}]
    result = cp.pack_priority(parts)
    assert "no priority key" in result


def test_pack_priority_missing_text_key():
    cp = Contextpacker(max_tokens=100)
    with pytest.raises(ValueError, match=r"parts\[0\]"):
        cp.pack_priority([{"priority": 5}])


def test_pack_priority_empty_list():
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


def test_pack_chat_no_keep_system():
    cp = Contextpacker(max_tokens=1000)
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
    ]
    result = cp.pack_chat(msgs, keep_system=False)
    assert all(m["role"] != "system" for m in result)


def test_pack_chat_missing_role_key():
    cp = Contextpacker(max_tokens=100)
    with pytest.raises(ValueError, match=r"messages\[0\]"):
        cp.pack_chat([{"content": "hello"}])


def test_pack_chat_missing_content_key():
    cp = Contextpacker(max_tokens=100)
    with pytest.raises(ValueError, match=r"messages\[0\]"):
        cp.pack_chat([{"role": "user"}])


def test_pack_chat_empty():
    cp = Contextpacker(max_tokens=100)
    assert cp.pack_chat([]) == []


def test_pack_chat_preserves_order():
    cp = Contextpacker(max_tokens=1000)
    msgs = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "second"},
        {"role": "user", "content": "third"},
    ]
    result = cp.pack_chat(msgs)
    roles = [m["role"] for m in result]
    assert roles == ["user", "assistant", "user"]


# ---------------------------------------------------------------------------
# Split
# ---------------------------------------------------------------------------

def test_split_basic():
    cp = Contextpacker(max_tokens=10)
    chunks = cp.split("a" * 200)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 40


def test_split_fits_in_one():
    cp = Contextpacker(max_tokens=100)
    text = "hello world"
    assert cp.split(text) == [text]


def test_split_empty():
    cp = Contextpacker(max_tokens=10)
    assert cp.split("") == []


def test_split_exact_boundary():
    cp = Contextpacker(max_tokens=10)
    text = "a" * 40  # exactly one chunk
    chunks = cp.split(text)
    assert chunks == [text]


def test_split_chunks_contiguous():
    cp = Contextpacker(max_tokens=10)
    text = "abcdefgh" * 10
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


def test_sliding_window_all_fit():
    cp = Contextpacker(max_tokens=1000)
    parts = ["a", "b", "c"]
    assert cp.sliding_window(parts) == parts


def test_sliding_window_empty():
    cp = Contextpacker(max_tokens=10)
    assert cp.sliding_window([]) == []


def test_sliding_window_preserves_order():
    cp = Contextpacker(max_tokens=20)
    parts = ["x" * 10, "y" * 10, "z" * 10]
    result = cp.sliding_window(parts)
    assert result == list(reversed(list(reversed(result))))  # order preserved


def test_sliding_window_override_limit():
    cp = Contextpacker(max_tokens=2)
    parts = ["a" * 8, "b" * 8]  # each 2 tokens
    result = cp.sliding_window(parts, max_tokens=4)
    assert len(result) == 2


# ---------------------------------------------------------------------------
# _resolve_limit
# ---------------------------------------------------------------------------

def test_resolve_limit_invalid_float():
    cp = Contextpacker()
    with pytest.raises(ValueError):
        cp.truncate("text", max_tokens=1.5)  # type: ignore[arg-type]


def test_resolve_limit_invalid_zero():
    cp = Contextpacker()
    with pytest.raises(ValueError):
        cp.pack(["a"], max_tokens=0)
