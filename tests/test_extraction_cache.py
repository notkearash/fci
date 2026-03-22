"""Tests for cache-backed extraction helpers."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from ui.extraction import fetch_and_cache_entry, run_extraction_from_cache, save_cache_entry


class FakeAgent:
    def __init__(self, messages):
        self._messages = messages

    def invoke(self, _payload):
        return {"messages": self._messages}


class ExtractionCacheTests(unittest.TestCase):
    @patch("ui.extraction.save_extraction_results")
    @patch("ui.extraction.create_cache_extraction_agent")
    @patch("ui.extraction.get_cached_source_content")
    def test_run_extraction_from_cache_returns_structured_result(
        self,
        mock_get_cached_source_content,
        mock_create_cache_extraction_agent,
        mock_save_extraction_results,
    ):
        mock_get_cached_source_content.return_value = {
            "initiative_id": "housing-4",
            "category": "Housing",
            "name": "Rental vacancy rate",
            "metric_label": "Rental vacancy rate",
            "target_value": "3%",
            "url": "https://example.com/data.csv",
            "source_type": "csv",
            "description": "Cached source",
            "content": "KW CMA | 4.1%",
        }
        mock_create_cache_extraction_agent.return_value = FakeAgent(
            [SimpleNamespace(content='{"raw_value":"4.1%","numeric_value":4.1,"unit":"%","context":"KW CMA row"}')]
        )

        result = run_extraction_from_cache("housing-4", "https://example.com/data.csv")

        self.assertEqual(result["extracted"]["raw_value"], "4.1%")
        self.assertEqual(result["extracted"]["numeric_value"], 4.1)
        mock_save_extraction_results.assert_called_once()

    @patch("ui.extraction.list_discovered_sources")
    @patch("ui.extraction.save_source_cache")
    def test_save_cache_entry_uses_discovered_source_record(self, mock_save_source_cache, mock_list_discovered_sources):
        mock_list_discovered_sources.return_value = [
            {
                "initiative_id": "housing-4",
                "category": "Housing",
                "name": "Rental vacancy rate",
                "metric_label": "Rental vacancy rate",
                "target_value": "3%",
                "url": "https://example.com/data.csv",
                "source_type": "csv",
                "description": "Saved source",
            }
        ]
        mock_save_source_cache.return_value = {"ok": True}

        result = save_cache_entry("housing-4", "https://example.com/data.csv", "KW CMA | 4.1%")

        self.assertEqual(result, {"ok": True})
        mock_save_source_cache.assert_called_once()

    def test_save_cache_entry_rejects_empty_content(self):
        with self.assertRaisesRegex(RuntimeError, "cannot be empty"):
            save_cache_entry("housing-4", "https://example.com/data.csv", "")

    @patch("ui.extraction.save_cache_entry")
    @patch("ui.extraction.fetch_source_content_for_cache")
    @patch("ui.extraction.list_discovered_sources")
    def test_fetch_and_cache_entry_fetches_then_saves(
        self,
        mock_list_discovered_sources,
        mock_fetch_source_content_for_cache,
        mock_save_cache_entry,
    ):
        mock_list_discovered_sources.return_value = [
            {
                "initiative_id": "housing-4",
                "category": "Housing",
                "name": "Rental vacancy rate",
                "metric_label": "Rental vacancy rate",
                "target_value": "3%",
                "url": "https://example.com/data.csv",
                "source_type": "csv",
                "description": "Saved source",
            }
        ]
        mock_fetch_source_content_for_cache.return_value = "KW CMA | 4.1%"
        mock_save_cache_entry.return_value = {"ok": True}

        result = fetch_and_cache_entry("housing-4", "https://example.com/data.csv")

        self.assertEqual(result, {"ok": True})
        mock_fetch_source_content_for_cache.assert_called_once_with(
            url="https://example.com/data.csv",
            source_type="csv",
        )
        mock_save_cache_entry.assert_called_once_with(
            initiative_id="housing-4",
            url="https://example.com/data.csv",
            content="KW CMA | 4.1%",
        )


if __name__ == "__main__":
    unittest.main()
