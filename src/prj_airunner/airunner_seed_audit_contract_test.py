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


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_airunner.airunner_jobs import seed_jobs

    ws = repo_root / ".cache" / "ws_airunner_seed_audit_test"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    res = seed_jobs(workspace_root=ws, kind="SMOKE_FULL", state="queued", count=1)
    if res.get("status") != "OK":
        raise SystemExit("airunner_seed_audit_contract_test failed: seed_jobs status")

    seeded_ids = res.get("seeded_job_ids", [])
    if not seeded_ids:
        raise SystemExit("airunner_seed_audit_contract_test failed: seeded_job_ids missing")

    audit_path = ws / ".cache" / "reports" / "airunner_seed_audit.v1.json"
    if not audit_path.exists():
        raise SystemExit("airunner_seed_audit_contract_test failed: seed audit missing")

    audit = _load_json(audit_path)
    if audit.get("seed_id") not in seeded_ids:
        raise SystemExit("airunner_seed_audit_contract_test failed: seed_id mismatch")
    if str(audit.get("kind")) != "SMOKE_FULL":
        raise SystemExit("airunner_seed_audit_contract_test failed: kind mismatch")
    if str(audit.get("state")) != "queued":
        raise SystemExit("airunner_seed_audit_contract_test failed: state mismatch")
    notes = audit.get("notes") if isinstance(audit.get("notes"), list) else []
    if "seeded=true" not in notes:
        raise SystemExit("airunner_seed_audit_contract_test failed: seeded note missing")

    print(json.dumps({"status": "OK", "seed_id": audit.get("seed_id")}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
