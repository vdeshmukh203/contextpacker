"""Tkinter GUI for contextpacker — interactive exploration of packing strategies."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from typing import List, Optional

from .packer import DEFAULT_MAX_TOKENS, Contextpacker


# ---------------------------------------------------------------------------
# Part row widget
# ---------------------------------------------------------------------------

class _PartRow(ttk.Frame):
    """A single input row: text entry + priority spinbox + remove button."""

    def __init__(self, parent: tk.Widget, index: int, remove_cb) -> None:
        super().__init__(parent)
        self._remove_cb = remove_cb

        ttk.Label(self, text=f"Part {index + 1}", width=7, anchor="e").grid(
            row=0, column=0, padx=(0, 4)
        )

        self.text_var = tk.StringVar()
        self._entry = ttk.Entry(self, textvariable=self.text_var)
        self._entry.grid(row=0, column=1, sticky="ew", padx=(0, 6))

        ttk.Label(self, text="Priority").grid(row=0, column=2)
        self.priority_var = tk.IntVar(value=index + 1)
        ttk.Spinbox(
            self,
            textvariable=self.priority_var,
            from_=0,
            to=999,
            width=5,
        ).grid(row=0, column=3, padx=(2, 6))

        ttk.Button(self, text="✕", width=2, command=self._on_remove).grid(
            row=0, column=4
        )
        self.columnconfigure(1, weight=1)

    def _on_remove(self) -> None:
        self._remove_cb(self)

    def relabel(self, index: int) -> None:
        """Update the "Part N" label after sibling rows are removed."""
        for child in self.winfo_children():
            if isinstance(child, ttk.Label) and child.cget("text").startswith("Part"):
                child.config(text=f"Part {index + 1}")
                break


# ---------------------------------------------------------------------------
# Main application window
# ---------------------------------------------------------------------------

class ContextpackerApp(tk.Tk):
    """Main window for the contextpacker interactive GUI.

    Provides a two-panel layout:
    - **Left** — a scrollable list of input parts, each with optional priority.
    - **Right** — output text area with a live token counter.

    Five packing strategies are available via toolbar buttons:
    *Pack*, *Pack Priority*, *Pack Proportional*, *Split*, and *Sliding Window*.
    """

    def __init__(self) -> None:
        super().__init__()
        self.title("contextpacker")
        self.minsize(780, 520)
        self.resizable(True, True)

        self._part_rows: List[_PartRow] = []
        self._build_menu()
        self._build_settings()
        self._build_main()
        self._build_toolbar()
        self._build_statusbar()

        # Seed with two empty parts so the UI is immediately usable.
        self._add_part()
        self._add_part()

    # ------------------------------------------------------------------
    # UI construction helpers
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Clear all parts", command=self._clear_texts)
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.destroy)
        menu.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="About", command=self._show_about)
        menu.add_cascade(label="Help", menu=help_menu)
        self.config(menu=menu)

    def _build_settings(self) -> None:
        bar = ttk.Frame(self, padding=(8, 4))
        bar.pack(fill="x", side="top")

        ttk.Label(bar, text="Max tokens:").pack(side="left")
        self._max_tokens_var = tk.IntVar(value=DEFAULT_MAX_TOKENS)
        ttk.Spinbox(
            bar,
            textvariable=self._max_tokens_var,
            from_=1,
            to=1_000_000,
            width=10,
        ).pack(side="left", padx=(2, 16))

        ttk.Label(bar, text="Separator:").pack(side="left")
        self._sep_var = tk.StringVar(value=r"\n\n")
        ttk.Entry(bar, textvariable=self._sep_var, width=12).pack(
            side="left", padx=(2, 0)
        )

        ttk.Label(bar, text="(use \\n for newline, \\t for tab)").pack(
            side="left", padx=(6, 0)
        )

        ttk.Separator(self, orient="horizontal").pack(fill="x")

    def _build_main(self) -> None:
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=6, pady=6)

        # --- Left: parts panel ---
        left = ttk.Frame(paned, padding=4)
        paned.add(left, weight=1)

        ttk.Label(left, text="Input Parts", font=("", 11, "bold")).pack(anchor="w")

        # Scrollable canvas for an arbitrary number of parts.
        self._canvas = tk.Canvas(left, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            left, orient="vertical", command=self._canvas.yview
        )
        self._canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._canvas.pack(fill="both", expand=True)

        self._parts_frame = ttk.Frame(self._canvas)
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._parts_frame, anchor="nw"
        )
        self._parts_frame.bind("<Configure>", self._on_parts_frame_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        btn_row = ttk.Frame(left)
        btn_row.pack(fill="x", pady=(4, 0))
        ttk.Button(btn_row, text="+ Add part", command=self._add_part).pack(
            side="left"
        )
        ttk.Button(btn_row, text="Clear texts", command=self._clear_texts).pack(
            side="left", padx=4
        )

        # --- Right: output panel ---
        right = ttk.Frame(paned, padding=4)
        paned.add(right, weight=1)

        ttk.Label(right, text="Output", font=("", 11, "bold")).pack(anchor="w")
        self._output = scrolledtext.ScrolledText(
            right, wrap="word", state="disabled", font=("Courier", 10)
        )
        self._output.pack(fill="both", expand=True)

        self._token_label = ttk.Label(right, text="Tokens used: — / —", anchor="e")
        self._token_label.pack(fill="x", pady=(2, 0))

    def _build_toolbar(self) -> None:
        ttk.Separator(self, orient="horizontal").pack(fill="x")
        bar = ttk.Frame(self, padding=(6, 4))
        bar.pack(fill="x")

        strategies = [
            ("Pack", self._run_pack,
             "Join parts with separator, truncate from end"),
            ("Pack Priority", self._run_pack_priority,
             "Keep highest-priority parts; restore original order"),
            ("Pack Proportional", self._run_pack_proportional,
             "Allocate budget proportionally across all parts"),
            ("Split", self._run_split,
             "Split first part into equal-sized chunks"),
            ("Sliding Window", self._run_sliding_window,
             "Keep most-recent contiguous parts that fit"),
        ]

        for label, cmd, tooltip in strategies:
            btn = ttk.Button(bar, text=label, command=cmd)
            btn.pack(side="left", padx=2)
            self._add_tooltip(btn, tooltip)

    def _build_statusbar(self) -> None:
        self._status_var = tk.StringVar(value="Ready — choose a strategy above")
        bar = ttk.Label(
            self,
            textvariable=self._status_var,
            relief="sunken",
            anchor="w",
            padding=(4, 2),
        )
        bar.pack(fill="x", side="bottom")

    # ------------------------------------------------------------------
    # Scrollable canvas bookkeeping
    # ------------------------------------------------------------------

    def _on_parts_frame_configure(self, _event: tk.Event) -> None:  # type: ignore[type-arg]
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        self._canvas.itemconfig(self._canvas_window, width=event.width)

    # ------------------------------------------------------------------
    # Part management
    # ------------------------------------------------------------------

    def _add_part(self) -> None:
        idx = len(self._part_rows)
        row = _PartRow(self._parts_frame, idx, remove_cb=self._remove_part)
        row.pack(fill="x", pady=2, padx=2)
        self._part_rows.append(row)

    def _remove_part(self, row: _PartRow) -> None:
        if len(self._part_rows) <= 1:
            messagebox.showinfo(
                "contextpacker",
                "At least one part must remain.",
                parent=self,
            )
            return
        self._part_rows.remove(row)
        row.destroy()
        for i, r in enumerate(self._part_rows):
            r.relabel(i)

    def _clear_texts(self) -> None:
        for row in self._part_rows:
            row.text_var.set("")
        self._set_output("")
        self._status_var.set("Texts cleared")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_packer(self) -> Contextpacker:
        sep = (
            self._sep_var.get()
            .replace(r"\n", "\n")
            .replace(r"\t", "\t")
        )
        try:
            return Contextpacker(
                max_tokens=self._max_tokens_var.get(),
                separator=sep,
            )
        except ValueError as exc:
            messagebox.showerror("Invalid settings", str(exc), parent=self)
            raise

    def _get_texts(self) -> List[str]:
        return [r.text_var.get() for r in self._part_rows]

    def _get_priority_parts(self) -> List[dict]:
        return [
            {"text": r.text_var.get(), "priority": r.priority_var.get()}
            for r in self._part_rows
        ]

    def _set_output(self, text: str, cp: Optional[Contextpacker] = None) -> None:
        self._output.config(state="normal")
        self._output.delete("1.0", "end")
        self._output.insert("end", text)
        self._output.config(state="disabled")
        if cp is not None and text:
            used = cp.count(text)
            limit = cp.max_tokens
            pct = min(100, round(used / limit * 100))
            self._token_label.config(
                text=f"Tokens used: {used:,} / {limit:,}  ({pct}%)"
            )
        elif not text:
            self._token_label.config(text="Tokens used: 0 / —")

    @staticmethod
    def _add_tooltip(widget: tk.Widget, text: str) -> None:
        tip: Optional[tk.Toplevel] = None

        def show(_event: tk.Event) -> None:  # type: ignore[type-arg]
            nonlocal tip
            x = widget.winfo_rootx() + 20
            y = widget.winfo_rooty() + widget.winfo_height() + 4
            tip = tk.Toplevel(widget)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{x}+{y}")
            tk.Label(
                tip,
                text=text,
                background="#ffffe0",
                relief="solid",
                borderwidth=1,
                font=("", 9),
                padx=4,
                pady=2,
            ).pack()

        def hide(_event: tk.Event) -> None:  # type: ignore[type-arg]
            nonlocal tip
            if tip:
                tip.destroy()
                tip = None

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)

    # ------------------------------------------------------------------
    # Strategy runners
    # ------------------------------------------------------------------

    def _run_pack(self) -> None:
        try:
            cp = self._make_packer()
        except ValueError:
            return
        result = cp.pack(self._get_texts())
        self._set_output(result, cp)
        self._status_var.set(
            f"Pack — {cp.count(result):,} tokens used of {cp.max_tokens:,}"
        )

    def _run_pack_priority(self) -> None:
        try:
            cp = self._make_packer()
        except ValueError:
            return
        result = cp.pack_priority(self._get_priority_parts())
        self._set_output(result, cp)
        self._status_var.set(
            f"Pack Priority — {cp.count(result):,} tokens used of {cp.max_tokens:,}"
        )

    def _run_pack_proportional(self) -> None:
        try:
            cp = self._make_packer()
        except ValueError:
            return
        result = cp.pack_proportional(self._get_texts())
        self._set_output(result, cp)
        self._status_var.set(
            f"Pack Proportional — {cp.count(result):,} tokens"
            f" used of {cp.max_tokens:,}"
        )

    def _run_split(self) -> None:
        try:
            cp = self._make_packer()
        except ValueError:
            return
        texts = [t for t in self._get_texts() if t]
        if not texts:
            messagebox.showinfo(
                "contextpacker",
                "Enter text in at least one part before splitting.",
                parent=self,
            )
            return
        combined = cp.separator.join(texts)
        chunks = cp.split(combined)
        annotated = "\n".join(
            f"── Chunk {i + 1} / {len(chunks)} ──\n{c}" for i, c in enumerate(chunks)
        )
        self._set_output(annotated, cp)
        self._status_var.set(f"Split — {len(chunks)} chunk(s)")

    def _run_sliding_window(self) -> None:
        try:
            cp = self._make_packer()
        except ValueError:
            return
        texts = self._get_texts()
        kept = cp.sliding_window(texts)
        result = cp.separator.join(kept)
        self._set_output(result, cp)
        self._status_var.set(
            f"Sliding Window — {len(kept)} / {len(texts)} part(s) fit"
        )

    # ------------------------------------------------------------------
    # Help
    # ------------------------------------------------------------------

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About contextpacker",
            (
                "contextpacker\n\n"
                "Interactive explorer for LLM context-window packing strategies.\n\n"
                "Strategies:\n"
                "  Pack              — join & truncate from end\n"
                "  Pack Priority     — keep highest-priority parts\n"
                "  Pack Proportional — allocate budget proportionally\n"
                "  Split             — divide text into equal chunks\n"
                "  Sliding Window    — keep most-recent contiguous parts\n\n"
                "Priority values are only used by Pack Priority."
            ),
            parent=self,
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def launch() -> None:
    """Launch the contextpacker GUI application."""
    app = ContextpackerApp()
    app.mainloop()


if __name__ == "__main__":
    launch()
