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


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.index_lock_file_diagnostics import run_index_lock_file_diagnostics

    ws = repo_root / ".cache" / "ws_index_lock_diag_test"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    tmp_repo = repo_root / ".cache" / "test_tmp" / "index_lock_repo_diag"
    if tmp_repo.exists():
        shutil.rmtree(tmp_repo)
    (tmp_repo / ".git").mkdir(parents=True, exist_ok=True)
    (tmp_repo / "pyproject.toml").write_text("[tool.test]\n", encoding="utf-8")

    lock_path = tmp_repo / ".git" / "index.lock"
    lock_path.write_text("lock", encoding="utf-8")
    stat_before = lock_path.stat()

    result = run_index_lock_file_diagnostics(
        workspace_root=ws,
        out_path=".cache/reports/index_lock_file_diagnostics.v0.1.json",
        repo_root_override=tmp_repo,
    )
    if result.get("status") != "OK":
        raise SystemExit("index_lock_file_diagnostics_contract_test failed: status not OK.")

    report_path = ws / ".cache" / "reports" / "index_lock_file_diagnostics.v0.1.json"
    if not report_path.exists():
        raise SystemExit("index_lock_file_diagnostics_contract_test failed: report missing.")

    report = _load_json(report_path)
    if report.get("lock_exists") is not True:
        raise SystemExit("index_lock_file_diagnostics_contract_test failed: lock_exists false.")
    if report.get("lock_path") != str(lock_path):
        raise SystemExit("index_lock_file_diagnostics_contract_test failed: lock_path mismatch.")

    stat_after = lock_path.stat()
    if stat_after.st_size != stat_before.st_size:
        raise SystemExit("index_lock_file_diagnostics_contract_test failed: lock file size changed.")
    if int(stat_after.st_mtime) != int(stat_before.st_mtime):
        raise SystemExit("index_lock_file_diagnostics_contract_test failed: lock file mtime changed.")

    res_fail = run_index_lock_file_diagnostics(
        workspace_root=ws,
        out_path="../outside.json",
        repo_root_override=tmp_repo,
    )
    if res_fail.get("status") != "FAIL":
        raise SystemExit("index_lock_file_diagnostics_contract_test failed: invalid out_path accepted.")

    print(json.dumps({"status": "OK", "workspace": str(ws), "ts": int(time.time())}, sort_keys=True))


if __name__ == "__main__":
    main()
