from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def script_budget_actions_from_report(core_root: Path) -> list[dict[str, Any]] | None:
    path = core_root / ".cache" / "script_budget" / "report.json"
    if not path.exists():
        return None
    try:
        obj = _load_json(path)
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None

    exceeded_hard = obj.get("exceeded_hard") if isinstance(obj.get("exceeded_hard"), list) else []
    exceeded_soft = obj.get("exceeded_soft") if isinstance(obj.get("exceeded_soft"), list) else []
    function_hard = obj.get("function_hard") if isinstance(obj.get("function_hard"), list) else []
    function_soft = obj.get("function_soft") if isinstance(obj.get("function_soft"), list) else []

    actions: list[dict[str, Any]] = []

    def _message(entry: dict[str, Any], *, severity: str, is_function: bool) -> str:
        path_val = str(entry.get("path") or "")
        qual = str(entry.get("qualname") or "") if is_function else ""
        lines = entry.get("lines")
        soft = entry.get("soft")
        hard = entry.get("hard")
        severity_label = "hard" if severity == "FAIL" else "soft"
        target = f"{path_val}::{qual}" if qual else path_val
        message = f"Script budget {severity_label} limit exceeded: {target}"
        if lines is not None:
            message += f" lines={lines}"
        if soft is not None:
            message += f" soft={soft}"
        if hard is not None:
            message += f" hard={hard}"
        return message

    def _action_id(path_val: str, qual: str, severity: str) -> str:
        digest = sha256(f"SCRIPT_BUDGET|{path_val}|{qual}|{severity}".encode("utf-8")).hexdigest()
        return digest[:16]

    def _add(entries: list[dict[str, Any]], *, severity: str, is_function: bool) -> None:
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            path_val = str(entry.get("path") or "").strip()
            if not path_val:
                continue
            qual = str(entry.get("qualname") or "").strip() if is_function else ""
            actions.append(
                {
                    "action_id": _action_id(path_val, qual, severity),
                    "severity": severity,
                    "kind": "SCRIPT_BUDGET",
                    "milestone_hint": "M0",
                    "message": _message(entry, severity=severity, is_function=is_function),
                }
            )

    _add(exceeded_hard, severity="FAIL", is_function=False)
    _add(function_hard, severity="FAIL", is_function=True)
    _add(exceeded_soft, severity="WARN", is_function=False)
    _add(function_soft, severity="WARN", is_function=True)

    actions.sort(key=lambda x: str(x.get("action_id") or ""))
    return actions
