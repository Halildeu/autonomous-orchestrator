from __future__ import annotations

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

    from src.ops.trace_meta import build_trace_meta

    trace = build_trace_meta(
        work_item_id="ITEM-TRACE-001",
        work_item_kind="RUN",
        run_id="RUN-TRACE-001",
        policy_hash=None,
        evidence_paths=[".cache/reports/sample.json"],
        workspace_root="/tmp/workspace",
    )
    if trace.get("workspace_root") != "/tmp/workspace":
        raise SystemExit("trace_meta_minimum_contract_test failed: workspace_root missing")
    if not isinstance(trace.get("owner_session"), str) or not trace.get("owner_session"):
        raise SystemExit("trace_meta_minimum_contract_test failed: owner_session missing")


if __name__ == "__main__":
    main()
