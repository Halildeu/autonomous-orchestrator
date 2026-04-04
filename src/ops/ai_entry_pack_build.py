from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root
from src.orchestrator import target_registry


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _build_context_continuity(workspace_root: Path, workspace_rel: str) -> dict[str, Any]:
    """Build context continuity section for agent handoff (Phase 6)."""
    continuity: dict[str, Any] = {}

    # Active profile
    profile_path = workspace_root / ".cache" / "index" / "active_context_profile.v1.json"
    if profile_path.exists():
        try:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            continuity["active_profile"] = {
                "id": profile.get("profile_id", "UNKNOWN"),
                "resolution_method": profile.get("resolution_method", "unknown"),
            }
        except Exception:
            pass

    # Quality snapshot
    metrics_path = workspace_root / ".cache" / "reports" / "context_session_metrics.v1.json"
    if metrics_path.exists():
        try:
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            continuity["quality_snapshot"] = {
                "cache_hit_rate": metrics.get("cache_hit_rate", 0.0),
                "quality_trend": metrics.get("quality_trend", "STABLE"),
            }
        except Exception:
            pass

    # Scope state
    scope_path = workspace_root / ".cache" / "reports" / "scope_guard_state.v1.json"
    if scope_path.exists():
        try:
            scope = json.loads(scope_path.read_text(encoding="utf-8"))
            continuity["scope_state"] = {"status": scope.get("status", "UNKNOWN")}
        except Exception:
            pass

    # Compiled context ref
    compiled_path = workspace_root / ".cache" / "reports" / "rule_packet.v1.json"
    if compiled_path.exists():
        continuity["compiled_context_ref"] = f"{workspace_rel}/.cache/reports/rule_packet.v1.json"

    return continuity


def ai_entry_pack_path(workspace_root: Path) -> Path:
    return workspace_root / "project" / "PRJ-MULTI-AI-CODING-OS" / "ai_entry_pack.v1.json"


def governance_source_paths(*, workspace_root: Path) -> dict[str, Path]:
    policy_path, _ = target_registry.load_execution_target_policy(workspace_root)
    active_path, _ = target_registry.load_active_execution_registry(workspace_root)
    apps_path, _ = target_registry.load_apps_and_launch_registry(workspace_root)
    version_path, _ = target_registry.load_version_registry(workspace_root)
    authority_path, _ = target_registry.load_authority_matrix(workspace_root)
    duplicate_path, _ = target_registry.load_duplicate_surface_register(workspace_root)
    return {
        "execution_target_governance_policy": policy_path,
        "active_execution_registry": active_path,
        "apps_and_launch_registry": apps_path,
        "version_registry": version_path,
        "authority_matrix": authority_path,
        "duplicate_surface_register": duplicate_path,
    }


def _mtime(path: Path | None) -> float:
    if path is None:
        return 0.0
    try:
        return float(path.stat().st_mtime)
    except Exception:
        return 0.0


def ai_entry_pack_runtime_state(*, workspace_root: Path) -> dict[str, Any]:
    source_paths = governance_source_paths(workspace_root=workspace_root)
    pack_path, pack = target_registry.load_ai_entry_pack(workspace_root)
    health = target_registry.ai_entry_pack_health(pack)
    pack_mtime = _mtime(pack_path)
    source_mtimes = {key: _mtime(path) for key, path in source_paths.items()}
    newest_source_mtime = max(source_mtimes.values(), default=0.0)

    refresh_reasons: list[str] = []
    if not bool(health.get("present", False)):
        refresh_reasons.append("missing")
    elif not bool(health.get("valid", False)):
        refresh_reasons.append("invalid")
    if pack_mtime > 0.0 and newest_source_mtime > pack_mtime:
        refresh_reasons.append("governance_source_newer")

    return {
        "path": str(pack_path) if pack_path is not None else "",
        "health": health,
        "source_paths": {key: str(path) for key, path in source_paths.items()},
        "source_count": len(source_paths),
        "pack_mtime": pack_mtime,
        "newest_source_mtime": newest_source_mtime,
        "needs_refresh": bool(refresh_reasons),
        "refresh_reasons": refresh_reasons,
    }


def ensure_ai_entry_pack(*, workspace_root: Path, allow_write: bool) -> dict[str, Any]:
    state = ai_entry_pack_runtime_state(workspace_root=workspace_root)
    result: dict[str, Any] = {
        **state,
        "auto_refreshed": False,
        "would_refresh": False,
        "auto_refresh_error": "",
    }

    if not state.get("needs_refresh", False):
        return result

    if not allow_write:
        result["would_refresh"] = True
        return result

    try:
        build_ai_entry_pack(workspace_root=workspace_root)
        state = ai_entry_pack_runtime_state(workspace_root=workspace_root)
        result = {
            **state,
            "auto_refreshed": True,
            "would_refresh": False,
            "auto_refresh_error": "",
        }
    except Exception as e:
        result["auto_refresh_error"] = str(e)
    return result


def build_ai_entry_pack(*, workspace_root: Path) -> dict[str, Any]:
    source_paths = governance_source_paths(workspace_root=workspace_root)
    active_path, active = target_registry.load_active_execution_registry(workspace_root)
    apps_path, apps = target_registry.load_apps_and_launch_registry(workspace_root)
    version_path, version_registry = target_registry.load_version_registry(workspace_root)
    authority_path, authority_matrix = target_registry.load_authority_matrix(workspace_root)
    duplicate_path, duplicate_surface_register = target_registry.load_duplicate_surface_register(workspace_root)
    _, policy = target_registry.load_execution_target_policy(workspace_root)

    repo = repo_root()
    try:
        workspace_rel = workspace_root.resolve().relative_to(repo.resolve()).as_posix()
    except Exception:
        workspace_rel = str(workspace_root)

    refs = {
        "execution_target_governance_doc": "docs/OPERATIONS/EXECUTION-TARGET-GOVERNANCE.v1.md",
        "execution_target_governance_policy": "policies/policy_execution_target_governance.v1.json",
        "active_execution_registry": "registry/active_execution_registry.v1.json",
        "apps_and_launch_registry": "registry/apps_and_launch_registry.v1.json",
        "version_registry": "registry/version_registry.v1.json",
        "authority_matrix": "registry/authority_matrix.v1.json",
        "duplicate_surface_register": "registry/duplicate_surface_register.v1.json",
        "system_status": f"{workspace_rel}/.cache/reports/system_status.v1.json",
        "portfolio_status": f"{workspace_rel}/.cache/reports/portfolio_status.v1.json",
        "worktree_health": f"{workspace_rel}/.cache/reports/worktree_health.v1.json",
    }

    # Phase 6: Context continuity fields
    context_continuity = _build_context_continuity(workspace_root, workspace_rel)

    payload = {
        "version": "v1",
        "kind": "ai-entry-pack",
        "project_id": "PRJ-MULTI-AI-CODING-OS",
        "status": "READY",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "notes": [
            "Apply sinifi runlardan once okunacak onboarding girdisi.",
            "Authority kaynagi degildir; canonical registry/policy/dokumanlara referans verir.",
        ],
        "refs": refs,
        "context_continuity": context_continuity,
        "summary": {
            "repo_count": len(active.get("repos") if isinstance(active.get("repos"), list) else []),
            "target_count": len(active.get("targets") if isinstance(active.get("targets"), list) else []),
            "launch_profile_count": len(apps.get("profiles") if isinstance(apps.get("profiles"), list) else []),
            "version_target_count": len(
                version_registry.get("targets") if isinstance(version_registry.get("targets"), list) else []
            ),
            "authority_surface_count": len(
                authority_matrix.get("surfaces") if isinstance(authority_matrix.get("surfaces"), list) else []
            ),
            "duplicate_concern_count": len(
                duplicate_surface_register.get("concerns")
                if isinstance(duplicate_surface_register.get("concerns"), list)
                else []
            ),
            "registry_first": bool(
                policy.get("resolution", {}).get("registry_first")
                if isinstance(policy.get("resolution"), dict)
                else False
            ),
        },
        "source_paths": {
            "active_execution_registry": str(active_path),
            "apps_and_launch_registry": str(apps_path),
            "version_registry": str(version_path),
            "authority_matrix": str(authority_path),
            "duplicate_surface_register": str(duplicate_path),
            "execution_target_governance_policy": str(source_paths["execution_target_governance_policy"]),
        },
    }

    out_path = ai_entry_pack_path(workspace_root)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "OK",
        "path": str(out_path),
        "project_id": payload["project_id"],
        "repo_count": payload["summary"]["repo_count"],
        "target_count": payload["summary"]["target_count"],
        "launch_profile_count": payload["summary"]["launch_profile_count"],
    }
