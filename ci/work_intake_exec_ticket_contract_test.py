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
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.commands.maintenance_cmds import cmd_work_intake_select
    from src.ops.work_intake_exec_ticket import run_work_intake_exec_ticket
    from src.ops.work_intake_from_sources import _intake_id, run_work_intake_build

    ws = repo_root / ".cache" / "ws_intake_exec_ticket_test"
    if ws.exists():
        shutil.rmtree(ws)

    manual_dir = ws / ".cache" / "index" / "manual_requests"
    manual_dir.mkdir(parents=True, exist_ok=True)
    request_id = "REQ-TEST-NOTE"
    manual_request = {
        "version": "v1",
        "request_id": request_id,
        "created_at": _now_iso(),
        "source": {"type": "human"},
        "artifact_type": "request",
        "domain": "general",
        "kind": "note",
        "impact_scope": "doc-only",
        "text": "Deterministic note for exec ticket contract test.",
    }
    _write_json(manual_dir / f"{request_id}.v1.json", manual_request)
    _write_json(
        ws / ".cache" / "index" / "workspace_repo_binding.v1.json",
        {
            "version": "v1",
            "kind": "workspace-repo-binding",
            "generated_at": _now_iso(),
            "workspace_root": str(ws.resolve()),
            "repo_root": str(repo_root.resolve()),
            "repo_slug": "autonomous-orchestrator",
            "repo_id": "orchestrator-self",
            "source": "contract_test",
        },
    )

    build_result = run_work_intake_build(workspace_root=ws)
    if build_result.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("work_intake_exec_ticket_contract_test failed: intake build status invalid.")
    intake_id = _intake_id("MANUAL_REQUEST", request_id, "TICKET")
    cmd_work_intake_select(
        argparse.Namespace(
            workspace_root=str(ws),
            intake_id=intake_id,
            selected="true",
        )
    )
    build_result = run_work_intake_build(workspace_root=ws)
    if build_result.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("work_intake_exec_ticket_contract_test failed: intake rebuild status invalid.")

    run_work_intake_exec_ticket(workspace_root=ws, limit=3)
    report_path = ws / ".cache" / "reports" / "work_intake_exec_ticket.v1.json"
    if not report_path.exists():
        raise SystemExit("work_intake_exec_ticket_contract_test failed: exec report missing.")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("policy_source") != "core":
        raise SystemExit("work_intake_exec_ticket_contract_test failed: policy_source must be core.")
    if not report.get("policy_hash"):
        raise SystemExit("work_intake_exec_ticket_contract_test failed: policy_hash missing.")
    if int(report.get("applied_count") or 0) < 1:
        raise SystemExit("work_intake_exec_ticket_contract_test failed: applied_count must be >= 1.")

    entries = report.get("entries") if isinstance(report.get("entries"), list) else []
    applied_entries = [e for e in entries if isinstance(e, dict) and e.get("status") == "APPLIED"]
    if not applied_entries:
        raise SystemExit("work_intake_exec_ticket_contract_test failed: no applied entries.")
    for entry in applied_entries:
        evidence = entry.get("evidence_paths")
        if not isinstance(evidence, list) or not evidence:
            raise SystemExit("work_intake_exec_ticket_contract_test failed: applied entry missing evidence_paths.")
        for p in evidence:
            if not isinstance(p, str):
                continue
            if p.startswith("/") or ".." in p.split("/"):
                raise SystemExit("work_intake_exec_ticket_contract_test failed: evidence_paths must be workspace-relative.")

    baseline_order = [str(e.get("intake_id")) for e in entries if isinstance(e, dict)]
    baseline_applied = int(report.get("applied_count") or 0)

    run_work_intake_exec_ticket(workspace_root=ws, limit=3)
    report2 = json.loads(report_path.read_text(encoding="utf-8"))
    order2 = [str(e.get("intake_id")) for e in report2.get("entries", []) if isinstance(e, dict)]
    if order2 != baseline_order:
        raise SystemExit("work_intake_exec_ticket_contract_test failed: ordering not deterministic.")
    if int(report2.get("applied_count") or 0) != 0:
        raise SystemExit("work_intake_exec_ticket_contract_test failed: second run must be idempotent (applied_count=0).")
    skipped2 = report2.get("skipped_by_reason") if isinstance(report2.get("skipped_by_reason"), dict) else {}
    if baseline_applied > 0 and int(skipped2.get("ALREADY_DONE") or 0) < baseline_applied:
        raise SystemExit("work_intake_exec_ticket_contract_test failed: already-done skip evidence missing.")

    print(json.dumps({"status": "OK", "workspace": str(ws)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
