from __future__ import annotations

import argparse
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
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.commands.maintenance_cmds import cmd_work_intake_select
    from src.ops.work_intake_exec_ticket import run_work_intake_exec_ticket
    from src.ops.work_intake_from_sources import run_work_intake_build, _intake_id

    ws = repo_root / ".cache" / "ws_single_trace_stale"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    request_id = "REQ-TRACE-STALE-001"
    manual_request = {
        "version": "v1",
        "request_id": request_id,
        "received_at": _now_iso(),
        "source": {"type": "chat"},
        "text": "Doc note",
        "kind": "note",
        "impact_scope": "doc-only",
        "requires_core_change": False,
    }
    _write_json(ws / ".cache" / "index" / "manual_requests" / f"{request_id}.v1.json", manual_request)

    res = run_work_intake_build(workspace_root=ws)
    if res.get("status") not in {"OK", "WARN"}:
        raise SystemExit("single_trace_stale_clear_contract_test failed: build status")

    intake_id = _intake_id("MANUAL_REQUEST", request_id, "TICKET")
    cmd_work_intake_select(
        argparse.Namespace(
            workspace_root=str(ws),
            intake_id=intake_id,
            selected="true",
        )
    )
    res2 = run_work_intake_build(workspace_root=ws)
    if res2.get("status") not in {"OK", "WARN"}:
        raise SystemExit("single_trace_stale_clear_contract_test failed: rebuild status")

    lease_payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(ws),
        "leases": [
            {
                "work_item_id": intake_id,
                "lease_id": "lease-stale-test",
                "owner": "test",
                "run_id": "run-stale",
                "expires_at": "2000-01-01T00:00:00Z",
                "heartbeat_at": "2000-01-01T00:00:00Z",
            }
        ],
    }
    _write_json(ws / ".cache" / "index" / "work_item_leases.v1.json", lease_payload)

    run_work_intake_exec_ticket(workspace_root=ws, limit=1)
    stale_report_path = ws / ".cache" / "reports" / "work_item_lease_stale_clear.v1.json"
    if not stale_report_path.exists():
        raise SystemExit("single_trace_stale_clear_contract_test failed: stale clear report missing")
    report = json.loads(stale_report_path.read_text(encoding="utf-8"))
    cleared = report.get("cleared") if isinstance(report.get("cleared"), list) else []
    if not any(isinstance(item, dict) and item.get("work_item_id") == intake_id for item in cleared):
        raise SystemExit("single_trace_stale_clear_contract_test failed: cleared item missing")


if __name__ == "__main__":
    main()
