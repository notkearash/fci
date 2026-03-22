"""Search tools using Tavily API."""

from __future__ import annotations

import os
from typing import Any
from langchain_core.tools import tool
from tavily import TavilyClient


def _get_client() -> TavilyClient:
    return TavilyClient(api_key=os.environ["TAVILY_API_KEY"])


def search_candidate_sources(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Return structured Tavily search results for source discovery UIs/tests."""
    client = _get_client()
    results = client.search(
        query=query,
        search_depth="advanced",
        max_results=max_results,
        include_answer=True,
    )

    candidates = []
    for item in results.get("results", []):
        candidates.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "score": item.get("score"),
            }
        )
    return candidates


@tool
def tavily_search(query: str) -> str:
    """Search the web for data sources related to a query.
    Use this to find public datasets, government statistics, and open data portals
    for Canadian municipal, provincial, or federal data.
    Returns a summary of search results with URLs.
    """
    client = _get_client()
    results = client.search(
        query=query,
        search_depth="advanced",
        max_results=5,
        include_answer=True,
    )

    parts = []
    if results.get("answer"):
        parts.append(f"Summary: {results['answer']}\n")

    for r in results.get("results", []):
        parts.append(f"- [{r['title']}]({r['url']})")
        if r.get("content"):
            parts.append(f"  {r['content'][:200]}")

    return "\n".join(parts) if parts else "No results found."


@tool
def tavily_extract(url: str) -> str:
    """Extract the main content from a URL using Tavily.
    Use this to get clean text content from a webpage without dealing with HTML parsing.
    Returns the extracted text content.
    """
    client = _get_client()
    result = client.extract(urls=[url])

    if result.get("results"):
        return result["results"][0].get("raw_content", "")[:8000]
    return "Failed to extract content."
