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


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.benchmark.assessment_runner import run_assessment

    ws = repo_root / ".cache" / "ws_assessment_cursor_heartbeat_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    # Minimal inputs to keep assessment runner happy (deterministic; no network).
    _write_json(
        ws / ".cache" / "reports" / "system_status.v1.json",
        {"version": "v1", "generated_at": "2026-01-09T00:00:00Z", "status": "OK"},
    )
    _write_json(
        ws / ".cache" / "index" / "pack_capability_index.v1.json",
        {"version": "v1", "generated_at": "2026-01-09T00:00:00Z", "packs": []},
    )
    _write_json(
        ws / ".cache" / "script_budget" / "report.json",
        {"exceeded_hard": [], "exceeded_soft": [], "function_hard": [], "function_soft": []},
    )

    heartbeat_path = ws / ".cache" / "airunner" / "airunner_heartbeat.v1.json"
    _write_json(
        heartbeat_path,
        {"version": "v1", "last_tick_at": "2000-01-01T00:00:00Z", "ended_at": "2026-01-10T00:00:00Z", "last_status": "OK"},
    )

    res1 = run_assessment(workspace_root=ws, dry_run=False)
    _assert(res1.get("status") == "OK", f"unexpected status: {res1.get('status')}")
    cursor_path = ws / ".cache" / "index" / "assessment_cursor.v1.json"
    _assert(cursor_path.exists(), "cursor missing after first run")
    sha1 = str(_load_json(cursor_path).get("inputs_sha256") or "")
    _assert(bool(sha1), "inputs_sha256 missing after first run")

    # No changes → inputs sha should stay stable.
    res2 = run_assessment(workspace_root=ws, dry_run=False)
    _assert(res2.get("status") == "OK", f"unexpected status: {res2.get('status')}")
    sha2 = str(_load_json(cursor_path).get("inputs_sha256") or "")
    _assert(sha2 == sha1, "inputs_sha256 changed without input changes")

    # Heartbeat changes must invalidate the cursor (no manual cursor deletion required).
    _write_json(
        heartbeat_path,
        {"version": "v1", "last_tick_at": "2000-01-01T00:00:00Z", "ended_at": "2026-01-11T00:00:00Z", "last_status": "OK"},
    )
    res3 = run_assessment(workspace_root=ws, dry_run=False)
    _assert(res3.get("status") == "OK", f"unexpected status: {res3.get('status')}")
    sha3 = str(_load_json(cursor_path).get("inputs_sha256") or "")
    _assert(sha3 != sha1, "inputs_sha256 did not change after heartbeat update")

    print(json.dumps({"status": "OK", "sha_changed": True}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
