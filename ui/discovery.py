"""Helpers for running the discovery step in isolation."""

from __future__ import annotations

from collections.abc import Callable

from dotenv import load_dotenv

from schema.graph import PipelineState
from schema.state import Initiative


load_dotenv()


def build_discovery_state(
    initiative_id: str,
    category: str,
    name: str,
    metric_label: str,
    target_value: str,
) -> PipelineState:
    initiative = Initiative(
        id=initiative_id,
        category=category,
        name=name,
        metric_label=metric_label,
        target_value=target_value,
    )
    return {
        "initiative": initiative.model_dump(),
        "sources": [],
        "extracted": [],
        "is_valid": False,
        "validation_errors": [],
        "retry_count": 0,
        "status": "NO_ASSESSMENT",
        "status_reasoning": "",
        "error": "",
    }


def run_discovery_step(
    initiative_id: str,
    category: str,
    name: str,
    metric_label: str,
    target_value: str,
    runner: Callable[[PipelineState], PipelineState] | None = None,
) -> PipelineState:
    state = build_discovery_state(
        initiative_id=initiative_id,
        category=category,
        name=name,
        metric_label=metric_label,
        target_value=target_value,
    )
    if runner is None:
        from agents.discovery import run_discovery

        runner = run_discovery
    return runner(state)
