"""Unit tests for the discovery workflow helper."""

from __future__ import annotations

import unittest

from ui.discovery import (
    DEFAULT_SECTION_INITIATIVES,
    build_tavily_query,
    build_discovery_state,
    run_discovery_batch,
    run_discovery_step,
    run_tavily_only_batch,
    run_tavily_only_search,
)


class DiscoveryWorkflowTests(unittest.TestCase):
    def test_build_discovery_state_sets_expected_defaults(self):
        state = build_discovery_state(
            initiative_id="housing-4",
            category="Housing",
            name="Rental vacancy rate",
            metric_label="Rental vacancy rate",
            target_value="3%",
        )

        self.assertEqual(state["initiative"]["id"], "housing-4")
        self.assertEqual(state["sources"], [])
        self.assertEqual(state["retry_count"], 0)
        self.assertEqual(state["status"], "NO_ASSESSMENT")

    def test_run_discovery_step_returns_runner_result(self):
        def fake_runner(state):
            return {
                **state,
                "sources": [
                    {
                        "url": "https://example.com/data.csv",
                        "source_type": "csv",
                        "description": "Example dataset",
                    }
                ],
            }

        result = run_discovery_step(
            initiative_id="housing-4",
            category="Housing",
            name="Rental vacancy rate",
            metric_label="Rental vacancy rate",
            target_value="3%",
            runner=fake_runner,
        )

        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(result["sources"][0]["url"], "https://example.com/data.csv")
        self.assertEqual(result["sources"][0]["source_type"], "csv")

    def test_run_discovery_batch_runs_all_default_sections(self):
        seen = []

        def fake_runner(state):
            seen.append(state["initiative"]["category"])
            return {
                **state,
                "sources": [{"url": f"https://example.com/{state['initiative']['id']}"}],
            }

        results = run_discovery_batch(runner=fake_runner)

        self.assertEqual(len(results), 5)
        self.assertEqual(len(seen), 5)
        self.assertEqual(seen, [item["category"] for item in DEFAULT_SECTION_INITIATIVES])

    def test_build_tavily_query_includes_region_terms(self):
        query = build_tavily_query(
            category="Housing",
            name="Rental vacancy rate",
            metric_label="Rental vacancy rate",
        )

        self.assertIn("Waterloo Region", query)
        self.assertIn("Ontario", query)
        self.assertIn("data source", query)

    def test_run_tavily_only_search_bypasses_predefined_and_returns_candidates(self):
        def fake_search(query, max_results):
            self.assertIn("Waterloo Region", query)
            self.assertEqual(max_results, 5)
            return [
                {"title": "A", "url": "https://example.com/a"},
                {"title": "B", "url": "https://example.com/b"},
                {"title": "C", "url": "https://example.com/c"},
                {"title": "D", "url": "https://example.com/d"},
                {"title": "E", "url": "https://example.com/e"},
            ]

        result = run_tavily_only_search(
            initiative_id="housing-4",
            category="Housing",
            name="Rental vacancy rate",
            metric_label="Rental vacancy rate",
            target_value="3%",
            search_fn=fake_search,
        )

        self.assertFalse(result["used_predefined_sources"])
        self.assertEqual(result["source_count"], 5)
        self.assertEqual(len(result["sources"]), 5)

    def test_run_tavily_only_batch_runs_all_default_sections(self):
        seen = []

        def fake_search(query, max_results):
            seen.append((query, max_results))
            return [{"title": "A", "url": "https://example.com/a"}] * 5

        results = run_tavily_only_batch(search_fn=fake_search)

        self.assertEqual(len(results), 5)
        self.assertEqual(len(seen), 5)
        self.assertTrue(all(item["source_count"] == 5 for item in results))


if __name__ == "__main__":
    unittest.main()
