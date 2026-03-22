"""Streamlit page for testing the extraction agent from MongoDB-cached content."""

from __future__ import annotations

import json

import streamlit as st

from ui.discovery import get_discovered_sources, get_mongo_connection_status, is_mongo_configured
from ui.extraction import (
    fetch_and_cache_entry,
    get_cached_sources,
    get_saved_extractions,
    run_extraction_from_cache,
    save_cache_entry,
)


st.set_page_config(page_title="Extraction From Cache", page_icon="V1M", layout="wide")

st.title("Extraction From Cache")
st.caption("Run the second agent using source content cached in MongoDB instead of hitting live URLs.")

if not is_mongo_configured():
    st.error("MongoDB is not configured. Set MONGODB_URI and MONGODB_DB in .env first.")
    st.stop()

ok, message = get_mongo_connection_status()
if not ok:
    st.error(message)
    st.stop()

st.info(
    "Workflow for this page: pick a discovered source, save cached source content in MongoDB, "
    "then run the extraction agent only against that cached content."
)

initiative_id = st.text_input("Initiative ID", value="housing-4")
discovered_records = get_discovered_sources(initiative_id=initiative_id or None, limit=50)
source_options = {
    f"{item.get('url', '')} | {item.get('source_type', 'html')}": item for item in discovered_records
}

if not source_options:
    st.warning("No discovered sources found for this initiative ID in MongoDB.")
else:
    selected_label = st.selectbox("Discovered Source", options=list(source_options.keys()))
    selected_source = source_options[selected_label]

    cached_content = st.text_area(
        "Cached Source Content",
        value="",
        height=240,
        help="Paste the source content you want the extraction agent to read from MongoDB cache.",
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Save Cached Content", type="primary", width="stretch"):
            try:
                saved = save_cache_entry(
                    initiative_id=selected_source["initiative_id"],
                    url=selected_source["url"],
                    content=cached_content,
                )
            except Exception as exc:
                st.error(str(exc))
            else:
                st.success("Cached content saved to MongoDB.")
                st.json(saved)

    with col2:
        if st.button("Fetch And Cache From URL", width="stretch"):
            try:
                saved = fetch_and_cache_entry(
                    initiative_id=selected_source["initiative_id"],
                    url=selected_source["url"],
                )
            except Exception as exc:
                st.error(str(exc))
            else:
                st.success("Fetched source content and cached it in MongoDB.")
                st.json(saved)

    with col3:
        if st.button("Run Extraction From Cache", width="stretch"):
            try:
                result = run_extraction_from_cache(
                    initiative_id=selected_source["initiative_id"],
                    url=selected_source["url"],
                )
            except Exception as exc:
                st.error(str(exc))
            else:
                st.success("Extraction completed from cached MongoDB content.")
                st.subheader("Answer")
                st.json(result["extracted"])
                st.subheader("Full Result")
                st.code(json.dumps(result, indent=2, default=str), language="json")

st.subheader("Cached Source Content Records")
cached_records = get_cached_sources(initiative_id=initiative_id or None, limit=20)
if cached_records:
    st.dataframe(cached_records, width="stretch", hide_index=True)

st.subheader("Saved Extraction Results")
extracted_records = get_saved_extractions(initiative_id=initiative_id or None, limit=20)
if extracted_records:
    st.dataframe(extracted_records, width="stretch", hide_index=True)
