from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _expected_gap_id(reason_code: str, window_hash: str) -> str:
    digest = hashlib.sha256(f"operability{reason_code}{window_hash}".encode("utf-8")).hexdigest()
    return f"GAP-EVAL-LENS-operability-docs-{digest}"


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.benchmark.gap_engine import build_gap_register

    reason_code = "operability_docs_ops_md_count_gt"
    window_hash = "deadbeef"
    lens_signals = [
        {
            "lens_id": "operability",
            "status": "WARN",
            "score": 0.5,
            "reasons": [reason_code],
        }
    ]
    gap_register = build_gap_register(
        controls=[],
        metrics=[],
        lens_signals=lens_signals,
        integrity_snapshot_ref=".cache/reports/integrity_verify.v1.json",
        source_eval_hash=window_hash,
        evidence_pointers=[".cache/index/assessment_eval.v1.json"],
        report_only=False,
    )
    gaps = gap_register.get("gaps") if isinstance(gap_register, dict) else None
    if not isinstance(gaps, list):
        raise SystemExit("operability_docs_hygiene_gap_contract_test failed: gaps missing")

    expected_gap_id = _expected_gap_id(reason_code, window_hash)
    gap_ids = {g.get("id") for g in gaps if isinstance(g, dict)}
    if expected_gap_id not in gap_ids:
        raise SystemExit("operability_docs_hygiene_gap_contract_test failed: hashed gap id missing")

    print(json.dumps({"status": "OK", "gap_id": expected_gap_id}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
