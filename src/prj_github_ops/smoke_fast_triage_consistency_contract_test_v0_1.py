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


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_github_ops.smoke_fast_triage import run_smoke_fast_triage

    tmp_parent = repo_root / ".cache"
    tmp_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=tmp_parent) as tmp_dir:
        ws_root = Path(tmp_dir)
        job_id = "TEST-PASS-TRIAGE"
        report_path = (
            ws_root
            / ".cache"
            / "reports"
            / "github_ops_jobs"
            / f"github_ops_job_{job_id}.v1.json"
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_payload = {
            "job_id": job_id,
            "kind": "SMOKE_FAST",
            "status": "PASS",
            "failure_class": "PASS",
        }
        report_path.write_text(json.dumps(report_payload, indent=2, sort_keys=True), encoding="utf-8")

        job_dir = ws_root / ".cache" / "github_ops" / "jobs" / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "stderr.log").write_text("", encoding="utf-8")
        (job_dir / "stdout.log").write_text("", encoding="utf-8")
        rc_payload = {"rc": 0, "workspace_root": str(ws_root)}
        (job_dir / "rc.json").write_text(json.dumps(rc_payload, indent=2, sort_keys=True), encoding="utf-8")

        res = run_smoke_fast_triage(workspace_root=ws_root, job_id=job_id)
        if res.get("status") != "OK":
            raise SystemExit("triage contract test failed: status != OK")

        triage_path = ws_root / ".cache" / "reports" / "smoke_fast_triage.v1.json"
        if not triage_path.exists():
            raise SystemExit("triage contract test failed: report missing")
        triage = json.loads(triage_path.read_text(encoding="utf-8"))
        if str(triage.get("job_status") or "").upper() != "PASS":
            raise SystemExit("triage contract test failed: job_status not PASS")
        if str(triage.get("recommended_class") or "") != "PASS":
            raise SystemExit("triage contract test failed: recommended_class not PASS")
        override = triage.get("classification_override")
        if not isinstance(override, dict) or override.get("used") is not False:
            raise SystemExit("triage contract test failed: classification_override.used not false")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
