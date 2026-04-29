# contextpacker

Pack and truncate context windows for LLM prompts.

## Installation

```bash
pip install contextpacker
```

## Quick start

```python
from contextpacker import Contextpacker

packer = Contextpacker(max_tokens=4096)

# Join parts, truncating to fit the budget
packed = packer.pack(["system prompt", "user message", "assistant reply"])

# Token estimates
print(packer.count(packed))        # word-heuristic (display only)
print(packer.count_chars(packed))  # char-based (used for budget arithmetic)

# Truncate from the end or from the start
packer.truncate("very long text...", max_tokens=100)
packer.truncate_start("very long text...", max_tokens=100)

# Priority-based packing — drop lowest priority when over budget
parts = [
    {"text": "retrieved document", "priority": 1},
    {"text": "system instructions", "priority": 10},
]
packer.pack_priority(parts)

# Fit a chat history inside the budget (drops oldest turns first)
messages = [
    {"role": "system",    "content": "You are helpful."},
    {"role": "user",      "content": "Hello"},
    {"role": "assistant", "content": "Hi there!"},
]
packer.pack_chat(messages)

# Split long text into token-bounded chunks
chunks = packer.split("a very long document …", max_tokens=512)

# Sliding window — keep the most-recent parts that fit
packer.sliding_window(["old context", "recent context"])
```

## GUI workbench

An interactive GUI for exploring all operations is bundled with the package
and requires no additional dependencies (uses Python's built-in `tkinter`).

```bash
contextpacker-gui          # after pip install
# or
python -m contextpacker.gui
```

The workbench provides a tab for each operation — Count, Truncate, Pack,
Pack Priority, Pack Chat, Split, and Sliding Window — with live token counts
and configurable `max_tokens` and separator settings.

## Token budget arithmetic

All budget enforcement uses the heuristic `tokens ≈ len(text) / 4`
(`CHARS_PER_TOKEN = 4`), the industry-standard approximation for English
prose.  This makes arithmetic fast and deterministic without requiring an
external tokeniser library.  `count()` provides a complementary word-based
estimate (`words × 1.3`) for display purposes only.

## API reference

| Method | Description |
|---|---|
| `count(text)` | Word-based token estimate (display only) |
| `count_chars(text)` | Char-based token estimate (used for all budgets) |
| `truncate(text, max_tokens)` | Keep the beginning of text |
| `truncate_start(text, max_tokens)` | Keep the end of text (drop oldest) |
| `pack(parts, max_tokens)` | Join parts and truncate to budget |
| `pack_priority(parts, max_tokens)` | Greedy selection by priority score |
| `pack_chat(messages, max_tokens)` | Trim oldest chat turns to fit budget |
| `split(text, max_tokens)` | Chunk text into token-bounded segments |
| `sliding_window(parts, max_tokens)` | Most-recent contiguous parts that fit |

## License

MIT — see `LICENSE`.
