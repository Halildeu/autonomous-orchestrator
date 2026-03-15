"""Domain profile resolver for managed repos.

Resolves a domain profile by ID and generates profile-specific
lane configuration, write roots, and bootstrap tiers.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_REGISTRY_REL = "registry/domain_profiles.v1.json"


def _load_registry(repo_root: Path) -> dict[str, Any]:
    path = repo_root / _REGISTRY_REL
    if not path.exists():
        return {}
    obj = json.loads(path.read_text(encoding="utf-8"))
    return obj if isinstance(obj, dict) else {}


def list_profiles(repo_root: Path) -> dict[str, Any]:
    """List all available domain profiles."""
    registry = _load_registry(repo_root)
    profiles = registry.get("profiles")
    if not isinstance(profiles, dict):
        return {"status": "FAIL", "error": "REGISTRY_MISSING", "profiles": []}

    items = []
    for pid, prof in profiles.items():
        if not isinstance(prof, dict):
            continue
        items.append({
            "profile_id": pid,
            "display_name": str(prof.get("display_name") or pid),
            "service_scopes": prof.get("service_scopes", []),
            "active_lanes": prof.get("active_lanes", []),
        })

    return {
        "status": "OK",
        "default_profile": str(registry.get("default_profile") or "fullstack"),
        "profiles": items,
    }


def resolve_profile(repo_root: Path, profile_id: str) -> dict[str, Any]:
    """Resolve a domain profile by ID. Returns profile definition or error."""
    registry = _load_registry(repo_root)
    profiles = registry.get("profiles")
    if not isinstance(profiles, dict):
        return {"status": "FAIL", "error": "REGISTRY_MISSING"}

    pid = str(profile_id or "").strip()
    if not pid:
        pid = str(registry.get("default_profile") or "fullstack")

    profile = profiles.get(pid)
    if not isinstance(profile, dict):
        return {"status": "FAIL", "error": "PROFILE_NOT_FOUND", "profile_id": pid}

    return {"status": "OK", "profile": profile}


def generate_lane_config(repo_root: Path, profile_id: str) -> dict[str, Any]:
    """Generate module_delivery_lanes.v1.json content for a given profile.

    This allows managed repos to get a lane config that matches their domain.
    """
    result = resolve_profile(repo_root, profile_id)
    if result.get("status") != "OK":
        return result

    profile = result["profile"]

    # Build scope_lane_map from profile's execution_sequence
    scope_lane_map: dict[str, str] = {}
    default_map = {
        "backend": "unit",
        "database": "database",
        "api": "api",
        "frontend": "contract",
        "integration": "integration",
        "e2e_gate": "e2e",
    }
    for scope in profile.get("execution_sequence", []):
        if scope in default_map:
            scope_lane_map[scope] = default_map[scope]
        elif scope == "e2e":
            scope_lane_map["e2e_gate"] = "e2e"

    # Read the full lane definitions from existing config
    full_lanes_path = repo_root / "ci" / "module_delivery_lanes.v1.json"
    full_lanes: dict[str, Any] = {}
    if full_lanes_path.exists():
        try:
            full_config = json.loads(full_lanes_path.read_text(encoding="utf-8"))
            full_lanes = full_config.get("lanes", {}) if isinstance(full_config, dict) else {}
        except Exception:
            pass

    # Filter lanes to only those active in this profile
    active_lane_ids = set(profile.get("active_lanes", []))
    lanes: dict[str, Any] = {}
    for lane_id, lane_def in full_lanes.items():
        if lane_id in active_lane_ids:
            lanes[lane_id] = lane_def

    # For any active lane not in the full config, provide a fallback
    for lane_id in active_lane_ids:
        if lane_id not in lanes:
            lanes[lane_id] = {
                "command": f"python3 ci/check_standards_lock.py --repo-root .",
                "timeout_seconds": 600,
            }

    config = {
        "version": "v1",
        "managed_repo_profile": profile.get("profile_id", profile_id),
        "merge_requires_all_green": profile.get("merge_requires_all_green", True),
        "scope_lane_map": scope_lane_map,
        "execution_sequence": profile.get("execution_sequence", []),
        "lanes": lanes,
        "notes": [
            f"Auto-generated from domain profile: {profile.get('display_name', profile_id)}",
        ],
    }

    return {"status": "OK", "lane_config": config}


def resolve_write_roots(repo_root: Path, profile_id: str) -> list[str]:
    """Return the allowed write root globs for a profile."""
    result = resolve_profile(repo_root, profile_id)
    if result.get("status") != "OK":
        return ["**"]
    return list(result["profile"].get("write_roots", ["**"]))


def resolve_bootstrap_tiers(repo_root: Path, profile_id: str) -> dict[str, list[str]]:
    """Return the bootstrap tier file lists for a profile."""
    result = resolve_profile(repo_root, profile_id)
    if result.get("status") != "OK":
        return {
            "tier1_status": [],
            "tier2_structural": ["AGENTS.md"],
        }
    return dict(result["profile"].get("bootstrap_tiers", {}))
