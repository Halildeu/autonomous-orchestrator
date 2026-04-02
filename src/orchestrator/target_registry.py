from __future__ import annotations

from pathlib import Path
from typing import Any

from src.utils.jsonio import load_json


_AI_ENTRY_PACK_WORKSPACE_REL = "project/PRJ-MULTI-AI-CODING-OS/ai_entry_pack.v1.json"
_AI_ENTRY_PACK_REPO_FALLBACK_REL = (
    ".cache/ws_customer_default/project/PRJ-MULTI-AI-CODING-OS/ai_entry_pack.v1.json"
)
_AI_ENTRY_PACK_REQUIRED_REFS = (
    "active_execution_registry",
    "apps_and_launch_registry",
    "version_registry",
    "authority_matrix",
    "duplicate_surface_register",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json_preferring_workspace(workspace: Path, relpath: str) -> tuple[Path, dict[str, Any]]:
    candidates = [workspace / relpath, repo_root() / relpath]
    for path in candidates:
        if not path.exists():
            continue
        raw = load_json(path)
        if isinstance(raw, dict):
            return path, raw
        raise RuntimeError(f"Registry/policy must be a JSON object: {path}")
    raise RuntimeError(f"Missing required governance artifact: {relpath}")


def load_execution_target_policy(workspace: Path) -> tuple[Path, dict[str, Any]]:
    return _load_json_preferring_workspace(workspace, "policies/policy_execution_target_governance.v1.json")


def load_active_execution_registry(workspace: Path) -> tuple[Path, dict[str, Any]]:
    return _load_json_preferring_workspace(workspace, "registry/active_execution_registry.v1.json")


def load_apps_and_launch_registry(workspace: Path) -> tuple[Path, dict[str, Any]]:
    return _load_json_preferring_workspace(workspace, "registry/apps_and_launch_registry.v1.json")


def load_version_registry(workspace: Path) -> tuple[Path, dict[str, Any]]:
    return _load_json_preferring_workspace(workspace, "registry/version_registry.v1.json")


def load_authority_matrix(workspace: Path) -> tuple[Path, dict[str, Any]]:
    return _load_json_preferring_workspace(workspace, "registry/authority_matrix.v1.json")


def load_duplicate_surface_register(workspace: Path) -> tuple[Path, dict[str, Any]]:
    return _load_json_preferring_workspace(workspace, "registry/duplicate_surface_register.v1.json")


def load_ai_entry_pack(workspace: Path) -> tuple[Path | None, dict[str, Any] | None]:
    candidates = [workspace / _AI_ENTRY_PACK_WORKSPACE_REL]
    default_workspace = repo_root() / ".cache" / "ws_customer_default"
    if workspace.resolve() == default_workspace.resolve():
        candidates.append(repo_root() / _AI_ENTRY_PACK_REPO_FALLBACK_REL)
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        if not path.exists():
            continue
        raw = load_json(path)
        if isinstance(raw, dict):
            return path, raw
        raise RuntimeError(f"AI entry pack JSON object olmalidir: {path}")
    return None, None


def ai_entry_pack_health(ai_entry_pack: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(ai_entry_pack, dict):
        return {
            "present": False,
            "valid": False,
            "status": "MISSING",
            "project_id": "",
            "ref_count": 0,
            "missing_refs": list(_AI_ENTRY_PACK_REQUIRED_REFS),
        }

    version = str(ai_entry_pack.get("version") or "").strip()
    kind = str(ai_entry_pack.get("kind") or "").strip()
    project_id = str(ai_entry_pack.get("project_id") or "").strip()
    status = str(ai_entry_pack.get("status") or "").strip()
    refs = ai_entry_pack.get("refs") if isinstance(ai_entry_pack.get("refs"), dict) else {}
    missing_refs = [key for key in _AI_ENTRY_PACK_REQUIRED_REFS if not str(refs.get(key) or "").strip()]
    valid = bool(
        version == "v1"
        and kind == "ai-entry-pack"
        and project_id
        and status
        and not missing_refs
    )
    return {
        "present": True,
        "valid": valid,
        "version": version,
        "kind": kind,
        "project_id": project_id,
        "status": status or "UNKNOWN",
        "ref_count": len(refs),
        "missing_refs": missing_refs,
    }


def envelope_target_hints(envelope: dict[str, Any]) -> dict[str, str]:
    context = envelope.get("context") if isinstance(envelope.get("context"), dict) else {}

    def _read(name: str) -> str:
        value = context.get(name)
        return str(value).strip() if isinstance(value, str) else ""

    return {
        "repo_id": _read("repo_id"),
        "target_id": _read("target_id"),
        "launch_profile_id": _read("launch_profile_id"),
        "app_id": _read("app_id"),
        "selection_reason": _read("selection_reason"),
    }


def is_apply_class(envelope: dict[str, Any]) -> bool:
    side_effect_policy = str(envelope.get("side_effect_policy") or "").strip()
    dry_run = bool(envelope.get("dry_run", False))
    return (not dry_run) and side_effect_policy in {"draft", "pr", "allow"}


def has_execution_target_authority_surface(authority_matrix: dict[str, Any]) -> bool:
    surfaces = authority_matrix.get("surfaces") if isinstance(authority_matrix.get("surfaces"), list) else []
    for item in surfaces:
        if not isinstance(item, dict):
            continue
        if str(item.get("surface_id") or "").strip() == "core:execution-target-governance":
            return True
    return False


def find_uncontrolled_target_duplicates(duplicate_surface_register: dict[str, Any]) -> list[str]:
    concerns = (
        duplicate_surface_register.get("concerns")
        if isinstance(duplicate_surface_register.get("concerns"), list)
        else []
    )
    uncontrolled: list[str] = []
    for item in concerns:
        if not isinstance(item, dict):
            continue
        domain = str(item.get("domain") or "").strip()
        status = str(item.get("status") or "").strip()
        concern_id = str(item.get("concern_id") or "").strip()
        if domain not in {"target-governance", "launch-governance"}:
            continue
        if status in {"CONTROLLED_DUPLICATION", "MIGRATION_ARCHIVE_CONTROLLED"}:
            continue
        if concern_id:
            uncontrolled.append(concern_id)
    return uncontrolled


def resolve_target_selection(workspace: Path, envelope: dict[str, Any]) -> dict[str, Any]:
    active_path, active = load_active_execution_registry(workspace)
    apps_path, apps = load_apps_and_launch_registry(workspace)
    version_path, version_registry = load_version_registry(workspace)
    authority_path, authority_matrix = load_authority_matrix(workspace)
    duplicate_path, duplicate_surface_register = load_duplicate_surface_register(workspace)

    hints = envelope_target_hints(envelope)
    requested_target_id = hints["target_id"]
    requested_repo_id = hints["repo_id"]
    requested_launch_profile_id = hints["launch_profile_id"] or hints["app_id"]

    repos = active.get("repos") if isinstance(active.get("repos"), list) else []
    targets = active.get("targets") if isinstance(active.get("targets"), list) else []
    profiles = apps.get("profiles") if isinstance(apps.get("profiles"), list) else []
    version_targets = (
        version_registry.get("targets") if isinstance(version_registry.get("targets"), list) else []
    )

    repo_by_id = {
        str(item.get("repo_id") or "").strip(): item
        for item in repos
        if isinstance(item, dict) and str(item.get("repo_id") or "").strip()
    }
    target_by_id = {
        str(item.get("target_id") or "").strip(): item
        for item in targets
        if isinstance(item, dict) and str(item.get("target_id") or "").strip()
    }
    profile_by_id = {
        str(item.get("app_id") or "").strip(): item
        for item in profiles
        if isinstance(item, dict) and str(item.get("app_id") or "").strip()
    }
    version_by_target = {
        str(item.get("target_id") or "").strip(): item
        for item in version_targets
        if isinstance(item, dict) and str(item.get("target_id") or "").strip()
    }

    selected_profile = profile_by_id.get(requested_launch_profile_id) if requested_launch_profile_id else None
    if not requested_target_id and isinstance(selected_profile, dict):
        requested_target_id = str(selected_profile.get("target_id") or "").strip()

    selected_target = target_by_id.get(requested_target_id) if requested_target_id else None
    selected_repo = None
    if isinstance(selected_target, dict):
        parent_repo_id = str(selected_target.get("parent_repo_id") or "").strip()
        selected_repo = repo_by_id.get(parent_repo_id)
    elif requested_repo_id:
        selected_repo = repo_by_id.get(requested_repo_id)
        if selected_repo is not None and not requested_target_id:
            requested_target_id = requested_repo_id
    elif requested_target_id and requested_target_id in repo_by_id:
        selected_repo = repo_by_id.get(requested_target_id)

    launch_profile_id = ""
    if isinstance(selected_profile, dict):
        launch_profile_id = str(selected_profile.get("app_id") or "").strip()
    elif isinstance(selected_target, dict):
        launch_ids = selected_target.get("launch_profile_ids") if isinstance(selected_target.get("launch_profile_ids"), list) else []
        launch_ids = [str(x).strip() for x in launch_ids if isinstance(x, str) and str(x).strip()]
        if len(launch_ids) == 1:
            auto_profile = profile_by_id.get(launch_ids[0])
            if isinstance(auto_profile, dict):
                selected_profile = auto_profile
                launch_profile_id = str(auto_profile.get("app_id") or "").strip()

    repo_id = str(selected_repo.get("repo_id") or "").strip() if isinstance(selected_repo, dict) else ""
    target_id = (
        str(selected_target.get("target_id") or "").strip()
        if isinstance(selected_target, dict)
        else requested_target_id
    )
    repo_root = str(selected_repo.get("repo_root") or "").strip() if isinstance(selected_repo, dict) else ""
    working_dir = ""
    if isinstance(selected_profile, dict):
        working_dir = str(selected_profile.get("working_dir") or "").strip()
    elif isinstance(selected_target, dict):
        working_dir = str(selected_target.get("root_path") or "").strip()
    elif repo_root:
        working_dir = repo_root

    lifecycle_state = ""
    if isinstance(selected_target, dict):
        lifecycle_state = str(selected_target.get("lifecycle_state") or "").strip()
    elif isinstance(selected_repo, dict):
        lifecycle_state = str(selected_repo.get("lifecycle_state") or "").strip()

    version_record = version_by_target.get(target_id) if target_id else None
    version_source_refs = (
        version_record.get("version_sources") if isinstance(version_record, dict) and isinstance(version_record.get("version_sources"), list) else []
    )

    selection_reason = hints["selection_reason"]
    if not selection_reason:
        if hints["target_id"]:
            selection_reason = "context.target_id"
        elif hints["launch_profile_id"] or hints["app_id"]:
            selection_reason = "context.launch_profile_id"
        elif hints["repo_id"]:
            selection_reason = "context.repo_id"
        else:
            selection_reason = "unresolved"

    return {
        "apply_class": is_apply_class(envelope),
        "hints": hints,
        "repo": selected_repo if isinstance(selected_repo, dict) else None,
        "target": selected_target if isinstance(selected_target, dict) else None,
        "launch_profile": selected_profile if isinstance(selected_profile, dict) else None,
        "repo_id": repo_id,
        "target_id": target_id,
        "repo_root": repo_root,
        "working_dir": working_dir,
        "launch_profile_id": launch_profile_id,
        "lifecycle_state": lifecycle_state,
        "version_source_refs": version_source_refs,
        "selection_reason": selection_reason,
        "source_paths": {
            "active_execution_registry": str(active_path),
            "apps_and_launch_registry": str(apps_path),
            "version_registry": str(version_path),
            "authority_matrix": str(authority_path),
            "duplicate_surface_register": str(duplicate_path),
        },
        "authority_matrix": authority_matrix,
        "duplicate_surface_register": duplicate_surface_register,
    }
