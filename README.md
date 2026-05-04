# contextpacker

Pack and truncate context windows for LLM prompts.

```python
from contextpacker import Contextpacker

packer = Contextpacker(max_tokens=4096)

# Join parts and truncate from the end.
packed = packer.pack(["system prompt", "user message", "assistant reply"])
print(packer.count(packed))   # approximate token count

# Keep highest-priority parts when the budget is tight; restore original order.
result = packer.pack_priority([
    {"text": "system instructions", "priority": 10},
    {"text": "retrieved document",  "priority": 3},
    {"text": "user query",          "priority": 7},
])

# Give every part a proportional share of the budget.
result = packer.pack_proportional(["long doc A", "long doc B", "short note"])

# Truncate a single string from the end or from the start.
truncated = packer.truncate("very long text...", max_tokens=100)
recent    = packer.truncate_start("very long text...", max_tokens=100)

# Fit a chat history; drop oldest non-system messages first.
messages = packer.pack_chat([
    {"role": "system",    "content": "You are helpful."},
    {"role": "user",      "content": "Tell me about Rome."},
    {"role": "assistant", "content": "Rome is ..."},
])

# Split a long document into equal-sized chunks.
chunks = packer.split("very long document ...", max_tokens=512)

# Keep the most-recent contiguous parts that fit.
window = packer.sliding_window(["old", "middle", "recent"], max_tokens=128)
```

## GUI

An interactive desktop GUI is included for exploring packing strategies without
writing code:

```bash
# From the command line (after installation):
contextpacker-gui

# Or from Python:
from contextpacker import launch_gui
launch_gui()
```

The GUI requires `tkinter`, which ships with most Python distributions. On
Debian/Ubuntu it can be installed with `sudo apt install python3-tk`.

## Installation

```bash
pip install contextpacker
```

Requires Python 3.9+. No external dependencies.

## How token counting works

`contextpacker` uses two lightweight heuristics — no external tokenizer
required:

| Method | Formula | Use |
|---|---|---|
| `count(text)` | `round(word_count × 1.3)` | Approximate token count for display |
| `count_chars(text)` | `len(text) // 4` | Budget arithmetic inside pack methods |

Both return `0` for empty strings.
