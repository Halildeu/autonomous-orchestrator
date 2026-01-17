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

    ws = repo_root / ".cache" / "ws_eval_lenses_github_ops_contract"
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
            "inputs": {"controls": 1, "metrics": 1},
            "notes": [],
        },
    )

    jobs_index = ws / ".cache" / "github_ops" / "jobs_index.v1.json"
    _write_json(
        jobs_index,
        {
            "version": "v1",
            "generated_at": "2026-01-07T00:00:00Z",
            "workspace_root": str(ws),
            "status": "IDLE",
            "jobs": [],
            "counts": {"total": 0, "queued": 0, "running": 0, "pass": 0, "fail": 0, "timeout": 0, "killed": 0, "skip": 0},
            "notes": [],
        },
    )

    release_manifest = ws / ".cache" / "reports" / "release_manifest.v1.json"
    _write_json(
        release_manifest,
        {"version": "v1", "generated_at": "2026-01-07T00:00:00Z", "workspace_root": str(ws)},
    )

    res = run_eval(workspace_root=ws, dry_run=False)
    out_path = Path(res.get("out") or "")
    if not out_path.exists():
        raise SystemExit("benchmark_eval_lenses_github_ops_contract_test failed: eval output missing")

    eval_obj = _load_json(out_path)
    lenses = eval_obj.get("lenses")
    if not isinstance(lenses, dict):
        raise SystemExit("benchmark_eval_lenses_github_ops_contract_test failed: lenses missing")

    if "github_ops_release" not in lenses:
        raise SystemExit("benchmark_eval_lenses_github_ops_contract_test failed: github_ops_release lens missing")

    schema_path = repo_root / "schemas" / "assessment-eval.schema.v1.json"
    Draft202012Validator(_load_json(schema_path)).validate(eval_obj)

    print(json.dumps({"status": "OK", "lens": "github_ops_release"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
