from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.utils.jsonio import load_json


@dataclass(frozen=True)
class StrategyTable:
    version: str
    intent_to_workflow: dict[str, str]


def load_strategy_table(path: Path) -> StrategyTable:
    raw = load_json(path)
    version = str(raw.get("version", ""))
    routes = raw.get("routes", [])
    if not isinstance(routes, list):
        raise ValueError("Invalid strategy table: routes must be a list.")

    mapping: dict[str, str] = {}
    for idx, row in enumerate(routes):
        if not isinstance(row, dict):
            raise ValueError(f"Invalid strategy table: routes[{idx}] must be an object.")
        intent = row.get("intent")
        workflow_id = row.get("workflow_id")
        if not isinstance(intent, str) or not intent:
            raise ValueError(f"Invalid strategy table: routes[{idx}].intent must be a non-empty string.")
        if not isinstance(workflow_id, str) or not workflow_id:
            raise ValueError(
                f"Invalid strategy table: routes[{idx}].workflow_id must be a non-empty string."
            )
        mapping[intent] = workflow_id

    return StrategyTable(version=version, intent_to_workflow=mapping)


def route_intent(strategy_table: StrategyTable, intent: str) -> str | None:
    return strategy_table.intent_to_workflow.get(intent)

