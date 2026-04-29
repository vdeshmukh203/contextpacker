"""Tkinter GUI workbench for contextpacker.

Launch with::

    python -m contextpacker.gui

or, after installation::

    contextpacker-gui
"""
from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from typing import List

from contextpacker.packer import CHARS_PER_TOKEN, DEFAULT_MAX_TOKENS, Contextpacker

# ---------------------------------------------------------------------------
# Colour palette & sizing constants
# ---------------------------------------------------------------------------
BG = "#1e1e2e"          # dark background
PANEL = "#2a2a3e"       # card / frame background
ACCENT = "#7c3aed"      # violet accent
ACCENT_HOVER = "#6d28d9"
SUCCESS = "#22c55e"
FG = "#e2e8f0"          # primary text
FG_DIM = "#94a3b8"      # secondary text
INPUT_BG = "#13131f"    # text-area background
BORDER = "#3f3f5a"

FONT_BODY = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_MONO = ("Consolas", 10)
FONT_HEADER = ("Segoe UI", 12, "bold")
FONT_TITLE = ("Segoe UI", 14, "bold")

PAD = 10
IPAD = 6

# ---------------------------------------------------------------------------
# Helper widgets
# ---------------------------------------------------------------------------

def _label(parent: tk.Widget, text: str, **kw) -> tk.Label:
    kw.setdefault("bg", PANEL)
    kw.setdefault("fg", FG_DIM)
    kw.setdefault("font", FONT_BODY)
    kw.setdefault("anchor", "w")
    return tk.Label(parent, text=text, **kw)


def _text_area(parent: tk.Widget, height: int = 8) -> scrolledtext.ScrolledText:
    return scrolledtext.ScrolledText(
        parent,
        height=height,
        font=FONT_MONO,
        bg=INPUT_BG,
        fg=FG,
        insertbackground=FG,
        relief="flat",
        borderwidth=1,
        highlightthickness=1,
        highlightbackground=BORDER,
        highlightcolor=ACCENT,
        wrap="word",
    )


def _button(parent: tk.Widget, text: str, command, **kw) -> tk.Button:
    btn = tk.Button(
        parent,
        text=text,
        command=command,
        bg=ACCENT,
        fg="#ffffff",
        font=FONT_BOLD,
        relief="flat",
        padx=14,
        pady=6,
        cursor="hand2",
        activebackground=ACCENT_HOVER,
        activeforeground="#ffffff",
        **kw,
    )
    btn.bind("<Enter>", lambda _e: btn.config(bg=ACCENT_HOVER))
    btn.bind("<Leave>", lambda _e: btn.config(bg=ACCENT))
    return btn


def _section_frame(parent: tk.Widget) -> tk.Frame:
    return tk.Frame(parent, bg=PANEL, padx=PAD, pady=PAD)


def _spin(parent: tk.Widget, var: tk.IntVar, from_: int = 1, to: int = 1_000_000) -> ttk.Spinbox:
    style = ttk.Style()
    style.configure(
        "Dark.TSpinbox",
        fieldbackground=INPUT_BG,
        foreground=FG,
        background=PANEL,
        arrowcolor=FG,
    )
    return ttk.Spinbox(
        parent,
        textvariable=var,
        from_=from_,
        to=to,
        style="Dark.TSpinbox",
        width=10,
    )


# ---------------------------------------------------------------------------
# Individual tab panels
# ---------------------------------------------------------------------------

class _CountTab(tk.Frame):
    """Count tokens (word-heuristic and char-based)."""

    def __init__(self, parent: tk.Widget, get_packer) -> None:
        super().__init__(parent, bg=BG)
        self._get_packer = get_packer
        self._build()

    def _build(self) -> None:
        f = _section_frame(self)
        f.pack(fill="both", expand=True, padx=PAD, pady=PAD)

        _label(f, "Input text:").pack(anchor="w")
        self._input = _text_area(f, height=12)
        self._input.pack(fill="both", expand=True, pady=(4, PAD))

        btn_row = tk.Frame(f, bg=PANEL)
        btn_row.pack(fill="x")
        _button(btn_row, "Count tokens", self._run).pack(side="left")

        res = tk.Frame(f, bg=PANEL)
        res.pack(fill="x", pady=(PAD, 0))
        self._word_var = tk.StringVar(value="—")
        self._char_var = tk.StringVar(value="—")
        for lbl, var in [("Word-heuristic (×1.3):", self._word_var),
                         ("Char-based (÷4):", self._char_var)]:
            row = tk.Frame(res, bg=PANEL)
            row.pack(fill="x", pady=2)
            _label(row, lbl, width=24).pack(side="left")
            tk.Label(row, textvariable=var, bg=PANEL, fg=SUCCESS,
                     font=FONT_BOLD).pack(side="left", padx=6)

    def _run(self) -> None:
        cp = self._get_packer()
        text = self._input.get("1.0", "end-1c")
        self._word_var.set(str(cp.count(text)))
        self._char_var.set(str(cp.count_chars(text)))


class _TruncateTab(tk.Frame):
    """Truncate text to a token budget."""

    def __init__(self, parent: tk.Widget, get_packer) -> None:
        super().__init__(parent, bg=BG)
        self._get_packer = get_packer
        self._build()

    def _build(self) -> None:
        f = _section_frame(self)
        f.pack(fill="both", expand=True, padx=PAD, pady=PAD)

        _label(f, "Input text:").pack(anchor="w")
        self._input = _text_area(f, height=8)
        self._input.pack(fill="both", expand=True, pady=(4, PAD))

        ctrl = tk.Frame(f, bg=PANEL)
        ctrl.pack(fill="x", pady=(0, PAD))
        _label(ctrl, "Direction:").pack(side="left")
        self._direction = tk.StringVar(value="end")
        ttk.Radiobutton(ctrl, text="Drop end (keep start)",
                        variable=self._direction, value="end").pack(side="left", padx=8)
        ttk.Radiobutton(ctrl, text="Drop start (keep end)",
                        variable=self._direction, value="start").pack(side="left")

        _button(f, "Truncate", self._run).pack(anchor="w")

        _label(f, "Result:").pack(anchor="w", pady=(PAD, 2))
        self._output = _text_area(f, height=8)
        self._output.config(state="disabled")
        self._output.pack(fill="both", expand=True)
        self._info_var = tk.StringVar()
        tk.Label(f, textvariable=self._info_var, bg=PANEL, fg=FG_DIM,
                 font=FONT_BODY).pack(anchor="w", pady=(4, 0))

    def _run(self) -> None:
        cp = self._get_packer()
        text = self._input.get("1.0", "end-1c")
        result = (cp.truncate_start(text) if self._direction.get() == "start"
                  else cp.truncate(text))
        self._output.config(state="normal")
        self._output.delete("1.0", "end")
        self._output.insert("1.0", result)
        self._output.config(state="disabled")
        self._info_var.set(
            f"Input: {cp.count_chars(text)} tokens  →  "
            f"Output: {cp.count_chars(result)} tokens  "
            f"(budget: {cp.max_tokens})"
        )


class _PackTab(tk.Frame):
    """Join multiple parts within a token budget."""

    def __init__(self, parent: tk.Widget, get_packer) -> None:
        super().__init__(parent, bg=BG)
        self._get_packer = get_packer
        self._parts: List[scrolledtext.ScrolledText] = []
        self._build()

    def _build(self) -> None:
        self._canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(self._canvas, bg=BG)
        self._canvas_window = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>", self._on_frame_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        self._parts_frame = tk.Frame(self._inner, bg=BG)
        self._parts_frame.pack(fill="x", padx=PAD, pady=PAD)

        btn_row = tk.Frame(self._inner, bg=BG)
        btn_row.pack(fill="x", padx=PAD)
        _button(btn_row, "+ Add part", self._add_part).pack(side="left", padx=(0, 8))
        _button(btn_row, "Pack", self._run).pack(side="left")

        f = _section_frame(self._inner)
        f.pack(fill="x", padx=PAD, pady=PAD)
        _label(f, "Result:").pack(anchor="w")
        self._output = _text_area(f, height=7)
        self._output.config(state="disabled")
        self._output.pack(fill="both", expand=True)
        self._info_var = tk.StringVar()
        tk.Label(f, textvariable=self._info_var, bg=PANEL, fg=FG_DIM,
                 font=FONT_BODY).pack(anchor="w", pady=(4, 0))

        self._add_part()
        self._add_part()

    def _on_frame_configure(self, _e=None) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, e) -> None:
        self._canvas.itemconfig(self._canvas_window, width=e.width)

    def _add_part(self) -> None:
        idx = len(self._parts) + 1
        f = _section_frame(self._parts_frame)
        f.pack(fill="x", pady=(0, 8))
        hdr = tk.Frame(f, bg=PANEL)
        hdr.pack(fill="x")
        _label(hdr, f"Part {idx}:", font=FONT_BOLD).pack(side="left")
        ta = _text_area(f, height=4)
        ta.pack(fill="x", pady=(4, 0))
        self._parts.append(ta)

    def _run(self) -> None:
        cp = self._get_packer()
        parts = [ta.get("1.0", "end-1c") for ta in self._parts]
        result = cp.pack(parts)
        self._output.config(state="normal")
        self._output.delete("1.0", "end")
        self._output.insert("1.0", result)
        self._output.config(state="disabled")
        self._info_var.set(
            f"Parts: {len(parts)}  →  "
            f"Output: {cp.count_chars(result)} / {cp.max_tokens} tokens"
        )


class _PackPriorityTab(tk.Frame):
    """Pack parts with numeric priority scores."""

    def __init__(self, parent: tk.Widget, get_packer) -> None:
        super().__init__(parent, bg=BG)
        self._get_packer = get_packer
        self._rows: List[tuple] = []  # (frame, text_widget, priority_var)
        self._build()

    def _build(self) -> None:
        self._canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(self._canvas, bg=BG)
        self._canvas_window = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>", self._on_frame_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        hdr = tk.Frame(self._inner, bg=BG, padx=PAD)
        hdr.pack(fill="x", pady=(PAD, 4))
        _label(hdr, "Add parts with priorities (higher = kept first when over budget):",
               bg=BG, fg=FG_DIM).pack(anchor="w")

        self._rows_frame = tk.Frame(self._inner, bg=BG)
        self._rows_frame.pack(fill="x", padx=PAD)

        btn_row = tk.Frame(self._inner, bg=BG)
        btn_row.pack(fill="x", padx=PAD, pady=(4, 0))
        _button(btn_row, "+ Add part", self._add_row).pack(side="left", padx=(0, 8))
        _button(btn_row, "Pack by priority", self._run).pack(side="left")

        f = _section_frame(self._inner)
        f.pack(fill="x", padx=PAD, pady=PAD)
        _label(f, "Result (in original list order):").pack(anchor="w")
        self._output = _text_area(f, height=7)
        self._output.config(state="disabled")
        self._output.pack(fill="both", expand=True)
        self._info_var = tk.StringVar()
        tk.Label(f, textvariable=self._info_var, bg=PANEL, fg=FG_DIM,
                 font=FONT_BODY).pack(anchor="w", pady=(4, 0))

        self._add_row()
        self._add_row()

    def _on_frame_configure(self, _e=None) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, e) -> None:
        self._canvas.itemconfig(self._canvas_window, width=e.width)

    def _add_row(self) -> None:
        idx = len(self._rows) + 1
        f = _section_frame(self._rows_frame)
        f.pack(fill="x", pady=(0, 6))
        hdr = tk.Frame(f, bg=PANEL)
        hdr.pack(fill="x")
        _label(hdr, f"Part {idx}", font=FONT_BOLD).pack(side="left")
        _label(hdr, "  priority:", bg=PANEL, fg=FG_DIM).pack(side="left")
        pvar = tk.IntVar(value=idx)
        ttk.Spinbox(hdr, textvariable=pvar, from_=0, to=9999, width=6).pack(side="left", padx=4)
        ta = _text_area(f, height=3)
        ta.pack(fill="x", pady=(4, 0))
        self._rows.append((f, ta, pvar))

    def _run(self) -> None:
        cp = self._get_packer()
        parts = [
            {"text": ta.get("1.0", "end-1c"), "priority": pvar.get()}
            for _, ta, pvar in self._rows
        ]
        result = cp.pack_priority(parts)
        self._output.config(state="normal")
        self._output.delete("1.0", "end")
        self._output.insert("1.0", result)
        self._output.config(state="disabled")
        self._info_var.set(
            f"Parts: {len(parts)}  →  "
            f"Output: {cp.count_chars(result)} / {cp.max_tokens} tokens"
        )


class _PackChatTab(tk.Frame):
    """Fit a list of chat messages within the token budget."""

    def __init__(self, parent: tk.Widget, get_packer) -> None:
        super().__init__(parent, bg=BG)
        self._get_packer = get_packer
        self._rows: List[tuple] = []  # (frame, role_var, text_widget)
        self._build()

    def _build(self) -> None:
        self._canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(self._canvas, bg=BG)
        self._canvas_window = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>", self._on_frame_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        hdr = tk.Frame(self._inner, bg=BG, padx=PAD)
        hdr.pack(fill="x", pady=(PAD, 4))
        _label(hdr, "Add chat messages (oldest first). Oldest non-system messages are dropped first.",
               bg=BG, fg=FG_DIM).pack(anchor="w")

        self._rows_frame = tk.Frame(self._inner, bg=BG)
        self._rows_frame.pack(fill="x", padx=PAD)

        ctrl_row = tk.Frame(self._inner, bg=BG)
        ctrl_row.pack(fill="x", padx=PAD, pady=(4, 0))
        _button(ctrl_row, "+ Add message", self._add_row).pack(side="left", padx=(0, 8))
        self._keep_system = tk.BooleanVar(value=True)
        ttk.Checkbutton(ctrl_row, text="Keep system messages",
                        variable=self._keep_system).pack(side="left", padx=8)
        _button(ctrl_row, "Fit to budget", self._run).pack(side="left", padx=8)

        f = _section_frame(self._inner)
        f.pack(fill="x", padx=PAD, pady=PAD)
        _label(f, "Result (JSON):").pack(anchor="w")
        self._output = _text_area(f, height=10)
        self._output.config(state="disabled")
        self._output.pack(fill="both", expand=True)
        self._info_var = tk.StringVar()
        tk.Label(f, textvariable=self._info_var, bg=PANEL, fg=FG_DIM,
                 font=FONT_BODY).pack(anchor="w", pady=(4, 0))

        self._add_row("system", "You are a helpful assistant.")
        self._add_row("user", "Hello!")
        self._add_row("assistant", "Hi there!")

    def _on_frame_configure(self, _e=None) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, e) -> None:
        self._canvas.itemconfig(self._canvas_window, width=e.width)

    def _add_row(self, default_role: str = "user", default_text: str = "") -> None:
        idx = len(self._rows) + 1
        f = _section_frame(self._rows_frame)
        f.pack(fill="x", pady=(0, 6))
        hdr = tk.Frame(f, bg=PANEL)
        hdr.pack(fill="x")
        _label(hdr, f"Message {idx}", font=FONT_BOLD).pack(side="left")
        _label(hdr, "  role:", bg=PANEL, fg=FG_DIM).pack(side="left")
        rvar = tk.StringVar(value=default_role)
        role_cb = ttk.Combobox(hdr, textvariable=rvar,
                               values=["system", "user", "assistant"],
                               width=10, state="readonly")
        role_cb.pack(side="left", padx=4)
        ta = _text_area(f, height=2)
        if default_text:
            ta.insert("1.0", default_text)
        ta.pack(fill="x", pady=(4, 0))
        self._rows.append((f, rvar, ta))

    def _run(self) -> None:
        cp = self._get_packer()
        messages = [
            {"role": rvar.get(), "content": ta.get("1.0", "end-1c")}
            for _, rvar, ta in self._rows
        ]
        result = cp.pack_chat(messages, keep_system=self._keep_system.get())
        self._output.config(state="normal")
        self._output.delete("1.0", "end")
        self._output.insert("1.0", json.dumps(result, indent=2, ensure_ascii=False))
        self._output.config(state="disabled")
        in_tok = sum(cp.count_chars(m["content"]) for m in messages)
        out_tok = sum(cp.count_chars(m["content"]) for m in result)
        self._info_var.set(
            f"Input: {len(messages)} messages ({in_tok} tokens)  →  "
            f"Output: {len(result)} messages ({out_tok} tokens)  "
            f"(budget: {cp.max_tokens})"
        )


class _SplitTab(tk.Frame):
    """Split text into token-bounded chunks."""

    def __init__(self, parent: tk.Widget, get_packer) -> None:
        super().__init__(parent, bg=BG)
        self._get_packer = get_packer
        self._build()

    def _build(self) -> None:
        f = _section_frame(self)
        f.pack(fill="both", expand=True, padx=PAD, pady=PAD)

        _label(f, "Input text:").pack(anchor="w")
        self._input = _text_area(f, height=8)
        self._input.pack(fill="both", expand=True, pady=(4, PAD))

        _button(f, "Split into chunks", self._run).pack(anchor="w")

        _label(f, "Chunks (one per block):").pack(anchor="w", pady=(PAD, 2))
        self._output = _text_area(f, height=10)
        self._output.config(state="disabled")
        self._output.pack(fill="both", expand=True)
        self._info_var = tk.StringVar()
        tk.Label(f, textvariable=self._info_var, bg=PANEL, fg=FG_DIM,
                 font=FONT_BODY).pack(anchor="w", pady=(4, 0))

    def _run(self) -> None:
        cp = self._get_packer()
        text = self._input.get("1.0", "end-1c")
        chunks = cp.split(text)
        separator = "\n" + "─" * 40 + "\n"
        self._output.config(state="normal")
        self._output.delete("1.0", "end")
        self._output.insert("1.0", separator.join(chunks))
        self._output.config(state="disabled")
        self._info_var.set(
            f"{len(chunks)} chunk(s)  ·  max {cp.max_tokens} tokens each  "
            f"(= {cp.max_tokens * CHARS_PER_TOKEN} chars)"
        )


class _SlidingWindowTab(tk.Frame):
    """Select the most-recent parts that fit the budget."""

    def __init__(self, parent: tk.Widget, get_packer) -> None:
        super().__init__(parent, bg=BG)
        self._get_packer = get_packer
        self._parts: List[scrolledtext.ScrolledText] = []
        self._build()

    def _build(self) -> None:
        self._canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(self._canvas, bg=BG)
        self._canvas_window = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>", self._on_frame_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        hdr = tk.Frame(self._inner, bg=BG, padx=PAD)
        hdr.pack(fill="x", pady=(PAD, 4))
        _label(hdr, "Parts (oldest first). The most-recent contiguous suffix that fits is returned.",
               bg=BG, fg=FG_DIM).pack(anchor="w")

        self._parts_frame = tk.Frame(self._inner, bg=BG)
        self._parts_frame.pack(fill="x", padx=PAD)

        btn_row = tk.Frame(self._inner, bg=BG)
        btn_row.pack(fill="x", padx=PAD, pady=(4, 0))
        _button(btn_row, "+ Add part", self._add_part).pack(side="left", padx=(0, 8))
        _button(btn_row, "Apply window", self._run).pack(side="left")

        f = _section_frame(self._inner)
        f.pack(fill="x", padx=PAD, pady=PAD)
        _label(f, "Selected parts (JSON array):").pack(anchor="w")
        self._output = _text_area(f, height=8)
        self._output.config(state="disabled")
        self._output.pack(fill="both", expand=True)
        self._info_var = tk.StringVar()
        tk.Label(f, textvariable=self._info_var, bg=PANEL, fg=FG_DIM,
                 font=FONT_BODY).pack(anchor="w", pady=(4, 0))

        self._add_part()
        self._add_part()
        self._add_part()

    def _on_frame_configure(self, _e=None) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, e) -> None:
        self._canvas.itemconfig(self._canvas_window, width=e.width)

    def _add_part(self) -> None:
        idx = len(self._parts) + 1
        f = _section_frame(self._parts_frame)
        f.pack(fill="x", pady=(0, 6))
        _label(f, f"Part {idx} (oldest → newest):", font=FONT_BOLD).pack(anchor="w")
        ta = _text_area(f, height=3)
        ta.pack(fill="x", pady=(4, 0))
        self._parts.append(ta)

    def _run(self) -> None:
        cp = self._get_packer()
        parts = [ta.get("1.0", "end-1c") for ta in self._parts]
        result = cp.sliding_window(parts)
        self._output.config(state="normal")
        self._output.delete("1.0", "end")
        self._output.insert("1.0", json.dumps(result, indent=2, ensure_ascii=False))
        self._output.config(state="disabled")
        used = sum(cp.count_chars(p) for p in result)
        self._info_var.set(
            f"Selected {len(result)} / {len(parts)} parts  ·  "
            f"{used} / {cp.max_tokens} tokens used"
        )


# ---------------------------------------------------------------------------
# Main application window
# ---------------------------------------------------------------------------

class ContextpackerApp(tk.Tk):
    """Root window for the contextpacker GUI workbench."""

    def __init__(self) -> None:
        super().__init__()
        self.title("contextpacker — context window workbench")
        self.configure(bg=BG)
        self.geometry("860x720")
        self.minsize(640, 480)
        self._build_style()
        self._build_header()
        self._build_settings_bar()
        self._build_notebook()

    # ------------------------------------------------------------------
    # Build helpers
    # ------------------------------------------------------------------

    def _build_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab",
                        background=PANEL, foreground=FG_DIM,
                        padding=[12, 6], font=FONT_BODY)
        style.map("TNotebook.Tab",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", "#ffffff")])
        style.configure("TFrame", background=BG)
        style.configure("TCheckbutton", background=BG, foreground=FG,
                        font=FONT_BODY)
        style.configure("TRadiobutton", background=PANEL, foreground=FG,
                        font=FONT_BODY)
        style.configure("TCombobox", fieldbackground=INPUT_BG, foreground=FG,
                        background=PANEL)
        style.configure("TScrollbar", background=PANEL, troughcolor=BG,
                        arrowcolor=FG_DIM)

    def _build_header(self) -> None:
        hdr = tk.Frame(self, bg=ACCENT, padx=PAD, pady=IPAD)
        hdr.pack(fill="x")
        tk.Label(hdr, text="contextpacker", font=FONT_TITLE,
                 bg=ACCENT, fg="#ffffff").pack(side="left")
        tk.Label(hdr, text="context window workbench",
                 font=FONT_BODY, bg=ACCENT, fg="#ddd6fe").pack(side="left", padx=10)

    def _build_settings_bar(self) -> None:
        bar = tk.Frame(self, bg=PANEL, padx=PAD, pady=IPAD)
        bar.pack(fill="x")

        _label(bar, "max_tokens:", bg=PANEL).pack(side="left")
        self._max_tokens_var = tk.IntVar(value=DEFAULT_MAX_TOKENS)
        _spin(bar, self._max_tokens_var).pack(side="left", padx=(4, 20))

        _label(bar, "separator:", bg=PANEL).pack(side="left")
        self._sep_var = tk.StringVar(value="\\n\\n")
        sep_entry = tk.Entry(
            bar, textvariable=self._sep_var, width=8,
            bg=INPUT_BG, fg=FG, insertbackground=FG,
            relief="flat", highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=ACCENT,
        )
        sep_entry.pack(side="left", padx=(4, 20))

        _button(bar, "Apply", self._apply_settings, pady=3).pack(side="left")
        self._settings_info = tk.StringVar(value="")
        tk.Label(bar, textvariable=self._settings_info, bg=PANEL, fg=SUCCESS,
                 font=FONT_BODY).pack(side="left", padx=10)

    def _build_notebook(self) -> None:
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=0, pady=0)

        tabs = [
            ("Count", _CountTab),
            ("Truncate", _TruncateTab),
            ("Pack", _PackTab),
            ("Pack Priority", _PackPriorityTab),
            ("Pack Chat", _PackChatTab),
            ("Split", _SplitTab),
            ("Sliding Window", _SlidingWindowTab),
        ]
        for title, cls in tabs:
            frame = cls(nb, self._get_packer)
            nb.add(frame, text=f"  {title}  ")

    # ------------------------------------------------------------------
    # Packer factory
    # ------------------------------------------------------------------

    def _get_packer(self) -> Contextpacker:
        try:
            mt = self._max_tokens_var.get()
            sep_raw = self._sep_var.get()
            sep = sep_raw.replace("\\n", "\n").replace("\\t", "\t")
            return Contextpacker(max_tokens=mt, separator=sep)
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror("Invalid settings", str(exc))
            raise

    def _apply_settings(self) -> None:
        try:
            self._get_packer()
            self._settings_info.set("✓ applied")
            self.after(2000, lambda: self._settings_info.set(""))
        except (ValueError, tk.TclError):
            self._settings_info.set("")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Launch the contextpacker GUI workbench."""
    app = ContextpackerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
