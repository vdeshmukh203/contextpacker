# contextpacker

Pack and truncate context windows for LLM prompts.

```python
from contextpacker import Contextpacker

packer = Contextpacker(max_tokens=4096)
packed = packer.pack(["system prompt", "user message", "assistant reply"])
print(packer.count(packed))  # approximate token count
truncated = packer.truncate("very long text...", max_tokens=100)
```
