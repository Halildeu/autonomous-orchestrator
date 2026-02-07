from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _write_manual_request(ws: Path, request_id: str) -> None:
    _write_json(
        ws / ".cache" / "index" / "manual_requests" / f"{request_id}.v1.json",
        {
            "version": "v1",
            "request_id": request_id,
            "received_at": _now_iso(),
            "source": {"type": "chat"},
            "text": "Doc note",
            "kind": "note",
            "impact_scope": "doc-only",
            "requires_core_change": False,
        },
    )


def _write_autopilot_override(ws: Path) -> None:
    path = ws / ".cache" / "policy_overrides" / "policy_autopilot_apply.override.v1.json"
    payload = {
        "version": "v1",
        "defaults": {"selected_default": False, "max_apply_per_tick": 2},
        "selection_rules": [
            {
                "id": "ticket_manual_doc_only_safe",
                "when": {
                    "bucket": "TICKET",
                    "source_type": "MANUAL_REQUEST",
                    "impact_scope": "doc-only",
                    "kind_in": ["note", "doc-fix"],
                },
                "set": {
                    "autopilot_allowed": True,
                    "autopilot_reason": "DOC_ONLY_MANUAL",
                },
            }
        ],
    }
    _write_json(path, payload)


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.work_intake_autoselect import run_work_intake_autoselect
    from src.ops.work_intake_exec_ticket import run_work_intake_exec_ticket
    from src.ops.work_intake_from_sources import run_work_intake_build

    ws = repo_root / ".cache" / "ws_doer_actionability_nonzero_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    request_id = "REQ-DOER-NONZERO-1"
    _write_manual_request(ws, request_id)
    _write_autopilot_override(ws)

    run_work_intake_build(workspace_root=ws)

    autoselect = run_work_intake_autoselect(workspace_root=ws, limit=5, mode="safe_first")
    if autoselect.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("doer_actionability_nonzero_contract_test failed: autoselect status")
    if int(autoselect.get("selected_count") or 0) < 1:
        raise SystemExit("doer_actionability_nonzero_contract_test failed: no selected items")

    run_work_intake_build(workspace_root=ws)

    exec_result = run_work_intake_exec_ticket(workspace_root=ws, limit=1)
    if exec_result.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("doer_actionability_nonzero_contract_test failed: exec status")
    if int(exec_result.get("applied_count") or 0) < 1:
        raise SystemExit("doer_actionability_nonzero_contract_test failed: applied_count < 1")


if __name__ == "__main__":
    main()
