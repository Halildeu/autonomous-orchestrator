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


def _extract_lines(stderr_text: str) -> list[str]:
    lines: list[str] = []
    for line in stderr_text.splitlines():
        line = line.strip()
        if not line:
            continue
        lines.append(line[:200])
        if len(lines) >= 10:
            break
    return lines


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_github_ops.smoke_fast_triage import run_smoke_fast_triage
    from src.prj_github_ops.github_ops_support_v2 import _hash_text

    job_id = "contract-smoke-fast-triage"
    stderr_text = "Smoke test failed: catalog must include pack-demo.\n"

    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_root = Path(tmp_dir)
        job_dir = ws_root / ".cache" / "github_ops" / "jobs" / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "stderr.log").write_text(stderr_text, encoding="utf-8")
        (job_dir / "stdout.log").write_text("", encoding="utf-8")
        _write_json(job_dir / "rc.json", {"rc": 1})

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
            raise SystemExit("smoke_fast_triage_contract_test failed: triage missing")
        triage = json.loads(triage_path.read_text(encoding="utf-8"))
        markers = triage.get("markers") if isinstance(triage, dict) else None
        if not isinstance(markers, list) or "DEMO_CATALOG_MISSING" not in markers:
            raise SystemExit("smoke_fast_triage_contract_test failed: markers missing")
        if triage.get("recommended_class") != "DEMO_CATALOG_MISSING":
            raise SystemExit("smoke_fast_triage_contract_test failed: recommended_class mismatch")

        expected_sig = _hash_text("DEMO_CATALOG_MISSING|" + "|".join(_extract_lines(stderr_text)))
        if triage.get("signature_hash") != expected_sig:
            raise SystemExit("smoke_fast_triage_contract_test failed: signature mismatch")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
