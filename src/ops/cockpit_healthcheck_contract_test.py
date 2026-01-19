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


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.cockpit_healthcheck import run_cockpit_healthcheck

    ws = repo_root / ".cache" / "ws_cockpit_healthcheck_test"
    if ws.exists():
        shutil.rmtree(ws)
    (ws / ".cache" / "reports").mkdir(parents=True, exist_ok=True)
    _write_json(ws / ".cache" / "reports" / "system_status.v1.json", {"status": "OK"})
    _write_json(
        ws / ".cache" / "index" / "work_item_claims.v1.json",
        {
            "claims": [
                {
                    "work_item_id": "WORK-TEST-1",
                    "owner_tag": "cockpit-healthcheck-test",
                    "owner_session": "contract-test",
                    "acquired_at": "2026-01-01T00:00:00Z",
                    "expires_at": "2099-01-01T00:00:00Z",
                    "ttl_seconds": 3600,
                }
            ]
        },
    )

    res = run_cockpit_healthcheck(workspace_root=ws, port=0)
    out_json = res.get("out_json")
    if not isinstance(out_json, str) or not out_json:
        raise SystemExit("cockpit_healthcheck_contract_test failed: out_json missing")
    out_path = ws / out_json
    if not out_path.exists():
        raise SystemExit("cockpit_healthcheck_contract_test failed: report missing")
    report = json.loads(out_path.read_text(encoding="utf-8"))
    if report.get("status") not in {"OK", "WARN"}:
        raise SystemExit("cockpit_healthcheck_contract_test failed: status invalid")
    if not isinstance(report.get("port"), int):
        raise SystemExit("cockpit_healthcheck_contract_test failed: port missing")
    checks = report.get("checks")
    if not isinstance(checks, dict):
        raise SystemExit("cockpit_healthcheck_contract_test failed: checks missing")
    locks_check = checks.get("/api/locks")
    if not isinstance(locks_check, dict):
        raise SystemExit("cockpit_healthcheck_contract_test failed: /api/locks check missing")
    if locks_check.get("ok") is not True:
        raise SystemExit("cockpit_healthcheck_contract_test failed: /api/locks check not ok")

    op_check = report.get("op_check")
    if not isinstance(op_check, dict):
        raise SystemExit("cockpit_healthcheck_contract_test failed: op_check missing")
    if op_check.get("ok") is not True:
        raise SystemExit("cockpit_healthcheck_contract_test failed: op_check not ok")
    if str(op_check.get("job_status") or "").upper() != "DONE":
        raise SystemExit("cockpit_healthcheck_contract_test failed: op job not DONE")
    mode = str(op_check.get("mode") or "")
    if mode not in {"async", "sync"}:
        raise SystemExit("cockpit_healthcheck_contract_test failed: op_check mode invalid")
    poll = op_check.get("poll")
    if not isinstance(poll, dict):
        raise SystemExit("cockpit_healthcheck_contract_test failed: op_check poll missing")
    try:
        attempts = int(poll.get("attempts") or 0)
    except Exception:
        attempts = -1
    if mode == "async" and attempts < 1:
        raise SystemExit("cockpit_healthcheck_contract_test failed: async op had no poll attempts")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
