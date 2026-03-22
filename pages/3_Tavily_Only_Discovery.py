"""Streamlit page for discovery testing with Tavily only."""

from __future__ import annotations

import json

import streamlit as st

from ui.discovery import DEFAULT_SECTION_INITIATIVES, run_tavily_only_batch, run_tavily_only_search


st.set_page_config(page_title="Tavily-Only Discovery", page_icon="V1M", layout="wide")

st.title("Tavily-Only Discovery")
st.caption("Bypass predefined sources and test whether Tavily alone can surface candidate sources.")

st.warning(
    "This page does not use predefined source mappings. "
    "It queries Tavily directly and returns up to 5 candidate sources per metric."
)

mode = st.radio(
    "Mode",
    options=["Single metric", "All 5 sections"],
    horizontal=True,
)

if mode == "Single metric":
    left, right = st.columns([1, 1])

    with left:
        initiative_id = st.text_input("Initiative ID", value="housing-4")
        category = st.text_input("Category", value="Housing")
        name = st.text_input("Initiative Name", value="Rental vacancy rate")
        metric_label = st.text_input("Metric", value="Rental vacancy rate")
        target_value = st.text_input("Target", value="3%")
        max_results = st.slider("Candidate sources", min_value=5, max_value=10, value=5, step=1)
        run_single = st.button("Run Tavily-Only Test", type="primary", use_container_width=True)

    with right:
        st.subheader("What This Does")
        st.markdown(
            """
- skips `lookup_predefined`
- does not use the discovery LLM agent
- calls Tavily search directly
- returns raw candidate sources so you can inspect coverage
"""
        )

    if run_single:
        with st.spinner("Running Tavily-only discovery..."):
            try:
                result = run_tavily_only_search(
                    initiative_id=initiative_id,
                    category=category,
                    name=name,
                    metric_label=metric_label,
                    target_value=target_value,
                    max_results=max_results,
                )
            except Exception as exc:
                st.error(str(exc))
            else:
                st.success(
                    f"Tavily-only discovery finished. Found {result['source_count']} candidate source(s)."
                )
                st.code(result["query"], language="text")
                for index, source in enumerate(result["sources"], start=1):
                    with st.container(border=True):
                        st.markdown(f"**Source {index}**")
                        st.json(source)
                st.subheader("Full Result")
                st.code(json.dumps(result, indent=2, default=str), language="json")
else:
    st.subheader("Batch Scope")
    st.dataframe(DEFAULT_SECTION_INITIATIVES, use_container_width=True, hide_index=True)
    max_results = st.slider("Candidate sources per section", min_value=5, max_value=10, value=5, step=1)
    run_batch = st.button("Run Tavily-Only Search For All Sections", type="primary", use_container_width=True)

    if run_batch:
        with st.spinner("Running Tavily-only discovery for all sections..."):
            try:
                results = run_tavily_only_batch(max_results=max_results)
            except Exception as exc:
                st.error(str(exc))
            else:
                total_sources = sum(item["source_count"] for item in results)
                st.success(
                    f"Tavily-only batch finished for {len(results)} sections. "
                    f"Total candidate sources found: {total_sources}."
                )
                for result in results:
                    initiative = result["initiative"]
                    label = f"{initiative['category']} | {initiative['name']}"
                    with st.expander(label, expanded=True):
                        st.code(result["query"], language="text")
                        if not result["sources"]:
                            st.warning("No candidate sources returned.")
                        else:
                            for index, source in enumerate(result["sources"], start=1):
                                st.markdown(f"**Source {index}**")
                                st.json(source)
                        st.markdown("**Full result**")
                        st.code(json.dumps(result, indent=2, default=str), language="json")
