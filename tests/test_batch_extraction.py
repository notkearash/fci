"""Tests for batch extraction over cached MongoDB records."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from ui.extraction import run_extraction_for_all_cached_sources


class BatchExtractionTests(unittest.TestCase):
    @patch("ui.extraction.run_extraction_from_cache")
    @patch("ui.extraction.list_source_cache")
    def test_run_extraction_for_all_cached_sources_success(self, mock_list_source_cache, mock_run_extraction_from_cache):
        mock_list_source_cache.return_value = [
            {
                "initiative_id": "housing-4",
                "category": "Housing",
                "name": "Rental vacancy rate",
                "url": "https://example.com/a.csv",
                "source_type": "csv",
            }
        ]
        mock_run_extraction_from_cache.return_value = {
            "extracted": {
                "raw_value": "4.1%",
                "numeric_value": 4.1,
                "unit": "%",
                "context": "KW CMA row",
            }
        }

        results = run_extraction_for_all_cached_sources("housing-4", 10)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "success")
        self.assertEqual(results[0]["raw_value"], "4.1%")

    @patch("ui.extraction.run_extraction_from_cache")
    @patch("ui.extraction.list_source_cache")
    def test_run_extraction_for_all_cached_sources_captures_errors(self, mock_list_source_cache, mock_run_extraction_from_cache):
        mock_list_source_cache.return_value = [
            {
                "initiative_id": "housing-4",
                "category": "Housing",
                "name": "Rental vacancy rate",
                "url": "https://example.com/a.csv",
                "source_type": "csv",
            }
        ]
        mock_run_extraction_from_cache.side_effect = RuntimeError("bad cache")

        results = run_extraction_for_all_cached_sources("housing-4", 10)

        self.assertEqual(results[0]["status"], "error")
        self.assertIn("bad cache", results[0]["error"])


if __name__ == "__main__":
    unittest.main()
