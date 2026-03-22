"""Streamlit home page for step-by-step workflow testing."""

from __future__ import annotations

import streamlit as st


st.set_page_config(
    page_title="Vision One Million Workflow Tester",
    page_icon="V1M",
    layout="wide",
)

st.title("Vision One Million Workflow Tester")
st.caption("Test the scorecard pipeline one unit at a time.")

st.markdown(
    """
Start with the **Discovery** page from the sidebar.

This UI is intentionally narrow in scope:

- Run one pipeline step at a time
- Inspect raw agent outputs
- Validate behavior before wiring the full end-to-end flow
"""
)

st.info(
    "Current first page: Discovery Agent. "
    "It runs the discovery node in isolation and shows the returned sources."
)
