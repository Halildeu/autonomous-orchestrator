from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


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
    from src.benchmark.gap_engine import build_gap_register

    ws = repo_root / ".cache" / "ws_eval_lenses_contract"
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
            "report_only": False,
            "integrity_snapshot_ref": ".cache/reports/integrity_verify.v1.json",
            "inputs": {"controls": 1, "metrics": 0},
            "notes": [],
        },
    )

    res = run_eval(workspace_root=ws, dry_run=False)
    out_path = Path(res.get("out") or "")
    if not out_path.exists():
        raise SystemExit("benchmark_eval_lenses_contract_test failed: eval output missing")

    eval_obj = _load_json(out_path)
    lenses = eval_obj.get("lenses")
    if not isinstance(lenses, dict):
        raise SystemExit("benchmark_eval_lenses_contract_test failed: lenses missing")

    required_lenses = {
        "trend_best_practice": "A",
        "integrity_compat": "B",
        "ai_ops_fit": "C",
        "github_ops_release": "D",
        "operability": "E",
        "integration_coherence": "F",
    }
    for lens_id, expected_dimension in required_lenses.items():
        lens_obj = lenses.get(lens_id)
        if not isinstance(lens_obj, dict):
            raise SystemExit(f"benchmark_eval_lenses_contract_test failed: missing lens {lens_id}")
        if lens_obj.get("status") not in {"WARN", "FAIL", "OK"}:
            raise SystemExit(f"benchmark_eval_lenses_contract_test failed: invalid status for {lens_id}")
        if lens_obj.get("dimension") != expected_dimension:
            raise SystemExit(
                f"benchmark_eval_lenses_contract_test failed: {lens_id} dimension must be {expected_dimension}"
            )

    maturity_doc = eval_obj.get("maturity_tracking")
    if not isinstance(maturity_doc, dict):
        raise SystemExit("benchmark_eval_lenses_contract_test failed: maturity_tracking missing")
    tracking = maturity_doc.get("tracking")
    if not isinstance(tracking, dict):
        raise SystemExit("benchmark_eval_lenses_contract_test failed: maturity tracking payload missing")
    if not isinstance(tracking.get("score"), (int, float)):
        raise SystemExit("benchmark_eval_lenses_contract_test failed: maturity score missing")

    schema_path = repo_root / "schemas" / "assessment-eval.schema.v1.json"
    Draft202012Validator(_load_json(schema_path)).validate(eval_obj)

    lens_signals = []
    for lens_id in sorted(lenses.keys()):
        lens = lenses.get(lens_id)
        if not isinstance(lens, dict):
            continue
        status = lens.get("status")
        if isinstance(status, str) and status:
            lens_signals.append({"lens_id": lens_id, "status": status, "score": lens.get("score")})

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
        raise SystemExit("benchmark_eval_lenses_contract_test failed: gaps missing")
    lens_gap_ids = {g.get("id") for g in gaps if isinstance(g, dict)}
    if "GAP-EVAL-LENS-trend_best_practice" not in lens_gap_ids:
        raise SystemExit("benchmark_eval_lenses_contract_test failed: lens gap not created")

    print(json.dumps({"status": "OK", "lens_gap_count": len(lens_gap_ids)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
