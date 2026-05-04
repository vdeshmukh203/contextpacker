# Changelog

All notable changes to contextpacker are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-05-04

### Added
- `pack_proportional` — allocates the token budget proportionally across all
  parts so that every part retains some content when the total exceeds the limit.
- Interactive Tkinter GUI (`contextpacker-gui` console script and `launch_gui()`
  Python entry point) for exploring all packing strategies without writing code.
- `separator` property on `Contextpacker` to expose the configured separator.
- `__repr__` implementation for `Contextpacker`.
- Input validation: `Contextpacker(max_tokens=...)` now raises `ValueError`
  immediately for non-positive or non-integer values.
- 28 additional tests covering edge cases, new features, and property access
  (40 tests total, up from 12).
- Full PyPI classifiers, keywords, and author metadata in `pyproject.toml`.

### Fixed
- `count("")` and `count_chars("")` previously returned `1` due to an
  unconditional `max(1, …)` guard; they now correctly return `0`.
- `pack_priority` now preserves the **original input order** of selected parts
  instead of outputting them in priority-descending order.
- `pack_priority` skips parts whose `"text"` key is empty or missing, avoiding
  spurious separator-only output.

## [0.1.0] - 2026-04-25

### Added
- Initial release of contextpacker.
- Token-budgeted packing of heterogeneous content into a single prompt.
- Priority-based selection and proportional truncation strategies.
- Tokenizer-agnostic API.
