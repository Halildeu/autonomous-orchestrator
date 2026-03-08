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
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.ops.work_intake_from_sources import _intake_id, run_work_intake_build

    ws = repo_root / ".cache" / "ws_work_intake_active_summary"
    if ws.exists():
        shutil.rmtree(ws)

    request_open = "REQ-ACTIVE-SUMMARY-OPEN"
    request_done = "REQ-ACTIVE-SUMMARY-DONE"
    for request_id in [request_open, request_done]:
        _write_json(
            ws / ".cache" / "index" / "manual_requests" / f"{request_id}.v1.json",
            {
                "version": "v1",
                "request_id": request_id,
                "created_at": _now_iso(),
                "source": {"type": "human"},
                "artifact_type": "request",
                "domain": "general",
                "kind": "note",
                "impact_scope": "doc-only",
                "text": f"Contract request {request_id}",
            },
        )

    done_intake_id = _intake_id("MANUAL_REQUEST", request_done, "TICKET")
    _write_json(
        ws / ".cache" / "index" / "work_item_state.v1.json",
        {
            "version": "v1",
            "generated_at": _now_iso(),
            "workspace_root": str(ws.resolve()),
            "items": [
                {
                    "work_item_id": done_intake_id,
                    "state": "CLOSED",
                    "last_updated_at": _now_iso(),
                }
            ],
        },
    )

    res = run_work_intake_build(workspace_root=ws)
    if str(res.get("status") or "") not in {"OK", "WARN"}:
        raise SystemExit("work_intake_active_summary_contract_test failed: build status")

    intake_obj = json.loads((ws / ".cache" / "index" / "work_intake.v1.json").read_text(encoding="utf-8"))
    summary = intake_obj.get("summary") if isinstance(intake_obj, dict) else {}
    if int(summary.get("active_count") or -1) != 1:
        raise SystemExit("work_intake_active_summary_contract_test failed: active_count mismatch")
    if int(summary.get("historical_done_count") or -1) != 1:
        raise SystemExit("work_intake_active_summary_contract_test failed: historical_done_count mismatch")
    top_next = summary.get("top_next_actions") if isinstance(summary.get("top_next_actions"), list) else []
    if len(top_next) != 1:
        raise SystemExit("work_intake_active_summary_contract_test failed: top_next_actions length mismatch")
    top_item = top_next[0] if isinstance(top_next[0], dict) else {}
    if str(top_item.get("source_ref") or "") != request_open:
        raise SystemExit("work_intake_active_summary_contract_test failed: top_next_actions must exclude DONE item")
    expected_focus = f"TICKET:{_intake_id('MANUAL_REQUEST', request_open, 'TICKET')}"
    if str(summary.get("next_intake_focus") or "") != expected_focus:
        raise SystemExit("work_intake_active_summary_contract_test failed: next_intake_focus mismatch")

    compaction_path = ws / ".cache" / "reports" / "work_intake_compaction.v1.json"
    if not compaction_path.exists():
        raise SystemExit("work_intake_active_summary_contract_test failed: compaction report missing")
    compaction = json.loads(compaction_path.read_text(encoding="utf-8"))
    if int(compaction.get("historical_done_count") or -1) != 1:
        raise SystemExit("work_intake_active_summary_contract_test failed: compaction historical_done_count mismatch")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
