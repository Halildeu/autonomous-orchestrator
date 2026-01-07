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


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_airunner.airunner_perf import append_perf_event
    from src.prj_airunner.airunner_time_sinks import build_time_sinks_report

    ws = repo_root / ".cache" / "ws_airunner_perf_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    policy = {
        "perf": {
            "enable": True,
            "event_log_max_lines": 20,
            "time_sinks_window": 10,
            "thresholds_ms": {
                "smoke_full_p95_warn": 100,
                "smoke_fast_p95_warn": 60,
                "release_prepare_p95_warn": 120,
            },
        }
    }

    for duration in [50, 150, 200]:
        append_perf_event(
            ws,
            event={
                "event_type": "JOB_RUN",
                "op_name": "SMOKE_FULL",
                "started_at": "2025-01-01T00:00:00Z",
                "ended_at": "2025-01-01T00:00:01Z",
                "duration_ms": duration,
                "status": "OK",
                "notes": ["contract_test"],
            },
            max_lines=20,
        )

    report = build_time_sinks_report(ws, policy=policy)
    sinks = report.get("sinks") if isinstance(report, dict) else None
    if not isinstance(sinks, list) or not sinks:
        raise SystemExit("airunner_perf_contract_test failed: expected time sink entry")
    if sinks[0].get("event_key") != "SMOKE_FULL":
        raise SystemExit("airunner_perf_contract_test failed: unexpected sink key")

    report2 = build_time_sinks_report(ws, policy=policy)
    if json.dumps(report, sort_keys=True) != json.dumps(report2, sort_keys=True):
        raise SystemExit("airunner_perf_contract_test failed: deterministic report mismatch")

    print(json.dumps({"status": "OK", "sink": sinks[0].get("event_key")}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
