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

    from src.benchmark.eval_runner import run_eval

    ws = repo_root / ".cache" / "ws_operability_eval_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    integrity_path = ws / ".cache" / "reports" / "integrity_verify.v1.json"
    _write_json(
        integrity_path,
        {
            "version": "v1",
            "generated_at": "2026-01-07T00:00:00Z",
            "workspace_root": str(ws),
            "verify_on_read_result": "PASS",
            "mismatch_count": 0,
            "mismatches": [],
        },
    )

    raw_path = ws / ".cache" / "index" / "assessment_raw.v1.json"
    _write_json(
        raw_path,
        {
            "version": "v1",
            "generated_at": "2026-01-07T00:00:00Z",
            "workspace_root": str(ws),
            "status": "OK",
            "integrity_snapshot_ref": ".cache/reports/integrity_verify.v1.json",
            "inputs": {"controls": 0, "metrics": 0},
            "notes": [],
            "signals": {
                "script_budget": {"hard_exceeded": 0, "soft_exceeded": 1},
                "doc_nav": {"placeholders_count": 30, "broken_refs": 0, "orphan_critical": 0},
                "airunner_jobs": {"queued": 0, "running": 0, "fail": 0, "pass": 0, "stuck": 0},
                "pdca_cursor": {"stale_hours": 25.0},
                "airunner_heartbeat": {"stale_seconds": 2000},
                "work_intake_noise": {"new_items_24h": 30, "suppressed_24h": 5},
                "integrity": {"status": "PASS"},
            },
        },
    )

    res = run_eval(workspace_root=ws, dry_run=False)
    out_path = Path(res.get("out") or "")
    if not out_path.exists():
        raise SystemExit("operability_eval_contract_test failed: eval output missing")

    eval_obj = _load_json(out_path)
    lenses = eval_obj.get("lenses") if isinstance(eval_obj, dict) else None
    if not isinstance(lenses, dict):
        raise SystemExit("operability_eval_contract_test failed: lenses missing")
    operability = lenses.get("operability")
    if not isinstance(operability, dict):
        raise SystemExit("operability_eval_contract_test failed: operability lens missing")
    reasons = operability.get("reasons")
    if not isinstance(reasons, list) or "soft_exceeded_gt" not in reasons:
        raise SystemExit("operability_eval_contract_test failed: expected soft_exceeded_gt reason")

    print(json.dumps({"status": "OK", "reasons": sorted(reasons)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
