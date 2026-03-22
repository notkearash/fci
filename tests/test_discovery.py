"""Unit tests for the discovery workflow helper."""

from __future__ import annotations

import unittest

from ui.discovery import build_discovery_state, run_discovery_step


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


if __name__ == "__main__":
    unittest.main()
