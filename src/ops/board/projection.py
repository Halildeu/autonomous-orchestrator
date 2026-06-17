from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from src.ops.board.drift import derive_projection_drift, summarize_drift
from src.ops.board.fixtures import load_fixture
from src.ops.board.reports import now_iso


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_schema() -> dict[str, Any]:
    path = _repo_root() / "schemas" / "board-projection.schema.v1.json"
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _schema_errors(projection: dict[str, Any]) -> list[str]:
    schema = _load_schema()
    if not schema:
        return ["board projection schema not found or invalid"]
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(projection), key=lambda err: err.json_path)
    return [f"{err.json_path or '$'}: {err.message}" for err in errors]


def _blocked_wrapper(*, mode: str, reason: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    wrapper = {
        "version": "v1",
        "command": "board-projection",
        "mode": mode,
        "status": "BLOCKED",
        "projection_path": "",
        "drift_summary": {"total": 0, "by_severity": {"ERROR": 0, "WARN": 0, "INFO": 0}, "by_code": {}, "max_severity": "OK"},
        "applied_actions": [],
        "blocked_reasons": [reason],
        "evidence": {
            "source": [],
            "desired_state": [],
            "runtime_live": [],
            "browser_user_path": [],
            "does_not_prove": [
                "Live GitHub Project mutation has not been applied.",
                "Projection apply remains blocked until BOG-5C."
            ],
        },
    }
    return (wrapper, None)


def build_projection_from_fixture(*, fixture_path: str, mode: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Build a schema-valid board projection from a local fixture and summarize drift."""
    if mode == "apply":
        return _blocked_wrapper(mode=mode, reason="APPLY_MODE_NOT_AVAILABLE_UNTIL_BOG_5C")
    if mode not in {"report", "dry-run"}:
        return _blocked_wrapper(mode=mode, reason=f"invalid mode: {mode}")
    fixture, error = load_fixture(fixture_path)
    if error:
        wrapper, _projection = _blocked_wrapper(mode=mode, reason=error)
        wrapper["status"] = "ERROR"
        return (wrapper, None)
    projection = copy.deepcopy(fixture)
    projection["mode"] = mode
    projection["generated_at"] = now_iso()
    evidence = projection.setdefault("evidence", {})
    if isinstance(evidence, dict):
        source = evidence.setdefault("source", [])
        if isinstance(source, list) and fixture_path and fixture_path not in source:
            source.append(fixture_path)
        does_not = evidence.setdefault("does_not_prove", [])
        if isinstance(does_not, list):
            for note in (
                "Live GitHub Project mutation has not been applied.",
                "Operator-bound sync apply is not enabled.",
            ):
                if note not in does_not:
                    does_not.append(note)
    schema_errors = _schema_errors(projection)
    if schema_errors:
        wrapper, _projection = _blocked_wrapper(mode=mode, reason="BOARD_PROJECTION_SCHEMA_INVALID")
        wrapper["status"] = "ERROR"
        wrapper["schema_errors"] = schema_errors
        return (wrapper, projection)
    drift = derive_projection_drift(projection)
    projection["drift"] = drift
    summary = summarize_drift(drift)
    status = "OK" if not drift else "WARN"
    wrapper = {
        "version": "v1",
        "command": "board-projection",
        "mode": mode,
        "status": status,
        "projection_path": "",
        "drift_summary": summary,
        "applied_actions": [],
        "blocked_reasons": [],
        "evidence": {
            "source": [fixture_path] if fixture_path else [],
            "desired_state": ["schemas/board-projection.schema.v1.json"],
            "runtime_live": [],
            "browser_user_path": [],
            "does_not_prove": [
                "Live GitHub Project mutation has not been applied.",
                "Runtime acceptance is not proven by projection dry-run.",
                "Operator-bound sync apply remains deferred until BOG-5C.",
            ],
        },
    }
    return (wrapper, projection)

