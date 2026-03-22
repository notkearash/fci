"""Streamlit page: run the discovery agent and browse results."""

from __future__ import annotations

import json

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from agents.discovery import create_discovery_agent
from data.sources import PREDEFINED_SOURCES, SCORECARD_INITIATIVES
from prompts.discovery import build_task

st.set_page_config(page_title="Source Discovery", page_icon="V1M", layout="wide")
st.title("Source Discovery")
st.caption("Run the discovery agent to find new data sources beyond the predefined list.")

# ── Sidebar: show knowledge base & predefined sources ────────────────────────
with st.sidebar:
    st.subheader("Knowledge Base")
    st.metric("Initiatives", len(SCORECARD_INITIATIVES))
    st.metric("Predefined URLs", len(PREDEFINED_SOURCES))

    with st.expander("Initiatives"):
        for init in SCORECARD_INITIATIVES:
            st.markdown(f"**{init['id']}** — {init['name']}  \n"
                        f"_{init['metric_label']}_  \n"
                        f"Target: {init['target_value']}")
            st.divider()

    with st.expander("Predefined Sources"):
        for url in PREDEFINED_SOURCES:
            st.code(url, language=None)

# ── Main: run discovery ──────────────────────────────────────────────────────
run = st.button("Run Discovery Agent", type="primary")

if run:
    task = build_task()

    with st.expander("Prompt sent to agent", expanded=False):
        st.code(task, language=None)

    with st.spinner("Discovery agent is searching for new sources..."):
        try:
            agent = create_discovery_agent()
            result = agent.invoke({"messages": [("user", task)]})
        except Exception as exc:
            st.error(f"Agent failed: {exc}")
            st.stop()

    # Parse all discovered sources from agent messages
    sources = []
    for msg in result["messages"]:
        if hasattr(msg, "content") and msg.content:
            try:
                parsed = json.loads(msg.content)
                if isinstance(parsed, dict) and "url" in parsed:
                    if parsed not in sources:
                        sources.append(parsed)
                elif isinstance(parsed, list):
                    for s in parsed:
                        if isinstance(s, dict) and "url" in s and s not in sources:
                            sources.append(s)
            except (json.JSONDecodeError, TypeError):
                continue

    # ── Results ──────────────────────────────────────────────────────────
    st.subheader(f"Discovered Sources ({len(sources)})")

    if not sources:
        st.warning("No new sources found.")
    else:
        for i, source in enumerate(sources, 1):
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{i}. {source.get('description', 'No description')}**")
                    st.code(source.get("url", ""), language=None)
                with col2:
                    st.caption("Type")
                    st.code(source.get("source_type", "unknown"))

    # ── Raw agent messages ───────────────────────────────────────────────
    with st.expander("Raw agent messages"):
        for msg in result["messages"]:
            role = getattr(msg, "type", "unknown")
            content = getattr(msg, "content", "")
            if content:
                st.markdown(f"**{role}**")
                st.text(str(content)[:2000])
                st.divider()
