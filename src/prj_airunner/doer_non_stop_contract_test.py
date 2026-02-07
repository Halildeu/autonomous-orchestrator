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


def _write_manual_request(ws: Path, request_id: str, kind: str) -> None:
    _write_json(
        ws / ".cache" / "index" / "manual_requests" / f"{request_id}.v1.json",
        {
            "version": "v1",
            "request_id": request_id,
            "created_at": _now_iso(),
            "source": {"type": "chat", "channel": "contract"},
            "artifact_type": "request",
            "domain": "general",
            "kind": kind,
            "impact_scope": "doc-only",
            "requires_core_change": False,
            "text": "contract",
            "attachments": [],
        },
    )


def _write_work_intake(ws: Path, items: list[dict]) -> None:
    counts = {"ROADMAP": 0, "PROJECT": 0, "TICKET": 0, "INCIDENT": 0}
    for item in items:
        bucket = str(item.get("bucket") or "")
        if bucket in counts:
            counts[bucket] += 1
    summary = {
        "total_count": len(items),
        "counts_by_bucket": counts,
        "top_next_actions": [
            {
                "intake_id": i["intake_id"],
                "bucket": i["bucket"],
                "severity": i["severity"],
                "priority": i["priority"],
                "status": i["status"],
                "title": i["title"],
                "source_type": i["source_type"],
                "source_ref": i["source_ref"],
            }
            for i in items[:5]
        ],
        "next_intake_focus": "TICKET_TOP3",
    }
    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(ws),
        "status": "OK",
        "plan_policy": "optional",
        "items": items,
        "summary": summary,
        "notes": ["PROGRAM_LED=true"],
    }
    _write_json(ws / ".cache" / "index" / "work_intake.v1.json", payload)


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.work_intake_exec_ticket import run_work_intake_exec_ticket

    ws = repo_root / ".cache" / "ws_doer_non_stop_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    _write_manual_request(ws, "REQ-DOER-1", "note")
    _write_manual_request(ws, "REQ-DOER-2", "note")

    items = [
        {
            "intake_id": "INTAKE-DOER-1",
            "bucket": "TICKET",
            "severity": "S3",
            "priority": "P3",
            "status": "OPEN",
            "title": "Doc-only note",
            "source_type": "MANUAL_REQUEST",
            "source_ref": "REQ-DOER-1",
            "evidence_paths": [],
            "owner_tenant": "CORE",
            "layer": "L2",
            "autopilot_allowed": True,
            "autopilot_selected": True,
            "autopilot_reason": "DOC_ONLY",
        },
        {
            "intake_id": "INTAKE-DOER-2",
            "bucket": "TICKET",
            "severity": "S2",
            "priority": "P2",
            "status": "OPEN",
            "title": "Needs decision",
            "source_type": "MANUAL_REQUEST",
            "source_ref": "REQ-DOER-2",
            "evidence_paths": [],
            "owner_tenant": "CORE",
            "layer": "L2",
            "autopilot_allowed": False,
            "autopilot_selected": True,
            "autopilot_reason": "DECISION_NEEDED",
        },
        {
            "intake_id": "INTAKE-DOER-3",
            "bucket": "TICKET",
            "severity": "S3",
            "priority": "P4",
            "status": "OPEN",
            "title": "Network blocked job",
            "source_type": "JOB_STATUS",
            "source_ref": "JOB-1",
            "evidence_paths": [],
            "owner_tenant": "CORE",
            "layer": "L2",
            "autopilot_allowed": False,
            "autopilot_selected": True,
            "autopilot_reason": "NETWORK_DISABLED",
        },
        {
            "intake_id": "INTAKE-DOER-4",
            "bucket": "TICKET",
            "severity": "S3",
            "priority": "P4",
            "status": "OPEN",
            "title": "Not selected",
            "source_type": "MANUAL_REQUEST",
            "source_ref": "REQ-DOER-1",
            "evidence_paths": [],
            "owner_tenant": "CORE",
            "layer": "L2",
            "autopilot_allowed": True,
            "autopilot_selected": False,
        },
    ]
    _write_work_intake(ws, items)

    result = run_work_intake_exec_ticket(workspace_root=ws, limit=3)
    if result.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("doer_non_stop_contract_test failed: exec status invalid")

    report_path = ws / ".cache" / "reports" / "work_intake_exec_ticket.v1.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if int(report.get("applied_count") or 0) < 1:
        raise SystemExit("doer_non_stop_contract_test failed: expected applied_count >= 1")
    if int(report.get("ignored_count") or 0) < 1:
        raise SystemExit("doer_non_stop_contract_test failed: expected ignored_count >= 1")
    if int(report.get("skipped_count") or 0) < 2:
        raise SystemExit("doer_non_stop_contract_test failed: expected skipped_count >= 2")
    if int(report.get("decision_needed_count") or 0) != 1:
        raise SystemExit("doer_non_stop_contract_test failed: decision_needed_count mismatch")

    skipped = report.get("skipped_by_reason") if isinstance(report.get("skipped_by_reason"), dict) else {}
    if "DECISION_NEEDED" not in skipped or "NETWORK_BLOCKED" not in skipped:
        raise SystemExit("doer_non_stop_contract_test failed: skipped_by_reason missing")
    ignored = report.get("ignored_by_reason") if isinstance(report.get("ignored_by_reason"), dict) else {}
    if "NOT_SELECTED" not in ignored:
        raise SystemExit("doer_non_stop_contract_test failed: ignored_by_reason missing")

    decision_inbox = ws / ".cache" / "index" / "decision_inbox.v1.json"
    if not decision_inbox.exists():
        raise SystemExit("doer_non_stop_contract_test failed: decision_inbox missing")


if __name__ == "__main__":
    main()
