"""Full pipeline: discovery → fetch → nurture → associate → validate for all sources."""

from __future__ import annotations

from typing import Any

from data.sources import PREDEFINED_SOURCES
from tools.crawler import fetch_source
from agents.nurture import nurture_content
from agents.associate import associate_content
from agents.quality import validate_quality
from storage.source_store import get_pipeline_cache, save_pipeline_cache


def collect_all_urls() -> dict[str, list[str]]:
    """Collect predefined + dynamically discovered URLs."""
    from agents.discovery import create_discovery_agent
    from prompts.discovery import build_task

    predefined = list(PREDEFINED_SOURCES)

    dynamic = []
    try:
        import json
        agent = create_discovery_agent()
        task = build_task()
        result = agent.invoke({"messages": [("user", task)]})

        for msg in result.get("messages", []):
            if hasattr(msg, "content") and msg.content:
                try:
                    parsed = json.loads(msg.content)
                    if isinstance(parsed, dict) and "url" in parsed:
                        url = parsed["url"]
                        if url not in predefined and url not in dynamic:
                            dynamic.append(url)
                    elif isinstance(parsed, list):
                        for s in parsed:
                            if isinstance(s, dict) and "url" in s:
                                url = s["url"]
                                if url not in predefined and url not in dynamic:
                                    dynamic.append(url)
                except (json.JSONDecodeError, TypeError):
                    continue
    except Exception:
        pass

    return {"predefined": predefined, "dynamic": dynamic, "all": predefined + dynamic}


def run_pipeline_single(url: str, origin: str = "unknown", use_cache: bool = True) -> dict[str, Any]:
    """Run the full pipeline for a single URL. Returns cached result if available."""

    # Check cache first
    if use_cache:
        cached = get_pipeline_cache(url)
        if cached and cached.get("stage") == "done":
            cached["from_cache"] = True
            return cached

    result: dict[str, Any] = {"url": url, "origin": origin, "stage": "fetch", "error": "", "from_cache": False}

    # Fetch
    try:
        raw = fetch_source.invoke({"url": url})
    except Exception as exc:
        result["error"] = f"Fetch failed: {exc}"
        save_pipeline_cache(url, result)
        return result

    if raw.startswith("[ERROR]"):
        result["error"] = raw
        save_pipeline_cache(url, result)
        return result

    result["stage"] = "nurture"
    result["raw_length"] = len(raw)

    # Nurture
    try:
        nurtured = nurture_content(url, raw)
    except Exception as exc:
        result["error"] = f"Nurture failed: {exc}"
        save_pipeline_cache(url, result)
        return result

    result["stage"] = "associate"
    result["nurtured"] = nurtured

    # Associate
    try:
        assoc_result = associate_content(url, nurtured)
        associations = assoc_result.get("associations", [])
    except Exception as exc:
        result["error"] = f"Association failed: {exc}"
        save_pipeline_cache(url, result)
        return result

    result["stage"] = "validate"
    result["associations"] = associations

    # Validate
    try:
        quality = validate_quality(url, nurtured, associations)
    except Exception as exc:
        result["error"] = f"Validation failed: {exc}"
        save_pipeline_cache(url, result)
        return result

    result["stage"] = "done"
    result["quality"] = quality
    result["score"] = quality["score"]
    result["tier"] = quality["tier"]

    # Cache the successful result
    save_pipeline_cache(url, result)

    return result


def run_pipeline_all(
    on_progress: callable = None,
    skip_discovery: bool = False,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Run the full pipeline: discover sources then process all of them.

    Args:
        on_progress: Optional callback(index, total, url, origin, result).
        skip_discovery: If True, only process predefined sources.
        use_cache: If True, skip URLs already cached with a completed result.
    """
    if skip_discovery:
        sources = {"predefined": list(PREDEFINED_SOURCES), "dynamic": [], "all": list(PREDEFINED_SOURCES)}
    else:
        sources = collect_all_urls()

    results = []
    total = len(sources["all"])

    for i, url in enumerate(sources["all"]):
        origin = "predefined" if url in sources["predefined"] else "dynamic"
        result = run_pipeline_single(url, origin=origin, use_cache=use_cache)
        results.append(result)
        if on_progress:
            on_progress(i, total, url, origin, result)

    completed = [r for r in results if not r.get("error")]
    errors = [r for r in results if r.get("error")]
    gold = [r for r in completed if r.get("tier") == "gold"]
    review = [r for r in completed if r.get("tier") == "review"]
    dropped = [r for r in completed if r.get("tier") == "drop"]
    cached = [r for r in results if r.get("from_cache")]

    return {
        "sources": {
            "predefined": len(sources["predefined"]),
            "dynamic": len(sources["dynamic"]),
            "total": total,
        },
        "results": results,
        "summary": {
            "total": total,
            "completed": len(completed),
            "gold": len(gold),
            "review": len(review),
            "dropped": len(dropped),
            "errors": len(errors),
            "from_cache": len(cached),
        },
    }
