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

    from src.benchmark.integrity_utils import build_integrity_snapshot, load_policy_integrity

    ws = repo_root / ".cache" / "ws_integrity_snapshot_stability"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    _write_json(ws / ".cache" / "reports" / "system_status.v1.json", {"version": "v1", "stamp": "a"})
    _write_json(ws / ".cache" / "index" / "pack_capability_index.v1.json", {"version": "v1"})
    _write_json(ws / ".cache" / "script_budget" / "report.json", {"version": "v1"})

    policy = load_policy_integrity(core_root=repo_root, workspace_root=ws)
    snapshot1 = build_integrity_snapshot(
        workspace_root=ws,
        core_root=repo_root,
        policy=policy,
        previous_snapshot=None,
    )

    _write_json(ws / ".cache" / "reports" / "system_status.v1.json", {"version": "v1", "stamp": "b"})

    snapshot2 = build_integrity_snapshot(
        workspace_root=ws,
        core_root=repo_root,
        policy=policy,
        previous_snapshot=snapshot1,
    )

    if int(snapshot2.get("mismatch_count") or 0) != 0:
        raise SystemExit("integrity_snapshot_stability_contract_test failed: mismatch_count must be 0")

    print(json.dumps({"status": "OK", "mismatch_count": snapshot2.get("mismatch_count")}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
