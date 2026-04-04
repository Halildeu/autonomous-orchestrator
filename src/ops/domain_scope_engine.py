"""Domain scope engine — auto-detect domain from file paths and content.

Detects 6 domains: frontend, backend, database, accounting, api, infra.
Uses glob-based path matching + optional content keyword analysis.
Confidence scoring determines whether domain-specific rules are loaded.

Usage:
    from src.ops.domain_scope_engine import detect_domain_scope
    result = detect_domain_scope(target_path="web/apps/mfe-shell/src/pages/Home.tsx")
    # {"detected_domains": ["frontend"], "primary_domain": "frontend", "confidence": 0.95}
"""
from __future__ import annotations

import fnmatch
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Domain definitions ──────────────────────────────────────────

DOMAIN_SCOPES: dict[str, dict[str, Any]] = {
    "frontend": {
        "globs": [
            "*.tsx", "*.jsx", "*.vue", "*.css", "*.scss", "*.less",
            "web/**", "apps/**", "packages/**",
            "**/components/**", "**/pages/**", "**/hooks/**",
            "**/*.module.css", "**/*.module.scss",
            "vite.config.*", "tsconfig*.json", "tailwind.config.*",
        ],
        "keywords": [
            "import React", "from 'react'", "from \"react\"",
            "defineComponent", "@mfe/design-system", "ag-grid-react",
            "useState", "useEffect", "jsx", "tsx",
        ],
        "rules_domain": "frontend",
    },
    "backend": {
        "globs": [
            "src/**/*.py", "services/**", "server/**",
            "**/*.go", "**/*.java", "**/*.rs",
            "requirements*.txt", "pyproject.toml", "Cargo.toml",
        ],
        "keywords": [
            "from src.", "import flask", "import fastapi",
            "import django", "func main()", "public class",
        ],
        "rules_domain": "backend",
    },
    "database": {
        "globs": [
            "*.sql", "db/**", "migrations/**", "**/*_migration*",
            "**/sql/**", "**/*.prisma", "**/*.dbml",
        ],
        "keywords": [
            "SELECT ", "CREATE TABLE", "ALTER TABLE", "INSERT INTO",
            "DROP TABLE", "CREATE INDEX", "FOREIGN KEY",
        ],
        "rules_domain": "database",
    },
    "accounting": {
        "globs": [
            "**/account*", "**/budget*", "**/muhasebe*",
            "**/hesap*", "**/fatura*", "**/invoice*",
        ],
        "keywords": [
            "ACCOUNT_PLAN", "ACCOUNT_CARD", "BUDGET_PLAN",
            "ACCOUNT_CARD_ROWS", "hesap_plani", "muhasebe",
        ],
        "rules_domain": "accounting",
    },
    "api": {
        "globs": [
            "api/**", "api/*", "**/api/**", "**/routes/**", "**/endpoints/**",
            "**/*.openapi.*", "**/swagger.*",
            "**/controllers/**", "**/handlers/**",
        ],
        "keywords": [
            "@app.route", "router.get", "router.post",
            "openapi", "swagger", "RestController",
        ],
        "rules_domain": "api",
    },
    "infra": {
        "globs": [
            "ci/**", "scripts/**", ".github/**",
            "docker*", "Dockerfile*", "**/deploy*",
            "*.yml", "*.yaml", "Makefile",
            ".pre-commit*", "*.toml",
        ],
        "keywords": [
            "workflow", "deploy", "pipeline", "terraform",
            "docker", "kubernetes", "helm",
        ],
        "rules_domain": "infra",
    },
}

# Confidence threshold for loading domain-specific rules
DEFAULT_CONFIDENCE_THRESHOLD = 0.7


# ── Public API ──────────────────────────────────────────────────


def detect_domain_scope(
    target_path: str,
    *,
    content: str | None = None,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> dict[str, Any]:
    """Detect domain scope from target path and optional file content.

    Returns:
        {
            "detected_domains": ["frontend", "api"],
            "primary_domain": "frontend",
            "confidence": 0.92,
            "detection_method": "path_glob",
            "evidence": ["path matches web/**"]
        }
    """
    scores: dict[str, float] = {}
    evidence: dict[str, list[str]] = {}

    for domain, config in DOMAIN_SCOPES.items():
        domain_score = 0.0
        domain_evidence: list[str] = []

        # 1. Path-based detection (0.0 - 0.8)
        path_score = _score_path_match(target_path, config["globs"])
        if path_score > 0:
            domain_score += path_score * 0.8
            domain_evidence.append(f"path matches {_best_matching_glob(target_path, config['globs'])}")

        # 2. Content-based detection (0.0 - 0.2)
        if content:
            content_score = _score_content_match(content, config["keywords"])
            if content_score > 0:
                domain_score += content_score * 0.2
                domain_evidence.append(f"content contains domain keywords ({content_score:.0%})")

        if domain_score > 0:
            scores[domain] = min(domain_score, 1.0)
            evidence[domain] = domain_evidence

    if not scores:
        return {
            "detected_domains": [],
            "primary_domain": "general",
            "confidence": 0.0,
            "detection_method": "none",
            "evidence": [],
        }

    # Sort by score descending
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary = ranked[0]

    detected = [d for d, s in ranked if s >= confidence_threshold]
    if not detected and primary[1] > 0:
        detected = [primary[0]]  # Always include primary even below threshold

    return {
        "detected_domains": detected,
        "primary_domain": primary[0],
        "confidence": round(primary[1], 4),
        "detection_method": "path_glob" + ("+content" if content else ""),
        "evidence": evidence.get(primary[0], []),
    }


def get_domain_rules_file(domain: str) -> str:
    """Return the .claude/rules/{domain}.md file name for a detected domain."""
    config = DOMAIN_SCOPES.get(domain, {})
    rules_domain = config.get("rules_domain", domain)
    return rules_domain


# ── Scoring helpers ─────────────────────────────────────────────


def _score_path_match(target_path: str, globs: list[str]) -> float:
    """Score how well target_path matches domain globs (0.0-1.0)."""
    matches = 0
    for pattern in globs:
        if fnmatch.fnmatch(target_path, pattern):
            matches += 1
        # Also check basename
        basename = target_path.rsplit("/", 1)[-1] if "/" in target_path else target_path
        if fnmatch.fnmatch(basename, pattern):
            matches += 1

    if matches == 0:
        return 0.0
    # Normalize: 1 match = 0.6, 2+ = 0.8, 3+ = 1.0
    return min(0.4 + matches * 0.2, 1.0)


def _score_content_match(content: str, keywords: list[str]) -> float:
    """Score how many domain keywords appear in content (0.0-1.0)."""
    if not content:
        return 0.0
    content_lower = content.lower()
    matches = sum(1 for kw in keywords if kw.lower() in content_lower)
    if matches == 0:
        return 0.0
    return min(matches / max(len(keywords), 1), 1.0)


def _best_matching_glob(target_path: str, globs: list[str]) -> str:
    """Return the first matching glob pattern for evidence reporting."""
    for pattern in globs:
        if fnmatch.fnmatch(target_path, pattern):
            return pattern
        basename = target_path.rsplit("/", 1)[-1] if "/" in target_path else target_path
        if fnmatch.fnmatch(basename, pattern):
            return pattern
    return "?"
