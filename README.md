# contextpacker

Pack and truncate context windows for LLM prompts.

`contextpacker` is a lightweight, dependency-free Python library that keeps
your prompts within a model's token budget.  It provides a single
`Contextpacker` class with seven composable operations: token counting,
truncation (both directions), basic packing, priority-based packing, chat
history trimming, text splitting, and sliding-window selection.

## Installation

```bash
pip install contextpacker
```

Python 3.9 or later is required.  No runtime dependencies beyond the standard
library.

## Quick start

```python
from contextpacker import Contextpacker

cp = Contextpacker(max_tokens=4096)

# Count tokens (word-aware heuristic)
print(cp.count("hello world"))          # → 3

# Truncate to budget
short = cp.truncate("very long text …", max_tokens=100)

# Pack multiple parts (joins with separator, then truncates)
prompt = cp.pack(["system instructions", "retrieved doc", "user query"])

# Priority-based selection — highest-priority content is kept first;
# items are output in their original document order
prompt = cp.pack_priority([
    {"text": "Critical instructions", "priority": 10},
    {"text": "Background context",    "priority": 5},
    {"text": "Nice-to-have note",     "priority": 1},
])

# Trim a chat history, keeping the most recent messages and the system prompt
messages = [
    {"role": "system",    "content": "You are helpful."},
    {"role": "user",      "content": "Hello!"},
    {"role": "assistant", "content": "Hi there!"},
]
trimmed = cp.pack_chat(messages, max_tokens=500)

# Split a long document into token-bounded chunks
chunks = cp.split(long_document, max_tokens=1024)

# Sliding window over a list of parts
recent = cp.sliding_window(history_parts, max_tokens=2048)
```

## API reference

All methods accept an optional `max_tokens` keyword argument that overrides
the instance default for that call.

| Method | Description |
|--------|-------------|
| `count(text)` | Word-heuristic token count (words × 1.3). Returns 0 for empty input. |
| `count_chars(text)` | Char-based token count (chars ÷ 4). Returns 0 for empty input. |
| `truncate(text)` | Keep the **start** of *text*, dropping the tail. |
| `truncate_start(text)` | Keep the **end** of *text*, dropping oldest content. |
| `pack(parts)` | Join *parts* with `separator` and truncate to budget. |
| `pack_priority(parts)` | Greedily select by `"priority"` score; output in original order. |
| `pack_chat(messages)` | Trim chat list, dropping oldest non-system messages first. |
| `split(text)` | Return list of token-bounded chunks; `[]` for empty input. |
| `sliding_window(parts)` | Most recent *parts* that fit in budget, in original order. |

Constructor parameters:

```python
Contextpacker(max_tokens=8192, separator="\n\n")
```

- `max_tokens` — default token budget; must be ≥ 1.
- `separator` — string placed between parts when joining (default `"\n\n"`).

## GUI

A desktop GUI ships with the package and can be launched with:

```bash
contextpacker-gui
```

or directly:

```bash
python -m contextpacker.gui
```

The interface provides seven tabs — one per operation — with live settings for
`max_tokens` and `separator`.

## Development

```bash
git clone https://github.com/vdeshmukh203/contextpacker
cd contextpacker
pip install -e ".[dev]"
pytest tests/ -v
```

## License

MIT — see [LICENSE](LICENSE).

## Citation

If you use `contextpacker` in published research, please cite the accompanying
[JOSS paper](paper.md) or use the metadata in
[CITATION.cff](CITATION.cff).
