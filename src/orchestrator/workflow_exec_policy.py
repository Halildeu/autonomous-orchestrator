from __future__ import annotations

from pathlib import Path
from typing import Any


def read_approval_threshold(decision_policy_path: Path, *, default: float = 0.7) -> float:
    if not decision_policy_path.exists():
        return default
    try:
        import json

        raw = json.loads(decision_policy_path.read_text(encoding="utf-8"))
    except Exception:
        return default

    v = raw.get("approval_risk_threshold", default)
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f < 0 or f > 1:
        return default
    return f


def _load_module_capabilities(workspace: Path) -> dict[str, dict[str, Any]]:
    reg_path = workspace / "registry" / "registry.v1.json"
    try:
        import json

        raw = json.loads(reg_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    modules = raw.get("modules")
    if not isinstance(modules, list):
        return {}

    out: dict[str, dict[str, Any]] = {}
    for m in modules:
        if not isinstance(m, dict):
            continue
        module_id = m.get("id")
        if not isinstance(module_id, str) or not module_id:
            continue

        allowed = m.get("allowed_tools", [])
        allowed_tools = [t for t in allowed if isinstance(t, str)] if isinstance(allowed, list) else []
        out[module_id] = {"allowed_tools": allowed_tools}
    return out
