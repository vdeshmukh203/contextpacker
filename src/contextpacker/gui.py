"""Tkinter GUI for contextpacker — interactive context window explorer."""
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from contextpacker import Contextpacker, __version__

# ── colour palette (light mode, high-contrast status colours) ──────────────
_KEPT_BG = "#d4edda"    # green tint  — kept / included
_DROP_BG = "#f8d7da"    # red tint    — dropped / excluded
_CHUNK_BG = "#cce5ff"   # blue tint   — chunk separator


def _unescape(s: str) -> str:
    """Expand \\n and \\t escape sequences in separator strings."""
    return s.replace("\\n", "\n").replace("\\t", "\t")


class _TextOutput(scrolledtext.ScrolledText):
    """Read-only ScrolledText with a helper to replace its contents."""

    def __init__(self, parent: tk.Widget, **kwargs: object) -> None:
        super().__init__(parent, state=tk.DISABLED, **kwargs)  # type: ignore[arg-type]

    def set(self, text: str) -> None:
        self.config(state=tk.NORMAL)
        self.delete("1.0", tk.END)
        self.insert(tk.END, text)
        self.config(state=tk.DISABLED)


# ── main application ────────────────────────────────────────────────────────

class ContextpackerGUI:
    """Top-level GUI window for contextpacker."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("contextpacker")
        self.root.minsize(820, 640)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        self._build_menu()
        self._build_config_bar()
        self._build_notebook()
        self._build_status_bar()

    # ── menu ────────────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Quit", accelerator="Ctrl+Q",
                              command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        self.root.bind_all("<Control-q>", lambda _e: self.root.quit())

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menubar)

    # ── config bar ──────────────────────────────────────────────────────

    def _build_config_bar(self) -> None:
        bar = ttk.Frame(self.root, padding=(6, 4))
        bar.grid(row=0, column=0, sticky="ew")

        ttk.Label(bar, text="Max tokens:").pack(side=tk.LEFT)
        self._max_tokens_var = tk.IntVar(value=8192)
        ttk.Spinbox(bar, from_=1, to=2_000_000,
                    textvariable=self._max_tokens_var, width=9).pack(side=tk.LEFT, padx=(2, 10))

        ttk.Label(bar, text="Separator:").pack(side=tk.LEFT)
        self._separator_var = tk.StringVar(value="\\n\\n")
        ttk.Entry(bar, textvariable=self._separator_var, width=8).pack(side=tk.LEFT, padx=(2, 4))
        ttk.Label(bar, text="(\\n = newline, \\t = tab)", foreground="grey").pack(side=tk.LEFT, padx=(0, 10))

        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=2)
        ttk.Label(bar, text="Token counter:").pack(side=tk.LEFT)
        self._counter_method = tk.StringVar(value="chars")
        ttk.Radiobutton(bar, text="char-based", variable=self._counter_method,
                        value="chars").pack(side=tk.LEFT)
        ttk.Radiobutton(bar, text="word-based", variable=self._counter_method,
                        value="words").pack(side=tk.LEFT, padx=(0, 6))

    def _make_packer(self) -> Contextpacker:
        return Contextpacker(
            max_tokens=self._max_tokens_var.get(),
            separator=_unescape(self._separator_var.get()),
        )

    def _token_count(self, cp: Contextpacker, text: str) -> int:
        return cp.count(text) if self._counter_method.get() == "words" else cp.count_chars(text)

    # ── notebook ────────────────────────────────────────────────────────

    def _build_notebook(self) -> None:
        nb = ttk.Notebook(self.root)
        nb.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))
        self._nb = nb

        self._build_truncate_tab(nb)
        self._build_pack_tab(nb)
        self._build_priority_tab(nb)
        self._build_chat_tab(nb)
        self._build_split_tab(nb)
        self._build_window_tab(nb)

    # ── Truncate tab ────────────────────────────────────────────────────

    def _build_truncate_tab(self, nb: ttk.Notebook) -> None:
        f = ttk.Frame(nb, padding=8)
        nb.add(f, text=" Truncate ")
        f.columnconfigure(0, weight=1)
        f.rowconfigure(1, weight=1)
        f.rowconfigure(4, weight=1)

        ttk.Label(f, text="Input text:").grid(row=0, column=0, sticky="w")
        self._trunc_input = scrolledtext.ScrolledText(f, height=8)
        self._trunc_input.grid(row=1, column=0, sticky="nsew")
        self._trunc_input.insert(tk.END,
            "The attention mechanism in transformer models computes a weighted "
            "sum of values, where the weight assigned to each value is computed "
            "by a compatibility function of the query with the corresponding key. "
            * 6)

        ctrl = ttk.Frame(f)
        ctrl.grid(row=2, column=0, sticky="ew", pady=4)
        ttk.Button(ctrl, text="Truncate (keep start)",
                   command=self._run_truncate).pack(side=tk.LEFT)
        ttk.Button(ctrl, text="Truncate (keep end)",
                   command=self._run_truncate_start).pack(side=tk.LEFT, padx=6)
        self._trunc_info = ttk.Label(ctrl, text="")
        self._trunc_info.pack(side=tk.LEFT)

        ttk.Label(f, text="Output:").grid(row=3, column=0, sticky="w")
        self._trunc_output = _TextOutput(f, height=8)
        self._trunc_output.grid(row=4, column=0, sticky="nsew")

    def _run_truncate(self) -> None:
        cp = self._make_packer()
        text = self._trunc_input.get("1.0", tk.END).rstrip("\n")
        result = cp.truncate(text)
        tokens = self._token_count(cp, result)
        self._trunc_output.set(result)
        self._trunc_info.config(
            text=f"~{tokens} tokens | {len(result)} chars | kept {len(result)}/{len(text)} chars")
        self._set_status(f"Truncated to {tokens} tokens")

    def _run_truncate_start(self) -> None:
        cp = self._make_packer()
        text = self._trunc_input.get("1.0", tk.END).rstrip("\n")
        result = cp.truncate_start(text)
        tokens = self._token_count(cp, result)
        self._trunc_output.set(result)
        self._trunc_info.config(
            text=f"~{tokens} tokens | {len(result)} chars | dropped {len(text) - len(result)} chars from start")
        self._set_status(f"Truncated (keep end) to {tokens} tokens")

    # ── Pack tab ────────────────────────────────────────────────────────

    def _build_pack_tab(self, nb: ttk.Notebook) -> None:
        f = ttk.Frame(nb, padding=8)
        nb.add(f, text=" Pack ")
        f.columnconfigure(0, weight=1)
        f.rowconfigure(1, weight=1)
        f.rowconfigure(4, weight=1)

        ttk.Label(f, text="Parts — one part per line:").grid(row=0, column=0, sticky="w")
        self._pack_input = scrolledtext.ScrolledText(f, height=10)
        self._pack_input.grid(row=1, column=0, sticky="nsew")
        self._pack_input.insert(tk.END,
            "System: You are a helpful assistant.\n"
            "User: Explain the transformer architecture in detail.\n"
            "Assistant: The transformer uses self-attention to process sequences in parallel.")

        ctrl = ttk.Frame(f)
        ctrl.grid(row=2, column=0, sticky="ew", pady=4)
        ttk.Button(ctrl, text="Pack", command=self._run_pack).pack(side=tk.LEFT)
        self._pack_info = ttk.Label(ctrl, text="")
        self._pack_info.pack(side=tk.LEFT, padx=8)

        ttk.Label(f, text="Packed output:").grid(row=3, column=0, sticky="w")
        self._pack_output = _TextOutput(f, height=8)
        self._pack_output.grid(row=4, column=0, sticky="nsew")

    def _run_pack(self) -> None:
        cp = self._make_packer()
        raw = self._pack_input.get("1.0", tk.END).rstrip("\n")
        parts = [ln for ln in raw.split("\n") if ln.strip()]
        result = cp.pack(parts)
        tokens = self._token_count(cp, result)
        self._pack_output.set(result)
        self._pack_info.config(
            text=f"~{tokens} tokens | {len(result)} chars | {len(parts)} parts joined")
        self._set_status(f"Packed {len(parts)} parts → ~{tokens} tokens")

    # ── Priority Pack tab ────────────────────────────────────────────────

    def _build_priority_tab(self, nb: ttk.Notebook) -> None:
        f = ttk.Frame(nb, padding=8)
        nb.add(f, text=" Priority Pack ")
        f.columnconfigure(0, weight=1)
        f.rowconfigure(1, weight=1)
        f.rowconfigure(5, weight=1)

        help_text = 'Format: "priority: text" per line. Higher priority = kept when budget is tight.'
        ttk.Label(f, text=help_text, foreground="grey").grid(row=0, column=0, sticky="w")
        self._prio_input = scrolledtext.ScrolledText(f, height=10)
        self._prio_input.grid(row=1, column=0, sticky="nsew")
        self._prio_input.insert(tk.END,
            "10: System instructions — always retain this context\n"
            "8: Critical retrieved document about the user's query\n"
            "5: Recent user message and assistant reply pair\n"
            "2: Older conversation context that can be dropped\n"
            "1: Least important background information")

        ctrl = ttk.Frame(f)
        ctrl.grid(row=2, column=0, sticky="ew", pady=4)
        ttk.Button(ctrl, text="Pack by Priority",
                   command=self._run_priority).pack(side=tk.LEFT)
        self._prio_info = ttk.Label(ctrl, text="")
        self._prio_info.pack(side=tk.LEFT, padx=8)

        ttk.Label(f, text="Included parts (insertion order):").grid(row=3, column=0, sticky="w")
        self._prio_output = _TextOutput(f, height=6)
        self._prio_output.grid(row=4, column=0, sticky="nsew")

        ttk.Label(f, text="Selection summary (highest priority first):").grid(row=5, column=0, sticky="w")
        self._prio_summary = _TextOutput(f, height=5)
        self._prio_summary.grid(row=6, column=0, sticky="nsew")
        f.rowconfigure(6, weight=1)

    def _run_priority(self) -> None:
        cp = self._make_packer()
        raw = self._prio_input.get("1.0", tk.END).rstrip("\n")
        parts = []
        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            if ":" in line:
                prio_str, _, content = line.partition(":")
                try:
                    priority = int(prio_str.strip())
                    text = content.strip()
                except ValueError:
                    priority = 0
                    text = line
            else:
                priority = 0
                text = line
            parts.append({"text": text, "priority": priority})

        if not parts:
            return

        limit = cp.max_tokens
        # Determine which parts are selected (mimic pack_priority logic).
        indexed = sorted(enumerate(parts),
                         key=lambda ip: ip[1].get("priority", 0), reverse=True)
        selected_set: set[int] = set()
        used = 0
        summary_lines: list[str] = []
        for idx, part in indexed:
            t = cp.count_chars(part["text"])
            kept = used + t <= limit
            if kept:
                selected_set.add(idx)
                used += t
            status = "✓ kept" if kept else "✗ dropped"
            summary_lines.append(
                f"[prio {part['priority']:>3}] {status}  (~{t} tok)  {part['text'][:60]}"
            )

        result = cp.pack_priority(parts)
        tokens = self._token_count(cp, result)
        kept_n = len(selected_set)

        self._prio_output.set(result)
        self._prio_summary.set("\n".join(summary_lines))
        self._prio_info.config(
            text=f"~{tokens} tokens | {kept_n}/{len(parts)} parts kept")
        self._set_status(f"Priority pack: {kept_n} of {len(parts)} parts selected (~{tokens} tokens)")

    # ── Chat Pack tab ────────────────────────────────────────────────────

    def _build_chat_tab(self, nb: ttk.Notebook) -> None:
        f = ttk.Frame(nb, padding=8)
        nb.add(f, text=" Chat Pack ")
        f.columnconfigure(0, weight=1)
        f.rowconfigure(1, weight=1)
        f.rowconfigure(5, weight=1)

        ttk.Label(f, text='Format: "role: content" per line. Roles: system, user, assistant.') \
            .grid(row=0, column=0, sticky="w")
        self._chat_input = scrolledtext.ScrolledText(f, height=10)
        self._chat_input.grid(row=1, column=0, sticky="nsew")
        self._chat_input.insert(tk.END,
            "system: You are a helpful assistant specialised in machine learning.\n"
            "user: What is the attention mechanism?\n"
            "assistant: The attention mechanism allows models to weight the importance of different input tokens.\n"
            "user: How is it different from RNNs?\n"
            "assistant: Unlike RNNs, attention processes all tokens in parallel rather than sequentially.\n"
            "user: Can you give me a simple example?")

        ctrl = ttk.Frame(f)
        ctrl.grid(row=2, column=0, sticky="ew", pady=4)
        ttk.Button(ctrl, text="Pack Chat", command=self._run_chat).pack(side=tk.LEFT)
        self._keep_sys_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(ctrl, text="Keep system messages",
                        variable=self._keep_sys_var).pack(side=tk.LEFT, padx=8)
        self._chat_info = ttk.Label(ctrl, text="")
        self._chat_info.pack(side=tk.LEFT)

        ttk.Label(f, text="Result — kept messages:").grid(row=3, column=0, sticky="w")
        self._chat_kept = _TextOutput(f, height=6)
        self._chat_kept.grid(row=4, column=0, sticky="nsew")

        ttk.Label(f, text="All messages with keep/drop status:").grid(row=5, column=0, sticky="w")
        self._chat_log = _TextOutput(f, height=5)
        self._chat_log.grid(row=6, column=0, sticky="nsew")
        f.rowconfigure(6, weight=1)

    def _run_chat(self) -> None:
        cp = self._make_packer()
        raw = self._chat_input.get("1.0", tk.END).rstrip("\n")
        messages = []
        for line in raw.split("\n"):
            line = line.strip()
            if not line or ":" not in line:
                continue
            role, _, content = line.partition(":")
            messages.append({"role": role.strip().lower(), "content": content.strip()})

        kept = cp.pack_chat(messages, keep_system=self._keep_sys_var.get())
        kept_contents = {id(m): True for m in kept}

        # Rebuild kept set by index for display.
        kept_set: set[int] = set()
        ki = 0
        for i, m in enumerate(messages):
            if ki < len(kept) and kept[ki] is m:
                kept_set.add(i)
                ki += 1

        log_lines = []
        for i, m in enumerate(messages):
            flag = "✓" if i in kept_set else "✗"
            log_lines.append(f"[{flag}] [{m['role']}] {m['content'][:80]}")

        result_lines = [f"[{m['role']}] {m['content']}" for m in kept]
        total_tokens = sum(self._token_count(cp, m["content"]) for m in kept)

        self._chat_kept.set("\n".join(result_lines))
        self._chat_log.set("\n".join(log_lines))
        self._chat_info.config(
            text=f"~{total_tokens} tokens | {len(kept)}/{len(messages)} messages kept")
        self._set_status(
            f"Chat packed: {len(kept)} of {len(messages)} messages (~{total_tokens} tokens)")

    # ── Split tab ────────────────────────────────────────────────────────

    def _build_split_tab(self, nb: ttk.Notebook) -> None:
        f = ttk.Frame(nb, padding=8)
        nb.add(f, text=" Split ")
        f.columnconfigure(0, weight=1)
        f.rowconfigure(1, weight=1)
        f.rowconfigure(4, weight=1)

        ttk.Label(f, text="Input text (will be split into token-sized chunks):") \
            .grid(row=0, column=0, sticky="w")
        self._split_input = scrolledtext.ScrolledText(f, height=8)
        self._split_input.grid(row=1, column=0, sticky="nsew")
        self._split_input.insert(tk.END,
            ("Large language models process text using tokenization, "
             "converting words and sub-words into numerical identifiers. ") * 30)

        ctrl = ttk.Frame(f)
        ctrl.grid(row=2, column=0, sticky="ew", pady=4)
        ttk.Button(ctrl, text="Split into chunks",
                   command=self._run_split).pack(side=tk.LEFT)
        self._split_info = ttk.Label(ctrl, text="")
        self._split_info.pack(side=tk.LEFT, padx=8)

        ttk.Label(f, text="Chunks:").grid(row=3, column=0, sticky="w")
        self._split_output = _TextOutput(f, height=10)
        self._split_output.grid(row=4, column=0, sticky="nsew")

    def _run_split(self) -> None:
        cp = self._make_packer()
        text = self._split_input.get("1.0", tk.END).rstrip("\n")
        chunks = cp.split(text)
        lines = []
        for i, chunk in enumerate(chunks, 1):
            t = self._token_count(cp, chunk)
            lines.append(f"─── Chunk {i} (~{t} tokens, {len(chunk)} chars) ───")
            lines.append(chunk)
            lines.append("")
        self._split_output.set("\n".join(lines).rstrip())
        total = self._token_count(cp, text)
        self._split_info.config(
            text=f"{len(chunks)} chunks | input ~{total} tokens total")
        self._set_status(f"Split into {len(chunks)} chunks")

    # ── Sliding Window tab ──────────────────────────────────────────────

    def _build_window_tab(self, nb: ttk.Notebook) -> None:
        f = ttk.Frame(nb, padding=8)
        nb.add(f, text=" Sliding Window ")
        f.columnconfigure(0, weight=1)
        f.rowconfigure(1, weight=1)
        f.rowconfigure(4, weight=1)

        ttk.Label(f,
            text="Parts — one per line (oldest first). Most-recent suffix kept within budget.") \
            .grid(row=0, column=0, sticky="w")
        self._win_input = scrolledtext.ScrolledText(f, height=10)
        self._win_input.grid(row=1, column=0, sticky="nsew")
        self._win_input.insert(tk.END,
            "Chunk 1: Initial system context and background documentation.\n"
            "Chunk 2: Earlier retrieved passages no longer directly relevant.\n"
            "Chunk 3: Mid-conversation retrieved context.\n"
            "Chunk 4: User's follow-up question with additional details.\n"
            "Chunk 5: Most recent assistant response — highest recency value.")

        ctrl = ttk.Frame(f)
        ctrl.grid(row=2, column=0, sticky="ew", pady=4)
        ttk.Button(ctrl, text="Apply Sliding Window",
                   command=self._run_window).pack(side=tk.LEFT)
        self._win_info = ttk.Label(ctrl, text="")
        self._win_info.pack(side=tk.LEFT, padx=8)

        ttk.Label(f, text="Kept parts (most-recent suffix):").grid(row=3, column=0, sticky="w")
        self._win_output = _TextOutput(f, height=9)
        self._win_output.grid(row=4, column=0, sticky="nsew")

    def _run_window(self) -> None:
        cp = self._make_packer()
        raw = self._win_input.get("1.0", tk.END).rstrip("\n")
        parts = [ln for ln in raw.split("\n") if ln.strip()]
        kept = cp.sliding_window(parts)
        n_dropped = len(parts) - len(kept)
        total = sum(self._token_count(cp, p) for p in kept)

        lines: list[str] = []
        for p in parts:
            flag = "✓" if p in kept else "✗ (dropped)"
            lines.append(f"[{flag}] {p}")

        self._win_output.set("\n".join(lines))
        self._win_info.config(
            text=f"{len(kept)}/{len(parts)} parts kept | {n_dropped} dropped | ~{total} tokens")
        self._set_status(
            f"Sliding window: {len(kept)} kept, {n_dropped} dropped (~{total} tokens)")

    # ── status bar ──────────────────────────────────────────────────────

    def _build_status_bar(self) -> None:
        self._status_var = tk.StringVar(value="Ready — configure max tokens above, then pick a tab.")
        bar = ttk.Frame(self.root)
        bar.grid(row=2, column=0, sticky="ew")
        ttk.Separator(bar).pack(fill=tk.X)
        ttk.Label(bar, textvariable=self._status_var,
                  anchor=tk.W, padding=(6, 2)).pack(fill=tk.X)

    def _set_status(self, msg: str) -> None:
        self._status_var.set(msg)

    # ── dialogs ─────────────────────────────────────────────────────────

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About contextpacker",
            f"contextpacker  v{__version__}\n\n"
            "Token-aware packing and truncation for LLM context windows.\n\n"
            "Tabs:\n"
            "  Truncate       — clip text to the token budget\n"
            "  Pack           — join parts and truncate to budget\n"
            "  Priority Pack  — keep highest-priority parts\n"
            "  Chat Pack      — fit a chat history within budget\n"
            "  Split          — break text into token-sized chunks\n"
            "  Sliding Window — retain the most-recent parts\n\n"
            "MIT License",
        )


# ── entry point ─────────────────────────────────────────────────────────────

def main() -> None:
    """Launch the contextpacker desktop GUI."""
    root = tk.Tk()
    ContextpackerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
