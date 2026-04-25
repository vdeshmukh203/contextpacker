"""Tests for contextpacker."""
from contextpacker import Contextpacker

def test_count():
    cp = Contextpacker()
    assert cp.count("hello") >= 1

def test_count_heuristic():
    cp = Contextpacker()
    text = "a" * 400
    assert cp.count(text) == 100

def test_truncate_short():
    cp = Contextpacker(max_tokens=100)
    text = "short"
    assert cp.truncate(text) == "short"

def test_truncate_long():
    cp = Contextpacker(max_tokens=10)
    text = "a" * 200
    result = cp.truncate(text)
    assert len(result) == 40

def test_pack():
    cp = Contextpacker(max_tokens=1000)
    result = cp.pack(["part1", "part2", "part3"])
    assert "part1" in result
    assert "part2" in result

def test_pack_truncates():
    cp = Contextpacker(max_tokens=5)
    result = cp.pack(["a" * 100, "b" * 100])
    assert len(result) <= 20
