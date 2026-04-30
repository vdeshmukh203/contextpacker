"""Tkinter GUI for contextpacker.

Launch with::

    python -m contextpacker

or programmatically::

    from contextpacker.gui import run_gui
    run_gui()
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from typing import Callable, List, Optional, Tuple

from contextpacker.packer import Contextpacker

_PAD = 6


def run_gui() -> None:
    """Launch the Contextpacker desktop GUI."""
    root = tk.Tk()
    _App(root)
    root.mainloop()


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class _App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Contextpacker")
        self.root.geometry("960x700")
        self.root.minsize(720, 520)

        self._max_tokens_var = tk.IntVar(value=4096)
        self._separator_var = tk.StringVar(value=r"\n\n")
        self._packer = Contextpacker(max_tokens=4096, separator="\n\n")

        self._build_header()
        self._build_notebook()
        self._build_statusbar()

    # ------------------------------------------------------------------
    # Layout builders
    # ------------------------------------------------------------------

    def _build_header(self) -> None:
        frame = ttk.LabelFrame(self.root, text="Settings", padding=_PAD)
        frame.pack(fill=tk.X, padx=_PAD, pady=(_PAD, 0))

        ttk.Label(frame, text="Max tokens:").pack(side=tk.LEFT)
        spin = ttk.Spinbox(
            frame,
            from_=1,
            to=200_000,
            textvariable=self._max_tokens_var,
            width=10,
        )
        spin.pack(side=tk.LEFT, padx=_PAD)
        spin.bind("<Return>", lambda _e: self._apply_settings())

        ttk.Label(frame, text="Separator (\\n = newline, \\t = tab):").pack(
            side=tk.LEFT, padx=(_PAD * 2, 0)
        )
        sep_entry = ttk.Entry(frame, textvariable=self._separator_var, width=14)
        sep_entry.pack(side=tk.LEFT, padx=_PAD)
        sep_entry.bind("<Return>", lambda _e: self._apply_settings())

        ttk.Button(frame, text="Apply", command=self._apply_settings).pack(
            side=tk.LEFT, padx=_PAD
        )

        self._header_info = ttk.Label(frame, text="max_tokens=4096  sep='\\n\\n'",
                                      foreground="gray")
        self._header_info.pack(side=tk.LEFT, padx=_PAD)

    def _build_notebook(self) -> None:
        nb = ttk.Notebook(self.root)
        nb.pack(fill=tk.BOTH, expand=True, padx=_PAD, pady=_PAD)

        tabs = [
            ("Pack", _PackTab),
            ("Truncate", _TruncateTab),
            ("Priority Pack", _PriorityTab),
            ("Chat Pack", _ChatTab),
            ("Split", _SplitTab),
        ]
        self._tabs = []
        for label, cls in tabs:
            tab = cls(nb, self)
            nb.add(tab.frame, text=label)
            self._tabs.append(tab)

    def _build_statusbar(self) -> None:
        self._status_var = tk.StringVar(value="Ready")
        ttk.Label(
            self.root,
            textvariable=self._status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 2),
        ).pack(fill=tk.X, side=tk.BOTTOM)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def packer(self) -> Contextpacker:
        return self._packer

    def _apply_settings(self) -> None:
        try:
            mt = int(self._max_tokens_var.get())
            raw_sep = self._separator_var.get()
            sep = raw_sep.replace(r"\n", "\n").replace(r"\t", "\t")
            self._packer = Contextpacker(max_tokens=mt, separator=sep)
            display_sep = raw_sep[:20] + ("…" if len(raw_sep) > 20 else "")
            self._header_info.config(
                text=f"max_tokens={mt}  sep={display_sep!r}"
            )
            self.status(f"Settings applied — max_tokens={mt}")
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror("Invalid setting", str(exc))

    def status(self, msg: str) -> None:
        self._status_var.set(msg)


# ---------------------------------------------------------------------------
# Tab base
# ---------------------------------------------------------------------------

class _TabBase:
    def __init__(self, nb: ttk.Notebook, app: _App) -> None:
        self.app = app
        self.frame = ttk.Frame(nb)

    def _make_output(self, parent: tk.Widget, height: int = 8) -> scrolledtext.ScrolledText:
        widget = scrolledtext.ScrolledText(
            parent, height=height, font=("Courier", 10), state=tk.DISABLED
        )
        return widget

    def _set_output(self, widget: scrolledtext.ScrolledText, text: str) -> None:
        widget.config(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        widget.config(state=tk.DISABLED)


# ---------------------------------------------------------------------------
# Pack tab
# ---------------------------------------------------------------------------

class _PackTab(_TabBase):
    def __init__(self, nb: ttk.Notebook, app: _App) -> None:
        super().__init__(nb, app)
        f = self.frame

        ttk.Label(f, text="Enter parts separated by blank lines:").pack(
            anchor=tk.W, padx=_PAD, pady=(_PAD, 0)
        )
        self._input = scrolledtext.ScrolledText(f, height=12, font=("Courier", 10))
        self._input.pack(fill=tk.BOTH, expand=True, padx=_PAD, pady=_PAD)
        self._input.insert(
            "1.0",
            "System: You are a helpful assistant.\n\n"
            "User: Tell me about Python.\n\n"
            "Assistant: Python is a versatile, high-level language.",
        )

        btn_row = ttk.Frame(f)
        btn_row.pack(fill=tk.X, padx=_PAD)
        ttk.Button(btn_row, text="Pack", command=self._run).pack(side=tk.LEFT)
        self._info_lbl = ttk.Label(btn_row, text="")
        self._info_lbl.pack(side=tk.LEFT, padx=_PAD)

        ttk.Label(f, text="Result:").pack(anchor=tk.W, padx=_PAD, pady=(_PAD, 0))
        self._output = self._make_output(f)
        self._output.pack(fill=tk.BOTH, expand=True, padx=_PAD, pady=_PAD)

    def _run(self) -> None:
        raw = self._input.get("1.0", tk.END)
        parts = [p.strip() for p in raw.split("\n\n") if p.strip()]
        if not parts:
            messagebox.showinfo("Info", "Enter at least one part.")
            return
        result = self.app.packer.pack(parts)
        tokens = self.app.packer.count(result)
        self._info_lbl.config(text=f"~{tokens} tokens  |  {len(parts)} parts")
        self._set_output(self._output, result)
        self.app.status(f"Packed {len(parts)} parts → ~{tokens} tokens")


# ---------------------------------------------------------------------------
# Truncate tab
# ---------------------------------------------------------------------------

class _TruncateTab(_TabBase):
    def __init__(self, nb: ttk.Notebook, app: _App) -> None:
        super().__init__(nb, app)
        f = self.frame

        mode_row = ttk.Frame(f)
        mode_row.pack(fill=tk.X, padx=_PAD, pady=(_PAD, 0))
        ttk.Label(mode_row, text="Mode:").pack(side=tk.LEFT)
        self._mode = tk.StringVar(value="end")
        ttk.Radiobutton(
            mode_row, text="Drop end (keep start)", variable=self._mode, value="end"
        ).pack(side=tk.LEFT, padx=_PAD)
        ttk.Radiobutton(
            mode_row, text="Drop start (keep end)", variable=self._mode, value="start"
        ).pack(side=tk.LEFT)

        ttk.Label(f, text="Input text:").pack(anchor=tk.W, padx=_PAD, pady=(_PAD, 0))
        self._input = scrolledtext.ScrolledText(f, height=12, font=("Courier", 10))
        self._input.pack(fill=tk.BOTH, expand=True, padx=_PAD, pady=_PAD)
        self._input.insert("1.0", "Paste your long text here to see it truncated…")
        self._input.bind("<<Modified>>", self._on_input_change)
        self._input.edit_modified(False)

        btn_row = ttk.Frame(f)
        btn_row.pack(fill=tk.X, padx=_PAD)
        ttk.Button(btn_row, text="Truncate", command=self._run).pack(side=tk.LEFT)
        self._info_lbl = ttk.Label(btn_row, text="")
        self._info_lbl.pack(side=tk.LEFT, padx=_PAD)

        ttk.Label(f, text="Result:").pack(anchor=tk.W, padx=_PAD, pady=(_PAD, 0))
        self._output = self._make_output(f)
        self._output.pack(fill=tk.BOTH, expand=True, padx=_PAD, pady=_PAD)

    def _on_input_change(self, _event: Optional[tk.Event] = None) -> None:
        if self._input.edit_modified():
            text = self._input.get("1.0", tk.END).rstrip("\n")
            tokens = self.app.packer.count(text)
            limit = self.app.packer.max_tokens
            colour = "red" if tokens > limit else "black"
            self._info_lbl.config(
                text=f"Input: ~{tokens} tokens  (limit {limit})", foreground=colour
            )
            self._input.edit_modified(False)

    def _run(self) -> None:
        text = self._input.get("1.0", tk.END).rstrip("\n")
        if self._mode.get() == "end":
            result = self.app.packer.truncate(text)
        else:
            result = self.app.packer.truncate_start(text)
        tokens = self.app.packer.count(result)
        self._info_lbl.config(
            text=f"Result: ~{tokens} tokens", foreground="black"
        )
        self._set_output(self._output, result)
        self.app.status(f"Truncated to ~{tokens} tokens")


# ---------------------------------------------------------------------------
# Priority Pack tab
# ---------------------------------------------------------------------------

class _PriorityTab(_TabBase):
    def __init__(self, nb: ttk.Notebook, app: _App) -> None:
        super().__init__(nb, app)
        self._rows: List[_PriorityRow] = []

        f = self.frame
        hdr = ttk.Frame(f)
        hdr.pack(fill=tk.X, padx=_PAD, pady=(_PAD, 0))
        ttk.Label(hdr, text="Parts (higher priority = kept first when budget is tight):").pack(
            side=tk.LEFT
        )

        self._rows_frame = ttk.Frame(f)
        self._rows_frame.pack(fill=tk.X, padx=_PAD)

        _PriorityRow.build_header(self._rows_frame)

        ctrl = ttk.Frame(f)
        ctrl.pack(fill=tk.X, padx=_PAD, pady=_PAD)
        ttk.Button(ctrl, text="+ Add part", command=self._add_row).pack(side=tk.LEFT)
        ttk.Button(ctrl, text="Pack Priority", command=self._run).pack(
            side=tk.LEFT, padx=_PAD
        )
        self._order_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            ctrl, text="Preserve original order", variable=self._order_var
        ).pack(side=tk.LEFT)
        self._info_lbl = ttk.Label(ctrl, text="")
        self._info_lbl.pack(side=tk.LEFT, padx=_PAD)

        ttk.Label(f, text="Result:").pack(anchor=tk.W, padx=_PAD, pady=(_PAD, 0))
        self._output = self._make_output(f, height=10)
        self._output.pack(fill=tk.BOTH, expand=True, padx=_PAD, pady=_PAD)

        self._add_row("High priority content — always kept", 10)
        self._add_row("Medium priority supplementary context", 5)
        self._add_row("Low priority filler — dropped first", 1)

    def _add_row(self, text: str = "", priority: int = 5) -> None:
        row = _PriorityRow(self._rows_frame, text, priority, self._remove_row)
        self._rows.append(row)

    def _remove_row(self, row: "_PriorityRow") -> None:
        row.destroy()
        self._rows.remove(row)

    def _run(self) -> None:
        parts = [
            {"text": t, "priority": p}
            for t, p in (r.values() for r in self._rows)
            if t
        ]
        if not parts:
            messagebox.showinfo("Info", "Add at least one part with text.")
            return
        try:
            result = self.app.packer.pack_priority(
                parts, preserve_order=self._order_var.get()
            )
        except ValueError as exc:
            messagebox.showerror("Error", str(exc))
            return
        tokens = self.app.packer.count(result)
        kept = result.count(self.app.packer.separator) + 1 if result else 0
        self._info_lbl.config(
            text=f"~{tokens} tokens  |  {kept}/{len(parts)} parts kept"
        )
        self._set_output(self._output, result)
        self.app.status(f"Priority-packed → ~{tokens} tokens")


class _PriorityRow:
    @staticmethod
    def build_header(parent: ttk.Frame) -> None:
        hdr = ttk.Frame(parent)
        hdr.pack(fill=tk.X)
        ttk.Label(hdr, text="Text", width=52, anchor=tk.W).pack(side=tk.LEFT, padx=2)
        ttk.Label(hdr, text="Priority", width=8, anchor=tk.W).pack(side=tk.LEFT, padx=2)

    def __init__(
        self,
        parent: ttk.Frame,
        text: str,
        priority: int,
        remove_cb: Callable[["_PriorityRow"], None],
    ) -> None:
        self._frame = ttk.Frame(parent)
        self._frame.pack(fill=tk.X, pady=1)

        self._text_var = tk.StringVar(value=text)
        self._priority_var = tk.IntVar(value=priority)

        ttk.Entry(self._frame, textvariable=self._text_var, width=52).pack(
            side=tk.LEFT, padx=(0, _PAD), expand=True, fill=tk.X
        )
        ttk.Spinbox(
            self._frame,
            from_=-100,
            to=100,
            textvariable=self._priority_var,
            width=6,
        ).pack(side=tk.LEFT, padx=_PAD)
        ttk.Button(
            self._frame, text="×", width=2, command=lambda: remove_cb(self)
        ).pack(side=tk.LEFT)

    def values(self) -> Tuple[str, int]:
        return self._text_var.get(), int(self._priority_var.get())

    def destroy(self) -> None:
        self._frame.destroy()


# ---------------------------------------------------------------------------
# Chat Pack tab
# ---------------------------------------------------------------------------

class _ChatTab(_TabBase):
    def __init__(self, nb: ttk.Notebook, app: _App) -> None:
        super().__init__(nb, app)
        self._rows: List[_ChatRow] = []

        f = self.frame
        ttk.Label(f, text="Messages (oldest → newest):").pack(
            anchor=tk.W, padx=_PAD, pady=(_PAD, 0)
        )

        self._rows_frame = ttk.Frame(f)
        self._rows_frame.pack(fill=tk.BOTH, expand=True, padx=_PAD)

        _ChatRow.build_header(self._rows_frame)

        ctrl = ttk.Frame(f)
        ctrl.pack(fill=tk.X, padx=_PAD, pady=_PAD)
        ttk.Button(ctrl, text="+ Add message", command=self._add_row).pack(
            side=tk.LEFT
        )
        ttk.Button(ctrl, text="Pack Chat", command=self._run).pack(
            side=tk.LEFT, padx=_PAD
        )
        self._keep_system = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            ctrl, text="Always keep system messages", variable=self._keep_system
        ).pack(side=tk.LEFT)
        self._info_lbl = ttk.Label(ctrl, text="")
        self._info_lbl.pack(side=tk.LEFT, padx=_PAD)

        ttk.Label(f, text="Result — messages that fit:").pack(
            anchor=tk.W, padx=_PAD, pady=(_PAD, 0)
        )
        self._output = self._make_output(f, height=9)
        self._output.pack(fill=tk.BOTH, expand=True, padx=_PAD, pady=_PAD)

        self._add_row("system", "You are a helpful assistant.")
        self._add_row("user", "Can you explain Python decorators?")
        self._add_row("assistant", "Sure! A decorator is a callable that wraps another function.")
        self._add_row("user", "Can you show me an example?")

    def _add_row(self, role: str = "user", content: str = "") -> None:
        row = _ChatRow(self._rows_frame, role, content, self._remove_row)
        self._rows.append(row)

    def _remove_row(self, row: "_ChatRow") -> None:
        row.destroy()
        self._rows.remove(row)

    def _run(self) -> None:
        messages = [
            {"role": role, "content": content}
            for role, content in (r.values() for r in self._rows)
            if content
        ]
        if not messages:
            messagebox.showinfo("Info", "Add at least one message with content.")
            return
        try:
            result = self.app.packer.pack_chat(
                messages, keep_system=self._keep_system.get()
            )
        except ValueError as exc:
            messagebox.showerror("Error", str(exc))
            return
        kept = len(result)
        total = len(messages)
        lines = "\n".join(f"[{m['role']}]  {m['content']}" for m in result)
        self._set_output(self._output, lines)
        self._info_lbl.config(text=f"{kept}/{total} messages kept")
        self.app.status(f"Chat packed: {kept}/{total} messages fit within budget")


class _ChatRow:
    _ROLES = ("system", "user", "assistant")

    @staticmethod
    def build_header(parent: ttk.Frame) -> None:
        hdr = ttk.Frame(parent)
        hdr.pack(fill=tk.X)
        ttk.Label(hdr, text="Role", width=12, anchor=tk.W).pack(side=tk.LEFT, padx=2)
        ttk.Label(hdr, text="Content", anchor=tk.W).pack(side=tk.LEFT, padx=2)

    def __init__(
        self,
        parent: ttk.Frame,
        role: str,
        content: str,
        remove_cb: Callable[["_ChatRow"], None],
    ) -> None:
        self._frame = ttk.Frame(parent)
        self._frame.pack(fill=tk.X, pady=1)

        self._role_var = tk.StringVar(value=role)
        self._content_var = tk.StringVar(value=content)

        ttk.Combobox(
            self._frame,
            textvariable=self._role_var,
            values=self._ROLES,
            width=10,
            state="readonly",
        ).pack(side=tk.LEFT, padx=(0, _PAD))
        ttk.Entry(self._frame, textvariable=self._content_var, width=60).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=_PAD
        )
        ttk.Button(
            self._frame, text="×", width=2, command=lambda: remove_cb(self)
        ).pack(side=tk.LEFT)

    def values(self) -> Tuple[str, str]:
        return self._role_var.get(), self._content_var.get()

    def destroy(self) -> None:
        self._frame.destroy()


# ---------------------------------------------------------------------------
# Split tab
# ---------------------------------------------------------------------------

class _SplitTab(_TabBase):
    def __init__(self, nb: ttk.Notebook, app: _App) -> None:
        super().__init__(nb, app)
        f = self.frame

        ttk.Label(f, text="Input text to split into token-sized chunks:").pack(
            anchor=tk.W, padx=_PAD, pady=(_PAD, 0)
        )
        self._input = scrolledtext.ScrolledText(f, height=12, font=("Courier", 10))
        self._input.pack(fill=tk.BOTH, expand=True, padx=_PAD, pady=_PAD)
        self._input.insert(
            "1.0",
            "Paste a long document here and click Split to see it divided into "
            "token-budget-sized chunks that can each be processed independently.",
        )

        btn_row = ttk.Frame(f)
        btn_row.pack(fill=tk.X, padx=_PAD)
        ttk.Button(btn_row, text="Split", command=self._run).pack(side=tk.LEFT)
        self._info_lbl = ttk.Label(btn_row, text="")
        self._info_lbl.pack(side=tk.LEFT, padx=_PAD)

        ttk.Label(f, text="Chunks:").pack(anchor=tk.W, padx=_PAD, pady=(_PAD, 0))
        self._output = self._make_output(f, height=9)
        self._output.pack(fill=tk.BOTH, expand=True, padx=_PAD, pady=_PAD)

    def _run(self) -> None:
        text = self._input.get("1.0", tk.END).rstrip("\n")
        chunks = self.app.packer.split(text)
        n = len(chunks)
        self._info_lbl.config(text=f"{n} chunk(s)")
        separator = "\n" + "─" * 60 + "\n"
        lines = separator.join(
            f"Chunk {i + 1}/{n}  (~{self.app.packer.count(c)} tokens)\n{c}"
            for i, c in enumerate(chunks)
        )
        self._set_output(self._output, lines if lines else "(empty)")
        self.app.status(f"Split into {n} chunk(s)")
