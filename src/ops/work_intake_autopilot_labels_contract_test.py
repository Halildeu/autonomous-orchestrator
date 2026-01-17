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

    from src.ops.work_intake_from_sources import run_work_intake_build

    ws = repo_root / ".cache" / "ws_work_intake_autopilot_labels"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    request_id = "REQ-TEST-AUTOPILOT-001"
    manual_request = {
        "version": "v1",
        "request_id": request_id,
        "received_at": _now_iso(),
        "source": {"type": "chat"},
        "text": "Doc note",
        "kind": "note",
        "impact_scope": "doc-only",
        "requires_core_change": False,
    }
    _write_json(ws / ".cache" / "index" / "manual_requests" / f"{request_id}.v1.json", manual_request)

    res = run_work_intake_build(workspace_root=ws)
    if res.get("status") not in {"OK", "WARN"}:
        raise SystemExit("work_intake_autopilot_labels_contract_test failed: build status")

    out_path = ws / ".cache" / "index" / "work_intake.v1.json"
    if not out_path.exists():
        raise SystemExit("work_intake_autopilot_labels_contract_test failed: output missing")

    work_intake = json.loads(out_path.read_text(encoding="utf-8"))
    items = [i for i in work_intake.get("items", []) if isinstance(i, dict)]
    target = [i for i in items if i.get("source_ref") == request_id]
    if not target:
        raise SystemExit("work_intake_autopilot_labels_contract_test failed: item missing")

    item = target[0]
    if item.get("autopilot_allowed") is not True:
        raise SystemExit("work_intake_autopilot_labels_contract_test failed: autopilot_allowed expected true")
    if item.get("autopilot_reason") != "DOC_ONLY":
        raise SystemExit("work_intake_autopilot_labels_contract_test failed: autopilot_reason mismatch")
    if item.get("autopilot_selected") is True:
        raise SystemExit("work_intake_autopilot_labels_contract_test failed: autopilot_selected default should be false")


if __name__ == "__main__":
    main()
