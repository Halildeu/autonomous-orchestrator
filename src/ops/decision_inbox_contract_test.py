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


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.decision_inbox import run_decision_inbox_build

    ws = repo_root / ".cache" / "ws_decision_inbox_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    exec_report = {
        "version": "v1",
        "generated_at": _now_iso(),
        "entries": [
            {
                "intake_id": "INTAKE-DECISION-1",
                "bucket": "TICKET",
                "status": "SKIPPED",
                "skip_reason": "DECISION_NEEDED",
                "autopilot_reason": "DECISION_NEEDED",
                "evidence_paths": [],
            }
        ],
    }
    _write_json(ws / ".cache" / "reports" / "work_intake_exec_ticket.v1.json", exec_report)

    res = run_decision_inbox_build(workspace_root=ws)
    if res.get("status") != "OK":
        raise SystemExit("decision_inbox_contract_test failed: expected OK status")

    inbox_path = ws / ".cache" / "index" / "decision_inbox.v1.json"
    if not inbox_path.exists():
        raise SystemExit("decision_inbox_contract_test failed: decision_inbox missing")

    first = inbox_path.read_text(encoding="utf-8")
    res2 = run_decision_inbox_build(workspace_root=ws)
    if res2.get("status") not in {"OK", "IDLE"}:
        raise SystemExit("decision_inbox_contract_test failed: second run status invalid")
    second = inbox_path.read_text(encoding="utf-8")
    if first != second:
        raise SystemExit("decision_inbox_contract_test failed: output not deterministic")


if __name__ == "__main__":
    main()
