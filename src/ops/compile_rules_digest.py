"""Compile a context-aware rules digest for a target path.

Merges AGENTS.md conventions, active profile, .claude/rules/{domain},
CODING-STANDARDS, and LAYER-MODEL-LOCK into a single JSON digest
that an agent can consume before writing code.

Usage (CLI):
    python -m src.ops.manage compile-rules-digest --workspace-root .cache/ws_customer_default --target-path src/ops/
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from src.shared.utils import load_json, now_iso8601

_REPO_ROOT = Path(__file__).resolve().parents[2]

# ── Path → Layer mapping ─────────────────────────────────────────

_LAYER_MAP = [
    # L0 CORE — canonical SSOT files
    (re.compile(r"^AGENTS\.md$"), "L0_CORE", False),  # allowlisted in AGENTS.md
    (re.compile(r"^CLAUDE\.md$"), "L0_CORE", False),
    (re.compile(r"^schemas/"), "L0_CORE", False),
    (re.compile(r"^policies/"), "L0_CORE", False),
    (re.compile(r"^docs/"), "L0_CORE", False),
    (re.compile(r"^orchestrator/"), "L0_CORE", False),
    (re.compile(r"^src/"), "L0_CORE", True),   # CORE_UNLOCK required
    (re.compile(r"^ci/"), "L0_CORE", False),
    (re.compile(r"^scripts/"), "L0_CORE", False),
    (re.compile(r"^\.github/"), "L0_CORE", False),
    (re.compile(r"^\.claude/"), "L0_CORE", False),  # rules, settings
    (re.compile(r"^\.codex/"), "L0_CORE", False),   # codex config
    (re.compile(r"^roadmaps/"), "L0_CORE", False),
    # L1 CATALOG
    (re.compile(r"^packs/"), "L1_CATALOG", False),
    (re.compile(r"^extensions/"), "L1_CATALOG", False),
    (re.compile(r"^templates/"), "L1_CATALOG", False),
    # L2 WORKSPACE
    (re.compile(r"^\.cache/"), "L2_WORKSPACE", False),
]

# ── Path → Rules domain mapping ──────────────────────────────────

_DOMAIN_MAP = [
    (re.compile(r"^src/ops/"), "src-ops"),
    (re.compile(r"^src/orchestrator/observability/"), "observability"),
    (re.compile(r"^src/orchestrator/"), "state-machine"),
    (re.compile(r"^src/evidence/"), "evidence"),
    (re.compile(r"^src/context/"), "context-pack"),
    (re.compile(r"^src/"), "src-ops"),
    (re.compile(r"^schemas/"), "schemas"),
    (re.compile(r"^policies/"), "policies"),
    (re.compile(r"^ci/"), "ci"),
    (re.compile(r"^extensions/"), "extensions"),
    (re.compile(r"^roadmaps/"), "roadmaps"),
    (re.compile(r"^tests/"), "tests"),
    (re.compile(r"^docs/"), "cross-repo"),
    (re.compile(r"^scripts/"), "ci"),
    (re.compile(r"^\.github/"), "ci"),
    (re.compile(r"^\.claude/"), "context-pack"),
    (re.compile(r"^\.codex/"), "cross-repo"),
    (re.compile(r"^AGENTS\.md$"), "cross-repo"),
    (re.compile(r"^CLAUDE\.md$"), "cross-repo"),
]

# ── CODING-STANDARDS shared utilities ─────────────────────────────

_SHARED_UTILS = {
    "json_io": "src.shared.utils (load_json, write_json_atomic)",
    "time": "src.shared.utils (now_iso8601)",
    "hashing": "src.shared.utils (hash_string)",
    "logging": "src.shared.logger (get_logger(__name__))",
    "status": "src.shared.status (validate_transition, validate_status)",
    "wal": "src.shared.wal (WALWriter) for durable state writes",
}


def _resolve_layer(target_path: str) -> tuple[str, bool]:
    """Resolve layer and CORE_UNLOCK requirement for a path."""
    for pattern, layer, needs_unlock in _LAYER_MAP:
        if pattern.match(target_path):
            return layer, needs_unlock
    return "L2_WORKSPACE", False


def _resolve_domain(target_path: str) -> str:
    """Resolve .claude/rules/ domain for a path."""
    for pattern, domain in _DOMAIN_MAP:
        if pattern.match(target_path):
            return domain
    return "general"


def _load_domain_rules(domain: str) -> list[str]:
    """Load rules from .claude/rules/{domain}.md (skip frontmatter)."""
    rules_path = _REPO_ROOT / ".claude" / "rules" / f"{domain}.md"
    if not rules_path.exists():
        return []
    lines = rules_path.read_text(encoding="utf-8").splitlines()
    # Skip frontmatter
    in_frontmatter = False
    rules = []
    for line in lines:
        if line.strip() == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter:
            continue
        if line.startswith("- "):
            rules.append(line[2:].strip())
    return rules


def _load_related_decisions(target_path: str) -> list[dict[str, Any]]:
    """Load active decisions from registry that relate to target_path."""
    registry_path = _REPO_ROOT / "decisions" / "registry.v1.json"
    if not registry_path.exists():
        return []
    try:
        registry = load_json(registry_path)
    except Exception:
        return []

    related = []
    for topic_entry in registry.get("topics", []):
        if topic_entry.get("status") != "ACTIVE":
            continue
        topic_path = _REPO_ROOT / topic_entry.get("path", "")
        if not topic_path.exists():
            continue
        try:
            topic = load_json(topic_path)
        except Exception:
            continue
        # Check if target_path relates to this topic's related_paths or cross_repo_refs
        paths = topic.get("related_paths", []) + topic.get("cross_repo_refs", [])
        for p in paths:
            if target_path in p or p in target_path:
                decisions = [d for d in topic.get("decisions", []) if d.get("status") == "FINAL"]
                rejected = topic.get("rejected_alternatives", [])
                related.append({
                    "topic_id": topic.get("topic_id"),
                    "title": topic.get("title"),
                    "decisions": [d.get("statement", "") for d in decisions],
                    "rejected": [r.get("alternative", "") for r in rejected],
                    "constraints": topic.get("constraints", []),
                })
                break
    return related


def compile_rules_digest(*, workspace_root: Path, target_path: str, intent: str | None = None) -> dict[str, Any]:
    """Compile a rules digest for a target path."""
    layer, needs_core_unlock = _resolve_layer(target_path)
    domain = _resolve_domain(target_path)
    domain_rules = _load_domain_rules(domain)

    # Naming conventions based on path
    naming = {}
    if target_path.startswith("schemas/"):
        naming = {"file": "<domain>.schema.v<N>.json", "indent": "2 spaces", "encoding": "UTF-8"}
    elif target_path.startswith("policies/"):
        naming = {"file": "policy_<domain>.v<N>.json", "indent": "2 spaces", "encoding": "UTF-8"}
    elif target_path.startswith("src/ops/"):
        naming = {"file": "snake_case.py", "commands": "kebab-case", "max_lines": 800}
    elif target_path.startswith("ci/"):
        naming = {"file": "snake_case.py", "max_lines": 800, "exit_codes": "0=pass, non-zero=fail"}
    elif target_path.startswith("tests/"):
        naming = {"file": "test_<description>.py", "functions": "test_<description>"}

    digest = {
        "version": "v1",
        "generated_at": now_iso8601(),
        "target_path": target_path,
        "layer": layer,
        "core_unlock_required": needs_core_unlock,
        "domain": domain,
        "naming": naming,
        "shared_utils": _SHARED_UTILS,
        "domain_rules": domain_rules[:20],  # Cap to prevent context overflow
        "general_rules": {
            "type_hints": "Required for all public functions",
            "docstrings": "Required for public functions",
            "forbidden": ["print() for structured output — use logger", "raw open() for JSON — use write_json_atomic"],
            "version_convention": "*.v1.json for data, *.schema.v1.json for schemas",
            "fail_closed": "On doubt, report_only / no side-effect",
            "secrets": "Never log/evidence tokens, keys, passwords",
        },
        "evidence_required": layer == "L0_CORE",
        "fail_action": "block" if needs_core_unlock else "warn",
    }

    if intent:
        digest["intent"] = intent

    # Load related decisions from registry
    related_decisions = _load_related_decisions(target_path)
    if related_decisions:
        digest["related_decisions"] = related_decisions

    return digest


# ── CLI ───────────────────────────────────────────────────────────

def register_compile_rules_digest_subcommand(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("compile-rules-digest", help="Compile context-aware rules digest for a target path")
    p.add_argument("--workspace-root", required=True)
    p.add_argument("--target-path", required=True, help="Repo-relative target path (e.g. src/ops/)")
    p.add_argument("--intent", default=None)
    p.set_defaults(func=_cmd_compile_rules_digest)


def _cmd_compile_rules_digest(args: argparse.Namespace) -> int:
    ws = Path(args.workspace_root).expanduser().resolve()
    result = compile_rules_digest(workspace_root=ws, target_path=args.target_path, intent=args.intent)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0
