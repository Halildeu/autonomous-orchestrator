from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_airunner import smoke_full_job
    from src.prj_github_ops.smoke_fast_triage import run_smoke_fast_triage

    job_id = "contract-smoke-fast-pointer"

    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_root = Path(tmp_dir)
        smoke_full_job._ensure_demo_public_candidates_bundle(ws_root)
        smoke_full_job._ensure_demo_public_candidates_pointer(ws_root)

        pointer_path = ws_root / ".cache" / "artifacts" / "public_candidates.pointer.v1.json"
        if not pointer_path.exists():
            raise SystemExit("public_candidates pointer missing after ensure")
        first = pointer_path.read_text(encoding="utf-8")
        smoke_full_job._ensure_demo_public_candidates_pointer(ws_root)
        second = pointer_path.read_text(encoding="utf-8")
        if first != second:
            raise SystemExit("public_candidates pointer ensure not deterministic")

        job_dir = ws_root / ".cache" / "github_ops" / "jobs" / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        stderr_text = (
            "Smoke test failed: M6.8 apply must write pointer: "
            ".cache/artifacts/public_candidates.pointer.v1.json\n"
        )
        (job_dir / "stderr.log").write_text(stderr_text, encoding="utf-8")
        (job_dir / "stdout.log").write_text("", encoding="utf-8")
        _write_json(job_dir / "rc.json", {"rc": 1, "workspace_root": str(ws_root)})

        job_report = {
            "job_id": job_id,
            "status": "FAIL",
            "kind": "SMOKE_FAST",
            "failure_class": "OTHER",
            "result_paths": [
                str(Path(".cache") / "github_ops" / "jobs" / job_id / "stderr.log"),
                str(Path(".cache") / "github_ops" / "jobs" / job_id / "stdout.log"),
                str(Path(".cache") / "github_ops" / "jobs" / job_id / "rc.json"),
            ],
        }
        report_path = ws_root / ".cache" / "reports" / "github_ops_jobs" / f"github_ops_job_{job_id}.v1.json"
        _write_json(report_path, job_report)

        run_smoke_fast_triage(workspace_root=ws_root, job_id=job_id, detail=True)

        triage_path = ws_root / ".cache" / "reports" / "smoke_fast_triage.v1.json"
        if not triage_path.exists():
            raise SystemExit("smoke_fast_triage did not produce a report")
        triage = json.loads(triage_path.read_text(encoding="utf-8"))
        pointer = triage.get("public_candidates_pointer") if isinstance(triage, dict) else None
        if not isinstance(pointer, dict):
            raise SystemExit("public_candidates_pointer missing in triage")
        if pointer.get("exists_all") is not True or pointer.get("json_valid_all") is not True:
            raise SystemExit("public_candidates_pointer not reported as present+valid")
        expected_paths = pointer.get("expected_paths")
        if not isinstance(expected_paths, list) or str(pointer_path) not in expected_paths:
            raise SystemExit("public_candidates_pointer expected_paths missing pointer path")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
