---
title: 'contextpacker: token-aware packing and truncation for LLM context windows'
tags:
  - Python
  - large language models
  - prompt engineering
  - tokenization
  - natural language processing
authors:
  - name: Vaibhav Deshmukh
    affiliation: 1
affiliations:
  - name: Independent Researcher
    index: 1
date: 25 April 2026
bibliography: paper.bib
---

# Summary

`contextpacker` is a Python library for assembling and truncating content to fit within the bounded context windows of large language models (LLMs) [@brown2020language].  Given a token budget and a list of candidate items — such as retrieved documents, chat history, and system instructions — the library selects and orders content so that the resulting prompt does not exceed the model's limit.  It exposes priority-based selection, proportional truncation, chat-history management, text splitting, and sliding-window strategies, and ships a built-in interactive GUI for exploratory use.  The library is tokenizer-agnostic and has no runtime dependencies.

# Statement of need

Modern LLM applications routinely assemble prompts from heterogeneous sources that together may exceed the target model's context window.  This problem is common across retrieval-augmented generation (RAG) [@lewis2020retrieval], multi-turn dialogue systems, and document summarisation pipelines.  Without a dedicated abstraction, context-window arithmetic is typically open-coded throughout application logic, leading to off-by-one errors, inconsistent truncation policies, and brittle prompt construction that breaks when model limits change.

`contextpacker` addresses this by isolating all context-budget arithmetic into a single, well-tested class.  Developers declare *what* content they have and *how important* each piece is; the library decides *what fits*.  This separation of concerns makes truncation policy explicit and auditable rather than scattered across application code.

Existing tools such as `tiktoken` [@tiktoken] provide exact tokenization for specific OpenAI models but do not address budget management or multi-source packing.  Higher-level frameworks such as LangChain [@langchain] and LlamaIndex [@llamaindex] offer document-splitting and retrieval utilities but couple them tightly to their own retrieval and agent abstractions.  `contextpacker` occupies a complementary niche: a minimal, dependency-free utility that can be dropped into any Python project regardless of the LLM provider or orchestration framework in use.

# Functionality

The library's central class, `Contextpacker`, exposes the following operations:

- **`count` / `count_chars`** — tokenizer-agnostic approximations of token count based on word count (1.3× multiplier) and character count (÷ 4), respectively.
- **`truncate` / `truncate_start`** — character-level truncation keeping either the head or tail of a string.
- **`pack`** — join an ordered list of text parts with a configurable separator and truncate the result to fit the budget.
- **`pack_priority`** — greedy selection from a priority-ranked list of parts, accumulating items in descending priority order until the budget is exhausted.
- **`pack_chat`** — fit a list of `{"role", "content"}` message dicts within a token budget, dropping oldest non-system messages first while optionally preserving system-role messages.
- **`split`** — divide a long string into fixed-size chunks.
- **`sliding_window`** — return the most-recent contiguous subset of an ordered list of context parts that fits within the budget.

An interactive Tkinter GUI (`contextpacker-gui`) exposes all operations without requiring users to write code, making the library accessible for exploratory prototyping and educational use.

# Implementation

`contextpacker` is a pure-Python package compatible with Python 3.9 and later.  It has no runtime dependencies beyond the standard library.  The package is distributed via PyPI and installable with `pip install contextpacker`.  A full test suite (pytest) covers all public methods including boundary conditions such as empty inputs, zero-token budgets, and system-message-only conversations.  Continuous integration runs on every pull request via GitHub Actions.

# Acknowledgements

This work was developed independently.  The author thanks the open-source community whose tooling made this project possible.

# References
