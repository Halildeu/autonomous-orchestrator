from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
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


def _write_selection(path: Path, selected_ids: list[str], workspace_root: Path) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload = {
        "version": "v1",
        "generated_at": generated_at,
        "workspace_root": str(workspace_root),
        "selected_ids": selected_ids,
        "content_hash": hashlib.sha256(
            json.dumps(selected_ids, ensure_ascii=True, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "notes": ["PROGRAM_LED=true"],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _run_clear(ws: Path) -> dict:
    from src.ops.commands.maintenance_cmds import cmd_work_intake_select

    args = argparse.Namespace(
        workspace_root=str(ws),
        mode="clear",
        backup="true",
        intake_id="",
        selected="false",
    )
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cmd_work_intake_select(args)
    if rc != 0:
        raise SystemExit("work_intake_select_clear_contract_test failed: command exit non-zero")
    output = buf.getvalue().strip().splitlines()[-1]
    return json.loads(output)


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    ws = repo_root / ".cache" / "ws_work_intake_select_clear_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    selection_path = ws / ".cache" / "index" / "work_intake_selection.v1.json"
    _write_selection(selection_path, ["INTAKE-AAA", "INTAKE-BBB"], ws)

    first = _run_clear(ws)
    if first.get("status") not in {"OK", "IDLE"}:
        raise SystemExit("work_intake_select_clear_contract_test failed: invalid status on first clear")
    if int(first.get("cleared_count") or 0) != 2:
        raise SystemExit("work_intake_select_clear_contract_test failed: cleared_count mismatch")

    backup_path = first.get("backup_path") or ""
    if not backup_path:
        raise SystemExit("work_intake_select_clear_contract_test failed: backup_path missing")
    backup_full = ws / backup_path
    if not backup_full.exists():
        raise SystemExit("work_intake_select_clear_contract_test failed: backup file missing")

    cleared = json.loads(selection_path.read_text(encoding="utf-8"))
    if cleared.get("selected_ids") != []:
        raise SystemExit("work_intake_select_clear_contract_test failed: selection not cleared")
    notes = cleared.get("notes") if isinstance(cleared.get("notes"), list) else []
    if "CLEARED=true" not in notes:
        raise SystemExit("work_intake_select_clear_contract_test failed: missing CLEARED note")

    second = _run_clear(ws)
    if second.get("status") not in {"OK", "IDLE"}:
        raise SystemExit("work_intake_select_clear_contract_test failed: invalid status on second clear")
    if int(second.get("cleared_count") or 0) != 0:
        raise SystemExit("work_intake_select_clear_contract_test failed: second cleared_count mismatch")

    backups = sorted((ws / ".cache" / "index").glob("work_intake_selection.v1.json.bak*"))
    if len(backups) != 1:
        raise SystemExit("work_intake_select_clear_contract_test failed: backup retention mismatch")


if __name__ == "__main__":
    main()
