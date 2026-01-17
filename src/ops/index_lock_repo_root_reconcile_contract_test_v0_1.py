from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _fail(msg: str) -> None:
    raise SystemExit(f"index_lock_repo_root_reconcile_contract_test failed: {msg}")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.index_lock_repo_root_reconcile import run_index_lock_repo_root_reconcile

    ws = repo_root / ".cache" / "ws_index_lock_repo_root_test"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    tmp_repo = repo_root / ".cache" / "test_tmp" / "index_lock_repo_root"
    if tmp_repo.exists():
        shutil.rmtree(tmp_repo)
    (tmp_repo / ".git").mkdir(parents=True, exist_ok=True)
    (tmp_repo / "pyproject.toml").write_text("[tool.test]\n", encoding="utf-8")

    lock_path = tmp_repo / ".git" / "index.lock"
    lock_path.write_text("lock", encoding="utf-8")

    result = run_index_lock_repo_root_reconcile(
        workspace_root=ws,
        out_path=".cache/reports/index_lock_repo_root_reconcile.v0.1.json",
        repo_root_override=tmp_repo,
    )
    if result.get("status") != "OK":
        _fail("status not OK")

    report_path = ws / ".cache" / "reports" / "index_lock_repo_root_reconcile.v0.1.json"
    if not report_path.exists():
        _fail("report missing")

    report = _load_json(report_path)
    moved_path = report.get("moved_path")
    if not moved_path:
        _fail("moved_path missing")
    if lock_path.exists():
        _fail("lock still exists after move")
    if not Path(moved_path).exists():
        _fail("moved_path does not exist")

    tmp_repo2 = repo_root / ".cache" / "test_tmp" / "index_lock_repo_root_missing"
    if tmp_repo2.exists():
        shutil.rmtree(tmp_repo2)
    (tmp_repo2 / ".git").mkdir(parents=True, exist_ok=True)
    (tmp_repo2 / "pyproject.toml").write_text("[tool.test]\n", encoding="utf-8")

    res_noop = run_index_lock_repo_root_reconcile(
        workspace_root=ws,
        out_path=".cache/reports/index_lock_repo_root_reconcile.noop.v0.1.json",
        repo_root_override=tmp_repo2,
    )
    if res_noop.get("status") != "NOOP":
        _fail("noop path did not return NOOP")

    res_fail = run_index_lock_repo_root_reconcile(
        workspace_root=ws,
        out_path="../outside.json",
        repo_root_override=tmp_repo2,
    )
    if res_fail.get("status") != "FAIL":
        _fail("invalid out_path accepted")

    print(json.dumps({"status": "OK", "ts": int(time.time())}, sort_keys=True))


if __name__ == "__main__":
    main()
