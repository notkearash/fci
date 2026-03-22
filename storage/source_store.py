"""Mongo-backed storage for predefined and discovered sources."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from data.sources import PREDEFINED_SOURCES, SCORECARD_INITIATIVES, INITIATIVES_BY_ID


DEFAULT_DB_NAME = "vision_1m"
PREDEFINED_COLLECTION = "predefined_sources"
DISCOVERED_COLLECTION = "discovered_sources"
SOURCE_CACHE_COLLECTION = "source_content_cache"
EXTRACTION_COLLECTION = "extracted_results"
EXTRACTION_ERRORS_COLLECTION = "extraction_errors"
QUALITY_REVIEWS_COLLECTION = "quality_reviews"
PIPELINE_CACHE_COLLECTION = "pipeline_cache"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def mongo_configured() -> bool:
    return bool(os.getenv("MONGODB_URI"))


def _get_collection(name: str):
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError

    uri = os.getenv("MONGODB_URI")
    if not uri:
        raise RuntimeError("MONGODB_URI is not configured.")
    db_name = os.getenv("MONGODB_DB", DEFAULT_DB_NAME)
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
    except PyMongoError as exc:
        raise RuntimeError(f"MongoDB is unreachable: {exc}") from exc
    return client[db_name][name]


def get_all_predefined_urls() -> list[str]:
    """Return the flat list of predefined source URLs."""
    return list(PREDEFINED_SOURCES)


def get_all_initiatives() -> list[dict[str, Any]]:
    """Return all scorecard initiatives (the knowledge base)."""
    return list(SCORECARD_INITIATIVES)


def get_initiative(initiative_id: str) -> dict[str, Any] | None:
    """Look up a single initiative by ID."""
    return INITIATIVES_BY_ID.get(initiative_id)


def list_human_predefined_sources(initiative_id: str | None = None) -> list[dict[str, Any]]:
    if not mongo_configured():
        return []

    query = {"kind": "human_predefined"}
    if initiative_id:
        query["initiative_id"] = initiative_id

    try:
        collection = _get_collection(PREDEFINED_COLLECTION)
        docs = list(collection.find(query, {"_id": 0}).sort("updated_at", -1))
    except RuntimeError:
        return []
    return [
        {
            "initiative_id": doc.get("initiative_id", ""),
            "category": doc.get("category", ""),
            "name": doc.get("name", ""),
            "metric_label": doc.get("metric_label", ""),
            "target_value": doc.get("target_value", ""),
            "url": doc.get("url", ""),
            "source_type": doc.get("source_type", "html"),
            "description": doc.get("description", ""),
            "is_predefined": True,
            "origin": "human",
            "notes": doc.get("notes", ""),
            "updated_at": doc.get("updated_at"),
        }
        for doc in docs
    ]


def get_predefined_sources() -> list[str]:
    """Return all predefined URLs (static from CSV + any human-added)."""
    urls = list(PREDEFINED_SOURCES)
    human = list_human_predefined_sources()
    for item in human:
        if item.get("url") and item["url"] not in urls:
            urls.append(item["url"])
    return urls


def upsert_human_predefined_source(
    *,
    initiative_id: str,
    category: str,
    name: str,
    metric_label: str,
    target_value: str,
    url: str,
    source_type: str,
    description: str,
    notes: str = "",
) -> dict[str, Any]:
    if not mongo_configured():
        raise RuntimeError("MONGODB_URI is not configured.")

    collection = _get_collection(PREDEFINED_COLLECTION)
    now = _utcnow()
    doc = {
        "kind": "human_predefined",
        "initiative_id": initiative_id,
        "category": category,
        "name": name,
        "metric_label": metric_label,
        "target_value": target_value,
        "url": url,
        "source_type": source_type,
        "description": description,
        "notes": notes,
        "updated_at": now,
    }
    collection.update_one(
        {"kind": "human_predefined", "initiative_id": initiative_id, "url": url},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return doc


def save_discovered_sources(
    *,
    initiative: dict[str, Any],
    sources: list[dict[str, Any]],
    retry_count: int = 0,
) -> int:
    if not mongo_configured() or not sources:
        return 0

    collection = _get_collection(DISCOVERED_COLLECTION)
    now = _utcnow()
    docs = []
    for source in sources:
        docs.append(
            {
                "initiative_id": initiative.get("id", ""),
                "category": initiative.get("category", ""),
                "name": initiative.get("name", ""),
                "metric_label": initiative.get("metric_label", ""),
                "target_value": initiative.get("target_value", ""),
                "url": source.get("url", ""),
                "source_type": source.get("source_type", "html"),
                "description": source.get("description", ""),
                "is_predefined": bool(source.get("is_predefined", False)),
                "origin": source.get("origin", "dynamic"),
                "retry_count": retry_count,
                "discovered_at": now,
            }
        )

    for doc in docs:
        collection.update_one(
            {"initiative_id": doc["initiative_id"], "url": doc["url"], "origin": doc["origin"]},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
    return len(docs)


def list_discovered_sources(
    initiative_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    if not mongo_configured():
        return []

    query: dict[str, Any] = {}
    if initiative_id:
        query["initiative_id"] = initiative_id

    try:
        collection = _get_collection(DISCOVERED_COLLECTION)
        docs = list(collection.find(query, {"_id": 0}).sort("discovered_at", -1).limit(limit))
    except RuntimeError:
        return []
    return docs


def save_source_cache(
    *,
    initiative: dict[str, Any],
    source: dict[str, Any],
    content: str,
) -> dict[str, Any]:
    if not mongo_configured():
        raise RuntimeError("MONGODB_URI is not configured.")

    collection = _get_collection(SOURCE_CACHE_COLLECTION)
    now = _utcnow()
    doc = {
        "initiative_id": initiative.get("id", ""),
        "category": initiative.get("category", ""),
        "name": initiative.get("name", ""),
        "metric_label": initiative.get("metric_label", ""),
        "target_value": initiative.get("target_value", ""),
        "url": source.get("url", ""),
        "source_type": source.get("source_type", "html"),
        "description": source.get("description", ""),
        "content": content,
        "cached_at": now,
    }
    collection.update_one(
        {"initiative_id": doc["initiative_id"], "url": doc["url"]},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return doc


def list_source_cache(
    initiative_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    if not mongo_configured():
        return []

    query: dict[str, Any] = {}
    if initiative_id:
        query["initiative_id"] = initiative_id

    try:
        collection = _get_collection(SOURCE_CACHE_COLLECTION)
        docs = list(collection.find(query, {"_id": 0}).sort("cached_at", -1).limit(limit))
    except RuntimeError:
        return []
    return docs


def get_cached_source_content(initiative_id: str, url: str) -> dict[str, Any] | None:
    if not mongo_configured():
        return None
    try:
        collection = _get_collection(SOURCE_CACHE_COLLECTION)
        return collection.find_one({"initiative_id": initiative_id, "url": url}, {"_id": 0})
    except RuntimeError:
        return None


def save_extraction_results(
    *,
    initiative: dict[str, Any],
    source: dict[str, Any],
    extracted: dict[str, Any],
) -> dict[str, Any]:
    if not mongo_configured():
        raise RuntimeError("MONGODB_URI is not configured.")

    collection = _get_collection(EXTRACTION_COLLECTION)
    now = _utcnow()
    doc = {
        "initiative_id": initiative.get("id", ""),
        "category": initiative.get("category", ""),
        "name": initiative.get("name", ""),
        "metric_label": initiative.get("metric_label", ""),
        "target_value": initiative.get("target_value", ""),
        "url": source.get("url", ""),
        "source_type": source.get("source_type", "html"),
        "description": source.get("description", ""),
        "raw_value": extracted.get("raw_value", ""),
        "numeric_value": extracted.get("numeric_value"),
        "unit": extracted.get("unit", ""),
        "context": extracted.get("context", ""),
        "source_url": extracted.get("source_url", source.get("url", "")),
        "extracted_at": now,
    }
    collection.update_one(
        {"initiative_id": doc["initiative_id"], "url": doc["url"]},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return doc


def list_extraction_results(
    initiative_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    if not mongo_configured():
        return []

    query: dict[str, Any] = {}
    if initiative_id:
        query["initiative_id"] = initiative_id

    try:
        collection = _get_collection(EXTRACTION_COLLECTION)
        docs = list(collection.find(query, {"_id": 0}).sort("extracted_at", -1).limit(limit))
    except RuntimeError:
        return []
    return docs


EXTRACTION_ERROR_CATEGORIES = {
    "http_error": {
        "label": "HTTP Error",
        "codes": ["4xx", "5xx", "timeout", "dns", "connection_reset", "ssl", "redirect_loop"],
    },
    "access_blocked": {
        "label": "Access Blocked",
        "codes": ["auth_required", "forbidden", "rate_limited", "ip_banned", "captcha", "bot_detection"],
    },
    "content_structure": {
        "label": "Content Structure",
        "codes": ["html_changed", "js_rendered", "lazy_loading", "inconsistent_layout"],
    },
    "data_quality": {
        "label": "Data Quality",
        "codes": ["missing_data", "duplicate_data", "bad_format", "noisy_content"],
    },
    "legal": {
        "label": "Legal / Policy",
        "codes": ["robots_txt", "tos", "copyright"],
    },
    "performance": {
        "label": "Performance",
        "codes": ["slow", "memory", "concurrency"],
    },
    "url_complexity": {
        "label": "URL Complexity",
        "codes": ["query_params", "session_url", "pagination"],
    },
    "anti_scraping": {
        "label": "Anti-Scraping",
        "codes": ["user_agent_filter", "honeypot", "obfuscated_html", "js_challenge"],
    },
}

# Flat lookup: error_code -> category
ERROR_CODE_TO_CATEGORY = {}
for cat_id, cat in EXTRACTION_ERROR_CATEGORIES.items():
    for code in cat["codes"]:
        ERROR_CODE_TO_CATEGORY[code] = cat_id

ALL_ERROR_CODES = list(ERROR_CODE_TO_CATEGORY.keys())


def save_extraction_error(
    *,
    url: str,
    error_code: str,
    error_message: str,
    source_type: str = "html",
    http_status: int | None = None,
    initiative_id: str = "",
    raw_response_preview: str = "",
) -> dict[str, Any]:
    """Log a source extraction error for human review."""
    category = ERROR_CODE_TO_CATEGORY.get(error_code, "unknown")

    doc = {
        "url": url,
        "error_code": error_code,
        "error_category": category,
        "error_message": error_message,
        "source_type": source_type,
        "http_status": http_status,
        "initiative_id": initiative_id,
        "raw_response_preview": raw_response_preview[:500],
        "reviewed": False,
        "resolution": "",
        "logged_at": _utcnow(),
    }

    if not mongo_configured():
        return doc

    collection = _get_collection(EXTRACTION_ERRORS_COLLECTION)
    collection.update_one(
        {"url": url, "error_code": error_code},
        {"$set": doc, "$setOnInsert": {"created_at": _utcnow()}},
        upsert=True,
    )
    return doc


def list_extraction_errors(
    *,
    category: str | None = None,
    reviewed: bool | None = None,
    initiative_id: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """List logged extraction errors, optionally filtered."""
    if not mongo_configured():
        return []

    query: dict[str, Any] = {}
    if category:
        query["error_category"] = category
    if reviewed is not None:
        query["reviewed"] = reviewed
    if initiative_id:
        query["initiative_id"] = initiative_id

    try:
        collection = _get_collection(EXTRACTION_ERRORS_COLLECTION)
        return list(collection.find(query, {"_id": 0}).sort("logged_at", -1).limit(limit))
    except RuntimeError:
        return []


def mark_error_reviewed(url: str, error_code: str, resolution: str = "") -> bool:
    """Mark an extraction error as reviewed."""
    if not mongo_configured():
        return False

    collection = _get_collection(EXTRACTION_ERRORS_COLLECTION)
    result = collection.update_one(
        {"url": url, "error_code": error_code},
        {"$set": {"reviewed": True, "resolution": resolution, "reviewed_at": _utcnow()}},
    )
    return result.modified_count > 0


def get_extraction_error_summary() -> dict[str, int]:
    """Get count of unreviewed errors per category."""
    if not mongo_configured():
        return {}

    try:
        collection = _get_collection(EXTRACTION_ERRORS_COLLECTION)
        pipeline = [
            {"$match": {"reviewed": False}},
            {"$group": {"_id": "$error_category", "count": {"$sum": 1}}},
        ]
        results = list(collection.aggregate(pipeline))
    except RuntimeError:
        return {}

    return {r["_id"]: r["count"] for r in results}


def save_quality_review(
    *,
    url: str,
    score: int,
    tier: str,
    issues: list[dict[str, Any]],
    nurtured: dict[str, Any],
    associations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Save a data quality review result. Tier is 'gold' (70-100) or 'review' (30-69)."""
    now = _utcnow()
    doc = {
        "url": url,
        "score": score,
        "tier": tier,
        "issues": issues,
        "nurtured_summary": nurtured.get("summary", ""),
        "nurtured_title": nurtured.get("title", ""),
        "associations": associations,
        "reviewed_at": now,
    }

    if mongo_configured():
        collection = _get_collection(QUALITY_REVIEWS_COLLECTION)
        collection.update_one(
            {"url": url},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )

    return doc


def list_quality_reviews(
    *,
    tier: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """List quality reviews, optionally filtered by tier ('gold' or 'review')."""
    if not mongo_configured():
        return []

    query: dict[str, Any] = {}
    if tier:
        query["tier"] = tier

    try:
        collection = _get_collection(QUALITY_REVIEWS_COLLECTION)
        return list(collection.find(query, {"_id": 0}).sort("reviewed_at", -1).limit(limit))
    except RuntimeError:
        return []


def get_pipeline_cache(url: str) -> dict[str, Any] | None:
    """Get cached pipeline result for a URL."""
    if not mongo_configured():
        return None
    try:
        collection = _get_collection(PIPELINE_CACHE_COLLECTION)
        return collection.find_one({"url": url}, {"_id": 0})
    except RuntimeError:
        return None


def save_pipeline_cache(url: str, result: dict[str, Any]) -> None:
    """Cache a pipeline result for a URL."""
    if not mongo_configured():
        return
    try:
        collection = _get_collection(PIPELINE_CACHE_COLLECTION)
        collection.update_one(
            {"url": url},
            {"$set": {**result, "cached_at": _utcnow()}},
            upsert=True,
        )
    except RuntimeError:
        pass


def clear_pipeline_cache() -> int:
    """Clear all cached pipeline results. Returns count deleted."""
    if not mongo_configured():
        return 0
    try:
        collection = _get_collection(PIPELINE_CACHE_COLLECTION)
        result = collection.delete_many({})
        return result.deleted_count
    except RuntimeError:
        return 0


def get_mongo_status() -> tuple[bool, str]:
    if not mongo_configured():
        return False, "MongoDB is not configured."
    try:
        _get_collection(PREDEFINED_COLLECTION)
    except RuntimeError as exc:
        return False, str(exc)
    return True, "MongoDB is reachable."
