from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_airunner.airunner_run import run_airunner_run

    ws = repo_root / ".cache" / "ws_airunner_run_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    _write_json(
        ws / ".cache" / "airunner" / "jobs_index.v1.json",
        {"version": "v1", "generated_at": "2026-01-07T00:00:00Z", "jobs": [], "notes": ["PROGRAM_LED=true"]},
    )
    _write_json(
        ws / ".cache" / "index" / "work_intake.v1.json",
        {"version": "v1", "generated_at": "2026-01-07T00:00:00Z", "items": [], "notes": ["PROGRAM_LED=true"]},
    )
    _write_json(
        ws / ".cache" / "index" / "intake_cooldowns.v1.json",
        {"version": "v1", "generated_at": "2026-01-07T00:00:00Z", "entries": {}, "notes": ["PROGRAM_LED=true"]},
    )
    _write_json(
        ws / ".cache" / "reports" / "time_sinks.v1.json",
        {
            "version": "v1",
            "generated_at": "2026-01-07T00:00:00Z",
            "workspace_root": str(ws),
            "status": "OK",
            "window_size": 1,
            "thresholds_ms": {"smoke_full_p95_warn": 240000, "smoke_fast_p95_warn": 60000, "release_prepare_p95_warn": 180000},
            "sinks": [
                {
                    "op_name": "SMOKE_FULL",
                    "event_key": "SMOKE_FULL",
                    "count": 2,
                    "p50_ms": 1000,
                    "p95_ms": 2000,
                    "threshold_ms": 1500,
                    "breach_count": 1,
                    "last_seen": "2026-01-07T00:00:00Z",
                    "status": "WARN",
                }
            ],
            "notes": [],
        },
    )

    def _stub_tick(*, workspace_root: Path) -> dict:
        report = {
            "version": "v1",
            "generated_at": "2026-01-07T00:00:00Z",
            "status": "OK",
            "ops_called": [],
            "jobs_started": 0,
            "jobs_polled": 0,
            "evidence_paths": [],
            "notes": ["PROGRAM_LED=true"],
        }
        _write_json(workspace_root / ".cache" / "reports" / "airunner_tick.v1.json", report)
        (workspace_root / ".cache" / "reports").mkdir(parents=True, exist_ok=True)
        (workspace_root / ".cache" / "reports" / "airunner_tick.v1.md").write_text("# Airunner Tick\n", encoding="utf-8")
        return {"status": "OK", "report_path": ".cache/reports/airunner_tick.v1.json"}

    res = run_airunner_run(workspace_root=ws, ticks=2, mode="no_wait", tick_runner=_stub_tick, budget_seconds=1)
    run_path = ws / ".cache" / "reports" / "airunner_run.v1.json"
    if not run_path.exists():
        raise SystemExit("airunner_run_contract_test failed: run report missing")
    run = _load_json(run_path)
    if run.get("ticks_run") != 1:
        raise SystemExit("airunner_run_contract_test failed: ticks_run mismatch")
    if not isinstance(run.get("time_sinks_top3"), list):
        raise SystemExit("airunner_run_contract_test failed: time_sinks_top3 missing")
    if not isinstance(res.get("run_path"), str):
        raise SystemExit("airunner_run_contract_test failed: run_path missing")

    print(json.dumps({"status": "OK", "run_path": res.get("run_path")}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
