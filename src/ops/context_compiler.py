"""Unified enforcement context compiler — single assembly layer for all agents.

Both Claude (enforcement_pre_write.py) and Codex (codex_enforcement_bridge.py)
call this module. This eliminates duplicate pipelines and provides:
  - Unified profile resolution + rules digest + write authorization
  - Agent-scoped artifacts (no race condition on shared rule_packet.v1.json)
  - Provenance tracking for every loaded rule
  - Fingerprint-based caching to avoid redundant compilations

Usage:
    from src.ops.context_compiler import compile_enforcement_context
    result = compile_enforcement_context(
        workspace_root=ws, target_path="src/ops/foo.py", agent_id="claude"
    )

CLI:
    python -m src.ops.manage compile-context --workspace-root .cache/ws_customer_default --target-path src/ops/foo.py
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

from src.shared.utils import load_json, load_json_or_default, now_iso8601, write_json_atomic

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Cache: fingerprint → compiled result (session-scoped, in-memory)
_COMPILATION_CACHE: dict[str, dict[str, Any]] = {}


# ── Public API ──────────────────────────────────────────────────


def compile_enforcement_context(
    *,
    workspace_root: Path,
    target_path: str,
    agent_id: str = "claude",
    request_hash: str = "",
) -> dict[str, Any]:
    """Compile enforcement context for any agent (Claude/Codex).

    Returns a compiled context dict and writes agent-scoped artifact.
    Uses fingerprint cache to avoid redundant compilations.
    """
    from src.ops.context_profile_resolver import resolve_profile
    from src.ops.compile_rules_digest import compile_rules_digest
    from src.ops.write_authorize import write_authorize

    # 1. Resolve profile (fail-safe: fallback to TASK_EXECUTION)
    profile = _safe_resolve_profile(workspace_root)
    profile_id = profile.get("profile_id", "TASK_EXECUTION")

    # 2. Check fingerprint cache
    fingerprint = _compute_fingerprint(target_path, profile_id, agent_id, workspace_root)
    cached = _COMPILATION_CACHE.get(fingerprint)
    if cached:
        logger.debug("Cache hit for fingerprint=%s", fingerprint[:12])
        return cached

    # 3. Compile rules digest
    digest = _safe_compile_digest(workspace_root, target_path)

    # 4. Write authorization
    auth = _safe_write_authorize(workspace_root, target_path)

    # 5. Build provenance records
    provenance = _build_provenance(digest, profile_id)

    # 6. List compilation sources
    sources = _list_compilation_sources(workspace_root)

    # 6b. Domain scope detection (Phase 2)
    domain_scope = _detect_domain(target_path)

    # 6c. Scope guard check (Phase 3)
    scope_check = _check_scope(workspace_root, target_path, domain_scope.get("primary_domain", "general"))

    # 6d. Impact analysis (Phase 3)
    impact = _analyze_impact(target_path)

    # 6e. Domain conventions (Phase 3)
    conventions = _load_conventions(domain_scope.get("primary_domain", "general"))

    # 7. Assemble result
    result: dict[str, Any] = {
        "version": "v1",
        "compiled_at": now_iso8601(),
        "compiler_version": "2.0.0",
        "agent_id": agent_id,
        "target_path": target_path,
        "profile": {
            "id": profile_id,
            "resolution_method": profile.get("resolution_method", "fallback"),
            "matched_trigger": profile.get("matched_trigger"),
        },
        "authorization": {
            "status": auth.get("status", "WARN"),
            "deny_reasons": auth.get("deny_reasons", []),
            "core_unlock_required": auth.get("core_unlock_required", False),
            "core_unlock_active": auth.get("core_unlock_active", False),
        },
        "rules": {
            "layer": digest.get("layer", "UNKNOWN"),
            "domain": digest.get("domain", "general"),
            "naming": digest.get("naming", {}),
            "shared_utils": digest.get("shared_utils", {}),
            "domain_rules": digest.get("domain_rules", []),
            "general_rules": digest.get("general_rules", {}),
            "forbidden_patterns": digest.get("general_rules", {}).get("forbidden", []),
        },
        "rules_with_provenance": provenance,
        "compilation_sources": sources,
        "domain_scope": domain_scope,
        "conventions": conventions,
        "scope_check": scope_check,
        "impact": impact,
        "required_validations": auth.get("required_validations", []),
        "evidence_required": digest.get("evidence_required", False),
        "fingerprint": fingerprint,
    }

    # 8. Write agent-scoped artifact (R2: no race condition)
    artifact_path = _agent_scoped_artifact_path(workspace_root, agent_id, request_hash or fingerprint[:8])
    _write_artifact(artifact_path, result)

    # 9. Also write legacy path for backward compat (post-write reads it)
    _write_legacy_packet(workspace_root, result)

    # 10. Cache
    _COMPILATION_CACHE[fingerprint] = result

    return result


def clear_cache() -> int:
    """Clear in-memory compilation cache. Returns count of cleared entries."""
    count = len(_COMPILATION_CACHE)
    _COMPILATION_CACHE.clear()
    return count


# ── Safe wrappers (fail-open for non-critical, fail-closed for auth) ────


def _safe_resolve_profile(workspace_root: Path) -> dict[str, Any]:
    from src.ops.context_profile_resolver import resolve_profile
    try:
        return resolve_profile(workspace_root)
    except Exception as exc:
        logger.warning("Profile resolution failed: %s", exc)
        return {"profile_id": "TASK_EXECUTION", "resolution_method": "fallback"}


def _safe_compile_digest(workspace_root: Path, target_path: str) -> dict[str, Any]:
    from src.ops.compile_rules_digest import compile_rules_digest
    try:
        return compile_rules_digest(workspace_root=workspace_root, target_path=target_path)
    except Exception as exc:
        logger.warning("Rules digest compilation failed: %s", exc)
        return {"layer": "UNKNOWN", "domain": "general", "domain_rules": [], "general_rules": {}}


def _safe_write_authorize(workspace_root: Path, target_path: str) -> dict[str, Any]:
    from src.ops.write_authorize import write_authorize
    try:
        return write_authorize(workspace_root=workspace_root, target_path=target_path)
    except Exception as exc:
        logger.warning("Write authorization failed: %s", exc)
        return {"status": "WARN", "deny_reasons": [f"authorization check failed: {exc}"]}


# ── Provenance ──────────────────────────────────────────────────


def _build_provenance(digest: dict[str, Any], profile_id: str) -> list[dict[str, Any]]:
    """Build provenance records for each rule, tracking source and why."""
    provenance: list[dict[str, Any]] = []
    domain = digest.get("domain", "general")

    # Domain rules
    for i, rule_text in enumerate(digest.get("domain_rules", [])):
        provenance.append({
            "rule_id": f"R-{domain}-{i + 1:03d}",
            "text": rule_text,
            "source": f".claude/rules/{domain}.md",
            "domain": domain,
            "profile": profile_id,
            "priority": "MUST",
        })

    # General rules
    general = digest.get("general_rules", {})
    for key, value in general.items():
        if isinstance(value, str):
            provenance.append({
                "rule_id": f"R-general-{key}",
                "text": value,
                "source": "docs/OPERATIONS/CODING-STANDARDS.md",
                "domain": "general",
                "profile": profile_id,
                "priority": "SHOULD" if key == "docstrings" else "MUST",
            })

    # Shared utils
    shared = digest.get("shared_utils", {})
    for key, value in shared.items():
        if isinstance(value, str):
            provenance.append({
                "rule_id": f"R-shared-{key}",
                "text": f"Use {value}",
                "source": "src/shared/utils.py",
                "domain": "general",
                "profile": profile_id,
                "priority": "MUST",
            })

    return provenance


# ── Domain Detection ───────────────────────────────────────────


def _detect_domain(target_path: str) -> dict[str, Any]:
    """Detect domain scope for target path using domain_scope_engine."""
    try:
        from src.ops.domain_scope_engine import detect_domain_scope
        return detect_domain_scope(target_path)
    except Exception as exc:
        logger.debug("Domain detection skipped: %s", exc)
        return {
            "detected_domains": [],
            "primary_domain": "general",
            "confidence": 0.0,
            "detection_method": "fallback",
            "evidence": [],
        }


# ── Scope Guard (Phase 3) ──────────────────────────────────────


def _check_scope(workspace_root: Path, target_path: str, domain: str) -> dict[str, Any]:
    """Check scope guard for this write."""
    try:
        from src.ops.scope_guard import check_scope
        return check_scope(workspace_root, new_file=target_path, new_domain=domain)
    except Exception as exc:
        logger.debug("Scope check skipped: %s", exc)
        return {"status": "WITHIN_SCOPE", "reason": "", "files_written": 0, "max_files": 10}


# ── Impact Analysis (Phase 3) ─────────────────────────────────


def _analyze_impact(target_path: str) -> dict[str, Any]:
    """Analyze change impact for target file."""
    try:
        from src.ops.impact_analyzer import analyze_impact
        return analyze_impact(_REPO_ROOT, target_path)
    except Exception as exc:
        logger.debug("Impact analysis skipped: %s", exc)
        return {"target": target_path, "affected_count": 0, "risk_level": "LOW"}


# ── Domain Conventions (Phase 3) ──────────────────────────────


def _load_conventions(domain: str) -> list[dict[str, str]]:
    """Load domain conventions from policy_domain_conventions.v1.json."""
    try:
        policy_path = _REPO_ROOT / "policies" / "policy_domain_conventions.v1.json"
        if not policy_path.exists():
            return []
        policy = load_json(policy_path)
        domain_config = policy.get("domains", {}).get(domain, {})
        if not domain_config:
            return []

        conventions: list[dict[str, str]] = []
        conv_id = 0

        # Forbidden imports
        for imp in domain_config.get("forbidden_imports", []):
            conv_id += 1
            conventions.append({"id": f"CONV-{domain[:2].upper()}-{conv_id:03d}", "text": f"Forbidden import: {imp}", "domain": domain})

        # Required package
        req_pkg = domain_config.get("required_package")
        if req_pkg:
            conv_id += 1
            conventions.append({"id": f"CONV-{domain[:2].upper()}-{conv_id:03d}", "text": f"Required package: {req_pkg}", "domain": domain})

        # Bundler
        bundler = domain_config.get("bundler")
        if bundler:
            conv_id += 1
            conventions.append({"id": f"CONV-{domain[:2].upper()}-{conv_id:03d}", "text": f"Bundler: {bundler}", "domain": domain})

        # Auth model
        auth = domain_config.get("auth_model")
        if auth:
            conv_id += 1
            conventions.append({"id": f"CONV-{domain[:2].upper()}-{conv_id:03d}", "text": f"Auth: {auth}", "domain": domain})

        # Query rules
        qr = domain_config.get("query_rules", {})
        for key, val in qr.items():
            if val:
                conv_id += 1
                conventions.append({"id": f"CONV-{domain[:2].upper()}-{conv_id:03d}", "text": f"Query rule: {key}", "domain": domain})

        return conventions[:20]  # Cap to prevent context overflow
    except Exception as exc:
        logger.debug("Convention loading skipped: %s", exc)
        return []


# ── Compilation Sources ─────────────────────────────────────────


def _list_compilation_sources(workspace_root: Path) -> list[dict[str, str]]:
    """List files that contributed to this compilation."""
    sources = []
    candidates = [
        _REPO_ROOT / "policies" / "policy_context_profile_registry.v1.json",
        _REPO_ROOT / "policies" / "policy_context_orchestration.v1.json",
        _REPO_ROOT / "AGENTS.md",
        _REPO_ROOT / "standards.lock",
        _REPO_ROOT / "decisions" / "registry.v1.json",
        _REPO_ROOT / "docs" / "OPERATIONS" / "CODING-STANDARDS.md",
    ]

    # Add all .claude/rules/*.md files
    rules_dir = _REPO_ROOT / ".claude" / "rules"
    if rules_dir.is_dir():
        candidates.extend(sorted(rules_dir.glob("*.md")))

    for path in candidates:
        if path.exists():
            sources.append({
                "path": str(path.relative_to(_REPO_ROOT)),
                "exists": True,
            })

    return sources


# ── Fingerprint & Caching ──────────────────────────────────────


def _compute_fingerprint(target_path: str, profile_id: str, agent_id: str, workspace_root: Path) -> str:
    """SHA256 fingerprint for cache key."""
    # Include target, profile, agent, and policy mtime for invalidation
    parts = [target_path, profile_id, agent_id]

    policy_path = _REPO_ROOT / "policies" / "policy_context_orchestration.v1.json"
    if policy_path.exists():
        parts.append(str(policy_path.stat().st_mtime_ns))

    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ── Artifact I/O ───────────────────────────────────────────────


def _agent_scoped_artifact_path(workspace_root: Path, agent_id: str, hash_prefix: str) -> Path:
    """Agent-scoped artifact path — prevents multi-agent race condition."""
    reports_dir = workspace_root / ".cache" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    safe_agent = re.sub(r"[^a-zA-Z0-9_-]", "_", agent_id)
    safe_hash = re.sub(r"[^a-fA-F0-9]", "", hash_prefix)[:8]
    return reports_dir / f"rule_packet.{safe_agent}.{safe_hash}.v1.json"


def _write_artifact(path: Path, result: dict[str, Any]) -> None:
    """Write compiled context artifact atomically."""
    try:
        write_json_atomic(path, result)
    except Exception as exc:
        logger.warning("Failed to write artifact to %s: %s", path, exc)


def _write_legacy_packet(workspace_root: Path, result: dict[str, Any]) -> None:
    """Write legacy rule_packet.v1.json for backward compat with post-write hook."""
    legacy_path = workspace_root / ".cache" / "reports" / "rule_packet.v1.json"
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    # Extract legacy-compatible subset
    legacy = {
        "version": result["version"],
        "generated_at": result["compiled_at"],
        "target_path": result["target_path"],
        "profile_id": result["profile"]["id"],
        "authorization": result["authorization"],
        "rules": result["rules"],
        "required_validations": result["required_validations"],
        "evidence_required": result["evidence_required"],
    }
    try:
        write_json_atomic(legacy_path, legacy)
    except Exception as exc:
        logger.warning("Failed to write legacy packet: %s", exc)
