from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.ops.ai_entry_pack_build import ai_entry_pack_path, build_ai_entry_pack
from src.ops.commands.common import repo_root, resolve_workspace_root_arg, warn
from src.orchestrator import target_registry
from src.orchestrator.target_health import evaluate_execution_target_guard
from src.utils.jsonio import load_json


def _workspace_from_arg(workspace_root: str) -> Path | None:
    return resolve_workspace_root_arg(repo_root(), workspace_root, prefer_customer_workspace=True)


def _json_print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _load_envelope_from_args(args: argparse.Namespace, workspace_root: Path) -> dict[str, Any]:
    envelope_arg = str(getattr(args, "envelope", "") or "").strip()
    if envelope_arg:
        path = Path(envelope_arg)
        resolved = (workspace_root / path).resolve() if not path.is_absolute() else path.resolve()
        raw = load_json(resolved)
        if not isinstance(raw, dict):
            raise RuntimeError("Envelope JSON object olmalidir.")
        return raw

    context: dict[str, Any] = {}
    for key in ("repo_id", "target_id", "launch_profile_id", "app_id", "selection_reason"):
        value = str(getattr(args, key, "") or "").strip()
        if value:
            context[key] = value
    envelope: dict[str, Any] = {
        "request_id": "OPS-EXECUTION-TARGET-RESOLVE",
        "tenant_id": "OPS",
        "intent": str(getattr(args, "intent", "") or "urn:core:summary:summary_to_file"),
        "risk_score": 0.0,
        "dry_run": str(getattr(args, "apply", "false") or "").strip().lower() != "true",
        "side_effect_policy": "allow" if str(getattr(args, "apply", "false") or "").strip().lower() == "true" else "none",
        "idempotency_key": "OPS:EXECUTION-TARGET-RESOLVE",
    }
    if context:
        envelope["context"] = context
    return envelope


def run_execution_target_status(*, workspace_root: Path) -> dict[str, Any]:
    policy_path, policy = target_registry.load_execution_target_policy(workspace_root)
    active_path, active = target_registry.load_active_execution_registry(workspace_root)
    apps_path, apps = target_registry.load_apps_and_launch_registry(workspace_root)
    version_path, version_registry = target_registry.load_version_registry(workspace_root)
    authority_path, authority = target_registry.load_authority_matrix(workspace_root)
    duplicate_path, duplicate = target_registry.load_duplicate_surface_register(workspace_root)
    ai_pack_path, ai_pack = target_registry.load_ai_entry_pack(workspace_root)
    ai_pack_health = target_registry.ai_entry_pack_health(ai_pack)
    duplicates = target_registry.find_uncontrolled_target_duplicates(duplicate)

    return {
        "status": "OK" if not duplicates else "WARN",
        "workspace_root": str(workspace_root),
        "policy_path": str(policy_path),
        "registry_paths": {
            "active_execution_registry": str(active_path),
            "apps_and_launch_registry": str(apps_path),
            "version_registry": str(version_path),
            "authority_matrix": str(authority_path),
            "duplicate_surface_register": str(duplicate_path),
        },
        "counts": {
            "repos": len(active.get("repos") if isinstance(active.get("repos"), list) else []),
            "targets": len(active.get("targets") if isinstance(active.get("targets"), list) else []),
            "launch_profiles": len(apps.get("profiles") if isinstance(apps.get("profiles"), list) else []),
            "version_targets": len(version_registry.get("targets") if isinstance(version_registry.get("targets"), list) else []),
            "authority_surfaces": len(authority.get("surfaces") if isinstance(authority.get("surfaces"), list) else []),
            "duplicate_concerns": len(duplicate.get("concerns") if isinstance(duplicate.get("concerns"), list) else []),
        },
        "resolution": {
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
        },
        "ai_entry_pack": {
            "path": str(ai_pack_path) if ai_pack_path is not None else "",
            **ai_pack_health,
        },
        "uncontrolled_duplicate_concerns": duplicates,
    }


def run_execution_target_resolve(*, workspace_root: Path, envelope: dict[str, Any]) -> dict[str, Any]:
    resolution = target_registry.resolve_target_selection(workspace_root, envelope)
    guard = evaluate_execution_target_guard(
        workspace=workspace_root,
        envelope=envelope,
        writes_allowed=True,
    )
    return {
        "status": str(guard.get("status") or "UNKNOWN"),
        "workspace_root": str(workspace_root),
        "apply_class": bool(resolution.get("apply_class")),
        "hints": resolution.get("hints") if isinstance(resolution.get("hints"), dict) else {},
        "selection_reason": str(resolution.get("selection_reason") or "").strip(),
        "resolved": {
            "repo_id": str(resolution.get("repo_id") or "").strip(),
            "target_id": str(resolution.get("target_id") or "").strip(),
            "repo_root": str(resolution.get("repo_root") or "").strip(),
            "working_dir": str(resolution.get("working_dir") or "").strip(),
            "launch_profile_id": str(resolution.get("launch_profile_id") or "").strip(),
            "version_source_refs": resolution.get("version_source_refs")
            if isinstance(resolution.get("version_source_refs"), list)
            else [],
        },
        "guard": guard,
    }


def cmd_execution_target_status(args: argparse.Namespace) -> int:
    ws = _workspace_from_arg(str(args.workspace_root or ""))
    if ws is None:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2
    _json_print(run_execution_target_status(workspace_root=ws))
    return 0


def cmd_execution_target_resolve(args: argparse.Namespace) -> int:
    ws = _workspace_from_arg(str(args.workspace_root or ""))
    if ws is None:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2
    try:
        envelope = _load_envelope_from_args(args, ws)
        result = run_execution_target_resolve(workspace_root=ws, envelope=envelope)
    except Exception as e:
        warn(f"FAIL error=EXECUTION_TARGET_RESOLVE detail={str(e)}")
        return 2
    _json_print(result)
    return 0


def cmd_ai_entry_pack_build(args: argparse.Namespace) -> int:
    ws = _workspace_from_arg(str(args.workspace_root or ""))
    if ws is None:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2
    try:
        result = build_ai_entry_pack(workspace_root=ws)
    except Exception as e:
        warn(f"FAIL error=AI_ENTRY_PACK_BUILD detail={str(e)}")
        return 2
    _json_print(result)
    return 0


def register_execution_target_subcommands(parent: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    ap_status = parent.add_parser(
        "execution-target-status",
        help="Read-only execution target governance status.",
    )
    ap_status.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_status.set_defaults(func=cmd_execution_target_status)

    ap_resolve = parent.add_parser(
        "execution-target-resolve",
        help="Read-only execution target resolve/guard output.",
    )
    ap_resolve.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_resolve.add_argument("--envelope", default="", help="Envelope JSON path (workspace-relative or absolute).")
    ap_resolve.add_argument("--repo-id", default="", help="Context repo_id hint.")
    ap_resolve.add_argument("--target-id", default="", help="Context target_id hint.")
    ap_resolve.add_argument("--launch-profile-id", default="", help="Context launch_profile_id hint.")
    ap_resolve.add_argument("--app-id", default="", help="Context app_id hint.")
    ap_resolve.add_argument("--selection-reason", default="ops.execution-target-resolve", help="Selection reason.")
    ap_resolve.add_argument("--intent", default="urn:core:summary:summary_to_file", help="Intent when envelope not provided.")
    ap_resolve.add_argument("--apply", default="false", help="true|false; true ise apply-class envelope kurulur.")
    ap_resolve.set_defaults(func=cmd_execution_target_resolve)

    ap_build = parent.add_parser(
        "ai-entry-pack-build",
        help="Build or refresh workspace AI entry pack from current governance sources.",
    )
    ap_build.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_build.set_defaults(func=cmd_ai_entry_pack_build)
