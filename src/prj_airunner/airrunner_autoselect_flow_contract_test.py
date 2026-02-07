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


def _write_preflight_stamp(ws: Path) -> None:
    _write_json(
        ws / ".cache" / "reports" / "preflight_stamp.v1.json",
        {
            "version": "v1",
            "generated_at": _now_iso(),
            "workspace_root": str(ws),
            "gates": {
                "validate_schemas": "PASS",
                "smoke_fast": "PASS",
                "script_budget": {"hard_exceeded": 0, "soft_exceeded": 0, "status": "OK"},
            },
            "overall": "PASS",
            "notes": ["PROGRAM_LED=true", "NO_WAIT=true"],
        },
    )


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_airunner.airunner_tick import run_airunner_tick

    ws = repo_root / ".cache" / "ws_airunner_autoselect"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    _write_json(
        ws / ".cache" / "policy_overrides" / "policy_airunner.override.v1.json",
        {
            "version": "v1",
            "enabled": True,
            "lock_ttl_seconds": 900,
            "heartbeat_interval_seconds": 300,
            "schedule": {
                "mode": "interval",
                "interval_seconds": 900,
                "jitter_seconds": 0,
                "active_hours": {"tz": "UTC", "start": "00:00", "end": "23:59"},
                "weekday_only": False,
            },
            "watchdog": {"enabled": True, "heartbeat_stale_seconds": 1800, "max_recoveries_per_day": 3},
            "job_policy": {"max_running_jobs": 1, "poll_interval_seconds": 60, "closeout_ttl_days": 7, "keep_last_n": 50},
            "limits": {"max_ticks_per_run": 1, "max_actions_per_tick": 2, "max_plans_per_tick": 2},
            "single_gate": {
                "allowed_ops": [
                    "work-intake-check",
                    "work-intake-autoselect",
                    "work-intake-exec-ticket",
                    "system-status",
                    "portfolio-status",
                    "ui-snapshot-bundle",
                ],
                "require_strict_isolation": True,
            },
            "notes": ["PROGRAM_LED=true", "WORKSPACE_ONLY=true"],
        },
    )

    _write_json(
        ws / ".cache" / "policy_overrides" / "policy_autopilot_apply.override.v1.json",
        {"version": "v1", "auto_select": {"enabled": True, "max_select": 2}},
    )

    _write_json(
        ws / ".cache" / "index" / "manual_requests" / "REQ-TEST-AUTOSELECT-FLOW.v1.json",
        {
            "version": "v1",
            "request_id": "REQ-TEST-AUTOSELECT-FLOW",
            "received_at": _now_iso(),
            "source": {"type": "chat"},
            "text": "Autoselect flow test",
            "impact_scope": "doc-only",
            "kind": "note",
            "requires_core_change": False,
        },
    )

    _write_preflight_stamp(ws)

    res = run_airunner_tick(workspace_root=ws)
    report_path = ws / ".cache" / "reports" / "airunner_tick.v1.json"
    if not report_path.exists():
        raise SystemExit("airrunner_autoselect_flow_contract_test failed: tick report missing")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    ops_called = report.get("ops_called") if isinstance(report.get("ops_called"), list) else []
    if "work-intake-autoselect" not in ops_called:
        raise SystemExit("airrunner_autoselect_flow_contract_test failed: autoselect not called")
    if "work-intake-exec-ticket" not in ops_called:
        raise SystemExit("airrunner_autoselect_flow_contract_test failed: exec-ticket not called")

    selection_path = ws / ".cache" / "index" / "work_intake_selection.v1.json"
    if not selection_path.exists():
        raise SystemExit("airrunner_autoselect_flow_contract_test failed: selection file missing")

    if res.get("status") not in {"OK", "WARN"}:
        raise SystemExit("airrunner_autoselect_flow_contract_test failed: unexpected status")

    print("OK")


if __name__ == "__main__":
    main()
