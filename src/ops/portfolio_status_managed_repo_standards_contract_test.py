from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.ops.roadmap_cli import cmd_portfolio_status


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("JSON_NOT_OBJECT")
    return obj


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    ws = repo_root / ".cache" / "ws_portfolio_status_managed_repo_standards"
    ws.mkdir(parents=True, exist_ok=True)

    sync_report = ws / ".cache" / "reports" / "managed_repo_standards_sync" / "report.v1.json"
    _write_json(
        sync_report,
        {
            "version": "v1",
            "mode": "dry-run",
            "target_count": 1,
            "failed_count": 0,
            "results": [
                {
                    "repo_root": "/tmp/repo-portfolio-1",
                    "status": "OK",
                    "changed_files": 1,
                    "files": [{"path": "standards.lock", "action": "would_update"}],
                }
            ],
        },
    )

    rc = cmd_portfolio_status(
        argparse.Namespace(
            workspace_root=str(ws.relative_to(repo_root)),
            mode="json",
        )
    )
    if int(rc) != 0:
        raise SystemExit(f"portfolio_status_managed_repo_standards_contract_test failed: rc={rc}")

    report_path = ws / ".cache" / "reports" / "portfolio_status.v1.json"
    if not report_path.exists():
        raise SystemExit("portfolio_status_managed_repo_standards_contract_test failed: report missing")

    report = _read_json(report_path)
    managed = report.get("managed_repo_standards")
    if not isinstance(managed, dict):
        raise SystemExit("portfolio_status_managed_repo_standards_contract_test failed: section missing")
    if str(managed.get("status")) != "WARN":
        raise SystemExit("portfolio_status_managed_repo_standards_contract_test failed: expected status WARN")
    if int(managed.get("drift_pending_count") or 0) != 1:
        raise SystemExit("portfolio_status_managed_repo_standards_contract_test failed: pending count mismatch")
    scoreboard = report.get("drift_scoreboard")
    if not isinstance(scoreboard, dict):
        raise SystemExit("portfolio_status_managed_repo_standards_contract_test failed: drift_scoreboard missing")
    if str(scoreboard.get("status")) != "WARN":
        raise SystemExit("portfolio_status_managed_repo_standards_contract_test failed: drift_scoreboard status mismatch")

    print(
        json.dumps(
            {
                "status": "OK",
                "managed_repo_standards_status": managed.get("status"),
                "drift_pending_count": managed.get("drift_pending_count"),
                "drift_scoreboard_status": scoreboard.get("status"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
