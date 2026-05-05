"""Tkinter GUI for contextpacker — interactive demo and exploration tool."""
from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from contextpacker import Contextpacker

_PAD = 8
_FONT_BODY = ("Helvetica", 10)
_FONT_MONO = ("Courier", 10)
_FONT_HEAD = ("Helvetica", 11, "bold")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _scrolled_text(
    parent: tk.Widget, height: int = 8, readonly: bool = False
) -> scrolledtext.ScrolledText:
    st = scrolledtext.ScrolledText(parent, height=height, font=_FONT_MONO, wrap=tk.WORD)
    if readonly:
        st.configure(state=tk.DISABLED, background="#f0f0f0")
    return st


def _set_readonly(widget: scrolledtext.ScrolledText, text: str) -> None:
    widget.configure(state=tk.NORMAL)
    widget.delete("1.0", tk.END)
    widget.insert(tk.END, text)
    widget.configure(state=tk.DISABLED)


# ---------------------------------------------------------------------------
# Configuration frame (shared across all tabs)
# ---------------------------------------------------------------------------

class _ConfigFrame(ttk.LabelFrame):
    def __init__(self, parent: tk.Widget, on_change) -> None:
        super().__init__(parent, text="Configuration", padding=_PAD)
        self._on_change = on_change

        ttk.Label(self, text="Max Tokens:", font=_FONT_BODY).pack(side=tk.LEFT, padx=(_PAD, 2))
        self._max_var = tk.StringVar(value="8192")
        ttk.Entry(self, textvariable=self._max_var, width=8).pack(side=tk.LEFT)

        ttk.Label(self, text="  Separator:", font=_FONT_BODY).pack(side=tk.LEFT, padx=(10, 2))
        self._sep_var = tk.StringVar(value=r"\n\n")
        ttk.Entry(self, textvariable=self._sep_var, width=8).pack(side=tk.LEFT)

        ttk.Button(self, text="Apply", command=self._apply).pack(side=tk.LEFT, padx=10)

        self._feedback = ttk.Label(self, text="", font=_FONT_BODY, foreground="green")
        self._feedback.pack(side=tk.LEFT)

    def _apply(self) -> None:
        try:
            max_tok = int(self._max_var.get())
            if max_tok <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Config", "Max Tokens must be a positive integer.")
            return
        sep = self._sep_var.get().replace(r"\n", "\n").replace(r"\t", "\t")
        self._on_change(max_tok, sep)
        self._feedback.configure(text=f"Applied (max_tokens={max_tok})")
        self.after(2000, lambda: self._feedback.configure(text=""))

    def build_packer(self) -> Contextpacker:
        try:
            max_tok = int(self._max_var.get())
            if max_tok <= 0:
                raise ValueError
        except ValueError:
            return Contextpacker()
        sep = self._sep_var.get().replace(r"\n", "\n").replace(r"\t", "\t")
        return Contextpacker(max_tokens=max_tok, separator=sep)


# ---------------------------------------------------------------------------
# Tab: Token Counter
# ---------------------------------------------------------------------------

class _CounterTab(ttk.Frame):
    def __init__(self, parent: tk.Widget, get_packer) -> None:
        super().__init__(parent, padding=_PAD)
        self._get_packer = get_packer

        ttk.Label(self, text="Input Text:", font=_FONT_HEAD).pack(anchor=tk.W)
        self._input = _scrolled_text(self, height=10)
        self._input.pack(fill=tk.BOTH, expand=True, pady=(4, _PAD))

        ttk.Button(self, text="Count Tokens", command=self._run).pack(anchor=tk.W)

        result_frame = ttk.Frame(self)
        result_frame.pack(fill=tk.X, pady=(_PAD, 0))

        rows = [
            ("Word-based estimate:", "_word_var"),
            ("Char-based estimate:", "_char_var"),
            ("Character count:", "_len_var"),
        ]
        for row, (label, attr) in enumerate(rows):
            ttk.Label(result_frame, text=label, font=_FONT_BODY).grid(
                row=row, column=0, sticky=tk.W, padx=_PAD, pady=2
            )
            var = tk.StringVar(value="—")
            setattr(self, attr, var)
            ttk.Label(result_frame, textvariable=var, font=_FONT_MONO).grid(
                row=row, column=1, sticky=tk.W
            )

    def _run(self) -> None:
        packer = self._get_packer()
        text = self._input.get("1.0", tk.END).rstrip("\n")
        self._word_var.set(str(packer.count(text)))
        self._char_var.set(str(packer.count_chars(text)))
        self._len_var.set(str(len(text)))


# ---------------------------------------------------------------------------
# Tab: Pack
# ---------------------------------------------------------------------------

class _PackTab(ttk.Frame):
    def __init__(self, parent: tk.Widget, get_packer) -> None:
        super().__init__(parent, padding=_PAD)
        self._get_packer = get_packer

        ttk.Label(
            self,
            text='Parts — separate each block with a line containing only "---":',
            font=_FONT_HEAD,
        ).pack(anchor=tk.W)
        self._input = _scrolled_text(self, height=9)
        self._input.pack(fill=tk.BOTH, expand=True, pady=(4, _PAD))

        ttk.Button(self, text="Pack", command=self._run).pack(anchor=tk.W)

        ttk.Label(self, text="Result:", font=_FONT_HEAD).pack(anchor=tk.W, pady=(_PAD, 0))
        self._output = _scrolled_text(self, height=5, readonly=True)
        self._output.pack(fill=tk.BOTH, expand=True)

        self._stats = ttk.Label(self, text="", font=_FONT_BODY)
        self._stats.pack(anchor=tk.W, pady=(4, 0))

    def _run(self) -> None:
        packer = self._get_packer()
        raw = self._input.get("1.0", tk.END).rstrip("\n")
        parts = [p.strip() for p in raw.split("\n---\n")]
        result = packer.pack(parts)
        _set_readonly(self._output, result)
        self._stats.configure(
            text=f"Result: {packer.count_chars(result)} tokens  |  {len(result)} chars"
        )


# ---------------------------------------------------------------------------
# Tab: Truncate
# ---------------------------------------------------------------------------

class _TruncateTab(ttk.Frame):
    def __init__(self, parent: tk.Widget, get_packer) -> None:
        super().__init__(parent, padding=_PAD)
        self._get_packer = get_packer

        ttk.Label(self, text="Input Text:", font=_FONT_HEAD).pack(anchor=tk.W)
        self._input = _scrolled_text(self, height=8)
        self._input.pack(fill=tk.BOTH, expand=True, pady=(4, _PAD))

        dir_frame = ttk.Frame(self)
        dir_frame.pack(anchor=tk.W, fill=tk.X)
        ttk.Label(dir_frame, text="Direction:", font=_FONT_BODY).pack(side=tk.LEFT, padx=(_PAD, 6))
        self._direction = tk.StringVar(value="end")
        ttk.Radiobutton(
            dir_frame, text="Keep start (drop end)", variable=self._direction, value="end"
        ).pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(
            dir_frame, text="Keep end (drop start)", variable=self._direction, value="start"
        ).pack(side=tk.LEFT, padx=4)

        ttk.Button(self, text="Truncate", command=self._run).pack(anchor=tk.W, pady=_PAD)

        ttk.Label(self, text="Result:", font=_FONT_HEAD).pack(anchor=tk.W)
        self._output = _scrolled_text(self, height=6, readonly=True)
        self._output.pack(fill=tk.BOTH, expand=True)

        self._stats = ttk.Label(self, text="", font=_FONT_BODY)
        self._stats.pack(anchor=tk.W, pady=(4, 0))

    def _run(self) -> None:
        packer = self._get_packer()
        text = self._input.get("1.0", tk.END).rstrip("\n")
        if self._direction.get() == "end":
            result = packer.truncate(text)
        else:
            result = packer.truncate_start(text)
        _set_readonly(self._output, result)
        self._stats.configure(
            text=f"Input: {len(text)} chars  →  Output: {len(result)} chars  ({packer.count_chars(result)} tokens)"
        )


# ---------------------------------------------------------------------------
# Tab: Priority Pack
# ---------------------------------------------------------------------------

class _PriorityTab(ttk.Frame):
    def __init__(self, parent: tk.Widget, get_packer) -> None:
        super().__init__(parent, padding=_PAD)
        self._get_packer = get_packer
        self._parts: list[dict] = []

        ttk.Label(self, text="Add Part:", font=_FONT_HEAD).pack(anchor=tk.W)
        add_frame = ttk.Frame(self)
        add_frame.pack(fill=tk.X, pady=(4, 0))

        ttk.Label(add_frame, text="Priority:", font=_FONT_BODY).pack(side=tk.LEFT, padx=(_PAD, 2))
        self._prio_var = tk.StringVar(value="1")
        ttk.Entry(add_frame, textvariable=self._prio_var, width=6).pack(side=tk.LEFT)
        ttk.Label(add_frame, text="  Text:", font=_FONT_BODY).pack(side=tk.LEFT, padx=(8, 2))
        self._text_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=self._text_var, width=38).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        ttk.Button(add_frame, text="Add", command=self._add_part).pack(side=tk.LEFT, padx=_PAD)

        ttk.Label(self, text="Parts:", font=_FONT_HEAD).pack(anchor=tk.W, pady=(_PAD, 0))
        list_frame = ttk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True)
        self._listbox = tk.Listbox(list_frame, height=5, font=_FONT_MONO, selectmode=tk.SINGLE)
        self._listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self._listbox.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._listbox.configure(yscrollcommand=sb.set)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(anchor=tk.W, pady=(4, _PAD))
        ttk.Button(btn_frame, text="Remove Selected", command=self._remove_selected).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(btn_frame, text="Clear All", command=self._clear_all).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(btn_frame, text="Pack Priority", command=self._run).pack(side=tk.LEFT)

        ttk.Label(self, text="Result:", font=_FONT_HEAD).pack(anchor=tk.W)
        self._output = _scrolled_text(self, height=4, readonly=True)
        self._output.pack(fill=tk.BOTH, expand=True)

        self._stats = ttk.Label(self, text="", font=_FONT_BODY)
        self._stats.pack(anchor=tk.W, pady=(4, 0))

    def _add_part(self) -> None:
        try:
            priority = int(self._prio_var.get())
        except ValueError:
            messagebox.showerror("Invalid", "Priority must be an integer.")
            return
        text = self._text_var.get().strip()
        if not text:
            messagebox.showerror("Invalid", "Text cannot be empty.")
            return
        self._parts.append({"text": text, "priority": priority})
        preview = text[:55] + "…" if len(text) > 55 else text
        self._listbox.insert(tk.END, f"[{priority:+d}] {preview}")
        self._text_var.set("")

    def _remove_selected(self) -> None:
        sel = self._listbox.curselection()
        if not sel:
            return
        i = sel[0]
        self._listbox.delete(i)
        del self._parts[i]

    def _clear_all(self) -> None:
        self._parts.clear()
        self._listbox.delete(0, tk.END)

    def _run(self) -> None:
        if not self._parts:
            messagebox.showinfo("Empty", "Add at least one part first.")
            return
        packer = self._get_packer()
        result = packer.pack_priority(self._parts)
        _set_readonly(self._output, result)
        self._stats.configure(
            text=f"Result: {packer.count_chars(result)} tokens  |  {len(result)} chars"
        )


# ---------------------------------------------------------------------------
# Tab: Chat Pack
# ---------------------------------------------------------------------------

class _ChatTab(ttk.Frame):
    def __init__(self, parent: tk.Widget, get_packer) -> None:
        super().__init__(parent, padding=_PAD)
        self._get_packer = get_packer
        self._messages: list[dict] = []

        ttk.Label(self, text="Add Message:", font=_FONT_HEAD).pack(anchor=tk.W)
        add_frame = ttk.Frame(self)
        add_frame.pack(fill=tk.X, pady=(4, 0))

        ttk.Label(add_frame, text="Role:", font=_FONT_BODY).pack(side=tk.LEFT, padx=(_PAD, 2))
        self._role_var = tk.StringVar(value="user")
        role_cb = ttk.Combobox(
            add_frame,
            textvariable=self._role_var,
            values=["system", "user", "assistant"],
            width=12,
            state="readonly",
        )
        role_cb.pack(side=tk.LEFT)
        ttk.Label(add_frame, text="  Content:", font=_FONT_BODY).pack(side=tk.LEFT, padx=(8, 2))
        self._content_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=self._content_var, width=36).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        ttk.Button(add_frame, text="Add", command=self._add_msg).pack(side=tk.LEFT, padx=_PAD)

        ttk.Label(self, text="Messages (oldest → newest):", font=_FONT_HEAD).pack(
            anchor=tk.W, pady=(_PAD, 0)
        )
        list_frame = ttk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True)
        self._listbox = tk.Listbox(list_frame, height=5, font=_FONT_MONO, selectmode=tk.SINGLE)
        self._listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self._listbox.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._listbox.configure(yscrollcommand=sb.set)

        opt_frame = ttk.Frame(self)
        opt_frame.pack(anchor=tk.W, fill=tk.X, pady=(4, 0))
        self._keep_system = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="Keep system messages", variable=self._keep_system).pack(
            side=tk.LEFT, padx=_PAD
        )

        btn_frame = ttk.Frame(self)
        btn_frame.pack(anchor=tk.W, pady=(4, _PAD))
        ttk.Button(btn_frame, text="Remove Selected", command=self._remove_selected).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(btn_frame, text="Clear All", command=self._clear_all).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(btn_frame, text="Pack Chat", command=self._run).pack(side=tk.LEFT)

        ttk.Label(self, text="Result (JSON):", font=_FONT_HEAD).pack(anchor=tk.W)
        self._output = _scrolled_text(self, height=5, readonly=True)
        self._output.pack(fill=tk.BOTH, expand=True)

        self._stats = ttk.Label(self, text="", font=_FONT_BODY)
        self._stats.pack(anchor=tk.W, pady=(4, 0))

    def _add_msg(self) -> None:
        role = self._role_var.get().strip()
        content = self._content_var.get().strip()
        if not content:
            messagebox.showerror("Invalid", "Content cannot be empty.")
            return
        self._messages.append({"role": role, "content": content})
        preview = content[:55] + "…" if len(content) > 55 else content
        self._listbox.insert(tk.END, f"[{role}] {preview}")
        self._content_var.set("")

    def _remove_selected(self) -> None:
        sel = self._listbox.curselection()
        if not sel:
            return
        i = sel[0]
        self._listbox.delete(i)
        del self._messages[i]

    def _clear_all(self) -> None:
        self._messages.clear()
        self._listbox.delete(0, tk.END)

    def _run(self) -> None:
        if not self._messages:
            messagebox.showinfo("Empty", "Add at least one message first.")
            return
        packer = self._get_packer()
        result = packer.pack_chat(self._messages, keep_system=self._keep_system.get())
        _set_readonly(self._output, json.dumps(result, indent=2))
        total = sum(packer.count_chars(m.get("content", "")) for m in result)
        self._stats.configure(
            text=f"{len(result)}/{len(self._messages)} messages kept  |  ~{total} tokens"
        )


# ---------------------------------------------------------------------------
# Tab: Split / Sliding Window
# ---------------------------------------------------------------------------

class _SplitTab(ttk.Frame):
    def __init__(self, parent: tk.Widget, get_packer) -> None:
        super().__init__(parent, padding=_PAD)
        self._get_packer = get_packer

        ttk.Label(
            self,
            text="Split: paste long text below.\nSliding Window: one part per line.",
            font=_FONT_HEAD,
            justify=tk.LEFT,
        ).pack(anchor=tk.W)
        self._input = _scrolled_text(self, height=9)
        self._input.pack(fill=tk.BOTH, expand=True, pady=(4, _PAD))

        btn_frame = ttk.Frame(self)
        btn_frame.pack(anchor=tk.W, pady=(0, _PAD))
        ttk.Button(btn_frame, text="Split into Chunks", command=self._run_split).pack(
            side=tk.LEFT, padx=(0, _PAD)
        )
        ttk.Button(btn_frame, text="Sliding Window", command=self._run_window).pack(side=tk.LEFT)

        ttk.Label(self, text="Result:", font=_FONT_HEAD).pack(anchor=tk.W)
        self._output = _scrolled_text(self, height=8, readonly=True)
        self._output.pack(fill=tk.BOTH, expand=True)

        self._stats = ttk.Label(self, text="", font=_FONT_BODY)
        self._stats.pack(anchor=tk.W, pady=(4, 0))

    def _run_split(self) -> None:
        packer = self._get_packer()
        text = self._input.get("1.0", tk.END).rstrip("\n")
        chunks = packer.split(text)
        divider = "\n" + "=" * 40 + "\n"
        body = divider.join(f"[Chunk {i + 1}]\n{c}" for i, c in enumerate(chunks))
        _set_readonly(self._output, body)
        self._stats.configure(text=f"{len(chunks)} chunk(s)")

    def _run_window(self) -> None:
        packer = self._get_packer()
        raw = self._input.get("1.0", tk.END).rstrip("\n")
        parts = raw.splitlines()
        selected = packer.sliding_window(parts)
        _set_readonly(self._output, "\n".join(selected))
        self._stats.configure(text=f"{len(selected)}/{len(parts)} parts selected")


# ---------------------------------------------------------------------------
# Main application window
# ---------------------------------------------------------------------------

class _App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ContextPacker")
        self.geometry("820x660")
        self.resizable(True, True)

        self._config = _ConfigFrame(self, self._on_config_change)
        self._config.pack(fill=tk.X, padx=_PAD, pady=(_PAD, 0))

        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=_PAD, pady=_PAD)
        nb.add(_CounterTab(nb, self._config.build_packer), text="Token Counter")
        nb.add(_PackTab(nb, self._config.build_packer), text="Pack")
        nb.add(_TruncateTab(nb, self._config.build_packer), text="Truncate")
        nb.add(_PriorityTab(nb, self._config.build_packer), text="Priority Pack")
        nb.add(_ChatTab(nb, self._config.build_packer), text="Chat Pack")
        nb.add(_SplitTab(nb, self._config.build_packer), text="Split / Window")

        self._status_var = tk.StringVar(value="Ready.")
        ttk.Label(
            self,
            textvariable=self._status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            font=_FONT_BODY,
        ).pack(fill=tk.X, side=tk.BOTTOM)

    def _on_config_change(self, max_tokens: int, separator: str) -> None:
        self._status_var.set(
            f"Config updated — max_tokens={max_tokens}, separator={separator!r}"
        )


def main() -> None:
    """Launch the ContextPacker GUI."""
    app = _App()
    app.mainloop()


if __name__ == "__main__":
    main()
