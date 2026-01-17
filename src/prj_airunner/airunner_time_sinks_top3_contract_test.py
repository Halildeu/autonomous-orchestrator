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


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.work_intake_from_sources import run_work_intake_build

    ws = repo_root / ".cache" / "ws_airunner_time_sinks_top3"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    sinks = [
        {"event_key": "SMOKE_FULL", "p95_ms": 250, "threshold_ms": 200, "breach_count": 5, "status": "WARN"},
        {"event_key": "SMOKE_FAST", "p95_ms": 150, "threshold_ms": 100, "breach_count": 2, "status": "WARN"},
        {"event_key": "RELEASE_PREPARE", "p95_ms": 120, "threshold_ms": 200, "breach_count": 0, "status": "OK"},
        {"event_key": "OTHER_TASK", "p95_ms": 50, "threshold_ms": 40, "breach_count": 1, "status": "WARN"},
    ]
    _write_json(
        ws / ".cache" / "reports" / "time_sinks.v1.json",
        {
            "version": "v1",
            "generated_at": "2026-01-07T00:00:00Z",
            "workspace_root": str(ws),
            "status": "WARN",
            "window_size": 4,
            "thresholds_ms": {},
            "sinks": sinks,
            "notes": [],
        },
    )

    run_work_intake_build(workspace_root=ws)
    out_path = ws / ".cache" / "index" / "work_intake.v1.json"
    if not out_path.exists():
        raise SystemExit("airunner_time_sinks_top3_contract_test failed: output missing")
    data = json.loads(out_path.read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise SystemExit("airunner_time_sinks_top3_contract_test failed: items missing")
    time_sink_items = [i for i in items if isinstance(i, dict) and i.get("source_type") == "TIME_SINK"]
    if len(time_sink_items) != 3:
        raise SystemExit("airunner_time_sinks_top3_contract_test failed: expected top 3 time sinks")

    buckets = {i.get("source_ref"): i.get("bucket") for i in time_sink_items}
    if buckets.get("SMOKE_FULL") != "PROJECT":
        raise SystemExit("airunner_time_sinks_top3_contract_test failed: SMOKE_FULL must be PROJECT")
    if buckets.get("SMOKE_FAST") != "PROJECT":
        raise SystemExit("airunner_time_sinks_top3_contract_test failed: SMOKE_FAST must be PROJECT")
    if buckets.get("RELEASE_PREPARE") != "TICKET":
        raise SystemExit("airunner_time_sinks_top3_contract_test failed: RELEASE_PREPARE must be TICKET")

    print(json.dumps({"status": "OK", "time_sink_items": len(time_sink_items)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
