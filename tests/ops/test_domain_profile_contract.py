"""Contract tests for domain profile system."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Registry & Schema
# ---------------------------------------------------------------------------

def test_domain_profiles_registry_exists() -> None:
    path = REPO_ROOT / "registry" / "domain_profiles.v1.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == "v1"
    assert "profiles" in data
    assert isinstance(data["profiles"], dict)
    assert len(data["profiles"]) >= 4  # At least 4 profiles


def test_domain_profile_schema_exists() -> None:
    path = REPO_ROOT / "schemas" / "domain-profile.schema.v1.json"
    assert path.exists()
    schema = json.loads(path.read_text(encoding="utf-8"))
    assert schema["title"] == "Domain Profile"
    assert "profile_id" in schema["properties"]


def test_all_profiles_have_required_fields() -> None:
    path = REPO_ROOT / "registry" / "domain_profiles.v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    required = {"profile_id", "display_name", "service_scopes", "active_lanes", "execution_sequence", "tech_stack", "write_roots", "bootstrap_tiers"}
    for pid, profile in data["profiles"].items():
        missing = required - set(profile.keys())
        assert not missing, f"Profile {pid} missing: {missing}"


def test_profile_scopes_are_valid() -> None:
    valid_scopes = {"backend", "database", "api", "frontend"}
    valid_lanes = {"unit", "database", "api", "contract", "integration", "e2e"}
    path = REPO_ROOT / "registry" / "domain_profiles.v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for pid, profile in data["profiles"].items():
        for scope in profile["service_scopes"]:
            assert scope in valid_scopes, f"{pid}: invalid scope {scope}"
        for lane in profile["active_lanes"]:
            assert lane in valid_lanes, f"{pid}: invalid lane {lane}"


# ---------------------------------------------------------------------------
# Profile Resolver
# ---------------------------------------------------------------------------

def test_list_profiles() -> None:
    from src.ops.domain_profile_resolver import list_profiles
    result = list_profiles(REPO_ROOT)
    assert result["status"] == "OK"
    assert len(result["profiles"]) >= 4
    pids = {p["profile_id"] for p in result["profiles"]}
    assert "fullstack" in pids
    assert "backend-api" in pids
    assert "frontend-web" in pids
    assert "frontend-mobile" in pids


def test_resolve_fullstack_profile() -> None:
    from src.ops.domain_profile_resolver import resolve_profile
    result = resolve_profile(REPO_ROOT, "fullstack")
    assert result["status"] == "OK"
    profile = result["profile"]
    assert set(profile["service_scopes"]) == {"backend", "database", "api", "frontend"}
    assert len(profile["active_lanes"]) == 6


def test_resolve_backend_api_profile() -> None:
    from src.ops.domain_profile_resolver import resolve_profile
    result = resolve_profile(REPO_ROOT, "backend-api")
    assert result["status"] == "OK"
    profile = result["profile"]
    assert "frontend" not in profile["service_scopes"]
    assert "contract" not in profile["active_lanes"]


def test_resolve_frontend_web_profile() -> None:
    from src.ops.domain_profile_resolver import resolve_profile
    result = resolve_profile(REPO_ROOT, "frontend-web")
    assert result["status"] == "OK"
    profile = result["profile"]
    assert "backend" not in profile["service_scopes"]
    assert "unit" not in profile["active_lanes"]
    assert "contract" in profile["active_lanes"]


def test_resolve_unknown_profile_fails() -> None:
    from src.ops.domain_profile_resolver import resolve_profile
    result = resolve_profile(REPO_ROOT, "nonexistent-profile")
    assert result["status"] == "FAIL"
    assert result["error"] == "PROFILE_NOT_FOUND"


def test_resolve_empty_defaults_to_fullstack() -> None:
    from src.ops.domain_profile_resolver import resolve_profile
    result = resolve_profile(REPO_ROOT, "")
    assert result["status"] == "OK"
    assert result["profile"]["profile_id"] == "fullstack"


# ---------------------------------------------------------------------------
# Lane Config Generator
# ---------------------------------------------------------------------------

def test_generate_lane_config_fullstack() -> None:
    from src.ops.domain_profile_resolver import generate_lane_config
    result = generate_lane_config(REPO_ROOT, "fullstack")
    assert result["status"] == "OK"
    config = result["lane_config"]
    assert config["managed_repo_profile"] == "fullstack"
    assert len(config["execution_sequence"]) == 6
    assert "unit" in config["lanes"]
    assert "contract" in config["lanes"]


def test_generate_lane_config_backend_only() -> None:
    from src.ops.domain_profile_resolver import generate_lane_config
    result = generate_lane_config(REPO_ROOT, "backend-api")
    assert result["status"] == "OK"
    config = result["lane_config"]
    assert "contract" not in config["lanes"]  # No frontend lane
    assert "unit" in config["lanes"]
    assert "frontend" not in config["execution_sequence"]


def test_generate_lane_config_frontend_web() -> None:
    from src.ops.domain_profile_resolver import generate_lane_config
    result = generate_lane_config(REPO_ROOT, "frontend-web")
    assert result["status"] == "OK"
    config = result["lane_config"]
    assert "unit" not in config["lanes"]  # No backend lane
    assert "contract" in config["lanes"]
    assert "backend" not in config["execution_sequence"]


# ---------------------------------------------------------------------------
# Write Roots & Bootstrap Tiers
# ---------------------------------------------------------------------------

def test_write_roots_differ_per_profile() -> None:
    from src.ops.domain_profile_resolver import resolve_write_roots
    full = resolve_write_roots(REPO_ROOT, "fullstack")
    be = resolve_write_roots(REPO_ROOT, "backend-api")
    fe = resolve_write_roots(REPO_ROOT, "frontend-web")

    assert "web/**" in full
    assert "backend/**" in full
    assert "web/**" not in be
    assert "backend/**" not in fe


def test_bootstrap_tiers_per_profile() -> None:
    from src.ops.domain_profile_resolver import resolve_bootstrap_tiers
    full = resolve_bootstrap_tiers(REPO_ROOT, "fullstack")
    be = resolve_bootstrap_tiers(REPO_ROOT, "backend-api")

    assert "AGENTS.md" in full["tier2_structural"]
    assert "AGENTS.md" in be["tier2_structural"]
    # Fullstack has more tier2 files
    assert len(full["tier2_structural"]) >= len(be["tier2_structural"])


# ---------------------------------------------------------------------------
# Profile-Aware AGENTS.md Generation
# ---------------------------------------------------------------------------

def test_agents_md_includes_profile_section() -> None:
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from generate_managed_repo_agents_md import generate_agents_md

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp)
        result = generate_agents_md(
            source_root=REPO_ROOT,
            target_root=target,
            domain_profile="backend-api",
            apply=True,
        )
        assert result["status"] == "OK"
        content = (target / "AGENTS.md").read_text(encoding="utf-8")
        assert "Domain Profile" in content
        assert "backend-api" in content
        assert "Backend + API Service" in content


def test_agents_md_fullstack_profile_has_all_scopes() -> None:
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from generate_managed_repo_agents_md import generate_agents_md

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp)
        generate_agents_md(
            source_root=REPO_ROOT,
            target_root=target,
            domain_profile="fullstack",
            apply=True,
        )
        content = (target / "AGENTS.md").read_text(encoding="utf-8")
        assert "backend" in content
        assert "frontend" in content
        assert "database" in content


# ---------------------------------------------------------------------------
# Ops command registration
# ---------------------------------------------------------------------------

def test_ops_commands_registered() -> None:
    from src.ops.manage import build_parser
    parser = build_parser()
    # Check that domain-profile commands are registered
    sub_action = None
    for action in parser._actions:
        if hasattr(action, "choices") and isinstance(action.choices, dict):
            sub_action = action
            break
    assert sub_action is not None
    assert "domain-profile-list" in sub_action.choices
    assert "domain-profile-resolve" in sub_action.choices
    assert "domain-profile-lanes" in sub_action.choices
