from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.ops.managed_repo_standards import build_managed_repo_standards_summary


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mrs-contract-") as td:
        root = Path(td).resolve()
        core_root = root / "core"
        workspace_root = core_root / ".cache" / "ws_customer_default"
        workspace_root.mkdir(parents=True, exist_ok=True)

        manifest_path = workspace_root / ".cache" / "managed_repos.v1.json"
        _write_json(
            manifest_path,
            {
                "version": "v1",
                "repos": [
                    {"repo_root": "/tmp/repo-a"},
                    {"repo_root": "/tmp/repo-b"},
                    {"repo_root": "/tmp/repo-c"},
                ],
            },
        )

        report_path = workspace_root / ".cache" / "reports" / "managed_repo_standards_sync" / "report.v1.json"
        _write_json(
            report_path,
            {
                "version": "v1",
                "mode": "dry-run",
                "target_count": 3,
                "failed_count": 1,
                "results": [
                    {
                        "repo_root": "/tmp/repo-a",
                        "status": "OK",
                        "changed_files": 1,
                        "files": [{"path": "standards.lock", "action": "would_update"}],
                    },
                    {
                        "repo_root": "/tmp/repo-b",
                        "status": "OK",
                        "changed_files": 0,
                        "files": [{"path": "standards.lock", "action": "no_change"}],
                    },
                    {
                        "repo_root": "/tmp/repo-c",
                        "status": "FAIL",
                        "changed_files": 0,
                        "files": [{"path": "standards.lock", "action": "error"}],
                    },
                ],
            },
        )

        summary = build_managed_repo_standards_summary(
            workspace_root=workspace_root,
            core_root=core_root,
            max_repos=10,
        )
        if str(summary.get("status")) != "FAIL":
            raise SystemExit("managed_repo_standards_summary_contract_test failed: expected status FAIL")
        if int(summary.get("drift_pending_count") or 0) != 1:
            raise SystemExit("managed_repo_standards_summary_contract_test failed: expected drift_pending_count=1")
        if int(summary.get("failed_count") or 0) != 1:
            raise SystemExit("managed_repo_standards_summary_contract_test failed: expected failed_count=1")
        if int(summary.get("clean_count") or 0) != 1:
            raise SystemExit("managed_repo_standards_summary_contract_test failed: expected clean_count=1")
        print(
            json.dumps(
                {
                    "status": "OK",
                    "summary_status": summary.get("status"),
                    "drift_pending_count": summary.get("drift_pending_count"),
                    "failed_count": summary.get("failed_count"),
                    "clean_count": summary.get("clean_count"),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
