from __future__ import annotations

import json
import shutil
import sys
import types
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




def _emit(payload: dict) -> int:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0

def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    import src.prj_airunner.airunner_tick as airunner_tick_mod

    def _fast_gate_stub(_workspace_root: Path) -> dict:
        return {
            "validate_schemas": "PASS",
            "smoke_fast": "PASS",
            "script_budget": "PASS",
            "hard_exceeded": 0,
            "report_path": "",
        }

    airunner_tick_mod._run_fast_gate = _fast_gate_stub
    def _stub_update_jobs(**kwargs):
        workspace_root = Path(str(kwargs.get("workspace_root")))
        jobs_index = workspace_root / ".cache" / "airunner" / "jobs_index.v1.json"
        payload = {
            "jobs_index_path": str(jobs_index.relative_to(workspace_root)),
            "queued_before": 0,
            "running_before": 0,
            "queued_after": 0,
            "running_after": 0,
            "jobs_running": 0,
            "jobs_polled": 0,
            "jobs_started": 0,
            "jobs_passed": 0,
            "jobs_failed": 0,
            "jobs_skipped_delta": 0,
            "jobs_archived_delta": 0,
            "last_smoke_full_job_id": None,
        }
        _write_json(jobs_index, {"version": "v1", "generated_at": _now_iso(), "jobs": []})
        notes = ["PROGRAM_LED=true"]
        run_stats = dict(payload)
        return payload, notes, run_stats

    airunner_tick_mod.update_jobs = _stub_update_jobs

    def _stub_work_intake_check(args):
        ws = Path(str(args.workspace_root))
        intake_path = ws / ".cache" / "index" / "work_intake.v1.json"
        _write_json(intake_path, {"version": "v1", "generated_at": _now_iso(), "items": []})
        payload = {"status": "OK", "work_intake_path": str(intake_path.relative_to(ws))}
        return _emit(payload)

    def _stub_exec_ticket(args):
        ws = Path(str(args.workspace_root))
        exec_path = ws / ".cache" / "reports" / "work_intake_exec_ticket.v1.json"
        _write_json(
            exec_path,
            {
                "version": "v1",
                "generated_at": _now_iso(),
                "entries": [
                    {
                        "intake_id": "INTAKE-DECISION-1",
                        "bucket": "PROJECT",
                        "status": "SKIPPED",
                        "skip_reason": "DECISION_NEEDED",
                        "autopilot_reason": "AUTO_APPLY_ALLOW",
                        "evidence_paths": [],
                    }
                ],
                "applied_count": 0,
                "planned_count": 0,
                "idle_count": 0,
                "selected_count": 0,
                "skipped_count": 1,
                "skipped_by_reason": {"DECISION_NEEDED": 1},
                "decision_needed_count": 1,
            },
        )
        decision_inbox_path = ws / ".cache" / "index" / "decision_inbox.v1.json"
        _write_json(
            decision_inbox_path,
            {
                "version": "v1",
                "generated_at": _now_iso(),
                "workspace_root": str(ws),
                "items": [
                    {
                        "decision_id": "DECISION-1",
                        "source_intake_id": "INTAKE-DECISION-1",
                        "bucket": "PROJECT",
                        "decision_kind": "AUTO_APPLY_ALLOW",
                        "question": "Allow apply after decision?",
                        "options": [{"option_id": "A", "title": "Allow apply", "changes_ref": ""}],
                        "default_option_id": "A",
                        "why_blocked": "DECISION_NEEDED",
                        "evidence_paths": [],
                        "expires_at": None,
                    }
                ],
                "counts": {"total": 1, "by_kind": {"AUTO_APPLY_ALLOW": 1}},
                "notes": ["PROGRAM_LED=true", "NO_WAIT=true"],
            },
        )
        payload = {
            "status": "OK",
            "work_intake_exec_path": str(exec_path.relative_to(ws)),
            "applied_count": 0,
            "planned_count": 0,
            "idle_count": 0,
            "selected_count": 0,
            "skipped_count": 1,
            "skipped_by_reason": {"DECISION_NEEDED": 1},
            "decision_needed_count": 1,
            "decision_inbox_path": str(decision_inbox_path.relative_to(ws)),
        }
        return _emit(payload)

    def _stub_system_status(args):
        ws = Path(str(args.workspace_root))
        report_path = ws / ".cache" / "reports" / "system_status.v1.json"
        _write_json(report_path, {"version": "v1", "generated_at": _now_iso(), "status": "OK"})
        payload = {"status": "OK", "report_path": str(report_path.relative_to(ws))}
        return _emit(payload)

    def _stub_portfolio_status(args):
        ws = Path(str(args.workspace_root))
        report_path = ws / ".cache" / "reports" / "portfolio_status.v1.json"
        _write_json(report_path, {"version": "v1", "generated_at": _now_iso(), "status": "OK"})
        payload = {"status": "OK", "report_path": str(report_path.relative_to(ws))}
        return _emit(payload)

    def _stub_ui_snapshot(args):
        report_path = Path(str(args.out))
        payload = {"status": "OK", "report_path": str(report_path)}
        _write_json(report_path, {"status": "OK", "generated_at": _now_iso()})
        return _emit(payload)

    airunner_tick_mod.cmd_work_intake_check = _stub_work_intake_check
    airunner_tick_mod.cmd_work_intake_exec_ticket = _stub_exec_ticket
    airunner_tick_mod.cmd_system_status = _stub_system_status
    airunner_tick_mod.cmd_portfolio_status = _stub_portfolio_status
    airunner_tick_mod.cmd_ui_snapshot = _stub_ui_snapshot

    def _stub_decision_inbox_build(*, workspace_root: Path) -> dict:
        ws = Path(str(workspace_root))
        inbox_path = ws / ".cache" / "index" / "decision_inbox.v1.json"
        _write_json(
            inbox_path,
            {
                "version": "v1",
                "generated_at": _now_iso(),
                "workspace_root": str(ws),
                "items": [
                    {
                        "decision_id": "DECISION-1",
                        "source_intake_id": "INTAKE-DECISION-1",
                        "bucket": "PROJECT",
                        "decision_kind": "AUTO_APPLY_ALLOW",
                        "question": "Allow apply after decision?",
                        "options": [{"option_id": "A", "title": "Allow apply", "changes_ref": ""}],
                        "default_option_id": "A",
                        "why_blocked": "DECISION_NEEDED",
                        "evidence_paths": [],
                        "expires_at": None,
                    }
                ],
                "counts": {"total": 1, "by_kind": {"AUTO_APPLY_ALLOW": 1}},
                "notes": ["PROGRAM_LED=true", "NO_WAIT=true"],
            },
        )
        return {"status": "OK", "decision_inbox_path": str(inbox_path.relative_to(ws))}

    stub_module = types.ModuleType("src.ops.decision_inbox")
    stub_module.run_decision_inbox_build = _stub_decision_inbox_build
    sys.modules["src.ops.decision_inbox"] = stub_module

    run_airunner_tick = airunner_tick_mod.run_airunner_tick

    ws = repo_root / ".cache" / "ws_airunner_decision_inbox"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    _write_json(
        ws / ".cache" / "policy_overrides" / "policy_airunner.override.v1.json",
        {
            "version": "v1",
            "enabled": True,
            "schedule": {
                "mode": "interval",
                "interval_seconds": 900,
                "jitter_seconds": 0,
                "active_hours": {"tz": "UTC", "start": "00:00", "end": "23:59"},
                "weekday_only": False,
            },
            "single_gate": {
                "allowed_ops": [
                    "work-intake-check",
                    "work-intake-exec-ticket",
                    "decision-inbox-build",
                    "system-status",
                    "portfolio-status",
                    "ui-snapshot-bundle",
                ],
                "require_strict_isolation": True,
            },
            "notes": ["PROGRAM_LED=true", "WORKSPACE_ONLY=true"],
        },
    )

    run_airunner_tick(workspace_root=ws)

    report_path = ws / ".cache" / "reports" / "airunner_tick.v1.json"
    if not report_path.exists():
        raise SystemExit("airrunner_decision_inbox_propagation_contract_test failed: report missing")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    inbox_path = report.get("decision_inbox_path")
    if not inbox_path:
        raise SystemExit("airrunner_decision_inbox_propagation_contract_test failed: decision_inbox_path missing")
    inbox_file = ws / inbox_path
    if not inbox_file.exists():
        raise SystemExit("airrunner_decision_inbox_propagation_contract_test failed: inbox file missing")

    print(json.dumps({"status": report.get("status", "OK")}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
