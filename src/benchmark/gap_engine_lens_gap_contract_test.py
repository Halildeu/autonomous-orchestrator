from __future__ import annotations

import json
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.benchmark.gap_engine import build_gap_register

    lens_signals = [
        {"lens_id": "github_ops_release", "status": "FAIL", "score": 0.0},
    ]
    gap_register = build_gap_register(
        controls=[],
        metrics=[],
        lens_signals=lens_signals,
        integrity_snapshot_ref=".cache/reports/integrity_verify.v1.json",
        evidence_pointers=[".cache/index/assessment_eval.v1.json"],
        report_only=False,
    )
    gaps = gap_register.get("gaps") if isinstance(gap_register, dict) else None
    if not isinstance(gaps, list):
        raise SystemExit("gap_engine_lens_gap_contract_test failed: gaps missing")
    gap_ids = {g.get("id") for g in gaps if isinstance(g, dict)}
    if "GAP-EVAL-LENS-github_ops_release" not in gap_ids:
        raise SystemExit("gap_engine_lens_gap_contract_test failed: github_ops_release gap missing")

    print(json.dumps({"status": "OK", "gap_ids": sorted(gap_ids)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
