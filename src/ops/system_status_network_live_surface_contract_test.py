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


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_summary(
    *,
    system_status: dict,
    ui_snapshot: dict,
    enabled: bool,
    enabled_by_decision: bool,
    decision_pending: int,
    domains_count: int,
    actions_count: int,
    has_override: bool,
) -> None:
    sections = system_status.get("sections") if isinstance(system_status.get("sections"), dict) else {}
    network_live = sections.get("network_live") if isinstance(sections.get("network_live"), dict) else None
    if not isinstance(network_live, dict):
        raise SystemExit("network_live_surface_contract_test failed: missing network_live section")
    if network_live.get("enabled") is not enabled:
        raise SystemExit("network_live_surface_contract_test failed: enabled mismatch")
    if network_live.get("enabled_by_decision") is not enabled_by_decision:
        raise SystemExit("network_live_surface_contract_test failed: enabled_by_decision mismatch")
    if int(network_live.get("decision_pending") or 0) != decision_pending:
        raise SystemExit("network_live_surface_contract_test failed: decision_pending mismatch")
    if int(network_live.get("allow_domains_count") or 0) != domains_count:
        raise SystemExit("network_live_surface_contract_test failed: allow_domains_count mismatch")
    if int(network_live.get("allow_actions_count") or 0) != actions_count:
        raise SystemExit("network_live_surface_contract_test failed: allow_actions_count mismatch")
    if "allow_domains" in network_live or "allow_actions" in network_live:
        raise SystemExit("network_live_surface_contract_test failed: leaked allowlist values")
    if has_override:
        if network_live.get("policy_source") != "workspace":
            raise SystemExit("network_live_surface_contract_test failed: policy_source mismatch (override)")
        if network_live.get("last_override_path") != ".cache/policy_overrides/policy_network_live.override.v1.json":
            raise SystemExit("network_live_surface_contract_test failed: last_override_path mismatch")
    else:
        if network_live.get("policy_source") != "core":
            raise SystemExit("network_live_surface_contract_test failed: policy_source mismatch (default)")

    summary = ui_snapshot.get("network_live_summary")
    if not isinstance(summary, dict):
        raise SystemExit("network_live_surface_contract_test failed: missing ui network_live_summary")
    if summary.get("enabled") is not enabled:
        raise SystemExit("network_live_surface_contract_test failed: ui enabled mismatch")
    if summary.get("enabled_by_decision") is not enabled_by_decision:
        raise SystemExit("network_live_surface_contract_test failed: ui enabled_by_decision mismatch")
    if int(summary.get("decision_pending") or 0) != decision_pending:
        raise SystemExit("network_live_surface_contract_test failed: ui decision_pending mismatch")
    if int(summary.get("allow_domains_count") or 0) != domains_count:
        raise SystemExit("network_live_surface_contract_test failed: ui allow_domains_count mismatch")
    if int(summary.get("allow_actions_count") or 0) != actions_count:
        raise SystemExit("network_live_surface_contract_test failed: ui allow_actions_count mismatch")
    if "allow_domains" in summary or "allow_actions" in summary:
        raise SystemExit("network_live_surface_contract_test failed: ui leaked allowlist values")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.system_status_report import run_system_status
    from src.ops.ui_snapshot_bundle import build_ui_snapshot_bundle
    from src.ops.decision_inbox import run_decision_inbox_build, run_decision_seed

    ws = repo_root / ".cache" / "ws_system_status_network_live_surface"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    override_payload = {
        "version": "v1",
        "enabled": True,
        "enabled_by_decision": True,
        "allow_domains_count": 1,
        "allow_actions_count": 2,
    }
    override_path = ws / ".cache" / "policy_overrides" / "policy_network_live.override.v1.json"
    _write_json(override_path, override_payload)
    run_decision_seed(workspace_root=ws, decision_kind="NETWORK_LIVE_ENABLE", target="NETWORK_LIVE")
    run_decision_inbox_build(workspace_root=ws)

    sys_result = run_system_status(workspace_root=ws, core_root=repo_root, dry_run=False)
    report_path = sys_result.get("out_json") if isinstance(sys_result, dict) else None
    if not isinstance(report_path, str) or not report_path:
        raise SystemExit("network_live_surface_contract_test failed: missing system status path")
    report = _load_json(Path(report_path))
    ui_payload = build_ui_snapshot_bundle(workspace_root=ws)

    _assert_summary(
        system_status=report,
        ui_snapshot=ui_payload,
        enabled=True,
        enabled_by_decision=True,
        decision_pending=1,
        domains_count=1,
        actions_count=2,
        has_override=True,
    )

    override_path.unlink()
    inbox_path = ws / ".cache" / "index" / "decision_inbox.v1.json"
    inbox_md_path = ws / ".cache" / "reports" / "decision_inbox.v1.md"
    if inbox_path.exists():
        inbox_path.unlink()
    if inbox_md_path.exists():
        inbox_md_path.unlink()
    sys_result = run_system_status(workspace_root=ws, core_root=repo_root, dry_run=False)
    report_path = sys_result.get("out_json") if isinstance(sys_result, dict) else None
    if not isinstance(report_path, str) or not report_path:
        raise SystemExit("network_live_surface_contract_test failed: missing system status path (default)")
    report = _load_json(Path(report_path))
    ui_payload = build_ui_snapshot_bundle(workspace_root=ws)

    _assert_summary(
        system_status=report,
        ui_snapshot=ui_payload,
        enabled=False,
        enabled_by_decision=False,
        decision_pending=0,
        domains_count=0,
        actions_count=0,
        has_override=False,
    )

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
