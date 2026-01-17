from __future__ import annotations

from typing import Any


def _upsert_actions(reg: dict[str, Any], new_actions: list[dict[str, Any]]) -> None:
    actions_raw = reg.get("actions")
    existing: list[dict[str, Any]] = [a for a in actions_raw if isinstance(a, dict)] if isinstance(actions_raw, list) else []
    by_id: dict[str, dict[str, Any]] = {}
    for a in existing:
        aid = a.get("action_id")
        if isinstance(aid, str) and aid:
            by_id[aid] = a

    for a in new_actions:
        if not isinstance(a, dict):
            continue
        aid = a.get("action_id")
        if not isinstance(aid, str) or not aid:
            continue
        by_id[aid] = a

    reg["actions"] = sorted(by_id.values(), key=lambda x: str(x.get("action_id") or ""))


def _add_actions(reg: dict[str, Any], new_actions: list[dict[str, Any]]) -> None:
    actions = reg.get("actions")
    if not isinstance(actions, list):
        actions = []
        reg["actions"] = actions
    existing_ids = {a.get("action_id") for a in actions if isinstance(a, dict)}
    for a in new_actions:
        if not isinstance(a, dict):
            continue
        aid = a.get("action_id")
        if not isinstance(aid, str) or not aid:
            continue
        if aid in existing_ids:
            continue
        actions.append(a)
        existing_ids.add(aid)
    actions.sort(key=lambda x: str(x.get("action_id") or ""))
