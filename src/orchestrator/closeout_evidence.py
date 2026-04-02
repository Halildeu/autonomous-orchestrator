from __future__ import annotations

from typing import Any


def _append_path(paths: list[str], seen: set[str], value: Any) -> None:
    if not isinstance(value, str):
        return
    normalized = value.strip()
    if not normalized or normalized in seen:
        return
    seen.add(normalized)
    paths.append(normalized)


def _collect_touched_paths(nodes: list[dict[str, Any]]) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict):
            continue
        output = node.get("output") if isinstance(node.get("output"), dict) else {}
        side_effects = output.get("side_effects") if isinstance(output.get("side_effects"), dict) else {}
        for effect_key in ("wrote", "would_write"):
            effect = side_effects.get(effect_key)
            if isinstance(effect, dict):
                _append_path(paths, seen, effect.get("target_path"))
        tool_calls = output.get("tool_calls") if isinstance(output.get("tool_calls"), list) else []
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue
            args_summary = tool_call.get("args_summary") if isinstance(tool_call.get("args_summary"), dict) else {}
            _append_path(paths, seen, args_summary.get("resolved_path"))
    return paths


def build_closeout_envelope(
    *,
    run_id: str,
    result_state: str,
    nodes: list[dict[str, Any]] | None,
    execution_target_guard: dict[str, Any] | None = None,
    execution_target: dict[str, Any] | None = None,
    replay_of: str | None = None,
) -> dict[str, Any]:
    guard = execution_target_guard if isinstance(execution_target_guard, dict) else {}
    if isinstance(guard.get("target_evidence"), dict):
        target = dict(guard.get("target_evidence") or {})
    elif isinstance(execution_target, dict):
        target = dict(execution_target)
    else:
        target = {}

    warnings = guard.get("warnings") if isinstance(guard.get("warnings"), list) else []
    warning_codes = [
        str(item.get("code") or "").strip()
        for item in warnings
        if isinstance(item, dict) and str(item.get("code") or "").strip()
    ]
    block = guard.get("block") if isinstance(guard.get("block"), dict) else {}
    touched_paths = _collect_touched_paths(nodes if isinstance(nodes, list) else [])

    closeout = {
        "version": "v1",
        "kind": "closeout-envelope",
        "run_id": run_id,
        "result_state": str(result_state or "").strip(),
        "guard_status": str(guard.get("status") or "").strip() if guard else "",
        "warning_codes": warning_codes,
        "block_code": str(block.get("code") or "").strip() if block else None,
        "execution_target": target,
        "touched_paths": touched_paths,
    }
    if isinstance(replay_of, str) and replay_of.strip():
        closeout["replay_of"] = replay_of.strip()
    return closeout


def closeout_summary_fields(closeout: dict[str, Any]) -> dict[str, Any]:
    execution_target = closeout.get("execution_target") if isinstance(closeout.get("execution_target"), dict) else {}
    touched_paths = closeout.get("touched_paths") if isinstance(closeout.get("touched_paths"), list) else []
    return {
        "execution_target": execution_target,
        "closeout_ref": "closeout.v1.json",
        "closeout_guard_status": str(closeout.get("guard_status") or "").strip(),
        "touched_paths": touched_paths,
    }
