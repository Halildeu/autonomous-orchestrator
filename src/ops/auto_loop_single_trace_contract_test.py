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

    from src.ops.auto_loop import run_auto_loop

    ws = repo_root / ".cache" / "ws_auto_loop_single_trace"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    run_auto_loop(workspace_root=ws, budget_seconds=60)
    report_path = ws / ".cache" / "reports" / "auto_loop.v1.json"
    if not report_path.exists():
        raise SystemExit("auto_loop_single_trace_contract_test failed: report missing")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    trace = report.get("trace_meta")
    if not isinstance(trace, dict):
        raise SystemExit("auto_loop_single_trace_contract_test failed: trace_meta missing")
    evidence = trace.get("evidence_paths")
    if not isinstance(evidence, list) or not evidence:
        raise SystemExit("auto_loop_single_trace_contract_test failed: evidence_paths missing")


if __name__ == "__main__":
    main()
