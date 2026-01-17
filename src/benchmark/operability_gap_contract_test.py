from __future__ import annotations

import json

from src.benchmark.gap_engine import build_gap_register


def main() -> None:
    lens_signals = [
        {
            "lens_id": "operability",
            "status": "WARN",
            "score": 0.5,
            "reasons": ["soft_exceeded_gt", "jobs_stuck_gt"],
        }
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
        raise SystemExit("operability_gap_contract_test failed: gaps missing")
    gap_ids = {g.get("id") for g in gaps if isinstance(g, dict)}
    expected = {
        "GAP-EVAL-LENS-operability-soft_exceeded_gt",
        "GAP-EVAL-LENS-operability-jobs_stuck_gt",
    }
    if not expected.issubset(gap_ids):
        raise SystemExit("operability_gap_contract_test failed: operability gaps missing")

    print(json.dumps({"status": "OK", "gap_ids": sorted(gap_ids)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
