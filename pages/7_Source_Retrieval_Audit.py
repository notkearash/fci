"""Streamlit page for auditing retrieval across all saved MongoDB sources."""

from __future__ import annotations

import json

import streamlit as st

from ui.discovery import get_mongo_connection_status, is_mongo_configured
from ui.extraction import audit_discovered_source_retrieval


st.set_page_config(page_title="Source Retrieval Audit", page_icon="V1M", layout="wide")

st.title("Source Retrieval Audit")
st.caption("Test whether all discovered MongoDB sources can be retrieved and cached regardless of source type.")

if not is_mongo_configured():
    st.error("MongoDB is not configured. Set MONGODB_URI and MONGODB_DB in .env first.")
    st.stop()

ok, message = get_mongo_connection_status()
if not ok:
    st.error(message)
    st.stop()

initiative_id = st.text_input("Filter by initiative ID", value="")
limit = st.slider("Max discovered sources to audit", min_value=10, max_value=500, value=100, step=10)

if st.button("Run Retrieval Audit", type="primary", width="stretch"):
    with st.spinner("Auditing saved sources from MongoDB..."):
        results = audit_discovered_source_retrieval(
            initiative_id=initiative_id or None,
            limit=limit,
        )

    if not results:
        st.warning("No discovered sources found to audit.")
    else:
        success_count = sum(1 for item in results if item["status"] == "success")
        error_count = len(results) - success_count
        st.success(f"Audit finished. Success: {success_count}. Errors: {error_count}.")
        st.dataframe(results, width="stretch", hide_index=True)

        for item in results:
            label = f"{item['initiative_id']} | {item['source_type']} | {item['status']}"
            with st.expander(label, expanded=False):
                st.code(json.dumps(item, indent=2, default=str), language="json")
