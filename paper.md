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

`contextpacker` is a lightweight, zero-dependency Python library for packing
and truncating content into a bounded large language model (LLM)
[@brown2020language] context window. Given a token budget and a list of
candidate items, the library selects and orders content so the resulting
prompt fits within the model's limit. It exposes six strategies — plain
packing, priority-based selection, chat-history trimming, fixed-size
splitting, end-truncation, and sliding-window access — through a single
consistent class interface. A Tkinter-based graphical interface is also
included so practitioners can experiment interactively without writing code.

# Statement of need

Transformer-based LLMs [@vaswani2017attention] impose a hard upper bound on
the number of tokens they can process in a single forward pass. Applications
that assemble prompts from heterogeneous sources — retrieved documents, chat
history, system instructions, few-shot examples — must therefore fit all
contributing pieces within this budget before calling the model API. When the
budget is exceeded the model silently truncates or raises an error, leading
to lost context and unpredictable behaviour.

In practice this bookkeeping is often open-coded: developers concatenate
strings, guess at token counts, and add ad-hoc truncation after the fact.
This approach has several failure modes:

1. **Off-by-one and overflow errors.** Token-counting heuristics differ from
   model-specific tokenizers, so budgets are routinely miscalculated.
2. **Implicit truncation policy.** When content is naively trimmed from the
   end, high-priority items (e.g. system instructions, recently retrieved
   facts) may be silently discarded.
3. **Duplicated logic across projects.** Every LLM application re-implements
   the same selection and truncation routines, making them hard to test and
   easy to get wrong.

`contextpacker` centralises context-window arithmetic in a single,
well-tested module. By separating *selection policy* (which parts to keep)
from *token arithmetic* (how large each part is), the library makes
truncation decisions explicit, auditable, and easy to swap.

# Implementation

The library is implemented as a single Python class (`Contextpacker`) with
no runtime dependencies beyond the standard library.

**Token counting.** Two heuristics are provided:

- `count(text)` estimates tokens as `round(word_count × 1.3)`, approximating
  the sub-word tokenization used by byte-pair encoding (BPE) models.
- `count_chars(text)` uses integer division by four (`len(text) // 4`), the
  standard OpenAI rule of thumb. This method is used internally because it is
  deterministic and requires no string splitting.

Both methods return zero for empty input, avoiding the silent `max(1, …)` bias
that inflates budgets for empty parts.

**Priority-based packing (`pack_priority`).** Parts are sorted by a
caller-supplied numeric priority and selected greedily (highest priority first)
until the budget is exhausted. Crucially, the output is emitted in *original
input order* rather than priority order, preserving document structure for the
model. This is achieved by recording original indices during selection and
sorting those indices before joining.

**Chat-history trimming (`pack_chat`).** OpenAI-compatible message lists
(`{"role": str, "content": str}`) are handled by separating system messages
(which are always retained) from non-system turns. Non-system messages are
accumulated in reverse chronological order until the remaining budget is
consumed, then prepended with system messages. Missing `"content"` keys are
treated as empty strings rather than raising `KeyError`.

**Sliding window and splitting.** `sliding_window` applies the same
newest-first traversal to arbitrary string parts. `split` partitions a long
string into equal-sized character-delimited chunks, each guaranteed to fit
within the per-chunk budget.

**Graphical interface.** A Tkinter GUI (`contextpacker-gui` / `python -m contextpacker`)
exposes all seven operations through a tabbed interface with live token-count
feedback. It requires no additional dependencies beyond CPython's standard
library.

# Acknowledgements

This work was developed independently. The author thanks the open-source
community whose tooling made this project possible.

# References
