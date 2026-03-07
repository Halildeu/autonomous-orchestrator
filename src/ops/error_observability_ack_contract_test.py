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

    from src.ops.error_observability_report import run_error_observability, run_error_observability_ack

    ws = repo_root / ".cache" / "ws_error_observability_ack"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    _write_json(
        ws / ".cache" / "reports" / "module_delivery_lanes" / "api.v1.json",
        {
            "version": "v1",
            "kind": "module-delivery-lane-report",
            "lane": "api",
            "status": "FAIL",
            "started_at": "2026-03-07T13:00:00Z",
            "finished_at": "2026-03-07T13:01:00Z",
            "return_code": 2,
            "timed_out": False,
            "stderr_tail": ["api failed"],
        },
    )
    report_before = run_error_observability(workspace_root=ws)
    if int(report_before.get("active_items_total") or 0) != 1:
        raise SystemExit("error_observability_ack_contract_test failed: active before mismatch")
    if int(report_before.get("acked_items_total") or 0) != 0:
        raise SystemExit("error_observability_ack_contract_test failed: acked before mismatch")

    ack_result = run_error_observability_ack(workspace_root=ws, mode="ack-current")
    if str(ack_result.get("status") or "") != "OK":
        raise SystemExit("error_observability_ack_contract_test failed: ack status mismatch")
    if int(ack_result.get("added") or 0) != 1:
        raise SystemExit("error_observability_ack_contract_test failed: ack add mismatch")
    if int(ack_result.get("active_items_after") or 0) != 0:
        raise SystemExit("error_observability_ack_contract_test failed: active after mismatch")

    report_after = run_error_observability(workspace_root=ws)
    if str(report_after.get("status") or "") != "OK":
        raise SystemExit("error_observability_ack_contract_test failed: report status mismatch")
    if int(report_after.get("active_items_total") or 0) != 0:
        raise SystemExit("error_observability_ack_contract_test failed: report active mismatch")
    if int(report_after.get("acked_items_total") or 0) != 1:
        raise SystemExit("error_observability_ack_contract_test failed: report acked mismatch")
    notes = report_after.get("notes") if isinstance(report_after.get("notes"), list) else []
    if "all_items_acked" not in notes:
        raise SystemExit("error_observability_ack_contract_test failed: notes mismatch")
    items = report_after.get("items") if isinstance(report_after.get("items"), list) else []
    if not items or str(items[0].get("ack_state") or "") != "ACKED":
        raise SystemExit("error_observability_ack_contract_test failed: item ack state mismatch")
    if str(report_after.get("latest_source_type") or "") != "":
        raise SystemExit("error_observability_ack_contract_test failed: latest source should be cleared")

    clear_result = run_error_observability_ack(workspace_root=ws, mode="clear")
    if str(clear_result.get("status") or "") != "OK":
        raise SystemExit("error_observability_ack_contract_test failed: clear status mismatch")
    if int(clear_result.get("ack_entries_total") or 0) != 0:
        raise SystemExit("error_observability_ack_contract_test failed: clear ack entries mismatch")

    report_cleared = run_error_observability(workspace_root=ws)
    if str(report_cleared.get("status") or "") != "WARN":
        raise SystemExit("error_observability_ack_contract_test failed: cleared report status mismatch")
    if int(report_cleared.get("active_items_total") or 0) != 1:
        raise SystemExit("error_observability_ack_contract_test failed: cleared active mismatch")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
