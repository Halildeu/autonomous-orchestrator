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


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.system_status_report import run_system_status
    from src.orchestrator.file_write_arbitration import acquire_path_write_lease

    ws = repo_root / ".cache" / "ws_system_status_execution_target_governance_surface"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    target = ws / "docs" / "same-file.md"
    acquire_path_write_lease(
        workspace_root=ws,
        target_path=target,
        run_id="RUN-ETG",
        owner_tag="MOD_B",
        owner_session="SESSION-ETG",
        evidence_paths=["evidence/RUN-ETG/request.json"],
    )

    result = run_system_status(workspace_root=ws, core_root=repo_root, dry_run=False)
    if str(result.get("status") or "") != "OK":
        raise SystemExit("system_status_execution_target_governance_surface_contract_test failed: run status")

    report_path = ws / ".cache" / "reports" / "system_status.v1.json"
    if not report_path.exists():
        raise SystemExit("system_status_execution_target_governance_surface_contract_test failed: report missing")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    sections = report.get("sections") if isinstance(report, dict) else {}
    etg = sections.get("execution_target_governance") if isinstance(sections, dict) else None
    if not isinstance(etg, dict):
        raise SystemExit("system_status_execution_target_governance_surface_contract_test failed: section missing")
    if not bool(etg.get("authority_surface_present", False)):
        raise SystemExit("system_status_execution_target_governance_surface_contract_test failed: authority surface")

    ai_entry_pack = etg.get("ai_entry_pack") if isinstance(etg.get("ai_entry_pack"), dict) else {}
    if str(ai_entry_pack.get("status") or "").strip() != "READY":
        raise SystemExit("system_status_execution_target_governance_surface_contract_test failed: ai entry pack READY expected")
    if not bool(ai_entry_pack.get("auto_refreshed", False)):
        raise SystemExit("system_status_execution_target_governance_surface_contract_test failed: auto refresh expected")

    arbitration = etg.get("file_write_arbitration") if isinstance(etg.get("file_write_arbitration"), dict) else {}
    if int(arbitration.get("active_lease_count", 0)) != 1:
        raise SystemExit("system_status_execution_target_governance_surface_contract_test failed: active lease count")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
