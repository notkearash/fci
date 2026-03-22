"""Validation Agent - deterministic data quality checks + Playwright verification."""

from __future__ import annotations

from datetime import datetime

from schema.graph import PipelineState
from tools.playwright_checker import check_source_with_playwright
from tools.download import download_xlsx, download_csv
from tools.crawler import fetch_page

MAX_RETRIES = 3

# ── Colors ───────────────────────────────────────────────────────────────────
G = "\033[32m"; R = "\033[31m"; Y = "\033[33m"
DIM = "\033[2m"; BOLD = "\033[1m"; RESET = "\033[0m"

# ── Validation criteria ──────────────────────────────────────────────────────
# Each criterion: {field, expected, match} where match is "any" (default) or "all"
# "expected" can be a single string or a |-separated list (matched as OR)
VALIDATION_CRITERIA: list[dict] = [
    {"field": "recent_year", "expected": f"{datetime.now().year}|{datetime.now().year - 1}"},
]


FILE_EXTENSIONS = {
    ".xlsx": "xlsx",
    ".xls": "xlsx",
    ".csv": "csv",
}


def _fetch_source_content(url: str) -> str | None:
    """Fetch content from a source URL using the appropriate tool."""
    url_path = url.split("?")[0].lower()

    for ext, kind in FILE_EXTENSIONS.items():
        if url_path.endswith(ext):
            try:
                if kind == "xlsx":
                    return download_xlsx.invoke({"url": url})
                elif kind == "csv":
                    return download_csv.invoke({"url": url})
            except Exception as e:
                return f"Error: {e}"

    # Default: treat as HTML page
    try:
        return fetch_page.invoke({"url": url})
    except Exception as e:
        return f"Error: {e}"


def _run_source_check(item: dict, errors: list[str]) -> None:
    """Verify extracted data against the live source (Playwright for HTML, tools for files)."""
    url = item.get("source_url", "")
    if not url:
        return

    url_path = url.split("?")[0].lower()
    is_file = any(url_path.endswith(ext) for ext in FILE_EXTENSIONS)

    if is_file:
        # Use download tools for file sources
        print(f"  {DIM}download: checking {url[:60]}...{RESET}")
        content = _fetch_source_content(url)

        if not content or content.startswith("Error:"):
            errors.append(f"Source fetch error: {content}")
            print(f"  {R}FAIL: could not fetch source{RESET}")
            return

        for criterion in VALIDATION_CRITERIA:
            field = criterion.get("field", "unknown")
            expected = str(criterion.get("expected", ""))
            candidates = [e.strip() for e in expected.split("|") if e.strip()]
            found = any(c.lower() in content.lower() for c in candidates) if candidates else False

            if not found:
                msg = f"Source check: '{field}' not found in file (expected any of: {candidates})"
                errors.append(msg)
                print(f"  {R}{msg}{RESET}")
            else:
                print(f"  {G}source check: '{field}' verified in file{RESET}")
    else:
        # Use Playwright for web pages
        raw = item.get("raw_value", "")
        criteria = VALIDATION_CRITERIA if VALIDATION_CRITERIA else [
            {"field": "raw_value", "expected": raw},
        ]

        print(f"  {DIM}playwright: checking {url[:60]}...{RESET}")
        result = check_source_with_playwright(url, criteria)

        if result.get("error"):
            print(f"  {Y}playwright: page error: {result['error'][:60]}{RESET}")
            errors.append(f"Playwright error: {result['error']}")
            return

        for r in result.get("results", []):
            if not r["found"]:
                msg = f"Playwright: '{r['field']}' not found on page"
                errors.append(msg)
                print(f"  {R}{msg}{RESET}")
            else:
                print(f"  {G}playwright: '{r['field']}' verified on page{RESET}")


def run_validation(state: PipelineState) -> PipelineState:
    """LangGraph node: validate extracted data. Deterministic checks + Playwright."""
    init = state["initiative"]
    extracted = state.get("extracted", [])
    errors: list[str] = []

    print(f"\n{Y}{BOLD}[VALIDATION]{RESET} {init['name']}")

    # Check: any data at all?
    if not extracted:
        errors.append("No data extracted")
        print(f"  {R}FAIL: no data extracted{RESET}")

    # Check each extraction
    for item in extracted:
        raw = item.get("raw_value", "")

        if not raw:
            errors.append("Empty raw_value")
            print(f"  {R}FAIL: empty value{RESET}")

        if raw.startswith("Error:") or raw.startswith("HTTP error:"):
            errors.append(f"Extraction error: {raw}")
            print(f"  {R}FAIL: {raw[:60]}{RESET}")

        if raw == "No data found" or raw == "No results found":
            errors.append("Source returned no relevant data")
            print(f"  {R}FAIL: no relevant data in source{RESET}")

        # Verify the extracted value exists on the live source
        _run_source_check(item, errors)

    is_valid = len(errors) == 0
    retry_count = state.get("retry_count", 0)

    if is_valid:
        print(f"  {G}PASS{RESET} -> routing to mapper")
    else:
        new_retry = retry_count + 1
        if new_retry >= MAX_RETRIES:
            print(f"  {R}FAIL (retry {new_retry}/{MAX_RETRIES}) -> exhausted{RESET}")
        else:
            print(f"  {Y}FAIL (retry {new_retry}/{MAX_RETRIES}) -> retrying{RESET}")

    return {
        **state,
        "is_valid": is_valid,
        "validation_errors": errors,
        "retry_count": retry_count + (0 if is_valid else 1),
    }


def should_retry(state: PipelineState) -> str:
    """Conditional edge: decide where to route after validation."""
    if state.get("is_valid", False):
        return "mapper"
    if state.get("retry_count", 0) >= MAX_RETRIES:
        return "exhausted"
    return "retry"
