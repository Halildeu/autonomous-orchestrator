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
    sys.path.insert(0, str(repo_root))

    from src.benchmark.gap_engine import apply_gap_closeout

    gap_register = {
        "version": "v1",
        "generated_at": "2026-03-08T00:00:00Z",
        "gaps": [
            {
                "id": "GAP-CTRL-001",
                "control_id": "CTRL-001",
                "severity": "medium",
                "risk_class": "medium",
                "effort": "medium",
                "status": "open",
                "notes": "Assessment not yet completed.",
            },
            {
                "id": "GAP-CTRL-002",
                "control_id": "CTRL-002",
                "severity": "medium",
                "risk_class": "medium",
                "effort": "medium",
                "status": "open",
                "notes": "Assessment not yet completed.",
            },
        ],
    }
    work_intake = {
        "version": "v1",
        "items": [
            {
                "source_type": "GAP",
                "source_ref": "GAP-CTRL-001",
                "status": "DONE",
                "closed_reason": "WORK_ITEM_STATE_CLOSED",
            },
            {
                "source_type": "GAP",
                "source_ref": "GAP-CTRL-002",
                "status": "OPEN",
            },
        ],
    }

    updated = apply_gap_closeout(
        gap_register=gap_register,
        work_intake=work_intake,
        evidence_pointer=".cache/index/work_intake.v1.json",
    )

    gaps = updated.get("gaps") if isinstance(updated, dict) else None
    if not isinstance(gaps, list):
        raise SystemExit("gap_closeout_from_work_intake_contract_test failed: gaps missing")
    by_id = {str(g.get("id") or ""): g for g in gaps if isinstance(g, dict)}
    closed_gap = by_id.get("GAP-CTRL-001")
    open_gap = by_id.get("GAP-CTRL-002")
    if not isinstance(closed_gap, dict) or str(closed_gap.get("status") or "") != "closed":
        raise SystemExit("gap_closeout_from_work_intake_contract_test failed: DONE intake should close gap")
    if "WORK_ITEM_STATE_CLOSED" not in str(closed_gap.get("notes") or ""):
        raise SystemExit("gap_closeout_from_work_intake_contract_test failed: closed note missing reason")
    evidence = closed_gap.get("evidence_pointers") if isinstance(closed_gap.get("evidence_pointers"), list) else []
    if ".cache/index/work_intake.v1.json" not in evidence:
        raise SystemExit("gap_closeout_from_work_intake_contract_test failed: evidence pointer missing")
    if not isinstance(open_gap, dict) or str(open_gap.get("status") or "") != "open":
        raise SystemExit("gap_closeout_from_work_intake_contract_test failed: OPEN intake should keep gap open")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
