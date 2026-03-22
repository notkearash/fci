"""Playwright-based source verification tool."""

from __future__ import annotations

import asyncio
from playwright.async_api import async_playwright


async def _check_source(url: str, criteria: list[dict]) -> dict:
    """Visit a URL with Playwright and verify extracted data against the live page.

    Args:
        url: The source URL to visit.
        criteria: List of dicts, each with:
            - field: name of the data point to verify
            - expected: the expected value (string)
            - selector: (optional) CSS selector to narrow the search

    Returns:
        dict with 'passed', 'results' (per-criterion), and 'page_title'.
    """
    results = []
    page_title = ""

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(url, timeout=30_000, wait_until="domcontentloaded")
            page_title = await page.title()

            for criterion in criteria:
                field = criterion.get("field", "unknown")
                expected = str(criterion.get("expected", ""))
                selector = criterion.get("selector")

                try:
                    if selector:
                        el = page.locator(selector)
                        text = await el.first.inner_text(timeout=5_000)
                    else:
                        text = await page.locator("body").inner_text(timeout=10_000)

                    candidates = [e.strip() for e in expected.split("|") if e.strip()]
                    found = any(c.lower() in text.lower() for c in candidates) if candidates else False
                    results.append({
                        "field": field,
                        "expected": expected,
                        "found": found,
                        "snippet": text[:200] if not found else "",
                    })
                except Exception as e:
                    results.append({
                        "field": field,
                        "expected": expected,
                        "found": False,
                        "error": str(e),
                    })

        except Exception as e:
            return {"passed": False, "error": str(e), "results": [], "page_title": ""}
        finally:
            await browser.close()

    passed = all(r["found"] for r in results) if results else False
    return {"passed": passed, "results": results, "page_title": page_title}


def check_source_with_playwright(url: str, criteria: list[dict]) -> dict:
    """Sync wrapper around the async Playwright checker."""
    return asyncio.run(_check_source(url, criteria))
