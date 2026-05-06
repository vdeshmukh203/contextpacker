# contextpacker

**Token-aware packing and truncation for LLM context windows.**

`contextpacker` is a lightweight Python library that centralises the bookkeeping required to keep assembled prompts within a model's token budget.  It provides priority-based selection, truncation, chat-history management, text splitting, and a sliding-window view over ordered context parts — all with no external dependencies.

---

## Installation

```bash
pip install contextpacker
```

## Quick start

```python
from contextpacker import Contextpacker

packer = Contextpacker(max_tokens=4096)

# Join parts and truncate to budget
packed = packer.pack(["system prompt", "retrieved doc", "user message"])

# Count approximate tokens
print(packer.count(packed))

# Truncate a single string
short = packer.truncate("very long text …", max_tokens=100)
```

---

## GUI

An interactive desktop GUI is bundled and launches with:

```bash
contextpacker-gui
```

or from Python:

```python
from contextpacker import launch_gui
launch_gui()
```

The GUI provides tabs for every operation (Token Counter, Pack, Truncate, Pack Chat, Pack Priority, Split, Sliding Window) so you can explore the library interactively without writing code.

---

## API reference

### `Contextpacker(max_tokens=8192, separator="\n\n")`

Creates a packer with a default token budget and part separator.

| Parameter | Type | Description |
|-----------|------|-------------|
| `max_tokens` | `int` | Default token budget (>= 0). |
| `separator` | `str` | String inserted between joined parts. |

---

### Token counting

#### `count(text) → int`

Word-aware heuristic: `round(word_count × 1.3)`.  Returns **0** for empty / whitespace-only strings.

#### `count_chars(text) → int`

Character-based estimate: `len(text) // 4`.  Used internally by all budget arithmetic.  Returns **0** for empty strings.

---

### Truncation

#### `truncate(text, max_tokens=None) → str`

Keeps the **beginning** of *text*, dropping the tail.

#### `truncate_start(text, max_tokens=None) → str`

Keeps the **end** of *text* (most-recent content), dropping the head.

---

### Packing

#### `pack(parts, max_tokens=None) → str`

Joins non-empty strings in *parts* with `separator` then truncates to the budget.

#### `pack_priority(parts, max_tokens=None) → str`

Greedy priority packing.  Each element of *parts* is a dict:

```python
{"text": "…", "priority": 10}   # higher priority → kept first
```

Items are selected in descending priority order until the budget is exhausted, then joined in the same order.

#### `pack_chat(messages, max_tokens=None, keep_system=True) → list`

Fits a list of chat messages within the token budget.  Drops **oldest** non-system messages first to preserve the most-recent context.

```python
messages = [
    {"role": "system",    "content": "You are helpful."},
    {"role": "user",      "content": "Hello!"},
    {"role": "assistant", "content": "Hi there!"},
]
result = packer.pack_chat(messages, max_tokens=200)
```

When `keep_system=True` (default) system messages are always preserved and their token cost is deducted from the budget before fitting non-system messages.

---

### Splitting

#### `split(text, max_tokens=None) → list[str]`

Splits *text* into chunks that each fit within `max_tokens`.  Returns `[]` for empty input.

---

### Sliding window

#### `sliding_window(parts, max_tokens=None) → list[str]`

Returns the most-recent contiguous tail of *parts* that fits within the budget (oldest parts are dropped first).

---

## Design notes

**Token counting heuristic** — `contextpacker` ships a tokenizer-agnostic heuristic (4 characters ≈ 1 token for English text) rather than depending on model-specific tokenizers such as `tiktoken`.  This keeps the library dependency-free at the cost of approximate counts; applications that need exact counts should supply a `max_tokens` value with a small safety margin.

**Contiguous window** — `pack_chat` and `sliding_window` preserve message order and stop accumulating as soon as a part would exceed the budget.  This avoids gaps in conversation history that would make context incoherent.

---

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

---

## Citation

If you use `contextpacker` in academic work, please cite the JOSS paper (see `CITATION.cff`).

---

## License

MIT — see `LICENSE`.
