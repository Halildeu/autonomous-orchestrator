"""Write-authorize gate — checks if a write to a target path is allowed.

Evaluates layer model, core_lock, naming conventions, and active profile
before allowing a file write. Returns PASS or BLOCKED with reasons.

Usage (CLI):
    python -m src.ops.manage write-authorize --workspace-root .cache/ws_customer_default --target-path schemas/foo.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from src.shared.utils import now_iso8601

_REPO_ROOT = Path(__file__).resolve().parents[2]

# ── CORE_LOCK allowlist (from AGENTS.md) ──────────────────────────

_CORE_ALLOWLIST = [
    re.compile(r"^schemas/"),
    re.compile(r"^policies/"),
    re.compile(r"^extensions/"),
    re.compile(r"^docs/OPERATIONS/"),
    re.compile(r"^docs/ROADMAP\.md$"),
    re.compile(r"^docs/LAYER-MODEL-LOCK\.v1\.md$"),
    re.compile(r"^docs/OPERATIONS/SSOT-MAP\.md$"),
    re.compile(r"^docs/OPERATIONS/AI-MULTIREPO-OPERATING-CONTRACT\.v1\.md$"),
    re.compile(r"^roadmaps/SSOT/roadmap\.v1\.json$"),
    re.compile(r"^\.github/"),
    re.compile(r"^standards\.lock$"),
    re.compile(r"^scripts/"),
    re.compile(r"^ci/"),
    re.compile(r"^pyproject\.toml$"),
    re.compile(r"^\.pre-commit-config\.yaml$"),
    re.compile(r"^AGENTS\.md$"),
    re.compile(r"^\.cache/"),  # Workspace writes always allowed
]

# ── Naming patterns ───────────────────────────────────────────────

_NAMING_RULES = [
    (re.compile(r"^schemas/.*\.schema\.(v\d+\.)?json$"), True, "schemas: must match *.schema.v<N>.json or *.schema.json"),
    (re.compile(r"^schemas/"), False, "schemas: file does not match naming convention"),
    (re.compile(r"^policies/policy_.*\.v\d+\.json$"), True, "policies: must match policy_*.v<N>.json"),
    (re.compile(r"^policies/"), False, "policies: file does not match naming convention"),
]


def write_authorize(*, workspace_root: Path, target_path: str) -> dict[str, Any]:
    """Check if writing to target_path is authorized."""
    deny_reasons: list[str] = []
    required_validations: list[str] = []

    # Layer resolution
    layer = "L2_WORKSPACE"
    core_unlock_required = False
    if target_path.startswith("src/"):
        layer = "L0_CORE"
        core_unlock_required = True
    elif target_path.startswith(("schemas/", "policies/", "docs/", "ci/", "orchestrator/", ".github/", "roadmaps/")):
        layer = "L0_CORE"
    elif target_path.startswith(("packs/", "extensions/", "templates/")):
        layer = "L1_CATALOG"
    elif target_path.startswith(".cache/"):
        layer = "L2_WORKSPACE"

    # Core lock check
    core_lock = "ON"
    core_unlock_env = os.environ.get("CORE_UNLOCK", "0")
    if core_unlock_required and core_unlock_env != "1":
        deny_reasons.append("CORE_UNLOCK=1 required for src/ writes")

    # Allowlist check (for L0 paths)
    if layer == "L0_CORE":
        allowed = any(p.match(target_path) for p in _CORE_ALLOWLIST)
        if not allowed and not target_path.startswith("src/"):
            deny_reasons.append(f"Path '{target_path}' not in core allowlist")
        elif target_path.startswith("src/") and core_unlock_env != "1":
            pass  # Already covered by core_unlock check

    # Naming convention check
    naming_valid = True
    naming_note = ""
    for pattern, is_valid, msg in _NAMING_RULES:
        if pattern.match(target_path):
            naming_valid = is_valid
            naming_note = msg
            break

    if not naming_valid:
        deny_reasons.append(f"Naming violation: {naming_note}")

    # Required validations based on path
    if target_path.startswith("schemas/"):
        required_validations.append("python3 ci/validate_schemas.py")
    if target_path.startswith("policies/"):
        required_validations.append("python3 ci/validate_schemas.py")
    if target_path.startswith("src/"):
        required_validations.append("python3 ci/core_ops_contract_test.py")
    if target_path.startswith("roadmaps/"):
        required_validations.append("python3 ci/validate_schemas.py")

    status = "BLOCKED" if deny_reasons else "PASS"

    return {
        "version": "v1",
        "status": status,
        "target_path": target_path,
        "layer": layer,
        "core_lock": core_lock,
        "core_unlock_required": core_unlock_required,
        "core_unlock_active": core_unlock_env == "1",
        "allow_paths_match": not any("not in core allowlist" in r for r in deny_reasons),
        "naming_valid": naming_valid,
        "deny_reasons": deny_reasons,
        "required_validations": required_validations,
        "checked_at": now_iso8601(),
    }


# ── CLI ───────────────────────────────────────────────────────────

def register_write_authorize_subcommand(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("write-authorize", help="Check if a write to a target path is authorized")
    p.add_argument("--workspace-root", required=True)
    p.add_argument("--target-path", required=True, help="Repo-relative target path")
    p.set_defaults(func=_cmd_write_authorize)


def _cmd_write_authorize(args: argparse.Namespace) -> int:
    ws = Path(args.workspace_root).expanduser().resolve()
    result = write_authorize(workspace_root=ws, target_path=args.target_path)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if result["status"] == "BLOCKED" else 0
