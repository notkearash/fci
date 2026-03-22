"""Tests for multi-source retrieval auditing."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from ui.extraction import audit_discovered_source_retrieval


class RetrievalAuditTests(unittest.TestCase):
    @patch("ui.extraction.save_cache_entry")
    @patch("ui.extraction.fetch_source_content_for_cache")
    @patch("ui.extraction.get_cached_source_content")
    @patch("ui.extraction.list_discovered_sources")
    def test_audit_uses_cache_when_present(
        self,
        mock_list_discovered_sources,
        mock_get_cached_source_content,
        mock_fetch_source_content_for_cache,
        mock_save_cache_entry,
    ):
        mock_list_discovered_sources.return_value = [
            {
                "initiative_id": "housing-4",
                "category": "Housing",
                "name": "Rental vacancy rate",
                "url": "https://example.com/data.csv",
                "source_type": "csv",
            }
        ]
        mock_get_cached_source_content.return_value = {"content": "cached body"}

        results = audit_discovered_source_retrieval("housing-4", 10)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "success")
        self.assertEqual(results[0]["cache_status"], "cache_hit")
        mock_fetch_source_content_for_cache.assert_not_called()
        mock_save_cache_entry.assert_not_called()

    @patch("ui.extraction.save_cache_entry")
    @patch("ui.extraction.fetch_source_content_for_cache")
    @patch("ui.extraction.get_cached_source_content")
    @patch("ui.extraction.list_discovered_sources")
    def test_audit_fetches_and_caches_when_missing(
        self,
        mock_list_discovered_sources,
        mock_get_cached_source_content,
        mock_fetch_source_content_for_cache,
        mock_save_cache_entry,
    ):
        mock_list_discovered_sources.return_value = [
            {
                "initiative_id": "housing-4",
                "category": "Housing",
                "name": "Rental vacancy rate",
                "url": "https://example.com/data.csv",
                "source_type": "csv",
            }
        ]
        mock_get_cached_source_content.return_value = None
        mock_fetch_source_content_for_cache.return_value = "fresh body"

        results = audit_discovered_source_retrieval("housing-4", 10)

        self.assertEqual(results[0]["cache_status"], "fetched_and_cached")
        self.assertEqual(results[0]["content_length"], len("fresh body"))
        mock_save_cache_entry.assert_called_once()

    @patch("ui.extraction.fetch_source_content_for_cache")
    @patch("ui.extraction.get_cached_source_content")
    @patch("ui.extraction.list_discovered_sources")
    def test_audit_records_errors(
        self,
        mock_list_discovered_sources,
        mock_get_cached_source_content,
        mock_fetch_source_content_for_cache,
    ):
        mock_list_discovered_sources.return_value = [
            {
                "initiative_id": "housing-4",
                "category": "Housing",
                "name": "Rental vacancy rate",
                "url": "https://bad.example/data.csv",
                "source_type": "csv",
            }
        ]
        mock_get_cached_source_content.return_value = None
        mock_fetch_source_content_for_cache.side_effect = RuntimeError("network failed")

        results = audit_discovered_source_retrieval("housing-4", 10)

        self.assertEqual(results[0]["status"], "error")
        self.assertIn("network failed", results[0]["error"])


if __name__ == "__main__":
    unittest.main()
