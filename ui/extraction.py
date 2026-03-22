"""Helpers for running the extraction step from cached MongoDB content."""

from __future__ import annotations

import json

from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from agents.llm import get_llm
from prompts.extraction import SYSTEM, TASK
from schema.graph import PipelineState
from tools.crawler import fetch_page, fetch_tables
from tools.download import download_csv, download_file, download_xlsx
from storage.source_store import (
    get_cached_source_content,
    list_discovered_sources,
    list_extraction_results,
    list_source_cache,
    save_extraction_results,
    save_source_cache,
)
from ui.discovery import build_discovery_state


def build_extraction_state_from_source(initiative: dict, source: dict) -> PipelineState:
    state = build_discovery_state(
        initiative_id=initiative["id"],
        category=initiative["category"],
        name=initiative["name"],
        metric_label=initiative["metric_label"],
        target_value=initiative["target_value"],
    )
    state["sources"] = [source]
    return state


def create_cache_extraction_agent(cached_content: str):
    @tool
    def read_cached_source(url: str) -> str:
        """Read cached source content from Mongo-backed cache."""
        return cached_content

    @tool
    def format_extraction_result(
        raw_value: str,
        numeric_value: float | None = None,
        unit: str = "",
        context: str = "",
    ) -> str:
        """Format the final extraction result from cached content."""
        return json.dumps(
            {
                "raw_value": raw_value,
                "numeric_value": numeric_value,
                "unit": unit,
                "context": context,
            }
        )

    prompt = (
        f"{SYSTEM}\n\n"
        "IMPORTANT FOR THIS RUN:\n"
        "- Do not fetch the live web.\n"
        "- Use only the read_cached_source tool.\n"
        "- The cached content is the only source of truth for this test.\n"
    )
    return create_react_agent(get_llm(), [read_cached_source, format_extraction_result], prompt=prompt)


def run_extraction_from_cache(initiative_id: str, url: str) -> dict:
    cached = get_cached_source_content(initiative_id, url)
    if not cached:
        raise RuntimeError("No cached content found for this initiative/source URL.")

    initiative = {
        "id": cached["initiative_id"],
        "category": cached["category"],
        "name": cached["name"],
        "metric_label": cached["metric_label"],
        "target_value": cached["target_value"],
    }
    source = {
        "url": cached["url"],
        "source_type": cached.get("source_type", "html"),
        "description": cached.get("description", ""),
    }
    agent = create_cache_extraction_agent(cached["content"])
    task = TASK.format(
        name=initiative["name"],
        metric_label=initiative["metric_label"],
        target_value=initiative["target_value"],
        source_url=source["url"],
        source_type=source["source_type"],
        source_description=source["description"],
    )
    result = agent.invoke({"messages": [("user", task)]})

    extracted = None
    for msg in reversed(result["messages"]):
        if hasattr(msg, "content") and msg.content:
            try:
                parsed = json.loads(msg.content)
                if isinstance(parsed, dict) and "raw_value" in parsed:
                    parsed["source_url"] = source["url"]
                    extracted = parsed
                    break
            except (json.JSONDecodeError, TypeError):
                continue

    if not extracted:
        raise RuntimeError("Extraction agent did not return a structured extraction result.")

    save_extraction_results(initiative=initiative, source=source, extracted=extracted)
    return {
        "initiative": initiative,
        "source": source,
        "cached_content": cached["content"],
        "extracted": extracted,
    }


def save_cache_entry(
    initiative_id: str,
    url: str,
    content: str,
) -> dict:
    if not content.strip():
        raise RuntimeError("Cached content cannot be empty.")

    records = [item for item in list_discovered_sources(initiative_id=initiative_id, limit=100) if item.get("url") == url]
    if not records:
        raise RuntimeError("No discovered source found for that initiative ID and URL.")

    source_record = records[0]
    initiative = {
        "id": source_record["initiative_id"],
        "category": source_record["category"],
        "name": source_record["name"],
        "metric_label": source_record["metric_label"],
        "target_value": source_record["target_value"],
    }
    source = {
        "url": source_record["url"],
        "source_type": source_record.get("source_type", "html"),
        "description": source_record.get("description", ""),
    }
    return save_source_cache(initiative=initiative, source=source, content=content)


def fetch_source_content_for_cache(url: str, source_type: str) -> str:
    source_type = (source_type or "html").lower()

    if source_type == "xlsx":
        content = download_xlsx.invoke({"url": url})
    elif source_type == "csv":
        content = download_csv.invoke({"url": url})
    elif source_type == "api":
        content = fetch_page.invoke({"url": url})
    elif source_type == "pdf":
        content = download_file.invoke({"url": url})
    else:
        page_text = fetch_page.invoke({"url": url})
        tables_text = fetch_tables.invoke({"url": url})
        if tables_text and not tables_text.startswith("No tables found"):
            content = f"{page_text}\n\n{tables_text}"
        else:
            content = page_text

    if not content or not str(content).strip():
        raise RuntimeError("Crawler returned empty content.")
    return str(content)


def fetch_and_cache_entry(initiative_id: str, url: str) -> dict:
    records = [item for item in list_discovered_sources(initiative_id=initiative_id, limit=100) if item.get("url") == url]
    if not records:
        raise RuntimeError("No discovered source found for that initiative ID and URL.")

    source_record = records[0]
    content = fetch_source_content_for_cache(
        url=source_record["url"],
        source_type=source_record.get("source_type", "html"),
    )
    return save_cache_entry(
        initiative_id=initiative_id,
        url=url,
        content=content,
    )


def audit_discovered_source_retrieval(
    initiative_id: str | None = None,
    limit: int = 100,
) -> list[dict]:
    records = list_discovered_sources(initiative_id=initiative_id, limit=limit)
    results = []

    for record in records:
        existing_cache = get_cached_source_content(record["initiative_id"], record["url"])
        source_type = record.get("source_type", "html")
        try:
            if existing_cache and str(existing_cache.get("content", "")).strip():
                content = str(existing_cache["content"])
                cache_status = "cache_hit"
            else:
                content = fetch_source_content_for_cache(
                    url=record["url"],
                    source_type=source_type,
                )
                save_cache_entry(
                    initiative_id=record["initiative_id"],
                    url=record["url"],
                    content=content,
                )
                cache_status = "fetched_and_cached"

            results.append(
                {
                    "initiative_id": record["initiative_id"],
                    "category": record.get("category", ""),
                    "name": record.get("name", ""),
                    "url": record["url"],
                    "source_type": source_type,
                    "status": "success",
                    "cache_status": cache_status,
                    "content_length": len(content),
                    "preview": content[:300],
                    "error": "",
                }
            )
        except Exception as exc:
            results.append(
                {
                    "initiative_id": record["initiative_id"],
                    "category": record.get("category", ""),
                    "name": record.get("name", ""),
                    "url": record["url"],
                    "source_type": source_type,
                    "status": "error",
                    "cache_status": "failed",
                    "content_length": 0,
                    "preview": "",
                    "error": str(exc),
                }
            )

    return results


def get_cached_sources(initiative_id: str | None = None, limit: int = 100) -> list[dict]:
    return list_source_cache(initiative_id=initiative_id, limit=limit)


def get_saved_extractions(initiative_id: str | None = None, limit: int = 100) -> list[dict]:
    return list_extraction_results(initiative_id=initiative_id, limit=limit)


def run_extraction_for_all_cached_sources(
    initiative_id: str | None = None,
    limit: int = 100,
) -> list[dict]:
    cached_records = list_source_cache(initiative_id=initiative_id, limit=limit)
    results = []

    for record in cached_records:
        url = record.get("url", "")
        current_initiative_id = record.get("initiative_id", "")
        try:
            result = run_extraction_from_cache(
                initiative_id=current_initiative_id,
                url=url,
            )
            results.append(
                {
                    "initiative_id": current_initiative_id,
                    "category": record.get("category", ""),
                    "name": record.get("name", ""),
                    "url": url,
                    "source_type": record.get("source_type", "html"),
                    "status": "success",
                    "raw_value": result["extracted"].get("raw_value", ""),
                    "numeric_value": result["extracted"].get("numeric_value"),
                    "unit": result["extracted"].get("unit", ""),
                    "context": result["extracted"].get("context", ""),
                    "error": "",
                }
            )
        except Exception as exc:
            results.append(
                {
                    "initiative_id": current_initiative_id,
                    "category": record.get("category", ""),
                    "name": record.get("name", ""),
                    "url": url,
                    "source_type": record.get("source_type", "html"),
                    "status": "error",
                    "raw_value": "",
                    "numeric_value": None,
                    "unit": "",
                    "context": "",
                    "error": str(exc),
                }
            )

    return results
