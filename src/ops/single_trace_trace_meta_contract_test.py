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


def _require_trace_meta(payload: dict, label: str) -> None:
    trace = payload.get("trace_meta")
    if not isinstance(trace, dict):
        raise SystemExit(f"single_trace_trace_meta_contract_test failed: {label} trace_meta missing")
    for key in ("version", "work_item_id", "work_item_kind", "run_id", "evidence_paths"):
        if key not in trace:
            raise SystemExit(f"single_trace_trace_meta_contract_test failed: {label} trace_meta.{key} missing")
    if not isinstance(trace.get("evidence_paths"), list) or not trace.get("evidence_paths"):
        raise SystemExit(f"single_trace_trace_meta_contract_test failed: {label} evidence_paths empty")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.commands.maintenance_cmds import cmd_work_intake_select
    from src.ops.work_intake_exec_ticket import run_work_intake_exec_ticket
    from src.ops.work_intake_from_sources import run_work_intake_build, _intake_id
    from src.prj_airunner.airunner_tick import run_airunner_tick
    from src.prj_github_ops.github_ops import start_github_ops_job

    ws = repo_root / ".cache" / "ws_single_trace_meta"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    run_airunner_tick(workspace_root=ws)
    tick_report_path = ws / ".cache" / "reports" / "airunner_tick.v1.json"
    tick_report = json.loads(tick_report_path.read_text(encoding="utf-8"))
    _require_trace_meta(tick_report, "airunner_tick")

    request_id = "REQ-TRACE-META-001"
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
        raise SystemExit("single_trace_trace_meta_contract_test failed: build status")

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
        raise SystemExit("single_trace_trace_meta_contract_test failed: rebuild status")

    run_work_intake_exec_ticket(workspace_root=ws, limit=1)
    exec_report_path = ws / ".cache" / "reports" / "work_intake_exec_ticket.v1.json"
    exec_report = json.loads(exec_report_path.read_text(encoding="utf-8"))
    _require_trace_meta(exec_report, "work_intake_exec_ticket")

    entries = exec_report.get("entries") if isinstance(exec_report.get("entries"), list) else []
    entry_with_trace = next((e for e in entries if isinstance(e, dict) and isinstance(e.get("trace_meta"), dict)), None)
    if entry_with_trace is None:
        raise SystemExit("single_trace_trace_meta_contract_test failed: entry trace_meta missing")

    job_res = start_github_ops_job(workspace_root=ws, kind="SMOKE_FULL", dry_run=True)
    job_report_rel = str(job_res.get("job_report_path") or "")
    job_report_path = ws / job_report_rel
    job_report = json.loads(job_report_path.read_text(encoding="utf-8"))
    _require_trace_meta(job_report, "github_ops_job")


if __name__ == "__main__":
    main()
