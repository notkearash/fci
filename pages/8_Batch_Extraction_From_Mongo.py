"""Streamlit page for running the extraction agent across all cached MongoDB records."""

from __future__ import annotations

import json

import streamlit as st

from ui.discovery import get_mongo_connection_status, is_mongo_configured
from ui.extraction import get_cached_sources, run_extraction_for_all_cached_sources


st.set_page_config(page_title="Batch Extraction From Mongo", page_icon="V1M", layout="wide")

st.title("Batch Extraction From Mongo")
st.caption("Read cached MongoDB source records and run the second agent across all of them.")

if not is_mongo_configured():
    st.error("MongoDB is not configured. Set MONGODB_URI and MONGODB_DB in .env first.")
    st.stop()

ok, message = get_mongo_connection_status()
if not ok:
    st.error(message)
    st.stop()

initiative_id = st.text_input("Filter by initiative ID", value="")
limit = st.slider("Max cached records", min_value=10, max_value=500, value=100, step=10)

cached_records = get_cached_sources(initiative_id=initiative_id or None, limit=limit)
if cached_records:
    st.subheader("Cached Records")
    st.dataframe(cached_records, width="stretch", hide_index=True)
else:
    st.warning("No cached MongoDB records found for this filter.")

if st.button("Run Second Agent On All Cached Records", type="primary", width="stretch"):
    with st.spinner("Running extraction across cached MongoDB records..."):
        results = run_extraction_for_all_cached_sources(
            initiative_id=initiative_id or None,
            limit=limit,
        )

    if not results:
        st.warning("No cached records were available for extraction.")
    else:
        success_count = sum(1 for item in results if item["status"] == "success")
        error_count = len(results) - success_count
        st.success(f"Batch extraction finished. Success: {success_count}. Errors: {error_count}.")
        st.dataframe(results, width="stretch", hide_index=True)

        for item in results:
            label = f"{item['initiative_id']} | {item['source_type']} | {item['status']}"
            with st.expander(label, expanded=False):
                st.code(json.dumps(item, indent=2, default=str), language="json")
