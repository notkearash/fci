"""Streamlit page: run the full pipeline — discovery + predefined → process all."""

from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from agents.pipeline import run_pipeline_all, collect_all_urls
from storage.source_store import clear_pipeline_cache

st.set_page_config(page_title="Pipeline Runner", page_icon="V1M", layout="wide")
st.title("Pipeline Runner")
st.caption("Discovers dynamic sources + predefined sources, then runs Fetch → Nurture → Associate → Validate. Results are cached — re-runs skip already processed URLs.")

col_opt1, col_opt2, col_opt3 = st.columns(3)
skip_discovery = col_opt1.checkbox("Skip discovery (predefined only)", value=False)
force_rerun = col_opt2.checkbox("Force re-run (ignore cache)", value=False)

with col_opt3:
    if st.button("Clear cache"):
        deleted = clear_pipeline_cache()
        st.success(f"Cleared {deleted} cached result(s).")

# Preview sources
if st.button("Preview sources"):
    with st.spinner("Collecting sources..." if not skip_discovery else "Loading predefined..."):
        from data.sources import PREDEFINED_SOURCES
        if skip_discovery:
            sources = {"predefined": list(PREDEFINED_SOURCES), "dynamic": [], "all": list(PREDEFINED_SOURCES)}
        else:
            sources = collect_all_urls()

    col1, col2, col3 = st.columns(3)
    col1.metric("Predefined", len(sources["predefined"]))
    col2.metric("Dynamic (discovered)", len(sources["dynamic"]))
    col3.metric("Total", len(sources["all"]))

    with st.expander(f"Predefined ({len(sources['predefined'])})"):
        for url in sources["predefined"]:
            st.code(url, language=None)

    if sources["dynamic"]:
        with st.expander(f"Dynamic ({len(sources['dynamic'])})"):
            for url in sources["dynamic"]:
                st.code(url, language=None)

st.divider()

run = st.button("Run Full Pipeline", type="primary")

if run:
    progress_bar = st.progress(0, text="Starting...")
    results_container = st.container()

    def on_progress(index, total, url, origin, result):
        pct = (index + 1) / total
        progress_bar.progress(pct, text=f"{index + 1}/{total}: {url[:60]}...")

        with results_container:
            tier = result.get("tier", "")
            score = result.get("score", "")
            error = result.get("error", "")
            cached = result.get("from_cache", False)
            tag = ":globe_with_meridians:" if origin == "dynamic" else ":pushpin:"
            cache_tag = " _(cached)_" if cached else ""

            if error:
                st.markdown(f":x: {tag} **{url[:60]}** — _{error[:80]}_")
            elif tier == "gold":
                st.markdown(f":trophy: {tag} **{score}/100** [GOLD] — {url[:60]}{cache_tag}")
            elif tier == "review":
                st.markdown(f":warning: {tag} **{score}/100** [REVIEW] — {url[:60]}{cache_tag}")
            elif tier == "drop":
                st.markdown(f":wastebasket: {tag} **{score}/100** [DROPPED] — {url[:60]}{cache_tag}")

    with st.spinner("Running pipeline..."):
        output = run_pipeline_all(
            on_progress=on_progress,
            skip_discovery=skip_discovery,
            use_cache=not force_rerun,
        )

    progress_bar.progress(1.0, text="Done!")

    st.divider()
    st.subheader("Summary")

    src = output["sources"]
    summary = output["summary"]

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Sources**")
        c1, c2, c3 = st.columns(3)
        c1.metric(":pushpin: Predefined", src["predefined"])
        c2.metric(":globe_with_meridians: Dynamic", src["dynamic"])
        c3.metric("Total", src["total"])

    with col_b:
        st.markdown("**Results**")
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Processed", summary["completed"])
        c2.metric(":trophy: Gold", summary["gold"])
        c3.metric(":warning: Review", summary["review"])
        c4.metric(":wastebasket: Dropped", summary["dropped"])
        c5.metric(":x: Errors", summary["errors"])
        c6.metric(":package: Cached", summary["from_cache"])

    errors = [r for r in output["results"] if r.get("error")]
    if errors:
        with st.expander(f"Errors ({len(errors)})"):
            for r in errors:
                st.markdown(f"- `{r['url'][:60]}` — {r['error']}")
