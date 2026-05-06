"""Tkinter GUI for interactive contextpacker exploration."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from .packer import DEFAULT_MAX_TOKENS, Contextpacker


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _scrolled_text(parent: tk.Widget, height: int = 6, state: str = tk.NORMAL) -> tk.Text:
    frame = ttk.Frame(parent)
    frame.pack(fill=tk.BOTH, expand=True)
    widget = tk.Text(
        frame, height=height, wrap=tk.WORD, font=("Courier", 10), state=state
    )
    sb = ttk.Scrollbar(frame, command=widget.yview)
    widget.configure(yscrollcommand=sb.set)
    widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb.pack(side=tk.RIGHT, fill=tk.Y)
    return widget


def _labeled(parent: tk.Widget, label: str) -> ttk.LabelFrame:
    lf = ttk.LabelFrame(parent, text=label)
    lf.pack(fill=tk.BOTH, expand=True, padx=6, pady=3)
    return lf


def _set_readonly(widget: tk.Text, text: str) -> None:
    widget.configure(state=tk.NORMAL)
    widget.delete("1.0", tk.END)
    widget.insert(tk.END, text)
    widget.configure(state=tk.DISABLED)


def _token_spinbox(parent: tk.Widget, var: tk.IntVar) -> ttk.Spinbox:
    return ttk.Spinbox(
        parent, textvariable=var, from_=0, to=1_000_000, width=10
    )


# ---------------------------------------------------------------------------
# Tab: Token Counter
# ---------------------------------------------------------------------------

class _CounterTab(ttk.Frame):
    def __init__(self, parent: ttk.Notebook, cp: Contextpacker) -> None:
        super().__init__(parent)
        self._cp = cp
        self._build()

    def _build(self) -> None:
        ttk.Label(
            self,
            text="Type or paste text below — counts update in real time.",
            foreground="gray",
        ).pack(anchor=tk.W, padx=8, pady=(6, 2))

        in_lf = _labeled(self, "Input text")
        self._input = _scrolled_text(in_lf, height=14)
        self._input.bind("<KeyRelease>", self._update)
        self._input.bind("<ButtonRelease>", self._update)

        stats = ttk.Frame(self)
        stats.pack(fill=tk.X, padx=8, pady=4)
        for col in range(4):
            stats.columnconfigure(col, weight=1)

        self._lbl_words = ttk.Label(stats, text="Words: 0", anchor=tk.CENTER)
        self._lbl_words.grid(row=0, column=0, padx=4)
        self._lbl_word_tok = ttk.Label(
            stats, text="Tokens (word): 0", anchor=tk.CENTER
        )
        self._lbl_word_tok.grid(row=0, column=1, padx=4)
        self._lbl_char_tok = ttk.Label(
            stats, text="Tokens (char): 0", anchor=tk.CENTER
        )
        self._lbl_char_tok.grid(row=0, column=2, padx=4)
        self._lbl_chars = ttk.Label(stats, text="Chars: 0", anchor=tk.CENTER)
        self._lbl_chars.grid(row=0, column=3, padx=4)

    def _update(self, _event: Optional[tk.Event] = None) -> None:
        text = self._input.get("1.0", tk.END).rstrip("\n")
        self._lbl_words.configure(text=f"Words: {len(text.split())}")
        self._lbl_word_tok.configure(
            text=f"Tokens (word): {self._cp.count(text)}"
        )
        self._lbl_char_tok.configure(
            text=f"Tokens (char): {self._cp.count_chars(text)}"
        )
        self._lbl_chars.configure(text=f"Chars: {len(text)}")


# ---------------------------------------------------------------------------
# Tab: Pack
# ---------------------------------------------------------------------------

class _PackTab(ttk.Frame):
    def __init__(self, parent: ttk.Notebook, cp: Contextpacker) -> None:
        super().__init__(parent)
        self._cp = cp
        self._build()

    def _build(self) -> None:
        ctrl = ttk.Frame(self)
        ctrl.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(ctrl, text="Max tokens:").pack(side=tk.LEFT)
        self._max_tokens = tk.IntVar(value=self._cp.max_tokens)
        _token_spinbox(ctrl, self._max_tokens).pack(side=tk.LEFT, padx=4)

        ttk.Label(
            self,
            text="Separate parts with a blank line.",
            foreground="gray",
        ).pack(anchor=tk.W, padx=8)

        in_lf = _labeled(self, "Input parts")
        self._input = _scrolled_text(in_lf, height=9)

        ttk.Button(self, text="Pack →", command=self._run).pack(pady=4)

        out_lf = _labeled(self, "Packed output")
        self._output = _scrolled_text(out_lf, height=6, state=tk.DISABLED)

        self._status = ttk.Label(self, text="")
        self._status.pack(pady=2)

    def _run(self) -> None:
        raw = self._input.get("1.0", tk.END).rstrip("\n")
        parts = [p.strip() for p in raw.split("\n\n") if p.strip()]
        try:
            result = self._cp.pack(parts, max_tokens=self._max_tokens.get())
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return
        _set_readonly(self._output, result)
        self._status.configure(
            text=f"≈{self._cp.count(result)} tokens  |  {len(result)} chars"
        )


# ---------------------------------------------------------------------------
# Tab: Truncate
# ---------------------------------------------------------------------------

class _TruncateTab(ttk.Frame):
    def __init__(self, parent: ttk.Notebook, cp: Contextpacker) -> None:
        super().__init__(parent)
        self._cp = cp
        self._build()

    def _build(self) -> None:
        ctrl = ttk.Frame(self)
        ctrl.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(ctrl, text="Max tokens:").pack(side=tk.LEFT)
        self._max_tokens = tk.IntVar(value=self._cp.max_tokens)
        _token_spinbox(ctrl, self._max_tokens).pack(side=tk.LEFT, padx=4)
        self._from_start = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            ctrl,
            text="Truncate from start (keep tail / most-recent content)",
            variable=self._from_start,
        ).pack(side=tk.LEFT, padx=12)

        in_lf = _labeled(self, "Input text")
        self._input = _scrolled_text(in_lf, height=9)

        ttk.Button(self, text="Truncate →", command=self._run).pack(pady=4)

        out_lf = _labeled(self, "Truncated output")
        self._output = _scrolled_text(out_lf, height=6, state=tk.DISABLED)

        self._status = ttk.Label(self, text="")
        self._status.pack(pady=2)

    def _run(self) -> None:
        text = self._input.get("1.0", tk.END).rstrip("\n")
        try:
            limit = self._max_tokens.get()
            result = (
                self._cp.truncate_start(text, max_tokens=limit)
                if self._from_start.get()
                else self._cp.truncate(text, max_tokens=limit)
            )
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return
        _set_readonly(self._output, result)
        self._status.configure(
            text=f"≈{self._cp.count(result)} tokens  |  {len(result)} chars"
        )


# ---------------------------------------------------------------------------
# Tab: Pack Chat
# ---------------------------------------------------------------------------

class _PackChatTab(ttk.Frame):
    _PLACEHOLDER = (
        "system: You are a helpful assistant.\n"
        "user: Tell me about LLMs.\n"
        "assistant: Large language models are neural networks...\n"
        "user: Can you summarize that?"
    )

    def __init__(self, parent: ttk.Notebook, cp: Contextpacker) -> None:
        super().__init__(parent)
        self._cp = cp
        self._build()

    def _build(self) -> None:
        ctrl = ttk.Frame(self)
        ctrl.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(ctrl, text="Max tokens:").pack(side=tk.LEFT)
        self._max_tokens = tk.IntVar(value=self._cp.max_tokens)
        _token_spinbox(ctrl, self._max_tokens).pack(side=tk.LEFT, padx=4)
        self._keep_sys = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            ctrl, text="Keep system messages", variable=self._keep_sys
        ).pack(side=tk.LEFT, padx=12)

        ttk.Label(
            self,
            text='One message per line in the format  "role: content"  (roles: system / user / assistant).',
            foreground="gray",
        ).pack(anchor=tk.W, padx=8)

        in_lf = _labeled(self, "Messages (chronological)")
        self._input = _scrolled_text(in_lf, height=8)
        self._input.insert(tk.END, self._PLACEHOLDER)

        ttk.Button(self, text="Pack chat →", command=self._run).pack(pady=4)

        out_lf = _labeled(self, "Retained messages")
        self._output = _scrolled_text(out_lf, height=6, state=tk.DISABLED)

        self._status = ttk.Label(self, text="")
        self._status.pack(pady=2)

    def _run(self) -> None:
        raw = self._input.get("1.0", tk.END).strip()
        messages = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            if ":" not in line:
                messagebox.showerror(
                    "Parse error",
                    f"Line has no colon: {line!r}\nExpected format: role: content",
                )
                return
            role, _, content = line.partition(":")
            messages.append({"role": role.strip(), "content": content.strip()})
        try:
            result = self._cp.pack_chat(
                messages,
                max_tokens=self._max_tokens.get(),
                keep_system=self._keep_sys.get(),
            )
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return
        output_text = "\n".join(
            f"{m['role']}: {m['content']}" for m in result
        )
        _set_readonly(self._output, output_text)
        total = sum(self._cp.count(m["content"]) for m in result)
        self._status.configure(
            text=f"{len(result)} message(s) retained  |  ≈{total} tokens"
        )


# ---------------------------------------------------------------------------
# Tab: Pack Priority
# ---------------------------------------------------------------------------

class _PackPriorityTab(ttk.Frame):
    _PLACEHOLDER = (
        "10 | IMPORTANT: safety instructions for the assistant.\n"
        "5  | Background context about the user's project.\n"
        "1  | Supplementary details that are nice to have.\n"
        "8  | Recent user query that needs answering."
    )

    def __init__(self, parent: ttk.Notebook, cp: Contextpacker) -> None:
        super().__init__(parent)
        self._cp = cp
        self._build()

    def _build(self) -> None:
        ctrl = ttk.Frame(self)
        ctrl.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(ctrl, text="Max tokens:").pack(side=tk.LEFT)
        self._max_tokens = tk.IntVar(value=self._cp.max_tokens)
        _token_spinbox(ctrl, self._max_tokens).pack(side=tk.LEFT, padx=4)

        ttk.Label(
            self,
            text='One part per line in the format  "priority | text".',
            foreground="gray",
        ).pack(anchor=tk.W, padx=8)

        in_lf = _labeled(self, "Priority parts")
        self._input = _scrolled_text(in_lf, height=8)
        self._input.insert(tk.END, self._PLACEHOLDER)

        ttk.Button(self, text="Pack priority →", command=self._run).pack(pady=4)

        out_lf = _labeled(self, "Packed output (highest priority first)")
        self._output = _scrolled_text(out_lf, height=6, state=tk.DISABLED)

        self._status = ttk.Label(self, text="")
        self._status.pack(pady=2)

    def _run(self) -> None:
        raw = self._input.get("1.0", tk.END).strip()
        parts = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            if "|" not in line:
                messagebox.showerror(
                    "Parse error",
                    f"Line has no '|': {line!r}\nExpected format: priority | text",
                )
                return
            pri_str, _, text = line.partition("|")
            try:
                priority = int(pri_str.strip())
            except ValueError:
                messagebox.showerror(
                    "Parse error",
                    f"Priority must be an integer, got: {pri_str.strip()!r}",
                )
                return
            parts.append({"priority": priority, "text": text.strip()})
        try:
            result = self._cp.pack_priority(parts, max_tokens=self._max_tokens.get())
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return
        _set_readonly(self._output, result)
        self._status.configure(
            text=f"≈{self._cp.count(result)} tokens  |  {len(result)} chars"
        )


# ---------------------------------------------------------------------------
# Tab: Split
# ---------------------------------------------------------------------------

class _SplitTab(ttk.Frame):
    def __init__(self, parent: ttk.Notebook, cp: Contextpacker) -> None:
        super().__init__(parent)
        self._cp = cp
        self._build()

    def _build(self) -> None:
        ctrl = ttk.Frame(self)
        ctrl.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(ctrl, text="Max tokens per chunk:").pack(side=tk.LEFT)
        self._max_tokens = tk.IntVar(value=self._cp.max_tokens)
        _token_spinbox(ctrl, self._max_tokens).pack(side=tk.LEFT, padx=4)

        in_lf = _labeled(self, "Input text")
        self._input = _scrolled_text(in_lf, height=9)

        ttk.Button(self, text="Split →", command=self._run).pack(pady=4)

        out_lf = _labeled(self, "Chunks (separated by dividers)")
        self._output = _scrolled_text(out_lf, height=6, state=tk.DISABLED)

        self._status = ttk.Label(self, text="")
        self._status.pack(pady=2)

    def _run(self) -> None:
        text = self._input.get("1.0", tk.END).rstrip("\n")
        try:
            chunks = self._cp.split(text, max_tokens=self._max_tokens.get())
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return
        divider = "\n" + "─" * 40 + "\n"
        _set_readonly(self._output, divider.join(chunks))
        self._status.configure(text=f"{len(chunks)} chunk(s)")


# ---------------------------------------------------------------------------
# Tab: Sliding Window
# ---------------------------------------------------------------------------

class _SlidingWindowTab(ttk.Frame):
    _PLACEHOLDER = (
        "This is the oldest context part.\n\n"
        "This is some middle context.\n\n"
        "This is more recent context.\n\n"
        "This is the most recent part."
    )

    def __init__(self, parent: ttk.Notebook, cp: Contextpacker) -> None:
        super().__init__(parent)
        self._cp = cp
        self._build()

    def _build(self) -> None:
        ctrl = ttk.Frame(self)
        ctrl.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(ctrl, text="Max tokens:").pack(side=tk.LEFT)
        self._max_tokens = tk.IntVar(value=self._cp.max_tokens)
        _token_spinbox(ctrl, self._max_tokens).pack(side=tk.LEFT, padx=4)

        ttk.Label(
            self,
            text="Separate parts with a blank line (oldest first).",
            foreground="gray",
        ).pack(anchor=tk.W, padx=8)

        in_lf = _labeled(self, "Input parts (oldest → newest)")
        self._input = _scrolled_text(in_lf, height=8)
        self._input.insert(tk.END, self._PLACEHOLDER)

        ttk.Button(self, text="Apply window →", command=self._run).pack(pady=4)

        out_lf = _labeled(self, "Most-recent parts that fit")
        self._output = _scrolled_text(out_lf, height=6, state=tk.DISABLED)

        self._status = ttk.Label(self, text="")
        self._status.pack(pady=2)

    def _run(self) -> None:
        raw = self._input.get("1.0", tk.END).rstrip("\n")
        parts = [p.strip() for p in raw.split("\n\n") if p.strip()]
        try:
            result = self._cp.sliding_window(parts, max_tokens=self._max_tokens.get())
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return
        _set_readonly(self._output, "\n\n".join(result))
        total = sum(self._cp.count(p) for p in result)
        self._status.configure(
            text=f"{len(result)} / {len(parts)} part(s) retained  |  ≈{total} tokens"
        )


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class ContextpackerApp:
    """Root application window."""

    def __init__(self, root: tk.Tk, max_tokens: int = DEFAULT_MAX_TOKENS) -> None:
        self._root = root
        root.title("contextpacker")
        root.geometry("860x680")
        root.minsize(640, 480)
        cp = Contextpacker(max_tokens=max_tokens)
        self._build(cp)

    def _build(self, cp: Contextpacker) -> None:
        hdr = ttk.Frame(self._root, padding=(8, 4))
        hdr.pack(fill=tk.X)
        ttk.Label(
            hdr,
            text="contextpacker",
            font=("TkDefaultFont", 13, "bold"),
        ).pack(side=tk.LEFT)
        ttk.Label(
            hdr,
            text=" — token-aware packing and truncation for LLM context windows",
            foreground="gray",
        ).pack(side=tk.LEFT)

        ttk.Separator(self._root, orient=tk.HORIZONTAL).pack(fill=tk.X)

        nb = ttk.Notebook(self._root)
        nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        tabs = [
            ("Token Counter", _CounterTab),
            ("Pack", _PackTab),
            ("Truncate", _TruncateTab),
            ("Pack Chat", _PackChatTab),
            ("Pack Priority", _PackPriorityTab),
            ("Split", _SplitTab),
            ("Sliding Window", _SlidingWindowTab),
        ]
        for label, cls in tabs:
            nb.add(cls(nb, cp), text=f"  {label}  ")


def launch_gui(max_tokens: int = DEFAULT_MAX_TOKENS) -> None:
    """Launch the contextpacker interactive GUI.

    Parameters
    ----------
    max_tokens:
        Default token budget pre-filled in every tab (default: 8192).
    """
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", 1.2)
    except tk.TclError:
        pass
    ContextpackerApp(root, max_tokens=max_tokens)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
