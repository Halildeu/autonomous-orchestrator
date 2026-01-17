from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_release_automation.pr_merge_e2e import run_pr_merge_e2e

    ws_root = repo_root / ".cache" / "ws_customer_default" / ".cache" / "test_tmp" / "pr_merge_e2e_contract"
    if ws_root.exists():
        shutil.rmtree(ws_root)
    (ws_root / ".cache" / "reports").mkdir(parents=True, exist_ok=True)

    res = run_pr_merge_e2e(workspace_root=ws_root, base_branch="main", allow_network=False, dry_run=True)
    _assert(res.get("status") == "IDLE", "Expected IDLE in dry-run")

    report_rel = res.get("report_path")
    _assert(report_rel == ".cache/reports/pr_merge_e2e.v1.json", "Expected fixed report_path")

    report_abs = ws_root / report_rel
    _assert(report_abs.exists(), "Expected report file to be written")
    parsed = json.loads(report_abs.read_text(encoding="utf-8"))
    _assert(parsed.get("status") == "IDLE", "Report status should be IDLE")
    _assert(parsed.get("version") == "v0.1", "Report version should be v0.1")
    _assert(parsed.get("workspace_root") == str(ws_root), "workspace_root should match")
    _assert(parsed.get("ts") <= _now_iso(), "ts should look ISO-like and not be in the far future")

    print("OK")


if __name__ == "__main__":
    main()

