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
    from src.ops.work_intake_exec_ticket import run_work_intake_exec_ticket

    ws = repo_root / ".cache" / "ws_work_intake_exec_repo_guard"
    if ws.exists():
        shutil.rmtree(ws)

    _write_json(
        ws / ".cache" / "index" / "workspace_repo_binding.v1.json",
        {
            "version": "v1",
            "kind": "workspace-repo-binding",
            "generated_at": _now_iso(),
            "workspace_root": str(ws.resolve()),
            "repo_root": "/tmp/repo-A",
            "repo_slug": "repo-a",
            "repo_id": "repo-A",
            "source": "work_intake_exec_repo_guard_contract_test",
        },
    )

    _write_json(
        ws / ".cache" / "index" / "work_intake.v1.json",
        {
            "version": "v1",
            "generated_at": _now_iso(),
            "workspace_root": str(ws.resolve()),
            "status": "OK",
            "plan_policy": "optional",
            "items": [
                {
                    "intake_id": "INTAKE-MISMATCH-1",
                    "bucket": "TICKET",
                    "severity": "S3",
                    "priority": "P3",
                    "status": "OPEN",
                    "title": "Mismatch guard test",
                    "source_type": "SCRIPT_BUDGET",
                    "source_ref": "docs/README.md",
                    "evidence_paths": [".cache/script_budget/report.json"],
                    "owner_tenant": "CORE",
                    "layer": "L2",
                    "repo_id": "repo-B",
                    "source_repo_root": "/tmp/repo-B",
                    "autopilot_allowed": True,
                    "autopilot_selected": True,
                }
            ],
            "summary": {
                "total_count": 1,
                "counts_by_bucket": {
                    "ROADMAP": 0,
                    "PROJECT": 0,
                    "TICKET": 1,
                    "INCIDENT": 0,
                },
                "top_next_actions": [
                    {
                        "intake_id": "INTAKE-MISMATCH-1",
                        "bucket": "TICKET",
                        "severity": "S3",
                        "priority": "P3",
                        "status": "OPEN",
                        "title": "Mismatch guard test",
                        "source_type": "SCRIPT_BUDGET",
                        "source_ref": "docs/README.md",
                    }
                ],
                "next_intake_focus": "TICKET:INTAKE-MISMATCH-1",
            },
            "notes": [],
        },
    )

    res = run_work_intake_exec_ticket(workspace_root=ws, limit=1)
    if res.get("status") != "OK":
        raise SystemExit("work_intake_exec_repo_guard_contract_test failed: exec status")
    if int(res.get("skipped_count") or 0) < 1:
        raise SystemExit("work_intake_exec_repo_guard_contract_test failed: skipped_count")

    report_path = ws / ".cache" / "reports" / "work_intake_exec_ticket.v1.json"
    if not report_path.exists():
        raise SystemExit("work_intake_exec_repo_guard_contract_test failed: exec report missing")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    entries = report.get("entries") if isinstance(report.get("entries"), list) else []
    if not entries:
        raise SystemExit("work_intake_exec_repo_guard_contract_test failed: entries missing")
    entry = entries[0] if isinstance(entries[0], dict) else {}
    if str(entry.get("skip_reason") or "") != "TARGET_REPO_MISMATCH":
        raise SystemExit("work_intake_exec_repo_guard_contract_test failed: skip_reason mismatch")

    print(json.dumps({"status": "OK", "workspace": str(ws)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
