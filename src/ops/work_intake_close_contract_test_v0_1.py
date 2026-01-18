from __future__ import annotations

import argparse
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

    from src.ops.commands.work_intake_close_cmds import cmd_work_intake_close
    from src.ops.work_intake_from_sources import _intake_id, run_work_intake_build

    ws = repo_root / ".cache" / "ws_work_intake_close_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    # Seed one MANUAL_REQUEST that maps to bucket=TICKET.
    req_id = "REQ-TEST"
    req_path = ws / ".cache" / "index" / "manual_requests" / f"{req_id}.v1.json"
    _write_json(
        req_path,
        {
            "version": "v1",
            "request_id": req_id,
            "kind": "note",
            "impact_scope": "doc-only",
            "artifact_type": "request",
            "domain": "general",
            "requires_core_change": False,
            "text": "contract",
            "attachments": [],
        },
    )

    intake_id = _intake_id("MANUAL_REQUEST", req_id, "TICKET")
    build1 = run_work_intake_build(workspace_root=ws)
    if build1.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("work_intake_close_contract_test failed: initial build status")

    intake_path = ws / ".cache" / "index" / "work_intake.v1.json"
    intake_obj = json.loads(intake_path.read_text(encoding="utf-8"))
    items = intake_obj.get("items") if isinstance(intake_obj, dict) else []
    before = [it for it in items if isinstance(it, dict) and it.get("intake_id") == intake_id]
    if not before:
        raise SystemExit("work_intake_close_contract_test failed: intake item missing after build")
    if before[0].get("status") == "DONE":
        raise SystemExit("work_intake_close_contract_test failed: item unexpectedly DONE before close")

    # Close it explicitly (workspace-only persistent state).
    rc = cmd_work_intake_close(
        argparse.Namespace(
            workspace_root=str(ws),
            intake_id=intake_id,
            mode="close",
            reason="contract_close",
            owner_tag="contract",
            force="false",
        )
    )
    if rc != 0:
        raise SystemExit("work_intake_close_contract_test failed: close command rc")

    # Rebuild intake; CLOSED state must turn the item into DONE.
    build2 = run_work_intake_build(workspace_root=ws)
    if build2.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("work_intake_close_contract_test failed: rebuild status")

    intake_obj2 = json.loads(intake_path.read_text(encoding="utf-8"))
    items2 = intake_obj2.get("items") if isinstance(intake_obj2, dict) else []
    after = [it for it in items2 if isinstance(it, dict) and it.get("intake_id") == intake_id]
    if not after:
        raise SystemExit("work_intake_close_contract_test failed: intake item missing after rebuild")
    if after[0].get("status") != "DONE":
        raise SystemExit("work_intake_close_contract_test failed: CLOSED state not reflected as DONE")
    if str(after[0].get("closed_reason") or "") != "WORK_ITEM_STATE_CLOSED":
        raise SystemExit("work_intake_close_contract_test failed: missing closed_reason WORK_ITEM_STATE_CLOSED")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

