from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _load_report(ws: Path) -> dict:
    report_path = ws / ".cache" / "reports" / "airunner_tick.v1.json"
    if not report_path.exists():
        return {}
    return json.loads(report_path.read_text(encoding="utf-8"))


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
    run_airunner_tick = airunner_tick_mod.run_airunner_tick

    ws = repo_root / ".cache" / "ws_airunner_active_hours_optional"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    start = (now + timedelta(minutes=5)).strftime("%H:%M")
    end = (now + timedelta(minutes=6)).strftime("%H:%M")

    override_path = ws / ".cache" / "policy_overrides" / "policy_airunner.override.v1.json"

    _write_json(
        override_path,
        {
            "version": "v1",
            "enabled": True,
            "schedule": {
                "mode": "interval",
                "interval_seconds": 900,
                "jitter_seconds": 0,
                "outside_hours_mode": "poll_only",
                "active_hours": {"enabled": False, "tz": "UTC", "start": start, "end": end},
                "weekday_only": False,
            },
            "single_gate": {"allowed_ops": [], "require_strict_isolation": True},
        },
    )

    run_airunner_tick(workspace_root=ws)
    report = _load_report(ws)
    if report.get("error_code") == "OUTSIDE_ACTIVE_HOURS":
        raise SystemExit("airunner_active_hours_optional_contract_test failed: enabled=false should ignore")
    if report.get("active_hours_enabled") is not False:
        raise SystemExit("airrunner_active_hours_optional_contract_test failed: active_hours_enabled false expected")

    lock_path = ws / ".cache" / "airunner" / "airunner_lock.v1.json"
    if lock_path.exists():
        lock_path.unlink()

    _write_json(
        override_path,
        {
            "version": "v1",
            "enabled": True,
            "schedule": {
                "mode": "interval",
                "interval_seconds": 900,
                "jitter_seconds": 0,
                "outside_hours_mode": "poll_only",
                "active_hours": {"enabled": True, "tz": "UTC", "start": start, "end": end},
                "weekday_only": False,
            },
            "single_gate": {"allowed_ops": [], "require_strict_isolation": True},
        },
    )

    run_airunner_tick(workspace_root=ws)
    report = _load_report(ws)
    if report.get("error_code") != "OUTSIDE_ACTIVE_HOURS":
        raise SystemExit("airunner_active_hours_optional_contract_test failed: expected OUTSIDE_ACTIVE_HOURS")
    if report.get("active_hours_enabled") is not True:
        raise SystemExit("airrunner_active_hours_optional_contract_test failed: active_hours_enabled true expected")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
