"""Comprehensive unit tests for the discovery node."""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agents.discovery import (
    create_discovery_agent,
    format_discovery_result,
    run_discovery,
)


class FakeAgent:
    def __init__(self, messages):
        self._messages = messages
        self.invocations = []

    def invoke(self, payload):
        self.invocations.append(payload)
        return {"messages": self._messages}


def build_state(**overrides):
    state = {
        "initiative": {
            "id": "housing-4",
            "category": "Housing",
            "name": "Rental vacancy rate",
            "metric_label": "Rental vacancy rate",
            "target_value": "3%",
        },
        "sources": [],
        "extracted": [],
        "is_valid": False,
        "validation_errors": [],
        "retry_count": 0,
        "status": "NO_ASSESSMENT",
        "status_reasoning": "",
        "error": "",
    }
    state.update(overrides)
    return state


class DiscoveryToolTests(unittest.TestCase):
    def test_format_discovery_result_returns_expected_json(self):
        result = format_discovery_result.invoke(
            {
                "url": "https://example.com/data.csv",
                "source_type": "csv",
                "description": "Example dataset",
            }
        )

        self.assertEqual(
            json.loads(result),
            {
                "url": "https://example.com/data.csv",
                "source_type": "csv",
                "description": "Example dataset",
            },
        )


class DiscoveryNodeTests(unittest.TestCase):
    @patch("agents.discovery.create_discovery_agent")
    @patch("agents.discovery.save_discovered_sources")
    def test_run_discovery_parses_single_source_object(self, mock_save_sources, mock_create_agent):
        mock_save_sources.return_value = 1
        agent = FakeAgent(
            [
                SimpleNamespace(content="not-json"),
                SimpleNamespace(
                    content=json.dumps(
                        {
                            "url": "https://example.com/data.csv",
                            "source_type": "csv",
                            "description": "Example dataset",
                        }
                    )
                ),
            ]
        )
        mock_create_agent.return_value = agent

        result = run_discovery(build_state())

        self.assertEqual(
            result["sources"],
            [
                {
                    "url": "https://example.com/data.csv",
                    "source_type": "csv",
                    "description": "Example dataset",
                }
            ],
        )
        mock_save_sources.assert_called_once()

    @patch("agents.discovery.create_discovery_agent")
    @patch("agents.discovery.save_discovered_sources")
    def test_run_discovery_parses_list_of_sources(self, mock_save_sources, mock_create_agent):
        mock_save_sources.return_value = 2
        agent = FakeAgent(
            [
                SimpleNamespace(
                    content=json.dumps(
                        [
                            {
                                "url": "https://example.com/one.csv",
                                "source_type": "csv",
                                "description": "Primary source",
                            },
                            {
                                "url": "https://example.com/two.xlsx",
                                "source_type": "xlsx",
                                "description": "Fallback source",
                            },
                        ]
                    )
                )
            ]
        )
        mock_create_agent.return_value = agent

        result = run_discovery(build_state())

        self.assertEqual(len(result["sources"]), 2)
        self.assertEqual(result["sources"][1]["source_type"], "xlsx")
        mock_save_sources.assert_called_once()

    @patch("agents.discovery.create_discovery_agent")
    @patch("agents.discovery.save_discovered_sources")
    def test_run_discovery_returns_empty_sources_when_no_json_payload_found(self, mock_save_sources, mock_create_agent):
        agent = FakeAgent(
            [
                SimpleNamespace(content="plain text"),
                SimpleNamespace(content=None),
                SimpleNamespace(content="still not json"),
            ]
        )
        mock_create_agent.return_value = agent

        result = run_discovery(build_state())

        self.assertEqual(result["sources"], [])
        mock_save_sources.assert_not_called()

    @patch("agents.discovery.create_discovery_agent")
    @patch("agents.discovery.save_discovered_sources")
    def test_run_discovery_includes_retry_context_in_prompt(self, mock_save_sources, mock_create_agent):
        mock_save_sources.return_value = 1
        agent = FakeAgent(
            [
                SimpleNamespace(
                    content=json.dumps(
                        {
                            "url": "https://example.com/retry.csv",
                            "source_type": "csv",
                            "description": "Retry source",
                        }
                    )
                )
            ]
        )
        mock_create_agent.return_value = agent

        state = build_state(
            retry_count=1,
            validation_errors=["No data extracted", "Empty raw_value"],
        )
        run_discovery(state)

        sent_task = agent.invocations[0]["messages"][0][1]
        self.assertIn("Previous attempt failed with:", sent_task)
        self.assertIn("No data extracted", sent_task)
        self.assertIn("Empty raw_value", sent_task)
        mock_save_sources.assert_called_once()

    @patch("agents.discovery.create_react_agent")
    @patch("agents.discovery.get_llm")
    def test_create_discovery_agent_wires_expected_prompt_and_tools(
        self,
        mock_get_llm,
        mock_create_react_agent,
    ):
        llm = object()
        mock_get_llm.return_value = llm
        mock_create_react_agent.return_value = "agent"

        result = create_discovery_agent()

        self.assertEqual(result, "agent")
        mock_create_react_agent.assert_called_once()
        args, kwargs = mock_create_react_agent.call_args
        self.assertIs(args[0], llm)
        self.assertEqual(len(args[1]), 4)
        self.assertIn("prompt", kwargs)


if __name__ == "__main__":
    unittest.main()
