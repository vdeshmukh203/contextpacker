# contextpacker

**Token-aware packing and truncation for LLM context windows.**

`contextpacker` is a lightweight, zero-dependency Python library for assembling
prompts that fit within a model's token budget. It provides priority-based
selection, chat-history trimming, sliding-window access, and fixed-size
chunking — all through a single, consistent class.

## Installation

```bash
pip install contextpacker
```

## Quick start

```python
from contextpacker import Contextpacker

packer = Contextpacker(max_tokens=4096)

# Join parts and truncate the combined text to fit the budget
result = packer.pack(["System instructions", "Retrieved document", "User question"])
print(packer.count(result))   # word-aware token estimate
print(packer.count_chars(result))  # char-based token estimate

# Select high-priority items first when the budget is tight;
# output preserves the original order of the input list
parts = [
    {"text": "Background knowledge", "priority": 1},
    {"text": "Critical facts",       "priority": 10},
    {"text": "Nice-to-have context", "priority": 3},
]
packed = packer.pack_priority(parts)

# Trim an OpenAI-style chat history, keeping the most recent turns
messages = [
    {"role": "system",    "content": "You are a helpful assistant."},
    {"role": "user",      "content": "Hello!"},
    {"role": "assistant", "content": "Hi there!"},
    # ... many more turns ...
]
trimmed = packer.pack_chat(messages)  # List[Dict] ready for the API

# Keep the start / end of a long string
short = packer.truncate("very long text …", max_tokens=100)       # keep start
short = packer.truncate_start("very long text …", max_tokens=100) # keep end

# Split a long document into same-size chunks
chunks = packer.split(long_text)

# Sliding window: keep the most recent parts that fit
recent = packer.sliding_window(parts_list)
```

## GUI

Launch the interactive graphical interface to experiment with all features
without writing any code:

```bash
contextpacker-gui
# or
python -m contextpacker
```

The GUI provides seven tabs — **Pack**, **Pack Priority**, **Pack Chat**,
**Truncate**, **Split**, **Token Counter**, and **Sliding Window** — each with
live token-count feedback and configurable max-token and separator settings.

## API reference

| Method | Description |
|---|---|
| `count(text)` | Word-aware token estimate (`words × 1.3`) |
| `count_chars(text)` | Character-based estimate (`chars ÷ 4`) |
| `truncate(text, max_tokens)` | Keep the *start* of text |
| `truncate_start(text, max_tokens)` | Keep the *end* of text (drop oldest) |
| `pack(parts, max_tokens)` | Join parts with separator, then truncate |
| `pack_priority(parts, max_tokens)` | Select by priority, emit in original order |
| `pack_chat(messages, max_tokens, keep_system)` | Trim a chat-message list |
| `split(text, max_tokens)` | Chunk text into equal-sized pieces |
| `sliding_window(parts, max_tokens)` | Return most-recent parts that fit |

### Token counting

`contextpacker` is tokenizer-agnostic. Both counting methods are heuristics:

- `count(text)` — splits on whitespace and multiplies by 1.3 to approximate
  sub-word tokenization (BPE). Best for prose.
- `count_chars(text)` — divides character length by 4 (the standard OpenAI
  rule of thumb). Faster and deterministic; used internally by all packing
  methods.

If you need exact token counts, count outside the library and pass a custom
`max_tokens` value that already accounts for your overhead.

## Design notes

- **No external dependencies** — only the Python standard library is required.
  The GUI uses Tkinter, which ships with CPython.
- **Tokenizer-agnostic** — works with any LLM. Pass your own estimates via
  the `max_tokens` parameter.
- **`pack_priority` preserves document order** — parts are *selected* by
  priority but *output* in their original input order, keeping document
  structure intact.
- **`pack_chat` never raises on malformed dicts** — missing `"content"` keys
  are treated as empty strings.

## Running the tests

```bash
pip install pytest
pytest
```

## Citation

If you use `contextpacker` in academic work, please cite:

```bibtex
@article{deshmukh2026contextpacker,
  title   = {contextpacker: token-aware packing and truncation for {LLM} context windows},
  author  = {Deshmukh, Vaibhav},
  journal = {Journal of Open Source Software},
  year    = {2026}
}
```

## License

MIT © Vaibhav Deshmukh
