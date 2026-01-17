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

    ws = repo_root / ".cache" / "ws_airunner_run_deltas"
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

    res1 = run_airunner_run(workspace_root=ws, ticks=2, mode="no_wait", tick_runner=_stub_tick)
    deltas_path = ws / ".cache" / "reports" / "airunner_deltas.v1.json"
    if not deltas_path.exists():
        raise SystemExit("airunner_run_deltas_contract_test failed: deltas missing")
    deltas1 = _load_json(deltas_path)
    if deltas1.get("baseline_missing_for_deltas") is not False:
        raise SystemExit("airunner_run_deltas_contract_test failed: baseline_missing_for_deltas")

    res2 = run_airunner_run(workspace_root=ws, ticks=2, mode="no_wait", tick_runner=_stub_tick)
    deltas2 = _load_json(deltas_path)

    for key in ("jobs_polled_delta", "jobs_started_delta", "intake_new_items_delta", "suppressed_delta"):
        if deltas1.get(key) != deltas2.get(key):
            raise SystemExit("airunner_run_deltas_contract_test failed: non-deterministic deltas")

    print(
        json.dumps(
            {"status": "OK", "first_status": res1.get("status"), "second_status": res2.get("status")},
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
