"""Streamlit GUI for contextpacker.

Launch with:
    streamlit run src/contextpacker/gui.py

Or, after installing the package with the [gui] extra:
    contextpacker-gui
"""
from __future__ import annotations

import json
import sys

import streamlit as st

from contextpacker import Contextpacker


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="contextpacker",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Sidebar — shared configuration
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("📦 contextpacker")
    st.caption("Token-aware packing for LLM context windows")
    st.divider()

    max_tokens = st.number_input(
        "Max tokens (budget)",
        min_value=1,
        max_value=200_000,
        value=4096,
        step=128,
        help="Default token budget applied to all operations on this page.",
    )
    separator = st.text_input(
        "Separator",
        value="\\n\\n",
        help='String used to join multiple parts. Use \\n\\n for double newline.',
    )
    # Unescape common sequences entered as literals
    separator = separator.replace("\\n", "\n").replace("\\t", "\t")

    st.divider()
    st.markdown(
        "**Token heuristic:** 1 token ≈ 4 characters  \n"
        "`count()` uses words × 1.3  \n"
        "`count_chars()` uses chars ÷ 4"
    )

try:
    cp = Contextpacker(max_tokens=int(max_tokens), separator=separator)
except ValueError as exc:
    st.error(str(exc))
    st.stop()


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

(
    tab_counter,
    tab_truncate,
    tab_pack,
    tab_priority,
    tab_chat,
    tab_split,
    tab_window,
) = st.tabs([
    "🔢 Token Counter",
    "✂️ Truncate",
    "📦 Pack",
    "⭐ Pack Priority",
    "💬 Pack Chat",
    "🔪 Split",
    "🪟 Sliding Window",
])


# ===========================================================================
# Tab 1 — Token Counter
# ===========================================================================

with tab_counter:
    st.header("Token Counter")
    st.markdown(
        "Estimate how many tokens a piece of text uses.  "
        "Two heuristics are shown for comparison."
    )

    text_input = st.text_area(
        "Text",
        value="The quick brown fox jumps over the lazy dog.",
        height=200,
        key="counter_text",
    )

    if text_input is not None:
        col1, col2, col3 = st.columns(3)
        word_count = cp.count(text_input)
        char_count = cp.count_chars(text_input)
        chars = len(text_input)

        col1.metric("Word-aware tokens", word_count, help="words × 1.3")
        col2.metric("Char-based tokens", char_count, help="chars ÷ 4")
        col3.metric("Characters", chars)

        budget_pct = word_count / cp.max_tokens * 100
        st.progress(
            min(budget_pct / 100, 1.0),
            text=f"{budget_pct:.1f}% of {cp.max_tokens:,} token budget (word-aware)",
        )

        if word_count > cp.max_tokens:
            st.warning(
                f"Text exceeds the {cp.max_tokens:,}-token budget by "
                f"{word_count - cp.max_tokens:,} tokens."
            )
        else:
            st.success(
                f"Text fits within the budget — "
                f"{cp.max_tokens - word_count:,} tokens remaining."
            )


# ===========================================================================
# Tab 2 — Truncate
# ===========================================================================

with tab_truncate:
    st.header("Truncate")
    st.markdown(
        "Trim text to fit inside a token budget.  "
        "**Keep beginning** preserves the start; **keep end** preserves the most recent context."
    )

    trunc_text = st.text_area(
        "Input text",
        value="a" * 300,
        height=150,
        key="trunc_text",
    )
    trunc_limit = st.number_input(
        "Override max_tokens (0 = use sidebar value)",
        min_value=0,
        value=0,
        key="trunc_limit",
    )
    limit_arg = int(trunc_limit) if trunc_limit > 0 else None

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Keep beginning")
        try:
            out = cp.truncate(trunc_text, max_tokens=limit_arg)
            st.text_area("Result", value=out, height=150, disabled=True, key="trunc_out_start")
            st.caption(
                f"{len(out)} chars · {cp.count_chars(out)} tokens "
                f"(input was {len(trunc_text)} chars)"
            )
        except ValueError as e:
            st.error(str(e))

    with col_b:
        st.subheader("Keep end")
        try:
            out2 = cp.truncate_start(trunc_text, max_tokens=limit_arg)
            st.text_area("Result", value=out2, height=150, disabled=True, key="trunc_out_end")
            st.caption(
                f"{len(out2)} chars · {cp.count_chars(out2)} tokens "
                f"(input was {len(trunc_text)} chars)"
            )
        except ValueError as e:
            st.error(str(e))


# ===========================================================================
# Tab 3 — Pack
# ===========================================================================

with tab_pack:
    st.header("Pack")
    st.markdown(
        "Join multiple text parts with the separator and truncate the result to the budget."
    )

    num_parts = st.number_input("Number of parts", min_value=1, max_value=10, value=3, key="pack_n")

    parts_pack: list[str] = []
    for i in range(int(num_parts)):
        val = st.text_area(
            f"Part {i + 1}",
            value=f"This is part {i + 1} of the context.",
            height=80,
            key=f"pack_part_{i}",
        )
        parts_pack.append(val)

    try:
        packed = cp.pack(parts_pack)
        st.subheader("Packed result")
        st.text_area("Output", value=packed, height=200, disabled=True, key="pack_out")
        st.caption(
            f"{len(packed)} chars · {cp.count_chars(packed)} tokens "
            f"(budget: {cp.max_tokens})"
        )
        if cp.count_chars(packed) >= cp.max_tokens:
            st.warning("Output was truncated to fit the budget.")
    except ValueError as e:
        st.error(str(e))


# ===========================================================================
# Tab 4 — Pack Priority
# ===========================================================================

with tab_priority:
    st.header("Pack Priority")
    st.markdown(
        "Select and pack parts by priority.  Higher-priority parts are retained "
        "when the budget is tight.  Selected parts are emitted in their **original input order**."
    )

    st.info(
        "Enter parts as a JSON array of `{\"text\": \"...\", \"priority\": N}` objects.",
        icon="ℹ️",
    )

    default_priority_json = json.dumps(
        [
            {"text": "System instructions (critical)", "priority": 100},
            {"text": "Retrieved document A — very relevant", "priority": 50},
            {"text": "Retrieved document B — somewhat relevant", "priority": 20},
            {"text": "Supplementary context — low relevance", "priority": 5},
        ],
        indent=2,
    )

    raw_json = st.text_area(
        "Parts (JSON)",
        value=default_priority_json,
        height=220,
        key="priority_json",
    )

    priority_limit = st.number_input(
        "Override max_tokens (0 = use sidebar value)",
        min_value=0,
        value=0,
        key="priority_limit",
    )
    p_limit_arg = int(priority_limit) if priority_limit > 0 else None

    try:
        priority_parts = json.loads(raw_json)
        if not isinstance(priority_parts, list):
            st.error("JSON must be a list of objects.")
        else:
            result_priority = cp.pack_priority(priority_parts, max_tokens=p_limit_arg)
            st.subheader("Packed result")
            st.text_area(
                "Output", value=result_priority, height=200, disabled=True, key="priority_out"
            )
            effective_limit = p_limit_arg or cp.max_tokens
            tokens_used = cp.count_chars(result_priority)
            st.caption(f"{tokens_used} / {effective_limit} tokens used")

            # Show which parts were included
            st.subheader("Selection summary")
            used = 0
            rows = []
            for p in priority_parts:
                t = cp.count_chars(p.get("text", ""))
                included = p.get("text", "") in result_priority
                rows.append(
                    {
                        "Priority": p.get("priority", 0),
                        "Tokens": t,
                        "Included": "✅" if included else "❌",
                        "Preview": p.get("text", "")[:60],
                    }
                )
            st.table(rows)

    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON: {e}")
    except ValueError as e:
        st.error(str(e))


# ===========================================================================
# Tab 5 — Pack Chat
# ===========================================================================

with tab_chat:
    st.header("Pack Chat")
    st.markdown(
        "Fit a conversation into the token budget.  "
        "The most-recent messages are kept; oldest non-system messages are dropped first.  "
        "System messages are always preserved (toggle below)."
    )

    keep_sys = st.checkbox("Keep system message", value=True)

    st.markdown("**Messages** (add or remove rows)")
    default_msgs = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me about token budgets."},
        {"role": "assistant", "content": "Token budgets define how much text a model can process at once."},
        {"role": "user", "content": "How does contextpacker help?"},
        {"role": "assistant", "content": "It truncates and prioritises content so prompts stay within the limit."},
        {"role": "user", "content": "What is the default max_tokens?"},
    ]

    n_msgs = st.number_input(
        "Number of messages", min_value=1, max_value=20, value=len(default_msgs), key="chat_n"
    )

    messages_in: list[dict] = []
    roles = ["system", "user", "assistant"]
    for i in range(int(n_msgs)):
        c1, c2 = st.columns([1, 4])
        default = default_msgs[i] if i < len(default_msgs) else {"role": "user", "content": ""}
        with c1:
            role = st.selectbox(
                "Role",
                roles,
                index=roles.index(default["role"]),
                key=f"chat_role_{i}",
                label_visibility="collapsed",
            )
        with c2:
            content = st.text_input(
                "Content",
                value=default["content"],
                key=f"chat_content_{i}",
                label_visibility="collapsed",
            )
        messages_in.append({"role": role, "content": content})

    chat_limit = st.number_input(
        "Override max_tokens (0 = use sidebar value)",
        min_value=0,
        value=0,
        key="chat_limit",
    )
    c_limit_arg = int(chat_limit) if chat_limit > 0 else None

    try:
        result_chat = cp.pack_chat(messages_in, max_tokens=c_limit_arg, keep_system=keep_sys)

        st.subheader("Result")
        effective = c_limit_arg or cp.max_tokens
        kept_ids = set()
        for r in result_chat:
            for i, m in enumerate(messages_in):
                if m["role"] == r["role"] and m["content"] == r["content"]:
                    kept_ids.add(i)

        for i, msg in enumerate(messages_in):
            kept = i in kept_ids
            icon = "✅" if kept else "❌"
            role_label = msg["role"].upper()
            preview = msg["content"][:80] + ("…" if len(msg["content"]) > 80 else "")
            st.markdown(f"{icon} **[{role_label}]** {preview}")

        tokens_chat = sum(cp.count_chars(m["content"]) for m in result_chat)
        st.caption(f"{len(result_chat)} / {len(messages_in)} messages kept · {tokens_chat} tokens")

    except ValueError as e:
        st.error(str(e))


# ===========================================================================
# Tab 6 — Split
# ===========================================================================

with tab_split:
    st.header("Split")
    st.markdown("Break a long text into non-overlapping chunks, each within the token budget.")

    split_text = st.text_area(
        "Input text",
        value="word " * 400,
        height=150,
        key="split_text",
    )
    split_limit = st.number_input(
        "Override max_tokens per chunk (0 = use sidebar value)",
        min_value=0,
        value=0,
        key="split_limit",
    )
    s_limit_arg = int(split_limit) if split_limit > 0 else None

    try:
        chunks = cp.split(split_text, max_tokens=s_limit_arg)
        st.metric("Chunks produced", len(chunks))

        for i, chunk in enumerate(chunks):
            with st.expander(f"Chunk {i + 1} — {len(chunk)} chars / {cp.count_chars(chunk)} tokens"):
                st.text(chunk)
    except ValueError as e:
        st.error(str(e))


# ===========================================================================
# Tab 7 — Sliding Window
# ===========================================================================

with tab_window:
    st.header("Sliding Window")
    st.markdown(
        "Select the most-recent parts that collectively fit within the token budget.  "
        "Older parts that cause an overflow are dropped."
    )

    n_window_parts = st.number_input(
        "Number of parts", min_value=1, max_value=15, value=5, key="window_n"
    )

    window_parts: list[str] = []
    for i in range(int(n_window_parts)):
        val = st.text_area(
            f"Part {i + 1} (oldest → newest)",
            value=f"Context segment {i + 1}: " + ("content " * (5 + i * 3)),
            height=70,
            key=f"window_part_{i}",
        )
        window_parts.append(val)

    window_limit = st.number_input(
        "Override max_tokens (0 = use sidebar value)",
        min_value=0,
        value=0,
        key="window_limit",
    )
    w_limit_arg = int(window_limit) if window_limit > 0 else None

    try:
        window_result = cp.sliding_window(window_parts, max_tokens=w_limit_arg)

        st.subheader("Result")
        for i, part in enumerate(window_parts):
            kept = part in window_result
            icon = "✅" if kept else "❌ (dropped — too old)"
            preview = part[:80] + ("…" if len(part) > 80 else "")
            st.markdown(f"{icon}  **Part {i + 1}:** {preview}")

        tokens_win = sum(cp.count_chars(p) for p in window_result)
        effective_win = w_limit_arg or cp.max_tokens
        st.caption(
            f"{len(window_result)} / {len(window_parts)} parts kept · "
            f"{tokens_win} / {effective_win} tokens"
        )
    except ValueError as e:
        st.error(str(e))


# ===========================================================================
# Footer
# ===========================================================================

st.divider()
st.caption(
    "contextpacker — token-aware packing for LLM context windows | "
    "[GitHub](https://github.com/vdeshmukh203/contextpacker)"
)
