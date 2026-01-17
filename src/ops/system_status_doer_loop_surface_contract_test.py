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
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.system_status_report import run_system_status

    ws = repo_root / ".cache" / "ws_doer_loop_surface_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    lock_path = ws / ".cache" / "doer" / "doer_loop_lock.v1.json"
    _write_json(
        lock_path,
        {
            "version": "v1",
            "lease_id": "lease-1",
            "owner_tag": "tester",
            "run_id": "run-1",
            "acquired_at": "2026-01-01T00:00:00Z",
            "expires_at": "2026-01-01T00:10:00Z",
            "heartbeat_at": "2026-01-01T00:00:00Z",
        },
    )

    res = run_system_status(workspace_root=ws, core_root=repo_root, dry_run=False)
    out_path = Path(str(res.get("out_json") or ""))
    if not out_path.exists():
        raise SystemExit("system_status_doer_loop_surface_contract_test failed: status report missing")
    report = _load_json(out_path)
    sections = report.get("sections") if isinstance(report.get("sections"), dict) else {}
    doer_loop = sections.get("doer_loop") if isinstance(sections.get("doer_loop"), dict) else {}
    if doer_loop.get("lock_state") != "LOCKED":
        raise SystemExit("system_status_doer_loop_surface_contract_test failed: lock_state not surfaced")


if __name__ == "__main__":
    main()
