from __future__ import annotations

import json
import shutil
import tempfile
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    from src.ops.commands import maintenance_policy_cmds as policy_cmds

    temp_root = Path(tempfile.mkdtemp(prefix="reaper_cleanup_guard_contract_"))
    try:
        _write_json(
            temp_root / "policies" / "policy_retention.v1.json",
            {
                "version": "v1",
                "evidence_days": 0,
                "dlq_days": 0,
                "cache_days": 0,
                "allow_critical_cache_delete": False,
                "cache_exclude_paths": [],
                "cache_exclude_globs": [],
            },
        )
        (temp_root / ".cache" / "reports").mkdir(parents=True, exist_ok=True)

        critical = temp_root / ".cache" / "ws_customer_default" / ".cache" / "index" / "mechanisms.registry.v1.json"
        critical.parent.mkdir(parents=True, exist_ok=True)
        critical.write_text("{\"status\":\"ok\"}\n", encoding="utf-8")

        stale = temp_root / ".cache" / "tmp" / "old.tmp"
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text("tmp\n", encoding="utf-8")

        old_ts = datetime(2000, 1, 1, tzinfo=timezone.utc).timestamp()
        import os

        os.utime(critical, (old_ts, old_ts))
        os.utime(stale, (old_ts, old_ts))

        old_repo_root = policy_cmds.repo_root
        policy_cmds.repo_root = lambda: temp_root
        try:
            rc = policy_cmds.cmd_reaper(
                Namespace(
                    dry_run="false",
                    now="2026-03-11T00:00:00Z",
                    out=str(temp_root / ".cache" / "reports" / "reaper_delete.v1.json"),
                )
            )
        finally:
            policy_cmds.repo_root = old_repo_root

        if rc != 0:
            raise SystemExit("reaper_cleanup_guard_contract_test failed: cmd_reaper returned non-zero")
        if not critical.exists():
            raise SystemExit("reaper_cleanup_guard_contract_test failed: critical file deleted")
        if stale.exists():
            raise SystemExit("reaper_cleanup_guard_contract_test failed: stale non-critical file not deleted")

        pre_path = temp_root / ".cache" / "reports" / "reaper_cleanup_pre_snapshot.v1.json"
        post_path = temp_root / ".cache" / "reports" / "reaper_cleanup_post_validate.v1.json"
        report_path = temp_root / ".cache" / "reports" / "reaper_delete.v1.json"
        if not pre_path.exists() or not post_path.exists() or not report_path.exists():
            raise SystemExit("reaper_cleanup_guard_contract_test failed: required guard reports missing")

        post = json.loads(post_path.read_text(encoding="utf-8"))
        if str(post.get("status") or "") != "PASS":
            raise SystemExit("reaper_cleanup_guard_contract_test failed: post validate status is not PASS")

        report = json.loads(report_path.read_text(encoding="utf-8"))
        guard = report.get("guard") if isinstance(report.get("guard"), dict) else {}
        if str(guard.get("status") or "") != "PASS":
            raise SystemExit("reaper_cleanup_guard_contract_test failed: report guard status is not PASS")
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
