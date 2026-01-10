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
            "created_at": _now_iso(),
            "source": {"type": "chat", "channel": "contract"},
            "artifact_type": "request",
            "domain": "general",
            "kind": "note",
            "impact_scope": "doc-only",
            "requires_core_change": False,
            "text": "contract",
            "attachments": [],
        },
    )


def _write_work_intake(ws: Path, item: dict) -> None:
    summary = {
        "total_count": 1,
        "counts_by_bucket": {"ROADMAP": 0, "PROJECT": 0, "TICKET": 1, "INCIDENT": 0},
        "top_next_actions": [
            {
                "intake_id": item["intake_id"],
                "bucket": item["bucket"],
                "severity": item["severity"],
                "priority": item["priority"],
                "status": item["status"],
                "title": item["title"],
                "source_type": item["source_type"],
                "source_ref": item["source_ref"],
            }
        ],
        "next_intake_focus": "TICKET_TOP3",
    }
    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(ws),
        "status": "OK",
        "plan_policy": "optional",
        "items": [item],
        "summary": summary,
        "notes": ["PROGRAM_LED=true"],
    }
    _write_json(ws / ".cache" / "index" / "work_intake.v1.json", payload)


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.decision_inbox import run_decision_apply
    from src.ops.work_intake_exec_ticket import run_work_intake_exec_ticket

    ws = repo_root / ".cache" / "ws_decision_loop_close_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    _write_manual_request(ws, "REQ-DECIDE-1")
    item = {
        "intake_id": "INTAKE-DECIDE-1",
        "bucket": "TICKET",
        "severity": "S3",
        "priority": "P3",
        "status": "OPEN",
        "title": "Decision required note",
        "source_type": "MANUAL_REQUEST",
        "source_ref": "REQ-DECIDE-1",
        "evidence_paths": [],
        "owner_tenant": "CORE",
        "layer": "L2",
        "autopilot_allowed": False,
        "autopilot_selected": True,
    }
    _write_work_intake(ws, item)

    run_work_intake_exec_ticket(workspace_root=ws, limit=1)
    inbox = json.loads((ws / ".cache" / "index" / "decision_inbox.v1.json").read_text(encoding="utf-8"))
    decision_id = inbox["items"][0]["decision_id"]
    run_decision_apply(workspace_root=ws, decision_id=decision_id, option_id="B")

    res2 = run_work_intake_exec_ticket(workspace_root=ws, limit=1)
    if int(res2.get("applied_count") or 0) < 1:
        raise SystemExit("decision_loop_close_contract_test failed: expected applied after decision")


if __name__ == "__main__":
    main()
