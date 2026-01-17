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

def _write_preflight_stamp(ws: Path) -> None:
    _write_json(
        ws / ".cache" / "reports" / "preflight_stamp.v1.json",
        {
            "version": "v1",
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
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

    ws = repo_root / ".cache" / "ws_airunner_schedule_contract"
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
                "active_hours": {"enabled": True, "tz": "UTC", "start": start, "end": end},
                "weekday_only": False,
            },
        },
    )

    _write_preflight_stamp(ws)
    res = run_airunner_tick(workspace_root=ws)
    report_path = ws / ".cache" / "reports" / "airunner_tick.v1.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    if res.get("status") != "IDLE" or report.get("error_code") != "OUTSIDE_ACTIVE_HOURS":
        raise SystemExit("airunner_schedule_contract_test failed: expected OUTSIDE_ACTIVE_HOURS")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
