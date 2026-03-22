"""Streamlit page for testing the discovery agent in isolation."""

from __future__ import annotations

import json

import streamlit as st

from ui.discovery import run_discovery_step


st.set_page_config(page_title="Discovery Agent", page_icon="V1M", layout="wide")

st.title("Discovery Agent")
st.caption("Run the discovery node by itself and inspect the found sources.")

left, right = st.columns([1, 1])

with left:
    st.subheader("Initiative Input")
    initiative_id = st.text_input("Initiative ID", value="housing-4")
    category = st.text_input("Category", value="Housing")
    name = st.text_input("Initiative Name", value="Rental vacancy rate")
    metric_label = st.text_input("Metric", value="Rental vacancy rate")
    target_value = st.text_input("Target", value="3%")

    run_test = st.button("Run Discovery Test", type="primary", use_container_width=True)

with right:
    st.subheader("What This Runs")
    st.code(
        "run_discovery(state)  # isolated discovery node only",
        language="python",
    )
    st.markdown(
        """
Expected behavior:

- checks predefined sources first
- falls back to Tavily search when needed
- validates candidate URLs
- returns one or more formatted source objects
"""
    )

if run_test:
    with st.spinner("Running discovery agent..."):
        try:
            result = run_discovery_step(
                initiative_id=initiative_id,
                category=category,
                name=name,
                metric_label=metric_label,
                target_value=target_value,
            )
        except Exception as exc:
            st.error(str(exc))
        else:
            sources = result.get("sources", [])
            st.success(f"Discovery finished. Found {len(sources)} source(s).")

            st.subheader("Found Sources")
            if not sources:
                st.warning("No sources were returned by the discovery agent.")
            else:
                for index, source in enumerate(sources, start=1):
                    with st.container(border=True):
                        st.markdown(f"**Source {index}**")
                        st.json(source)

            st.subheader("Full Returned State")
            st.code(json.dumps(result, indent=2, default=str), language="json")
