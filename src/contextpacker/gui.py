"""Tkinter GUI for contextpacker.

Launch with::

    python -m contextpacker.gui
    # or, after installation:
    contextpacker-gui
"""
import json
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from contextpacker import Contextpacker


def main() -> None:
    """Entry point for the ``contextpacker-gui`` console script."""
    app = _App()
    app.root.mainloop()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_readonly(widget: scrolledtext.ScrolledText, text: str) -> None:
    """Replace the content of a read-only ScrolledText widget."""
    widget.config(state="normal")
    widget.delete("1.0", tk.END)
    widget.insert("1.0", text)
    widget.config(state="disabled")


def _read(widget: scrolledtext.ScrolledText) -> str:
    return widget.get("1.0", tk.END).rstrip("\n")


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class _App:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("contextpacker")
        self.root.geometry("860x640")
        self.root.minsize(640, 480)
        self._build_settings()
        self._build_notebook()
        self._build_statusbar()

    # ------------------------------------------------------------------
    # Layout scaffolding
    # ------------------------------------------------------------------

    def _build_settings(self) -> None:
        bar = ttk.LabelFrame(self.root, text="Global settings", padding=(8, 4))
        bar.pack(fill=tk.X, padx=8, pady=(8, 0))

        ttk.Label(bar, text="max_tokens:").pack(side=tk.LEFT)
        self._max_tokens = tk.StringVar(value="4096")
        ttk.Entry(bar, textvariable=self._max_tokens, width=7).pack(
            side=tk.LEFT, padx=(2, 12)
        )

        ttk.Label(bar, text="separator:").pack(side=tk.LEFT)
        self._separator = tk.StringVar(value="\\n\\n")
        ttk.Entry(bar, textvariable=self._separator, width=8).pack(
            side=tk.LEFT, padx=(2, 12)
        )
        ttk.Label(
            bar,
            text="(use \\n for newline, \\t for tab)",
            foreground="gray",
        ).pack(side=tk.LEFT)

    def _build_notebook(self) -> None:
        nb = ttk.Notebook(self.root)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        for builder in (
            self._tab_count,
            self._tab_truncate,
            self._tab_pack,
            self._tab_priority,
            self._tab_chat,
            self._tab_split,
            self._tab_window,
        ):
            frame = ttk.Frame(nb, padding=8)
            title = builder(frame)
            nb.add(frame, text=title)

    def _build_statusbar(self) -> None:
        self._status = tk.StringVar(value="Ready.")
        ttk.Label(
            self.root,
            textvariable=self._status,
            relief="sunken",
            anchor="w",
        ).pack(fill=tk.X, side=tk.BOTTOM, padx=8, pady=(0, 4))

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _packer(self) -> Contextpacker:
        try:
            max_tokens = int(self._max_tokens.get())
            if max_tokens < 1:
                raise ValueError
        except ValueError:
            self._status.set("Invalid max_tokens — using 4096.")
            max_tokens = 4096
        sep = (
            self._separator.get()
            .replace("\\n", "\n")
            .replace("\\t", "\t")
        )
        return Contextpacker(max_tokens=max_tokens, separator=sep)

    def _status_ok(self, msg: str) -> None:
        self._status.set(msg)

    @staticmethod
    def _input_box(parent: tk.Widget, label: str, height: int = 8) -> scrolledtext.ScrolledText:
        ttk.Label(parent, text=label).pack(anchor="w")
        box = scrolledtext.ScrolledText(parent, height=height, wrap=tk.WORD)
        box.pack(fill=tk.BOTH, expand=True, pady=(2, 6))
        return box

    @staticmethod
    def _output_box(parent: tk.Widget, label: str, height: int = 8) -> scrolledtext.ScrolledText:
        ttk.Label(parent, text=label).pack(anchor="w")
        box = scrolledtext.ScrolledText(
            parent, height=height, wrap=tk.WORD, state="disabled", background="#f5f5f5"
        )
        box.pack(fill=tk.BOTH, expand=True, pady=(2, 0))
        return box

    # ------------------------------------------------------------------
    # Tab: Count tokens
    # ------------------------------------------------------------------

    def _tab_count(self, f: ttk.Frame) -> str:
        self._count_in = self._input_box(f, "Input text:")

        btn_row = ttk.Frame(f)
        btn_row.pack(fill=tk.X, pady=4)
        ttk.Button(
            btn_row, text="Word heuristic (count)", command=self._do_count
        ).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(
            btn_row, text="Char-based (count_chars)", command=self._do_count_chars
        ).pack(side=tk.LEFT)

        self._count_result = tk.StringVar(value="—")
        ttk.Label(f, textvariable=self._count_result, font=("TkDefaultFont", 13, "bold")).pack(
            pady=6
        )
        return "Count tokens"

    def _do_count(self) -> None:
        cp = self._packer()
        n = cp.count(_read(self._count_in))
        self._count_result.set(f"≈ {n} tokens  (word heuristic)")
        self._status_ok(f"count() → {n}")

    def _do_count_chars(self) -> None:
        cp = self._packer()
        n = cp.count_chars(_read(self._count_in))
        self._count_result.set(f"≈ {n} tokens  (char-based)")
        self._status_ok(f"count_chars() → {n}")

    # ------------------------------------------------------------------
    # Tab: Truncate
    # ------------------------------------------------------------------

    def _tab_truncate(self, f: ttk.Frame) -> str:
        self._trunc_in = self._input_box(f, "Input text:")

        btn_row = ttk.Frame(f)
        btn_row.pack(fill=tk.X, pady=4)
        ttk.Button(
            btn_row, text="truncate()  — keep start", command=self._do_truncate
        ).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(
            btn_row, text="truncate_start()  — keep end", command=self._do_truncate_start
        ).pack(side=tk.LEFT)

        self._trunc_out = self._output_box(f, "Output:")
        return "Truncate"

    def _do_truncate(self) -> None:
        cp = self._packer()
        out = cp.truncate(_read(self._trunc_in))
        _set_readonly(self._trunc_out, out)
        self._status_ok(f"truncate() → {cp.count_chars(out)} tokens")

    def _do_truncate_start(self) -> None:
        cp = self._packer()
        out = cp.truncate_start(_read(self._trunc_in))
        _set_readonly(self._trunc_out, out)
        self._status_ok(f"truncate_start() → {cp.count_chars(out)} tokens")

    # ------------------------------------------------------------------
    # Tab: Pack
    # ------------------------------------------------------------------

    def _tab_pack(self, f: ttk.Frame) -> str:
        ttk.Label(
            f, text='Parts — separate with a line containing only "---"', foreground="gray"
        ).pack(anchor="w")
        self._pack_in = scrolledtext.ScrolledText(f, height=9, wrap=tk.WORD)
        self._pack_in.pack(fill=tk.BOTH, expand=True, pady=(2, 6))
        self._pack_in.insert(
            "1.0",
            "System: You are a helpful assistant.\n---\nUser: What is Python?\n---\nAssistant: Python is a high-level programming language.",
        )

        ttk.Button(f, text="pack()", command=self._do_pack).pack(pady=4)
        self._pack_out = self._output_box(f, "Packed output:")
        return "Pack"

    def _do_pack(self) -> None:
        cp = self._packer()
        raw = _read(self._pack_in)
        parts = [p.strip() for p in raw.split("---") if p.strip()]
        out = cp.pack(parts)
        _set_readonly(self._pack_out, out)
        self._status_ok(f"pack() → {cp.count_chars(out)} tokens, {len(parts)} parts → {len(out)} chars")

    # ------------------------------------------------------------------
    # Tab: Priority pack
    # ------------------------------------------------------------------

    def _tab_priority(self, f: ttk.Frame) -> str:
        ttk.Label(
            f, text='JSON array of {"text": "…", "priority": N}', foreground="gray"
        ).pack(anchor="w")
        self._prio_in = scrolledtext.ScrolledText(f, height=9, wrap=tk.WORD)
        self._prio_in.pack(fill=tk.BOTH, expand=True, pady=(2, 6))
        example = json.dumps(
            [
                {"text": "Critical system instructions", "priority": 10},
                {"text": "Relevant retrieved context", "priority": 5},
                {"text": "Optional background note", "priority": 1},
            ],
            indent=2,
        )
        self._prio_in.insert("1.0", example)

        ttk.Button(f, text="pack_priority()", command=self._do_priority).pack(pady=4)
        self._prio_out = self._output_box(f, "Packed output (original order):")
        return "Priority pack"

    def _do_priority(self) -> None:
        cp = self._packer()
        try:
            parts = json.loads(_read(self._prio_in))
        except json.JSONDecodeError as exc:
            messagebox.showerror("JSON error", str(exc))
            return
        out = cp.pack_priority(parts)
        _set_readonly(self._prio_out, out)
        self._status_ok(f"pack_priority() → {cp.count_chars(out)} tokens")

    # ------------------------------------------------------------------
    # Tab: Chat pack
    # ------------------------------------------------------------------

    def _tab_chat(self, f: ttk.Frame) -> str:
        ttk.Label(
            f,
            text='JSON array of {"role": "system|user|assistant", "content": "…"}',
            foreground="gray",
        ).pack(anchor="w")
        self._chat_in = scrolledtext.ScrolledText(f, height=9, wrap=tk.WORD)
        self._chat_in.pack(fill=tk.BOTH, expand=True, pady=(2, 4))
        example = json.dumps(
            [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is Python?"},
                {"role": "assistant", "content": "Python is a high-level programming language."},
                {"role": "user", "content": "Tell me more about it."},
            ],
            indent=2,
        )
        self._chat_in.insert("1.0", example)

        opt_row = ttk.Frame(f)
        opt_row.pack(fill=tk.X, pady=2)
        self._keep_system = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opt_row, text="keep_system", variable=self._keep_system
        ).pack(side=tk.LEFT)
        ttk.Button(opt_row, text="pack_chat()", command=self._do_chat).pack(
            side=tk.LEFT, padx=8
        )

        self._chat_out = self._output_box(f, "Trimmed messages (JSON):")
        return "Chat pack"

    def _do_chat(self) -> None:
        cp = self._packer()
        try:
            messages = json.loads(_read(self._chat_in))
        except json.JSONDecodeError as exc:
            messagebox.showerror("JSON error", str(exc))
            return
        result = cp.pack_chat(messages, keep_system=self._keep_system.get())
        _set_readonly(self._chat_out, json.dumps(result, indent=2))
        self._status_ok(f"pack_chat() → {len(result)} message(s) kept")

    # ------------------------------------------------------------------
    # Tab: Split
    # ------------------------------------------------------------------

    def _tab_split(self, f: ttk.Frame) -> str:
        self._split_in = self._input_box(f, "Input text:")
        ttk.Button(f, text="split()", command=self._do_split).pack(pady=4)
        self._split_out = self._output_box(f, "Chunks (JSON array):")
        return "Split"

    def _do_split(self) -> None:
        cp = self._packer()
        chunks = cp.split(_read(self._split_in))
        _set_readonly(self._split_out, json.dumps(chunks, indent=2, ensure_ascii=False))
        self._status_ok(f"split() → {len(chunks)} chunk(s)")

    # ------------------------------------------------------------------
    # Tab: Sliding window
    # ------------------------------------------------------------------

    def _tab_window(self, f: ttk.Frame) -> str:
        ttk.Label(
            f, text='Parts — separate with a line containing only "---"', foreground="gray"
        ).pack(anchor="w")
        self._win_in = scrolledtext.ScrolledText(f, height=9, wrap=tk.WORD)
        self._win_in.pack(fill=tk.BOTH, expand=True, pady=(2, 6))
        self._win_in.insert(
            "1.0", "oldest entry\n---\nmiddle entry\n---\nrecent entry"
        )

        ttk.Button(f, text="sliding_window()", command=self._do_window).pack(pady=4)
        self._win_out = self._output_box(f, "Selected parts (most recent that fit):")
        return "Sliding window"

    def _do_window(self) -> None:
        cp = self._packer()
        raw = _read(self._win_in)
        parts = [p.strip() for p in raw.split("---") if p.strip()]
        result = cp.sliding_window(parts)
        _set_readonly(self._win_out, "\n---\n".join(result))
        self._status_ok(
            f"sliding_window() → {len(result)} of {len(parts)} part(s) fit"
        )


if __name__ == "__main__":
    main()
