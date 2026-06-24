from __future__ import annotations

from pathlib import Path
from typing import Any

from src.ops.system_status_sections import _load_json, _rel_to_workspace

def _execution_target_governance_section_impl(workspace_root: Path, *, allow_write: bool) -> dict[str, Any]:
    try:
        from src.ops.ai_entry_pack_build import ensure_ai_entry_pack
        from src.orchestrator import target_registry
        from src.orchestrator.file_write_arbitration import summarize_path_write_leases
    except ImportError:
        return {"status": "SKIP", "notes": ["execution_target_governance dependencies not available"]}

    try:
        policy_path, policy = target_registry.load_execution_target_policy(workspace_root)
        active_path, active = target_registry.load_active_execution_registry(workspace_root)
        apps_path, apps = target_registry.load_apps_and_launch_registry(workspace_root)
        version_path, version_registry = target_registry.load_version_registry(workspace_root)
        authority_path, authority_matrix = target_registry.load_authority_matrix(workspace_root)
        duplicate_path, duplicate_surface_register = target_registry.load_duplicate_surface_register(workspace_root)
    except Exception as e:
        return {
            "status": "FAIL",
            "policy_path": "",
            "active_execution_registry_path": "",
            "apps_and_launch_registry_path": "",
            "version_registry_path": "",
            "authority_matrix_path": "",
            "duplicate_surface_register_path": "",
            "last_resolution_report_path": str(Path(".cache") / "reports" / "execution_target_resolution.v1.json"),
            "last_guard_report_path": str(Path(".cache") / "reports" / "execution_target_guard.v1.json"),
            "registry_first": False,
            "require_launch_profile_registry": False,
            "require_version_source_for_apply": False,
            "authority_surface_present": False,
            "repo_count": 0,
            "target_count": 0,
            "launch_profile_count": 0,
            "version_target_count": 0,
            "authority_surface_count": 0,
            "duplicate_concern_count": 0,
            "uncontrolled_duplicate_concerns": [],
            "last_guard_status": "",
            "last_guard_block_code": "",
            "ai_entry_pack": {
                "path": "",
                "status": "MISSING",
                "valid": False,
                "project_id": "",
                "ref_count": 0,
                "missing_refs": [],
                "needs_refresh": False,
                "refresh_reasons": [],
                "auto_refreshed": False,
                "would_refresh": False,
                "auto_refresh_error": "",
                "source_count": 0,
            },
            "file_write_arbitration": {
                "lease_path": str(workspace_root / ".cache" / "index" / "file_write_leases.v1.json"),
                "active_lease_count": 0,
                "stale_lease_count": 0,
                "active_targets": [],
                "latest_heartbeat_at": "",
            },
            "notes": [f"governance_load_error={str(e)}"],
        }

    duplicates = target_registry.find_uncontrolled_target_duplicates(duplicate_surface_register)
    ai_entry_pack_state = ensure_ai_entry_pack(workspace_root=workspace_root, allow_write=allow_write)
    ai_entry_pack_health = (
        ai_entry_pack_state.get("health") if isinstance(ai_entry_pack_state.get("health"), dict) else {}
    )
    arbitration = summarize_path_write_leases(workspace_root=workspace_root)

    resolution_path = workspace_root / ".cache" / "reports" / "execution_target_resolution.v1.json"
    guard_path = workspace_root / ".cache" / "reports" / "execution_target_guard.v1.json"
    last_guard_status = ""
    last_guard_block_code = ""
    if guard_path.exists():
        try:
            guard = _load_json(guard_path)
        except Exception:
            guard = {}
        if isinstance(guard, dict):
            last_guard_status = str(guard.get("status") or "").strip()
            block = guard.get("block") if isinstance(guard.get("block"), dict) else {}
            last_guard_block_code = str(block.get("code") or "").strip()

    authority_surfaces = (
        authority_matrix.get("surfaces") if isinstance(authority_matrix.get("surfaces"), list) else []
    )
    notes: list[str] = []
    if ai_entry_pack_state.get("auto_refreshed", False):
        notes.append("ai_entry_pack_auto_refreshed")
    if ai_entry_pack_state.get("would_refresh", False):
        notes.append("ai_entry_pack_refresh_pending")
    for reason in ai_entry_pack_state.get("refresh_reasons", []):
        if isinstance(reason, str) and reason.strip():
            notes.append(f"ai_entry_pack_refresh_reason={reason}")
    if duplicates:
        notes.append("uncontrolled_duplicates_present")
    if arbitration.get("active_lease_count", 0):
        notes.append("file_write_leases_active")

    status = "OK"
    if not target_registry.has_execution_target_authority_surface(authority_matrix):
        status = "FAIL"
        notes.append("authority_surface_missing")
    elif not bool(ai_entry_pack_health.get("valid", False)) or duplicates:
        status = "WARN"
    elif str(ai_entry_pack_state.get("auto_refresh_error") or "").strip():
        status = "WARN"
        notes.append("ai_entry_pack_auto_refresh_error")

    return {
        "status": status,
        "policy_path": str(policy_path),
        "active_execution_registry_path": str(active_path),
        "apps_and_launch_registry_path": str(apps_path),
        "version_registry_path": str(version_path),
        "authority_matrix_path": str(authority_path),
        "duplicate_surface_register_path": str(duplicate_path),
        "last_resolution_report_path": _rel_to_workspace(resolution_path, workspace_root),
        "last_guard_report_path": _rel_to_workspace(guard_path, workspace_root),
        "registry_first": bool(
            policy.get("resolution", {}).get("registry_first")
            if isinstance(policy.get("resolution"), dict)
            else False
        ),
        "require_launch_profile_registry": bool(
            policy.get("resolution", {}).get("require_launch_profile_registry")
            if isinstance(policy.get("resolution"), dict)
            else False
        ),
        "require_version_source_for_apply": bool(
            policy.get("resolution", {}).get("require_version_source_for_apply")
            if isinstance(policy.get("resolution"), dict)
            else False
        ),
        "authority_surface_present": target_registry.has_execution_target_authority_surface(authority_matrix),
        "repo_count": len(active.get("repos") if isinstance(active.get("repos"), list) else []),
        "target_count": len(active.get("targets") if isinstance(active.get("targets"), list) else []),
        "launch_profile_count": len(apps.get("profiles") if isinstance(apps.get("profiles"), list) else []),
        "version_target_count": len(
            version_registry.get("targets") if isinstance(version_registry.get("targets"), list) else []
        ),
        "authority_surface_count": len(authority_surfaces),
        "duplicate_concern_count": len(
            duplicate_surface_register.get("concerns")
            if isinstance(duplicate_surface_register.get("concerns"), list)
            else []
        ),
        "uncontrolled_duplicate_concerns": duplicates,
        "last_guard_status": last_guard_status,
        "last_guard_block_code": last_guard_block_code,
        "ai_entry_pack": {
            "path": str(ai_entry_pack_state.get("path") or ""),
            "status": str(ai_entry_pack_health.get("status") or "MISSING"),
            "valid": bool(ai_entry_pack_health.get("valid", False)),
            "project_id": str(ai_entry_pack_health.get("project_id") or ""),
            "ref_count": int(ai_entry_pack_health.get("ref_count") or 0),
            "missing_refs": (
                ai_entry_pack_health.get("missing_refs")
                if isinstance(ai_entry_pack_health.get("missing_refs"), list)
                else []
            ),
            "needs_refresh": bool(ai_entry_pack_state.get("needs_refresh", False)),
            "refresh_reasons": (
                ai_entry_pack_state.get("refresh_reasons")
                if isinstance(ai_entry_pack_state.get("refresh_reasons"), list)
                else []
            ),
            "auto_refreshed": bool(ai_entry_pack_state.get("auto_refreshed", False)),
            "would_refresh": bool(ai_entry_pack_state.get("would_refresh", False)),
            "auto_refresh_error": str(ai_entry_pack_state.get("auto_refresh_error") or ""),
            "source_count": int(ai_entry_pack_state.get("source_count") or 0),
        },
        "file_write_arbitration": arbitration,
        "notes": notes,
    }
