"""Source Discovery Agent - finds data sources using knowledge base + predefined sources."""

from __future__ import annotations

import json
from datetime import date
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from agents.llm import get_llm
from tools.search import tavily_search, tavily_extract
from tools.crawler import check_url
from prompts.discovery import build_system_prompt, build_task
from schema.graph import PipelineState
from storage.source_store import save_discovered_sources

# ── Colors ───────────────────────────────────────────────────────────────────
G = "\033[32m"; Y = "\033[33m"; R = "\033[31m"
DIM = "\033[2m"; BOLD = "\033[1m"; RESET = "\033[0m"


# ── Discovery-specific tools ────────────────────────────────────────────────

@tool
def format_discovery_result(url: str, source_type: str, description: str) -> str:
    """Format a discovered source. Call this for each new source found.
    Args:
        url: The data source URL.
        source_type: One of 'api', 'html', 'pdf', 'csv', 'xlsx'.
        description: Brief description of what this source provides.
    """
    return json.dumps({
        "url": url,
        "source_type": source_type,
        "description": description,
    })


TOOLS = [tavily_search, tavily_extract, check_url, format_discovery_result]


def create_discovery_agent(current_date: str | None = None):
    prompt = build_system_prompt(current_date or date.today().isoformat())
    return create_react_agent(get_llm(), TOOLS, prompt=prompt)


# ── Node function for orchestrator ──────────────────────────────────────────

def run_discovery(state: PipelineState) -> PipelineState:
    """LangGraph node: run the discovery agent."""
    init = state["initiative"]
    retry = state.get("retry_count", 0)

    print(f"\n{G}{BOLD}[DISCOVERY]{RESET} {DIM}searching for new sources{RESET}")
    if retry > 0:
        print(f"  {Y}retry #{retry}{RESET}")

    retry_context = ""
    if retry > 0:
        errors = state.get("validation_errors", [])
        retry_context = f"Previous attempt failed with: {errors}. Try different sources."

    task = build_task(retry_context=retry_context)
    agent = create_discovery_agent()
    result = agent.invoke({"messages": [("user", task)]})

    # Collect all format_discovery_result tool call outputs
    sources = []
    for msg in result["messages"]:
        if hasattr(msg, "content") and msg.content:
            try:
                parsed = json.loads(msg.content)
                if isinstance(parsed, dict) and "url" in parsed:
                    if parsed not in sources:
                        sources.append(parsed)
                        print(f"  {G}found{RESET} {DIM}{parsed.get('source_type','?')}{RESET} -> {parsed['url'][:80]}")
                elif isinstance(parsed, list):
                    for s in parsed:
                        if isinstance(s, dict) and "url" in s and s not in sources:
                            sources.append(s)
                            print(f"  {G}found{RESET} {DIM}{s.get('source_type','?')}{RESET} -> {s.get('url','')[:80]}")
            except (json.JSONDecodeError, TypeError):
                continue

    if not sources:
        print(f"  {R}no new sources found{RESET}")
    else:
        saved = save_discovered_sources(
            initiative=init,
            sources=sources,
            retry_count=retry,
        )
        if saved:
            print(f"  {DIM}saved {saved} source(s) to MongoDB{RESET}")

    return {**state, "sources": sources}
