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


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.intake_link_report import run_intake_link_report

    ws = repo_root / ".cache" / "ws_intake_link_contract"
    if ws.exists():
        shutil.rmtree(ws)
    (ws / ".cache" / "index").mkdir(parents=True, exist_ok=True)

    work_intake = {
        "version": "v1",
        "items": [
            {
                "intake_id": "INTAKE-0002",
                "bucket": "PROJECT",
                "priority": "P2",
                "severity": "S2",
                "title": "Other",
                "source_ref": "REQ-OTHER",
                "source_type": "MANUAL_REQUEST",
            },
            {
                "intake_id": "INTAKE-0001",
                "bucket": "TICKET",
                "priority": "P3",
                "severity": "S3",
                "title": "Chat Gateway seed",
                "source_ref": "REQ-20260114-73973d292b4c",
                "source_type": "MANUAL_REQUEST",
                "suggested_extension": ["PRJ-UI-COCKPIT-LITE"],
            },
        ],
    }
    intake_path = ws / ".cache" / "index" / "work_intake.v1.json"
    intake_path.write_text(json.dumps(work_intake, indent=2, sort_keys=True), encoding="utf-8")

    res = run_intake_link_report(workspace_root=ws, req_id="REQ-20260114-73973d292b4c", write_plan=True)
    if res.get("status") not in {"OK", "WARN"}:
        raise SystemExit("intake_link_report_contract_test failed: status invalid")

    report_path = ws / ".cache" / "reports" / "ui_chat_gateway_intake_link.v1.json"
    if not report_path.exists():
        raise SystemExit("intake_link_report_contract_test failed: report missing")

    report = _load_json(report_path)
    if report.get("match_count") != 1:
        raise SystemExit("intake_link_report_contract_test failed: match_count mismatch")

    matches = report.get("matches") if isinstance(report.get("matches"), list) else []
    if matches[0].get("intake_id") != "INTAKE-0001":
        raise SystemExit("intake_link_report_contract_test failed: sorting mismatch")

    plan_path = report.get("plan_path")
    if not isinstance(plan_path, str) or not plan_path:
        raise SystemExit("intake_link_report_contract_test failed: plan_path missing")

    first = report_path.read_text(encoding="utf-8")
    run_intake_link_report(workspace_root=ws, req_id="REQ-20260114-73973d292b4c", write_plan=True)
    second = report_path.read_text(encoding="utf-8")
    if first != second:
        raise SystemExit("intake_link_report_contract_test failed: output not deterministic")


if __name__ == "__main__":
    main()
