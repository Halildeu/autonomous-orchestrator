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

    ws = repo_root / ".cache" / "ws_operability_integrity_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    _write_json(
        ws / ".cache" / "reports" / "integrity_verify.v1.json",
        {
            "version": "v1",
            "generated_at": "2026-01-09T00:00:00Z",
            "workspace_root": str(ws),
            "verify_on_read_result": "PASS",
            "mismatch_count": 0,
            "mismatches": [],
        },
    )

    _write_json(
        ws / ".cache" / "index" / "assessment_raw.v1.json",
        {
            "version": "v1",
            "generated_at": "2026-01-09T00:00:00Z",
            "workspace_root": str(ws),
            "status": "OK",
            "report_only": False,
            "integrity_snapshot_ref": ".cache/reports/integrity_verify.v1.json",
            "inputs": {"controls": 0, "metrics": 0},
            "signals": {
                "script_budget": {"hard_exceeded": 0, "soft_exceeded": 0},
                "doc_nav": {"placeholders_count": 0, "broken_refs": 0, "orphan_critical": 0},
                "airunner_jobs": {"queued": 0, "running": 0, "fail": 0, "pass": 0, "stuck": 0},
                "pdca_cursor": {"stale_hours": 0.0},
                "airunner_heartbeat": {"stale_seconds": 0},
                "work_intake_noise": {"new_items_24h": 0, "suppressed_24h": 0},
                "integrity": {"status": "PASS"},
            },
            "notes": [],
        },
    )

    res = run_eval(workspace_root=ws, dry_run=False)
    eval_path = Path(res.get("out") or "")
    if not eval_path.exists():
        raise SystemExit("operability_integrity_contract_test failed: eval output missing")

    eval_obj = _load_json(eval_path)
    lenses = eval_obj.get("lenses") if isinstance(eval_obj, dict) else None
    oper = lenses.get("operability") if isinstance(lenses, dict) else None
    if not isinstance(oper, dict):
        raise SystemExit("operability_integrity_contract_test failed: operability lens missing")
    reasons = oper.get("reasons") if isinstance(oper.get("reasons"), list) else []
    if "integrity_fail" in reasons:
        raise SystemExit("operability_integrity_contract_test failed: integrity_fail present when PASS")

    print(json.dumps({"status": "OK", "reasons_count": len(reasons)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
