from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.benchmark.gap_engine import build_gap_register

    gap_id = "GAP-EVAL-LENS-integration_coherence-pack_conflicts_fail"
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    previous_gap_register = {
        "version": "v1",
        "generated_at": now,
        "gaps": [
            {
                "id": gap_id,
                "severity": "high",
                "status": "open",
            }
        ],
    }

    gap_register = build_gap_register(
        controls=[],
        metrics=[],
        lens_signals=[
            {
                "lens_id": "integration_coherence",
                "status": "FAIL",
                "score": 0.0,
                "reasons": ["pack_conflicts_fail"],
            }
        ],
        integrity_snapshot_ref=".cache/reports/integrity_verify.v1.json",
        evidence_pointers=[".cache/index/assessment_eval.v1.json"],
        report_only=False,
        previous_gap_register=previous_gap_register,
        cooldown_seconds=86400,
    )

    gaps = gap_register.get("gaps") if isinstance(gap_register, dict) else None
    if not isinstance(gaps, list):
        raise SystemExit("integration_coherence_gap_contract_test failed: gaps missing")
    match = [g for g in gaps if isinstance(g, dict) and g.get("id") == gap_id]
    if not match:
        raise SystemExit("integration_coherence_gap_contract_test failed: expected gap missing")
    if not bool(match[0].get("update_only", False)):
        raise SystemExit("integration_coherence_gap_contract_test failed: update_only not set")

    print(json.dumps({"status": "OK", "gap_id": gap_id}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
