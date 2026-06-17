from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.board.models import BOARD_TITLE_DEFAULT, EVIDENCE_DOES_NOT_PROVE
from src.shared.utils import write_json_atomic


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def base_report(
    *,
    command: str,
    mode: str,
    repo: str,
    board_title: str,
    inputs: dict[str, Any],
) -> dict[str, Any]:
    started_at = now_iso()
    return {
        "version": "v1",
        "command": command,
        "mode": mode,
        "status": "OK",
        "repo": repo,
        "board_title": board_title or BOARD_TITLE_DEFAULT,
        "started_at": started_at,
        "completed_at": started_at,
        "inputs": inputs,
        "findings": [],
        "planned_actions": [],
        "applied_actions": [],
        "blocked_reasons": [],
        "evidence": {
            "source": [],
            "desired_state": [],
            "runtime_live": [],
            "browser_user_path": [],
            "does_not_prove": list(EVIDENCE_DOES_NOT_PROVE),
        },
    }


def finish_report(payload: dict[str, Any], *, status: str | None = None) -> dict[str, Any]:
    payload["completed_at"] = now_iso()
    if status:
        payload["status"] = status
    if payload.get("mode") != "apply":
        payload["applied_actions"] = []
    evidence = payload.setdefault("evidence", {})
    if not isinstance(evidence.get("does_not_prove"), list) or not evidence.get("does_not_prove"):
        evidence["does_not_prove"] = list(EVIDENCE_DOES_NOT_PROVE)
    return payload


def write_report(*, workspace_root: Path, out_value: str, payload: dict[str, Any]) -> str:
    rel = Path(out_value)
    if rel.is_absolute():
        out_path = rel.resolve()
    else:
        out_path = (workspace_root / rel).resolve()
    out_path.relative_to(workspace_root.resolve())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(out_path, payload)
    try:
        return out_path.relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        return out_path.as_posix()


def dump_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)

