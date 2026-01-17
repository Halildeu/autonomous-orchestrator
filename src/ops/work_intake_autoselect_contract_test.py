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


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _make_ws(repo_root: Path, name: str) -> Path:
    ws = repo_root / ".cache" / name
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def _write_manual_request(ws: Path, request_id: str) -> None:
    _write_json(
        ws / ".cache" / "index" / "manual_requests" / f"{request_id}.v1.json",
        {
            "version": "v1",
            "request_id": request_id,
            "received_at": _now_iso(),
            "source": {"type": "chat"},
            "text": "Autoselect contract test",
            "impact_scope": "doc-only",
            "kind": "note",
            "requires_core_change": False,
        },
    )


def _write_autoselect_override(ws: Path) -> None:
    _write_json(
        ws / ".cache" / "policy_overrides" / "policy_autopilot_apply.override.v1.json",
        {"version": "v1", "auto_select": {"enabled": True, "max_select": 2}},
    )


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.work_intake_autoselect import run_work_intake_autoselect

    ws = _make_ws(repo_root, "ws_work_intake_autoselect")
    _write_autoselect_override(ws)
    _write_manual_request(ws, "REQ-TEST-AUTOSELECT-001")

    res = run_work_intake_autoselect(workspace_root=ws, limit=2)
    if res.get("status") != "OK":
        raise SystemExit("work_intake_autoselect_contract_test failed: expected OK")
    if res.get("selected_count") != 1:
        raise SystemExit("work_intake_autoselect_contract_test failed: expected 1 selected item")

    sel_path = ws / ".cache" / "index" / "work_intake_selection.v1.json"
    if not sel_path.exists():
        raise SystemExit("work_intake_autoselect_contract_test failed: selection file missing")

    res2 = run_work_intake_autoselect(workspace_root=ws, limit=2)
    if res2.get("selected_ids") != res.get("selected_ids"):
        raise SystemExit("work_intake_autoselect_contract_test failed: selection not deterministic")

    ws_empty = _make_ws(repo_root, "ws_work_intake_autoselect_empty")
    _write_autoselect_override(ws_empty)
    res_empty = run_work_intake_autoselect(workspace_root=ws_empty, limit=2)
    if res_empty.get("status") != "IDLE":
        raise SystemExit("work_intake_autoselect_contract_test failed: expected IDLE with no items")

    print("OK")


if __name__ == "__main__":
    main()
