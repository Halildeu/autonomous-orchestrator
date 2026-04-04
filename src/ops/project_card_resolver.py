"""Project context card resolver — resolve project card from target path.

Two independent axes (R5):
  - domain_scope_engine → technical domain (frontend, backend, database...)
  - project_card_resolver → project context (dev-web-frontend, orchestrator...)
  They don't override each other; they work together.

Built on extension_registry + feature_execution_contract (R9).

Usage:
    from src.ops.project_card_resolver import resolve_project_card
    card = resolve_project_card("web/apps/mfe-shell/src/Home.tsx", workspace_root)
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from src.shared.utils import load_json, load_json_or_default

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Path → Project mapping (fallback when registry/contract not available)
_PROJECT_MAP = [
    (re.compile(r"^web/apps/"), "dev-web-frontend"),
    (re.compile(r"^web/packages/"), "dev-web-frontend"),
    (re.compile(r"^apps/"), "dev-web-frontend"),
    (re.compile(r"^packages/"), "dev-web-frontend"),
    (re.compile(r".*\.tsx$"), "dev-web-frontend"),
    (re.compile(r".*\.jsx$"), "dev-web-frontend"),
    (re.compile(r"^services/"), "dev-web-backend"),
    (re.compile(r"^server/"), "dev-web-backend"),
    (re.compile(r"^src/ops/"), "orchestrator"),
    (re.compile(r"^src/orchestrator/"), "orchestrator"),
    (re.compile(r"^src/"), "orchestrator"),
    (re.compile(r"^ci/"), "orchestrator"),
    (re.compile(r"^scripts/"), "orchestrator"),
    (re.compile(r"^schemas/"), "orchestrator"),
    (re.compile(r"^policies/"), "orchestrator"),
    (re.compile(r"^db/"), "workcube-db"),
    (re.compile(r"^migrations/"), "workcube-db"),
    (re.compile(r".*\.sql$"), "workcube-db"),
]

# Project group definitions
_PROJECT_GROUPS: dict[str, dict[str, Any]] = {
    "dev-web-frontend": {
        "group": "frontend",
        "name": "Dev Web Frontend (MFE Shell)",
        "conventions_ref": ".claude/rules/frontend.md",
        "tech_stack_ref": ".cache/reports/tech_stack_discovery.v1.json",
        "ports": {"mfe-shell": 3000, "storybook": 6006, "keycloak": 8081},
        "extension_ref": "PRJ-PM-SUITE",
    },
    "dev-web-backend": {
        "group": "backend",
        "name": "Dev Web Backend Services",
        "conventions_ref": ".claude/rules/backend.md",
        "ports": {"schema-service": 8096, "keycloak": 8081},
        "extension_ref": "PRJ-KERNEL-API",
    },
    "orchestrator": {
        "group": "orchestrator",
        "name": "Autonomous Orchestrator (this repo)",
        "conventions_ref": ".claude/rules/src-ops.md",
        "ports": {"cockpit-ui": 8787, "cockpit-api": 8790},
    },
    "workcube-db": {
        "group": "database",
        "name": "Workcube Database",
        "conventions_ref": ".claude/rules/database.md",
        "ports": {"schema-service": 8096},
    },
}


def resolve_project_card(
    target_path: str,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    """Resolve project context card from target path.

    Independent from domain_scope_engine (R5 — separate axis).
    Falls back to path-based mapping if extension registry unavailable.
    """
    project_id = _resolve_project_id(target_path)

    card_template = _PROJECT_GROUPS.get(project_id, {})

    card: dict[str, Any] = {
        "project_id": project_id,
        "project_group": card_template.get("group", "unknown"),
        "name": card_template.get("name", project_id),
        "conventions_ref": card_template.get("conventions_ref", ""),
        "tech_stack_ref": card_template.get("tech_stack_ref", ""),
        "ports": card_template.get("ports", {}),
        "extension_ref": card_template.get("extension_ref", ""),
        "resolution_method": "path_map",
    }

    # Try extension registry enrichment (R9)
    if workspace_root:
        _enrich_from_registry(card, workspace_root)

    return card


def _resolve_project_id(target_path: str) -> str:
    """Resolve project ID from target path using path map."""
    for pattern, project_id in _PROJECT_MAP:
        if pattern.match(target_path):
            return project_id
    return "unknown"


def _enrich_from_registry(card: dict[str, Any], workspace_root: Path) -> None:
    """Enrich card from extension registry + feature_execution_contract (R9)."""
    ext_ref = card.get("extension_ref")
    if not ext_ref:
        return

    # Try loading feature execution contract
    contract_path = _REPO_ROOT / "extensions" / ext_ref / "contract" / "feature_execution_contract.v1.json"
    if contract_path.exists():
        try:
            contract = load_json(contract_path)
            card["service_scopes"] = contract.get("service_scopes", [])
            card["change_path_globs"] = contract.get("change_path_globs", [])
            card["resolution_method"] = "extension_registry"
        except Exception:
            pass

    # Try loading active decisions from decision registry
    try:
        registry = load_json_or_default(_REPO_ROOT / "decisions" / "registry.v1.json", {})
        active = [t.get("topic_id") for t in registry.get("topics", []) if t.get("status") == "ACTIVE"]
        card["active_decisions"] = active
    except Exception:
        pass


def detect_project_change(
    previous_project: str,
    current_project: str,
) -> dict[str, Any] | None:
    """Detect project change — returns change info or None if same project."""
    if previous_project == current_project:
        return None
    if not previous_project or previous_project == "unknown":
        return None

    return {
        "changed": True,
        "from_project": previous_project,
        "to_project": current_project,
        "from_group": _PROJECT_GROUPS.get(previous_project, {}).get("group", "unknown"),
        "to_group": _PROJECT_GROUPS.get(current_project, {}).get("group", "unknown"),
        "message": f"Project changed: {previous_project} → {current_project}",
    }
