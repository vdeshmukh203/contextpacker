"""Graphical interface for contextpacker.

Launch with::

    python -m contextpacker
    # or, if installed:
    contextpacker-gui
"""
from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import List, Optional, Set, Tuple

from contextpacker import Contextpacker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_separator(raw: str) -> str:
    """Expand \\n and \\t escape sequences entered in the UI text fields."""
    return raw.replace("\\n", "\n").replace("\\t", "\t")


def _make_packer(
    max_tokens_var: tk.StringVar,
    sep_var: tk.StringVar,
) -> Optional[Contextpacker]:
    """Build a Contextpacker from the current configuration widgets."""
    try:
        mt = int(max_tokens_var.get())
        sep = _resolve_separator(sep_var.get())
        return Contextpacker(max_tokens=mt, separator=sep)
    except (ValueError, TypeError) as exc:
        messagebox.showerror("Configuration Error", str(exc))
        return None


def _set_output(widget: ScrolledText, text: str) -> None:
    """Replace the contents of a read-only ScrolledText widget."""
    widget.configure(state=tk.NORMAL)
    widget.delete("1.0", tk.END)
    widget.insert(tk.END, text)
    widget.configure(state=tk.DISABLED)


def _make_output_area(parent: ttk.Frame) -> Tuple[ScrolledText, tk.StringVar]:
    """Create an output panel: a status label above a read-only text area."""
    out_frame = ttk.LabelFrame(parent, text=" Output ", padding=4)
    out_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    status_var = tk.StringVar(value="")
    ttk.Label(out_frame, textvariable=status_var, anchor=tk.W).pack(fill=tk.X, pady=(0, 2))

    txt = ScrolledText(
        out_frame, height=8, wrap=tk.WORD, font=("Courier", 10), state=tk.DISABLED
    )
    txt.pack(fill=tk.BOTH, expand=True)
    return txt, status_var


# ---------------------------------------------------------------------------
# Scrollable parts list
# ---------------------------------------------------------------------------

class _PartsManager:
    """Manages a dynamic, scrollable list of text-entry rows."""

    def __init__(self, inner_frame: ttk.Frame, with_priority: bool = False) -> None:
        self._frame = inner_frame
        self._with_priority = with_priority
        # Each entry: (container_frame, text_widget, priority_var_or_None)
        self._rows: List[Tuple[ttk.Frame, ScrolledText, Optional[tk.IntVar]]] = []

    def add_part(self, initial_text: str = "") -> None:
        row = ttk.Frame(self._frame)
        row.pack(fill=tk.X, padx=4, pady=3)

        hdr = ttk.Frame(row)
        hdr.pack(fill=tk.X)

        n = len(self._rows) + 1
        ttk.Label(hdr, text=f"Part {n}", width=7).pack(side=tk.LEFT)

        priority_var: Optional[tk.IntVar] = None
        if self._with_priority:
            ttk.Label(hdr, text="Priority:").pack(side=tk.LEFT, padx=(8, 2))
            priority_var = tk.IntVar(value=5)
            ttk.Spinbox(hdr, from_=0, to=100, textvariable=priority_var, width=5).pack(
                side=tk.LEFT
            )

        txt = ScrolledText(row, height=3, wrap=tk.WORD, font=("Courier", 10))
        txt.pack(fill=tk.X, padx=2, pady=2)
        if initial_text:
            txt.insert(tk.END, initial_text)

        entry = (row, txt, priority_var)
        self._rows.append(entry)

        def _remove(e=entry, r=row):
            r.destroy()
            if e in self._rows:
                self._rows.remove(e)

        ttk.Button(hdr, text="✕", width=2, command=_remove).pack(side=tk.RIGHT, padx=2)

    def get_texts(self) -> List[str]:
        return [txt.get("1.0", tk.END).strip() for _, txt, _ in self._rows]

    def get_priority_parts(self) -> List[dict]:
        return [
            {
                "text": txt.get("1.0", tk.END).strip(),
                "priority": pv.get() if pv is not None else 1,
            }
            for _, txt, pv in self._rows
        ]


def _scrollable_parts_area(
    parent: ttk.Frame, with_priority: bool = False
) -> Tuple[ttk.Frame, _PartsManager]:
    """Return an (inner_frame, PartsManager) backed by a Canvas+Scrollbar."""
    canvas = tk.Canvas(parent, borderwidth=0, highlightthickness=0)
    vsb = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
    inner = ttk.Frame(canvas)

    canvas.configure(yscrollcommand=vsb.set)
    vsb.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    win_id = canvas.create_window((0, 0), window=inner, anchor=tk.NW)

    def _on_inner_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _on_canvas_configure(event):
        canvas.itemconfig(win_id, width=event.width)

    inner.bind("<Configure>", _on_inner_configure)
    canvas.bind("<Configure>", _on_canvas_configure)

    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    return inner, _PartsManager(inner, with_priority=with_priority)


# ---------------------------------------------------------------------------
# Tab: Pack
# ---------------------------------------------------------------------------

class _PackTab(ttk.Frame):
    TAB_NAME = "Pack"

    def __init__(
        self,
        parent,
        max_tokens_var: tk.StringVar,
        sep_var: tk.StringVar,
        app_status: tk.StringVar,
    ) -> None:
        super().__init__(parent)
        self._mt = max_tokens_var
        self._sep = sep_var
        self._app_status = app_status
        self._build()

    def _build(self) -> None:
        ctrl = ttk.Frame(self)
        ctrl.pack(fill=tk.X, padx=4, pady=4)
        ttk.Button(ctrl, text="+ Add Part", command=self._add).pack(side=tk.LEFT, padx=2)
        ttk.Button(ctrl, text="Pack", command=self._run).pack(side=tk.LEFT, padx=2)
        ttk.Label(ctrl, text="Join parts, truncate to budget").pack(
            side=tk.LEFT, padx=8, foreground="gray"
        )

        parts_outer = ttk.LabelFrame(self, text=" Input Parts ", padding=4)
        parts_outer.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        _, self._mgr = _scrollable_parts_area(parts_outer)

        self._out, self._status = _make_output_area(self)
        self._add()

    def _add(self, text: str = "") -> None:
        self._mgr.add_part(text)

    def _run(self) -> None:
        cp = _make_packer(self._mt, self._sep)
        if cp is None:
            return
        result = cp.pack(self._mgr.get_texts())
        tokens = cp.count_chars(result)
        self._status.set(f"Tokens (char-based): {tokens} / {cp.max_tokens}")
        _set_output(self._out, result)
        self._app_status.set(f"Pack: {tokens}/{cp.max_tokens} tokens")


# ---------------------------------------------------------------------------
# Tab: Pack Priority
# ---------------------------------------------------------------------------

class _PriorityTab(ttk.Frame):
    TAB_NAME = "Pack Priority"

    def __init__(
        self,
        parent,
        max_tokens_var: tk.StringVar,
        sep_var: tk.StringVar,
        app_status: tk.StringVar,
    ) -> None:
        super().__init__(parent)
        self._mt = max_tokens_var
        self._sep = sep_var
        self._app_status = app_status
        self._build()

    def _build(self) -> None:
        ctrl = ttk.Frame(self)
        ctrl.pack(fill=tk.X, padx=4, pady=4)
        ttk.Button(ctrl, text="+ Add Part", command=self._add).pack(side=tk.LEFT, padx=2)
        ttk.Button(ctrl, text="Pack Priority", command=self._run).pack(side=tk.LEFT, padx=2)
        ttk.Label(ctrl, text="Higher priority kept first when budget is tight").pack(
            side=tk.LEFT, padx=8, foreground="gray"
        )

        parts_outer = ttk.LabelFrame(self, text=" Input Parts ", padding=4)
        parts_outer.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        _, self._mgr = _scrollable_parts_area(parts_outer, with_priority=True)

        self._out, self._status = _make_output_area(self)
        self._add()
        self._add()

    def _add(self) -> None:
        self._mgr.add_part()

    def _run(self) -> None:
        cp = _make_packer(self._mt, self._sep)
        if cp is None:
            return
        parts = self._mgr.get_priority_parts()
        result = cp.pack_priority(parts)
        tokens = cp.count_chars(result)
        self._status.set(f"Tokens (char-based): {tokens} / {cp.max_tokens}")
        _set_output(self._out, result)
        self._app_status.set(f"Pack Priority: {tokens}/{cp.max_tokens} tokens")


# ---------------------------------------------------------------------------
# Tab: Pack Chat
# ---------------------------------------------------------------------------

class _ChatTab(ttk.Frame):
    TAB_NAME = "Pack Chat"

    def __init__(
        self,
        parent,
        max_tokens_var: tk.StringVar,
        sep_var: tk.StringVar,
        app_status: tk.StringVar,
    ) -> None:
        super().__init__(parent)
        self._mt = max_tokens_var
        self._sep = sep_var
        self._app_status = app_status
        # (container_frame, role_var, text_widget)
        self._rows: List[Tuple[ttk.Frame, tk.StringVar, ScrolledText]] = []
        self._build()

    def _build(self) -> None:
        ctrl = ttk.Frame(self)
        ctrl.pack(fill=tk.X, padx=4, pady=4)
        ttk.Button(ctrl, text="+ Add Message", command=lambda: self._add_msg()).pack(
            side=tk.LEFT, padx=2
        )
        self._keep_sys = tk.BooleanVar(value=True)
        ttk.Checkbutton(ctrl, text="Keep system messages", variable=self._keep_sys).pack(
            side=tk.LEFT, padx=8
        )
        ttk.Button(ctrl, text="Pack Chat", command=self._run).pack(side=tk.LEFT, padx=2)

        msgs_outer = ttk.LabelFrame(
            self, text=" Messages  (oldest → newest, newest kept first when tight) ", padding=4
        )
        msgs_outer.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        canvas = tk.Canvas(msgs_outer, borderwidth=0, highlightthickness=0)
        vsb = ttk.Scrollbar(msgs_outer, orient=tk.VERTICAL, command=canvas.yview)
        self._msgs_inner = ttk.Frame(canvas)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        win_id = canvas.create_window((0, 0), window=self._msgs_inner, anchor=tk.NW)
        self._msgs_inner.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))

        out_frame = ttk.LabelFrame(self, text=" Result (JSON) ", padding=4)
        out_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._status = tk.StringVar(value="")
        ttk.Label(out_frame, textvariable=self._status, anchor=tk.W).pack(fill=tk.X)
        self._out = ScrolledText(
            out_frame, height=8, wrap=tk.WORD, font=("Courier", 10), state=tk.DISABLED
        )
        self._out.pack(fill=tk.BOTH, expand=True)

        self._add_msg("system", "You are a helpful assistant.")
        self._add_msg("user", "Hello!")
        self._add_msg("assistant", "Hi! How can I help?")
        self._add_msg("user", "What is the capital of France?")

    def _add_msg(self, role: str = "user", content: str = "") -> None:
        row = ttk.Frame(self._msgs_inner)
        row.pack(fill=tk.X, padx=4, pady=2)

        role_var = tk.StringVar(value=role)
        ttk.Combobox(
            row,
            textvariable=role_var,
            values=["user", "assistant", "system"],
            width=10,
            state="readonly",
        ).pack(side=tk.LEFT, padx=(0, 4))

        txt = ScrolledText(row, height=2, wrap=tk.WORD, font=("Courier", 10))
        txt.pack(side=tk.LEFT, fill=tk.X, expand=True)
        if content:
            txt.insert(tk.END, content)

        entry = (row, role_var, txt)
        self._rows.append(entry)

        def _remove(e=entry, r=row):
            r.destroy()
            if e in self._rows:
                self._rows.remove(e)

        ttk.Button(row, text="✕", width=2, command=_remove).pack(side=tk.RIGHT, padx=2)

    def _run(self) -> None:
        cp = _make_packer(self._mt, self._sep)
        if cp is None:
            return
        messages = [
            {"role": rv.get(), "content": txt.get("1.0", tk.END).strip()}
            for _, rv, txt in self._rows
        ]
        result = cp.pack_chat(messages, keep_system=self._keep_sys.get())
        total = sum(cp.count_chars(m.get("content", "")) for m in result)
        dropped = len(messages) - len(result)
        self._status.set(
            f"Kept: {len(result)}/{len(messages)} messages  |  "
            f"~{total}/{cp.max_tokens} tokens  |  Dropped: {dropped}"
        )
        _set_output(self._out, json.dumps(result, indent=2, ensure_ascii=False))
        self._app_status.set(f"Pack Chat: {len(result)}/{len(messages)} messages fit")


# ---------------------------------------------------------------------------
# Tab: Truncate
# ---------------------------------------------------------------------------

class _TruncateTab(ttk.Frame):
    TAB_NAME = "Truncate"

    def __init__(
        self,
        parent,
        max_tokens_var: tk.StringVar,
        sep_var: tk.StringVar,
        app_status: tk.StringVar,
    ) -> None:
        super().__init__(parent)
        self._mt = max_tokens_var
        self._sep = sep_var
        self._app_status = app_status
        self._build()

    def _build(self) -> None:
        in_frame = ttk.LabelFrame(self, text=" Input Text ", padding=4)
        in_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._in = ScrolledText(in_frame, height=10, wrap=tk.WORD, font=("Courier", 10))
        self._in.pack(fill=tk.BOTH, expand=True)

        ctrl = ttk.Frame(self)
        ctrl.pack(fill=tk.X, padx=4, pady=4)
        ttk.Button(
            ctrl, text="Truncate (keep start)", command=lambda: self._run(keep_end=False)
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            ctrl, text="Truncate (keep end)", command=lambda: self._run(keep_end=True)
        ).pack(side=tk.LEFT, padx=2)

        self._out, self._status = _make_output_area(self)

    def _run(self, keep_end: bool) -> None:
        cp = _make_packer(self._mt, self._sep)
        if cp is None:
            return
        text = self._in.get("1.0", tk.END).strip()
        result = cp.truncate_start(text) if keep_end else cp.truncate(text)
        in_tok = cp.count_chars(text)
        out_tok = cp.count_chars(result)
        mode = "keep end" if keep_end else "keep start"
        self._status.set(
            f"Mode: {mode}  |  Input: ~{in_tok} tokens → Output: ~{out_tok} tokens"
        )
        _set_output(self._out, result)
        self._app_status.set(f"Truncate: {in_tok} → {out_tok} tokens")


# ---------------------------------------------------------------------------
# Tab: Split
# ---------------------------------------------------------------------------

class _SplitTab(ttk.Frame):
    TAB_NAME = "Split"

    def __init__(
        self,
        parent,
        max_tokens_var: tk.StringVar,
        sep_var: tk.StringVar,
        app_status: tk.StringVar,
    ) -> None:
        super().__init__(parent)
        self._mt = max_tokens_var
        self._sep = sep_var
        self._app_status = app_status
        self._build()

    def _build(self) -> None:
        in_frame = ttk.LabelFrame(self, text=" Input Text ", padding=4)
        in_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._in = ScrolledText(in_frame, height=8, wrap=tk.WORD, font=("Courier", 10))
        self._in.pack(fill=tk.BOTH, expand=True)

        ctrl = ttk.Frame(self)
        ctrl.pack(fill=tk.X, padx=4, pady=4)
        ttk.Button(ctrl, text="Split into Chunks", command=self._run).pack(
            side=tk.LEFT, padx=2
        )

        self._out, self._status = _make_output_area(self)

    def _run(self) -> None:
        cp = _make_packer(self._mt, self._sep)
        if cp is None:
            return
        text = self._in.get("1.0", tk.END).strip()
        chunks = cp.split(text)
        self._status.set(
            f"Chunks: {len(chunks)}  |  max {cp.max_tokens} tokens each"
        )
        lines: List[str] = []
        for i, chunk in enumerate(chunks, 1):
            lines.append(f"--- Chunk {i}  (~{cp.count_chars(chunk)} tokens) ---")
            lines.append(chunk)
            lines.append("")
        _set_output(self._out, "\n".join(lines))
        self._app_status.set(f"Split: {len(chunks)} chunks")


# ---------------------------------------------------------------------------
# Tab: Token Counter
# ---------------------------------------------------------------------------

class _CounterTab(ttk.Frame):
    TAB_NAME = "Token Counter"

    def __init__(
        self,
        parent,
        max_tokens_var: tk.StringVar,
        sep_var: tk.StringVar,
        app_status: tk.StringVar,
    ) -> None:
        super().__init__(parent)
        self._mt = max_tokens_var
        self._sep = sep_var
        self._app_status = app_status
        self._build()

    def _build(self) -> None:
        in_frame = ttk.LabelFrame(self, text=" Text (live counting) ", padding=4)
        in_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._in = ScrolledText(in_frame, height=12, wrap=tk.WORD, font=("Courier", 10))
        self._in.pack(fill=tk.BOTH, expand=True)
        self._in.bind("<KeyRelease>", self._update)

        stats = ttk.LabelFrame(self, text=" Estimates ", padding=6)
        stats.pack(fill=tk.X, padx=4, pady=4)

        self._wc_var = tk.StringVar(value="Word-aware count : 0")
        self._cc_var = tk.StringVar(value="Char-based count : 0")
        self._budget_var = tk.StringVar(value="Budget used      : 0 / ?")
        self._chars_var = tk.StringVar(value="Characters       : 0")

        for var in (self._wc_var, self._cc_var, self._budget_var, self._chars_var):
            ttk.Label(stats, textvariable=var, font=("Courier", 11)).pack(
                anchor=tk.W, padx=4, pady=1
            )

    def _update(self, _event=None) -> None:
        cp = _make_packer(self._mt, self._sep)
        if cp is None:
            return
        text = self._in.get("1.0", tk.END)
        wc = cp.count(text)
        cc = cp.count_chars(text)
        chars = len(text)
        self._wc_var.set(f"Word-aware count : {wc}")
        self._cc_var.set(f"Char-based count : {cc}")
        self._budget_var.set(f"Budget used      : {cc} / {cp.max_tokens} tokens")
        self._chars_var.set(f"Characters       : {chars}")
        self._app_status.set(f"Counter: {cc}/{cp.max_tokens} tokens")


# ---------------------------------------------------------------------------
# Tab: Sliding Window
# ---------------------------------------------------------------------------

class _SlidingWindowTab(ttk.Frame):
    TAB_NAME = "Sliding Window"

    def __init__(
        self,
        parent,
        max_tokens_var: tk.StringVar,
        sep_var: tk.StringVar,
        app_status: tk.StringVar,
    ) -> None:
        super().__init__(parent)
        self._mt = max_tokens_var
        self._sep = sep_var
        self._app_status = app_status
        self._build()

    def _build(self) -> None:
        ctrl = ttk.Frame(self)
        ctrl.pack(fill=tk.X, padx=4, pady=4)
        ttk.Button(ctrl, text="+ Add Part", command=self._add).pack(side=tk.LEFT, padx=2)
        ttk.Button(ctrl, text="Sliding Window", command=self._run).pack(side=tk.LEFT, padx=2)
        ttk.Label(ctrl, text="Newest parts (bottom) are kept first").pack(
            side=tk.LEFT, padx=8, foreground="gray"
        )

        parts_outer = ttk.LabelFrame(
            self, text=" Parts  (oldest → newest) ", padding=4
        )
        parts_outer.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        _, self._mgr = _scrollable_parts_area(parts_outer)

        self._out, self._status = _make_output_area(self)

        for seed in ("Old context that may be dropped", "Middle context", "Recent context"):
            self._add(seed)

    def _add(self, text: str = "") -> None:
        self._mgr.add_part(text)

    def _run(self) -> None:
        cp = _make_packer(self._mt, self._sep)
        if cp is None:
            return
        parts = self._mgr.get_texts()
        kept = cp.sliding_window(parts)
        kept_set: Set[str] = set(kept)
        tokens = sum(cp.count_chars(p) for p in kept)
        self._status.set(
            f"Parts kept: {len(kept)}/{len(parts)}  |  "
            f"~{tokens}/{cp.max_tokens} tokens"
        )
        lines: List[str] = []
        for i, part in enumerate(parts, 1):
            flag = "✓ kept   " if part in kept_set else "✗ dropped"
            preview = part[:80] + ("…" if len(part) > 80 else "")
            lines.append(f"Part {i:2d} [{flag}]: {preview}")
        _set_output(self._out, "\n".join(lines))
        self._app_status.set(f"Sliding Window: {len(kept)}/{len(parts)} parts fit")


# ---------------------------------------------------------------------------
# Main application window
# ---------------------------------------------------------------------------

class ContextPackerApp:
    """Root window for the ContextPacker GUI application."""

    _TABS = (
        _PackTab,
        _PriorityTab,
        _ChatTab,
        _TruncateTab,
        _SplitTab,
        _CounterTab,
        _SlidingWindowTab,
    )

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("ContextPacker")
        self.root.geometry("960x720")
        self.root.minsize(700, 520)
        self._build()

    def _build(self) -> None:
        # --- Configuration bar ---
        cfg = ttk.LabelFrame(self.root, text=" Configuration ", padding=5)
        cfg.pack(fill=tk.X, padx=8, pady=(8, 0))

        ttk.Label(cfg, text="Max tokens:").grid(row=0, column=0, sticky=tk.W, padx=4)
        self._mt_var = tk.StringVar(value="8192")
        ttk.Entry(cfg, textvariable=self._mt_var, width=10).grid(row=0, column=1, padx=4)

        ttk.Label(cfg, text="Separator (use \\n for newline):").grid(
            row=0, column=2, sticky=tk.W, padx=(20, 4)
        )
        self._sep_var = tk.StringVar(value="\\n\\n")
        ttk.Entry(cfg, textvariable=self._sep_var, width=14).grid(row=0, column=3, padx=4)

        # --- Status bar ---
        self._status_var = tk.StringVar(value="Ready")
        ttk.Label(
            self.root,
            textvariable=self._status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 2),
        ).pack(fill=tk.X, side=tk.BOTTOM, padx=8, pady=(0, 8))

        # --- Notebook ---
        nb = ttk.Notebook(self.root)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        for cls in self._TABS:
            tab = cls(nb, self._mt_var, self._sep_var, self._status_var)
            nb.add(tab, text=f"  {cls.TAB_NAME}  ")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def launch() -> None:
    """Launch the ContextPacker GUI application."""
    root = tk.Tk()
    ContextPackerApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch()
