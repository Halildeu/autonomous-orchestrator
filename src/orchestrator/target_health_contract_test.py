from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

_WORKSPACE_DIRS = (
    "schemas",
    "policies",
    "registry",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _clone_workspace(*, root: Path, workspace: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    for rel in _WORKSPACE_DIRS:
        shutil.copytree(root / rel, workspace / rel)


def _seed_ai_entry_pack(workspace: Path) -> None:
    payload = {
        "version": "v1",
        "kind": "ai-entry-pack",
        "project_id": "PRJ-MULTI-AI-CODING-OS",
        "status": "READY",
        "refs": {
            "active_execution_registry": "registry/active_execution_registry.v1.json",
            "apps_and_launch_registry": "registry/apps_and_launch_registry.v1.json",
            "version_registry": "registry/version_registry.v1.json",
            "authority_matrix": "registry/authority_matrix.v1.json",
            "duplicate_surface_register": "registry/duplicate_surface_register.v1.json",
        },
    }
    path = workspace / "project" / "PRJ-MULTI-AI-CODING-OS" / "ai_entry_pack.v1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    root = _repo_root()
    sys.path.insert(0, str(root))

    from src.orchestrator.target_health import evaluate_execution_target_guard

    with tempfile.TemporaryDirectory(prefix="target-health-") as td:
        workspace = Path(td) / "ws"
        _clone_workspace(root=root, workspace=workspace)
        _seed_ai_entry_pack(workspace)

        ok_report = evaluate_execution_target_guard(
            workspace=workspace,
            envelope={
                "request_id": "REQ-TARGET-OK",
                "tenant_id": "TENANT-LOCAL",
                "intent": "urn:core:apply:test",
                "risk_score": 0.2,
                "dry_run": False,
                "side_effect_policy": "allow",
                "idempotency_key": "TENANT-LOCAL:REQ-TARGET-OK",
                "context": {
                    "target_id": "dev:web",
                    "launch_profile_id": "dev:web-shell",
                    "selection_reason": "target_health_contract_test",
                },
            },
            writes_allowed=True,
        )
        if ok_report.get("status") not in {"OK", "WARN"}:
            raise SystemExit("target_health_contract_test failed: valid target must not block")
        if ok_report.get("target_id") != "dev:web":
            raise SystemExit("target_health_contract_test failed: target_id mismatch")
        if ok_report.get("launch_profile_id") != "dev:web-shell":
            raise SystemExit("target_health_contract_test failed: launch_profile_id mismatch")
        target_evidence = ok_report.get("target_evidence") if isinstance(ok_report.get("target_evidence"), dict) else {}
        if str(target_evidence.get("ai_entry_pack_state") or "").strip() != "READY":
            raise SystemExit("target_health_contract_test failed: ai_entry_pack_state must be READY")

        blocked_unknown = evaluate_execution_target_guard(
            workspace=workspace,
            envelope={
                "request_id": "REQ-TARGET-UNKNOWN",
                "tenant_id": "TENANT-LOCAL",
                "intent": "urn:core:apply:test",
                "risk_score": 0.2,
                "dry_run": False,
                "side_effect_policy": "allow",
                "idempotency_key": "TENANT-LOCAL:REQ-TARGET-UNKNOWN",
                "context": {
                    "target_id": "dev:missing",
                    "selection_reason": "target_health_contract_test_unknown",
                },
            },
            writes_allowed=True,
        )
        block = blocked_unknown.get("block") if isinstance(blocked_unknown.get("block"), dict) else {}
        if blocked_unknown.get("status") != "BLOCKED" or block.get("code") != "UNKNOWN_TARGET":
            raise SystemExit("target_health_contract_test failed: unknown target must block")

        (workspace / "project" / "PRJ-MULTI-AI-CODING-OS" / "ai_entry_pack.v1.json").unlink()
        missing_pack = evaluate_execution_target_guard(
            workspace=workspace,
            envelope={
                "request_id": "REQ-TARGET-MISSING-AI-PACK",
                "tenant_id": "TENANT-LOCAL",
                "intent": "urn:core:apply:test",
                "risk_score": 0.2,
                "dry_run": False,
                "side_effect_policy": "allow",
                "idempotency_key": "TENANT-LOCAL:REQ-TARGET-MISSING-AI-PACK",
                "context": {
                    "target_id": "dev:web",
                    "launch_profile_id": "dev:web-shell",
                    "selection_reason": "target_health_contract_test_missing_ai_entry_pack",
                },
            },
            writes_allowed=True,
        )
        missing_pack_block = missing_pack.get("block") if isinstance(missing_pack.get("block"), dict) else {}
        if missing_pack.get("status") != "BLOCKED" or missing_pack_block.get("code") != "AI_ENTRY_PACK_MISSING":
            raise SystemExit("target_health_contract_test failed: missing ai entry pack must block")

        report_only = evaluate_execution_target_guard(
            workspace=workspace,
            envelope={
                "request_id": "REQ-TARGET-REPORT",
                "tenant_id": "TENANT-LOCAL",
                "intent": "urn:core:summary:summary_to_file",
                "risk_score": 0.1,
                "dry_run": True,
                "side_effect_policy": "none",
                "idempotency_key": "TENANT-LOCAL:REQ-TARGET-REPORT",
            },
            writes_allowed=True,
        )
        if report_only.get("status") not in {"OK", "WARN"}:
            raise SystemExit("target_health_contract_test failed: report-only targetless run must not block")

    print("target_health_contract_test: PASS")


if __name__ == "__main__":
    main()
