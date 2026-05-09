"""Tkinter GUI for contextpacker — interactive context-window management."""
from __future__ import annotations

import json
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk
from typing import List

from contextpacker.packer import CHARS_PER_TOKEN, DEFAULT_MAX_TOKENS, Contextpacker


# ---------------------------------------------------------------------------
# Palette & sizing
# ---------------------------------------------------------------------------

_BG = "#1e1e2e"
_FG = "#cdd6f4"
_ACCENT = "#89b4fa"
_SURFACE = "#313244"
_SURFACE2 = "#45475a"
_GREEN = "#a6e3a1"
_RED = "#f38ba8"
_YELLOW = "#f9e2af"
_ENTRY_BG = "#181825"
_FONT_MONO = ("Courier New", 10)
_FONT_LABEL = ("Helvetica", 10)
_FONT_BOLD = ("Helvetica", 10, "bold")
_FONT_TITLE = ("Helvetica", 12, "bold")
_PAD = 8


def _configure_styles(root: tk.Tk) -> None:
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TFrame", background=_BG)
    style.configure("TLabel", background=_BG, foreground=_FG, font=_FONT_LABEL)
    style.configure("TLabelFrame", background=_BG, foreground=_ACCENT, font=_FONT_BOLD)
    style.configure("TLabelFrame.Label", background=_BG, foreground=_ACCENT)
    style.configure(
        "TNotebook", background=_BG, tabmargins=[2, 5, 2, 0]
    )
    style.configure(
        "TNotebook.Tab",
        background=_SURFACE,
        foreground=_FG,
        padding=[12, 4],
        font=_FONT_BOLD,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", _ACCENT)],
        foreground=[("selected", _BG)],
    )
    style.configure(
        "TButton",
        background=_ACCENT,
        foreground=_BG,
        font=_FONT_BOLD,
        padding=[10, 4],
        relief="flat",
    )
    style.map("TButton", background=[("active", _GREEN)])
    style.configure("TCheckbutton", background=_BG, foreground=_FG, font=_FONT_LABEL)
    style.configure("TSpinbox", fieldbackground=_ENTRY_BG, foreground=_FG, font=_FONT_MONO)
    style.configure(
        "TCombobox", fieldbackground=_ENTRY_BG, foreground=_FG, font=_FONT_MONO
    )
    style.configure("Horizontal.TProgressbar", troughcolor=_SURFACE, background=_ACCENT)
    style.configure("Red.Horizontal.TProgressbar", troughcolor=_SURFACE, background=_RED)
    style.configure(
        "Status.TLabel",
        background=_SURFACE2,
        foreground=_FG,
        font=_FONT_LABEL,
        padding=[6, 2],
    )


def _make_text(parent: tk.Widget, height: int = 8, readonly: bool = False) -> tk.Text:
    t = tk.Text(
        parent,
        height=height,
        wrap="word",
        font=_FONT_MONO,
        bg=_ENTRY_BG,
        fg=_FG,
        insertbackground=_ACCENT,
        selectbackground=_ACCENT,
        selectforeground=_BG,
        relief="flat",
        padx=6,
        pady=4,
        undo=True,
    )
    if readonly:
        t.config(state="disabled", fg=_GREEN)
    sb = ttk.Scrollbar(parent, orient="vertical", command=t.yview)
    t.configure(yscrollcommand=sb.set)
    t.grid(sticky="nsew")
    sb.grid(row=0, column=1, sticky="ns")
    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(0, weight=1)
    return t


def _get_text(widget: tk.Text) -> str:
    return widget.get("1.0", "end-1c")


def _set_text(widget: tk.Text, content: str, readonly: bool = False) -> None:
    if readonly:
        widget.config(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", content)
    if readonly:
        widget.config(state="disabled")


# ---------------------------------------------------------------------------
# Shared settings bar
# ---------------------------------------------------------------------------

class SettingsBar(ttk.Frame):
    """Top bar: max_tokens spinner + separator combo, shared by all tabs."""

    _SEPARATOR_OPTIONS = {
        "Double newline (\\n\\n)": "\n\n",
        "Single newline (\\n)": "\n",
        "Dash rule (---)": "---",
        "Pipe ( | )": " | ",
        "Space": " ",
    }

    def __init__(self, master: tk.Widget) -> None:
        super().__init__(master)
        self.configure(style="TFrame")

        ttk.Label(self, text="Max tokens:").pack(side="left", padx=(_PAD, 2))
        self._tokens_var = tk.IntVar(value=DEFAULT_MAX_TOKENS)
        sb = ttk.Spinbox(
            self,
            from_=1,
            to=1_000_000,
            textvariable=self._tokens_var,
            width=9,
            font=_FONT_MONO,
        )
        sb.pack(side="left", padx=(0, _PAD))

        ttk.Label(self, text="Separator:").pack(side="left", padx=(0, 2))
        self._sep_label_var = tk.StringVar(value="Double newline (\\n\\n)")
        sep_combo = ttk.Combobox(
            self,
            textvariable=self._sep_label_var,
            values=list(self._SEPARATOR_OPTIONS),
            state="readonly",
            width=22,
        )
        sep_combo.pack(side="left", padx=(0, _PAD))

    def get_packer(self) -> Contextpacker:
        sep = self._SEPARATOR_OPTIONS.get(self._sep_label_var.get(), "\n\n")
        max_tok = max(1, self._tokens_var.get())
        return Contextpacker(max_tokens=max_tok, separator=sep)

    def max_tokens(self) -> int:
        return max(1, self._tokens_var.get())


# ---------------------------------------------------------------------------
# Token budget bar
# ---------------------------------------------------------------------------

class BudgetBar(ttk.Frame):
    """Progress bar + label showing token usage vs budget."""

    def __init__(self, master: tk.Widget, settings: SettingsBar) -> None:
        super().__init__(master)
        self._settings = settings
        self._bar_var = tk.IntVar(value=0)
        self._label_var = tk.StringVar(value="0 / — tokens")
        self._bar = ttk.Progressbar(
            self,
            orient="horizontal",
            mode="determinate",
            variable=self._bar_var,
            maximum=100,
            style="Horizontal.TProgressbar",
        )
        self._bar.pack(fill="x", side="left", expand=True, padx=(_PAD, 4))
        ttk.Label(self, textvariable=self._label_var, style="Status.TLabel").pack(
            side="left", padx=(0, _PAD)
        )

    def update(self, used_chars: int) -> None:
        limit = self._settings.max_tokens()
        used_tokens = used_chars // CHARS_PER_TOKEN
        pct = min(100, int(used_tokens / limit * 100)) if limit > 0 else 0
        self._bar_var.set(pct)
        self._label_var.set(f"{used_tokens:,} / {limit:,} tokens  ({pct}%)")
        style = "Red.Horizontal.TProgressbar" if pct >= 90 else "Horizontal.TProgressbar"
        self._bar.configure(style=style)


# ---------------------------------------------------------------------------
# Tab 1 — Truncate
# ---------------------------------------------------------------------------

class TruncateTab(ttk.Frame):
    def __init__(self, master: tk.Widget, settings: SettingsBar) -> None:
        super().__init__(master)
        self._settings = settings
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(4, weight=1)

        # Controls
        ctrl = ttk.Frame(self)
        ctrl.grid(row=0, column=0, sticky="ew", padx=_PAD, pady=(_PAD, 0))
        self._mode = tk.StringVar(value="keep_start")
        ttk.Radiobutton(ctrl, text="Keep beginning", variable=self._mode,
                        value="keep_start").pack(side="left", padx=4)
        ttk.Radiobutton(ctrl, text="Keep end (drop oldest)", variable=self._mode,
                        value="keep_end").pack(side="left", padx=4)
        ttk.Button(ctrl, text="Truncate →", command=self._run).pack(side="right", padx=4)

        # Input
        ttk.Label(self, text="Input text").grid(row=1, column=0, sticky="w",
                                                padx=_PAD, pady=(4, 0))
        in_frame = ttk.Frame(self)
        in_frame.grid(row=2, column=0, sticky="nsew", padx=_PAD, pady=(0, 4))
        in_frame.columnconfigure(0, weight=1)
        in_frame.rowconfigure(0, weight=1)
        self._input = _make_text(in_frame)

        # Budget bar
        self._budget = BudgetBar(self, settings)
        self._budget.grid(row=3, column=0, sticky="ew", padx=_PAD, pady=2)
        self._input.bind("<KeyRelease>", self._on_key)

        # Output
        ttk.Label(self, text="Truncated output").grid(row=4, column=0, sticky="w",
                                                      padx=_PAD, pady=(4, 0))
        out_frame = ttk.Frame(self)
        out_frame.grid(row=5, column=0, sticky="nsew", padx=_PAD, pady=(0, _PAD))
        out_frame.columnconfigure(0, weight=1)
        out_frame.rowconfigure(0, weight=1)
        self._output = _make_text(out_frame, readonly=True)

        self.rowconfigure(2, weight=3)
        self.rowconfigure(5, weight=2)

    def _on_key(self, _event=None) -> None:
        self._budget.update(len(_get_text(self._input)))

    def _run(self) -> None:
        cp = self._settings.get_packer()
        text = _get_text(self._input)
        if self._mode.get() == "keep_start":
            result = cp.truncate(text)
        else:
            result = cp.truncate_start(text)
        _set_text(self._output, result, readonly=True)
        self._budget.update(len(result))


# ---------------------------------------------------------------------------
# Tab 2 — Pack
# ---------------------------------------------------------------------------

class PackTab(ttk.Frame):
    def __init__(self, master: tk.Widget, settings: SettingsBar) -> None:
        super().__init__(master)
        self._settings = settings
        self._parts: List[tk.Text] = []
        self.columnconfigure(0, weight=1)

        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.grid(row=0, column=0, sticky="ew", padx=_PAD, pady=(_PAD, 0))
        ttk.Button(toolbar, text="+ Add part", command=self._add_part).pack(
            side="left", padx=2)
        ttk.Button(toolbar, text="- Remove last", command=self._remove_part).pack(
            side="left", padx=2)
        ttk.Button(toolbar, text="Pack →", command=self._run).pack(side="right", padx=2)

        # Parts container (scrollable)
        self._parts_frame = ttk.LabelFrame(self, text="Parts  (top → bottom order)")
        self._parts_frame.grid(row=1, column=0, sticky="nsew", padx=_PAD, pady=4)
        self._parts_frame.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=3)

        self._add_part()
        self._add_part()

        # Budget
        self._budget = BudgetBar(self, settings)
        self._budget.grid(row=2, column=0, sticky="ew", padx=_PAD, pady=2)

        # Output
        ttk.Label(self, text="Packed output").grid(row=3, column=0, sticky="w",
                                                   padx=_PAD)
        out_frame = ttk.Frame(self)
        out_frame.grid(row=4, column=0, sticky="nsew", padx=_PAD, pady=(0, _PAD))
        out_frame.columnconfigure(0, weight=1)
        out_frame.rowconfigure(0, weight=1)
        self._output = _make_text(out_frame, height=6, readonly=True)
        self.rowconfigure(4, weight=2)

    def _add_part(self) -> None:
        idx = len(self._parts) + 1
        lf = ttk.LabelFrame(self._parts_frame, text=f"Part {idx}")
        lf.grid(row=idx - 1, column=0, sticky="ew", padx=4, pady=2)
        lf.columnconfigure(0, weight=1)
        lf.rowconfigure(0, weight=1)
        t = _make_text(lf, height=3)
        self._parts.append(t)
        self._parts_frame.rowconfigure(idx - 1, weight=1)

    def _remove_part(self) -> None:
        if len(self._parts) <= 1:
            return
        widget = self._parts.pop()
        widget.master.master.destroy()  # LabelFrame > grid cell

    def _run(self) -> None:
        cp = self._settings.get_packer()
        parts = [_get_text(t) for t in self._parts]
        result = cp.pack(parts)
        _set_text(self._output, result, readonly=True)
        self._budget.update(len(result))


# ---------------------------------------------------------------------------
# Tab 3 — Pack Priority
# ---------------------------------------------------------------------------

class PriorityRow(ttk.Frame):
    """Single priority-part row: priority spinner + text entry."""

    def __init__(self, master: tk.Widget, index: int) -> None:
        super().__init__(master)
        self.columnconfigure(1, weight=1)
        ttk.Label(self, text=f"Priority:").grid(row=0, column=0, sticky="w", padx=(4, 2))
        self._priority = tk.IntVar(value=1)
        ttk.Spinbox(self, from_=0, to=999, textvariable=self._priority,
                    width=5).grid(row=0, column=1, sticky="w", padx=(0, _PAD))
        ttk.Label(self, text=f"Part {index}:").grid(row=1, column=0, sticky="nw",
                                                    padx=(4, 2), pady=2)
        self._text = tk.Text(
            self, height=2, font=_FONT_MONO,
            bg=_ENTRY_BG, fg=_FG, insertbackground=_ACCENT, relief="flat",
            padx=4, pady=4,
        )
        self._text.grid(row=1, column=1, sticky="ew", padx=(0, 4), pady=(0, 4))

    def get_part(self) -> dict:
        return {"text": _get_text(self._text), "priority": self._priority.get()}


class PackPriorityTab(ttk.Frame):
    def __init__(self, master: tk.Widget, settings: SettingsBar) -> None:
        super().__init__(master)
        self._settings = settings
        self._rows: List[PriorityRow] = []
        self.columnconfigure(0, weight=1)

        toolbar = ttk.Frame(self)
        toolbar.grid(row=0, column=0, sticky="ew", padx=_PAD, pady=(_PAD, 0))
        ttk.Button(toolbar, text="+ Add part", command=self._add_row).pack(
            side="left", padx=2)
        ttk.Button(toolbar, text="- Remove last", command=self._remove_row).pack(
            side="left", padx=2)
        ttk.Button(toolbar, text="Pack Priority →", command=self._run).pack(
            side="right", padx=2)

        self._container = ttk.LabelFrame(self, text="Parts with priority scores")
        self._container.grid(row=1, column=0, sticky="nsew", padx=_PAD, pady=4)
        self._container.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=3)

        self._add_row()
        self._add_row()

        self._budget = BudgetBar(self, settings)
        self._budget.grid(row=2, column=0, sticky="ew", padx=_PAD, pady=2)

        ttk.Label(self, text="Packed output (highest priority first)").grid(
            row=3, column=0, sticky="w", padx=_PAD)
        out_frame = ttk.Frame(self)
        out_frame.grid(row=4, column=0, sticky="nsew", padx=_PAD, pady=(0, _PAD))
        out_frame.columnconfigure(0, weight=1)
        out_frame.rowconfigure(0, weight=1)
        self._output = _make_text(out_frame, height=6, readonly=True)
        self.rowconfigure(4, weight=2)

    def _add_row(self) -> None:
        row = PriorityRow(self._container, len(self._rows) + 1)
        row.grid(row=len(self._rows), column=0, sticky="ew", padx=4, pady=2)
        self._rows.append(row)
        self._container.rowconfigure(len(self._rows) - 1, weight=1)

    def _remove_row(self) -> None:
        if len(self._rows) <= 1:
            return
        row = self._rows.pop()
        row.destroy()

    def _run(self) -> None:
        cp = self._settings.get_packer()
        parts = [r.get_part() for r in self._rows]
        result = cp.pack_priority(parts)
        _set_text(self._output, result, readonly=True)
        self._budget.update(len(result))


# ---------------------------------------------------------------------------
# Tab 4 — Pack Chat
# ---------------------------------------------------------------------------

class ChatMessageRow(ttk.Frame):
    """Single chat message: role selector + content entry."""

    _ROLES = ["user", "assistant", "system"]

    def __init__(self, master: tk.Widget, index: int) -> None:
        super().__init__(master)
        self.columnconfigure(1, weight=1)
        ttk.Label(self, text=f"#{index} Role:").grid(row=0, column=0, sticky="w",
                                                     padx=(4, 2))
        self._role = tk.StringVar(value="user")
        ttk.Combobox(
            self, textvariable=self._role, values=self._ROLES,
            state="readonly", width=10,
        ).grid(row=0, column=1, sticky="w", padx=(0, _PAD))
        ttk.Label(self, text="Content:").grid(row=1, column=0, sticky="nw",
                                              padx=(4, 2), pady=2)
        self._content = tk.Text(
            self, height=2, font=_FONT_MONO, bg=_ENTRY_BG, fg=_FG,
            insertbackground=_ACCENT, relief="flat", padx=4, pady=4,
        )
        self._content.grid(row=1, column=1, sticky="ew", padx=(0, 4), pady=(0, 4))

    def get_message(self) -> dict:
        return {"role": self._role.get(), "content": _get_text(self._content)}


class PackChatTab(ttk.Frame):
    def __init__(self, master: tk.Widget, settings: SettingsBar) -> None:
        super().__init__(master)
        self._settings = settings
        self._rows: List[ChatMessageRow] = []
        self.columnconfigure(0, weight=1)

        toolbar = ttk.Frame(self)
        toolbar.grid(row=0, column=0, sticky="ew", padx=_PAD, pady=(_PAD, 0))
        ttk.Button(toolbar, text="+ Add message", command=self._add_row).pack(
            side="left", padx=2)
        ttk.Button(toolbar, text="- Remove last", command=self._remove_row).pack(
            side="left", padx=2)
        self._keep_system = tk.BooleanVar(value=True)
        ttk.Checkbutton(toolbar, text="Keep system messages",
                        variable=self._keep_system).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Pack Chat →", command=self._run).pack(
            side="right", padx=2)

        self._container = ttk.LabelFrame(self, text="Chat messages  (oldest → newest)")
        self._container.grid(row=1, column=0, sticky="nsew", padx=_PAD, pady=4)
        self._container.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=3)

        self._add_row()
        self._add_row()

        self._budget = BudgetBar(self, settings)
        self._budget.grid(row=2, column=0, sticky="ew", padx=_PAD, pady=2)

        ttk.Label(self, text="Retained messages (JSON)").grid(
            row=3, column=0, sticky="w", padx=_PAD)
        out_frame = ttk.Frame(self)
        out_frame.grid(row=4, column=0, sticky="nsew", padx=_PAD, pady=(0, _PAD))
        out_frame.columnconfigure(0, weight=1)
        out_frame.rowconfigure(0, weight=1)
        self._output = _make_text(out_frame, height=8, readonly=True)
        self.rowconfigure(4, weight=2)

    def _add_row(self) -> None:
        row = ChatMessageRow(self._container, len(self._rows) + 1)
        row.grid(row=len(self._rows), column=0, sticky="ew", padx=4, pady=2)
        self._rows.append(row)
        self._container.rowconfigure(len(self._rows) - 1, weight=1)

    def _remove_row(self) -> None:
        if len(self._rows) <= 1:
            return
        row = self._rows.pop()
        row.destroy()

    def _run(self) -> None:
        cp = self._settings.get_packer()
        messages = [r.get_message() for r in self._rows]
        kept = cp.pack_chat(messages, keep_system=self._keep_system.get())
        result = json.dumps(kept, indent=2, ensure_ascii=False)
        _set_text(self._output, result, readonly=True)
        total_chars = sum(len(m.get("content", "")) for m in kept)
        self._budget.update(total_chars)


# ---------------------------------------------------------------------------
# Tab 5 — Split
# ---------------------------------------------------------------------------

class SplitTab(ttk.Frame):
    def __init__(self, master: tk.Widget, settings: SettingsBar) -> None:
        super().__init__(master)
        self._settings = settings
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=3)
        self.rowconfigure(4, weight=2)

        ctrl = ttk.Frame(self)
        ctrl.grid(row=0, column=0, sticky="ew", padx=_PAD, pady=(_PAD, 0))
        ttk.Button(ctrl, text="Split →", command=self._run).pack(side="right", padx=2)

        ttk.Label(self, text="Input text").grid(row=1, column=0, sticky="w",
                                                padx=_PAD, pady=(4, 0))
        in_frame = ttk.Frame(self)
        in_frame.grid(row=2, column=0, sticky="nsew", padx=_PAD, pady=(0, 4))
        in_frame.columnconfigure(0, weight=1)
        in_frame.rowconfigure(0, weight=1)
        self._input = _make_text(in_frame)

        self._budget = BudgetBar(self, settings)
        self._budget.grid(row=3, column=0, sticky="ew", padx=_PAD, pady=2)
        self._input.bind("<KeyRelease>", self._on_key)

        self._chunk_label = tk.StringVar(value="Chunks: 0")
        ttk.Label(self, textvariable=self._chunk_label).grid(
            row=4, column=0, sticky="w", padx=_PAD, pady=(4, 0))
        out_frame = ttk.Frame(self)
        out_frame.grid(row=5, column=0, sticky="nsew", padx=_PAD, pady=(0, _PAD))
        out_frame.columnconfigure(0, weight=1)
        out_frame.rowconfigure(0, weight=1)
        self._output = _make_text(out_frame, height=10, readonly=True)
        self.rowconfigure(5, weight=2)

    def _on_key(self, _event=None) -> None:
        self._budget.update(len(_get_text(self._input)))

    def _run(self) -> None:
        cp = self._settings.get_packer()
        text = _get_text(self._input)
        chunks = cp.split(text)
        self._chunk_label.set(f"Chunks: {len(chunks)}")
        output_lines = []
        for i, chunk in enumerate(chunks, 1):
            tokens = cp.count_chars(chunk)
            output_lines.append(f"─── Chunk {i}  ({tokens} tokens) ───")
            output_lines.append(chunk)
            output_lines.append("")
        _set_text(self._output, "\n".join(output_lines), readonly=True)
        self._budget.update(len(text))


# ---------------------------------------------------------------------------
# Tab 6 — Sliding Window
# ---------------------------------------------------------------------------

class SlidingWindowTab(ttk.Frame):
    def __init__(self, master: tk.Widget, settings: SettingsBar) -> None:
        super().__init__(master)
        self._settings = settings
        self._parts: List[tk.Text] = []
        self.columnconfigure(0, weight=1)

        toolbar = ttk.Frame(self)
        toolbar.grid(row=0, column=0, sticky="ew", padx=_PAD, pady=(_PAD, 0))
        ttk.Button(toolbar, text="+ Add part", command=self._add_part).pack(
            side="left", padx=2)
        ttk.Button(toolbar, text="- Remove last", command=self._remove_part).pack(
            side="left", padx=2)
        ttk.Button(toolbar, text="Slide →", command=self._run).pack(
            side="right", padx=2)

        self._container = ttk.LabelFrame(
            self, text="Parts  (oldest → newest, newest kept first)")
        self._container.grid(row=1, column=0, sticky="nsew", padx=_PAD, pady=4)
        self._container.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=3)

        for _ in range(3):
            self._add_part()

        self._budget = BudgetBar(self, settings)
        self._budget.grid(row=2, column=0, sticky="ew", padx=_PAD, pady=2)

        self._kept_label = tk.StringVar(value="Kept: 0 / 0 parts")
        ttk.Label(self, textvariable=self._kept_label).grid(
            row=3, column=0, sticky="w", padx=_PAD, pady=(4, 0))
        out_frame = ttk.Frame(self)
        out_frame.grid(row=4, column=0, sticky="nsew", padx=_PAD, pady=(0, _PAD))
        out_frame.columnconfigure(0, weight=1)
        out_frame.rowconfigure(0, weight=1)
        self._output = _make_text(out_frame, height=8, readonly=True)
        self.rowconfigure(4, weight=2)

    def _add_part(self) -> None:
        idx = len(self._parts) + 1
        lf = ttk.LabelFrame(self._container, text=f"Part {idx}")
        lf.grid(row=idx - 1, column=0, sticky="ew", padx=4, pady=2)
        lf.columnconfigure(0, weight=1)
        lf.rowconfigure(0, weight=1)
        t = _make_text(lf, height=2)
        self._parts.append(t)
        self._container.rowconfigure(idx - 1, weight=1)

    def _remove_part(self) -> None:
        if len(self._parts) <= 1:
            return
        widget = self._parts.pop()
        widget.master.master.destroy()

    def _run(self) -> None:
        cp = self._settings.get_packer()
        parts = [_get_text(t) for t in self._parts]
        kept = cp.sliding_window(parts)
        self._kept_label.set(f"Kept: {len(kept)} / {len(parts)} parts")
        output_lines = []
        for i, part in enumerate(kept, 1):
            tokens = cp.count_chars(part)
            output_lines.append(f"─── Part {i}  ({tokens} tokens) ───")
            output_lines.append(part)
            output_lines.append("")
        _set_text(self._output, "\n".join(output_lines), readonly=True)
        total_chars = sum(len(p) for p in kept)
        self._budget.update(total_chars)


# ---------------------------------------------------------------------------
# Token counter tab
# ---------------------------------------------------------------------------

class CounterTab(ttk.Frame):
    def __init__(self, master: tk.Widget, settings: SettingsBar) -> None:
        super().__init__(master)
        self._settings = settings
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        ctrl = ttk.Frame(self)
        ctrl.grid(row=0, column=0, sticky="ew", padx=_PAD, pady=(_PAD, 0))
        ttk.Label(ctrl, text="Live token estimates as you type",
                  font=_FONT_BOLD).pack(side="left")

        in_frame = ttk.Frame(self)
        in_frame.grid(row=1, column=0, sticky="nsew", padx=_PAD, pady=4)
        in_frame.columnconfigure(0, weight=1)
        in_frame.rowconfigure(0, weight=1)
        self._text = _make_text(in_frame, height=14)
        self._text.bind("<KeyRelease>", self._on_key)

        stats_frame = ttk.LabelFrame(self, text="Estimates")
        stats_frame.grid(row=2, column=0, sticky="ew", padx=_PAD, pady=(0, _PAD))
        for col in range(4):
            stats_frame.columnconfigure(col, weight=1)

        self._chars_var = tk.StringVar(value="—")
        self._words_var = tk.StringVar(value="—")
        self._word_tok_var = tk.StringVar(value="—")
        self._char_tok_var = tk.StringVar(value="—")
        self._budget_var = tk.StringVar(value="—")

        def _stat(label: str, var: tk.StringVar, col: int, color: str = _FG) -> None:
            f = ttk.Frame(stats_frame)
            f.grid(row=0, column=col, padx=8, pady=8, sticky="nsew")
            tk.Label(f, text=label, font=_FONT_LABEL, bg=_BG, fg=_ACCENT).pack()
            tk.Label(f, textvariable=var, font=("Helvetica", 16, "bold"),
                     bg=_BG, fg=color).pack()

        _stat("Characters", self._chars_var, 0)
        _stat("Words", self._words_var, 1)
        _stat("Tokens (word)", self._word_tok_var, 2, _YELLOW)
        _stat("Tokens (char)", self._char_tok_var, 3, _GREEN)

        self._budget = BudgetBar(self, settings)
        self._budget.grid(row=3, column=0, sticky="ew", padx=_PAD, pady=(0, _PAD))

    def _on_key(self, _event=None) -> None:
        cp = self._settings.get_packer()
        text = _get_text(self._text)
        chars = len(text)
        words = len(text.split())
        word_tok = cp.count(text)
        char_tok = cp.count_chars(text)
        self._chars_var.set(f"{chars:,}")
        self._words_var.set(f"{words:,}")
        self._word_tok_var.set(f"{word_tok:,}")
        self._char_tok_var.set(f"{char_tok:,}")
        self._budget.update(chars)


# ---------------------------------------------------------------------------
# Main application window
# ---------------------------------------------------------------------------

class ContextpackerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("contextpacker — Context Window Manager")
        self.geometry("880x700")
        self.minsize(700, 540)
        self.configure(bg=_BG)

        _configure_styles(self)

        # Header
        header = tk.Frame(self, bg=_SURFACE, pady=6)
        header.pack(fill="x")
        tk.Label(
            header,
            text="contextpacker",
            font=("Helvetica", 16, "bold"),
            bg=_SURFACE,
            fg=_ACCENT,
        ).pack(side="left", padx=_PAD)
        tk.Label(
            header,
            text="Token-aware packing & truncation for LLM context windows",
            font=_FONT_LABEL,
            bg=_SURFACE,
            fg=_FG,
        ).pack(side="left")

        # Settings bar
        self._settings = SettingsBar(self)
        self._settings.pack(fill="x", padx=_PAD, pady=4)

        ttk.Separator(self).pack(fill="x", padx=_PAD)

        # Notebook
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=_PAD, pady=4)

        tabs = [
            ("Counter", CounterTab),
            ("Truncate", TruncateTab),
            ("Pack", PackTab),
            ("Pack Priority", PackPriorityTab),
            ("Pack Chat", PackChatTab),
            ("Split", SplitTab),
            ("Sliding Window", SlidingWindowTab),
        ]
        for label, cls in tabs:
            frame = cls(nb, self._settings)
            nb.add(frame, text=label)

        # Status bar
        status = tk.Frame(self, bg=_SURFACE2, pady=2)
        status.pack(fill="x", side="bottom")
        tk.Label(
            status,
            text="contextpacker v0.1.0  |  MIT License",
            font=_FONT_LABEL,
            bg=_SURFACE2,
            fg=_SURFACE,
        ).pack(side="right", padx=_PAD)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Launch the contextpacker GUI."""
    app = ContextpackerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
