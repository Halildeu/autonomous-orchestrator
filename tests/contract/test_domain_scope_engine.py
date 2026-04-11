"""Contract tests for domain scope engine (Phase 2).

Validates:
  - 6 domains detected by path matching
  - Confidence scoring
  - Content-based detection
  - Fallback to general when no match
  - Domain rules files exist
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("src.ops.domain_scope_engine", reason="domain_scope_engine not yet implemented")

from src.ops.domain_scope_engine import detect_domain_scope, get_domain_rules_file, DOMAIN_SCOPES


# ── Path-based detection ────────────────────────────────────────


class TestFrontendDetection:
    def test_tsx_file(self) -> None:
        r = detect_domain_scope("web/apps/mfe-shell/src/pages/Home.tsx")
        assert r["primary_domain"] == "frontend"
        assert r["confidence"] >= 0.7

    def test_jsx_file(self) -> None:
        r = detect_domain_scope("apps/dashboard/Button.jsx")
        assert r["primary_domain"] == "frontend"

    def test_vite_config(self) -> None:
        r = detect_domain_scope("vite.config.ts")
        assert r["primary_domain"] == "frontend"

    def test_css_file(self) -> None:
        r = detect_domain_scope("web/styles/main.css")
        assert r["primary_domain"] == "frontend"


class TestBackendDetection:
    def test_python_service(self) -> None:
        r = detect_domain_scope("services/auth/handler.py")
        assert r["primary_domain"] == "backend"

    def test_src_python(self) -> None:
        r = detect_domain_scope("src/ops/context_compiler.py")
        # src/ maps to backend via globs
        assert r["primary_domain"] == "backend"


class TestDatabaseDetection:
    def test_sql_file(self) -> None:
        r = detect_domain_scope("db/migrations/001_create_users.sql")
        assert r["primary_domain"] == "database"

    def test_bare_sql(self) -> None:
        r = detect_domain_scope("queries/report.sql")
        assert r["primary_domain"] == "database"


class TestAccountingDetection:
    def test_account_file(self) -> None:
        r = detect_domain_scope("modules/accounting/account_plan.py")
        assert r["primary_domain"] == "accounting"

    def test_budget_file(self) -> None:
        r = detect_domain_scope("reports/budget_summary.sql")
        # Could be database or accounting — both valid
        assert r["primary_domain"] in ("accounting", "database")


class TestApiDetection:
    def test_api_route(self) -> None:
        r = detect_domain_scope("api/v1/users.py")
        assert r["primary_domain"] == "api"

    def test_nested_api(self) -> None:
        r = detect_domain_scope("services/api/endpoints/health.py")
        assert "api" in r["detected_domains"] or r["primary_domain"] in ("api", "backend")


class TestInfraDetection:
    def test_dockerfile(self) -> None:
        r = detect_domain_scope("Dockerfile")
        assert r["primary_domain"] == "infra"

    def test_github_workflow(self) -> None:
        r = detect_domain_scope(".github/workflows/ci.yml")
        assert r["primary_domain"] == "infra"


# ── Content-based detection ─────────────────────────────────────


class TestContentDetection:
    def test_react_import_boosts_frontend(self) -> None:
        r = detect_domain_scope("utils/helper.ts", content="import React from 'react';")
        assert "frontend" in r["detected_domains"]

    def test_sql_keywords_boost_database(self) -> None:
        # Use a neutral path (not matching infra/scripts) to test content detection
        r = detect_domain_scope("tools/run.py", content="SELECT * FROM ACCOUNT_PLAN WHERE id = 1")
        assert "database" in r["detected_domains"] or "accounting" in r["detected_domains"]


# ── Edge cases ──────────────────────────────────────────────────


class TestEdgeCases:
    def test_no_match_returns_general(self) -> None:
        r = detect_domain_scope("README.md")
        assert r["primary_domain"] == "general"
        assert r["confidence"] == 0.0

    def test_confidence_below_threshold(self) -> None:
        r = detect_domain_scope("README.md", confidence_threshold=0.99)
        assert r["confidence"] < 0.99

    def test_all_domains_defined(self) -> None:
        assert len(DOMAIN_SCOPES) == 6
        expected = {"frontend", "backend", "database", "accounting", "api", "infra"}
        assert set(DOMAIN_SCOPES.keys()) == expected


# ── Domain rules file mapping ───────────────────────────────────


class TestDomainRulesFile:
    def test_frontend_rules_file(self) -> None:
        assert get_domain_rules_file("frontend") == "frontend"

    def test_backend_rules_file(self) -> None:
        assert get_domain_rules_file("backend") == "backend"

    def test_unknown_domain_returns_domain(self) -> None:
        assert get_domain_rules_file("unknown") == "unknown"

    def test_domain_rule_files_exist(self) -> None:
        """All domain rule .md files must exist in .claude/rules/."""
        repo_root = Path(__file__).resolve().parents[2]
        for domain, config in DOMAIN_SCOPES.items():
            rules_domain = config["rules_domain"]
            rules_path = repo_root / ".claude" / "rules" / f"{rules_domain}.md"
            assert rules_path.exists(), f"Missing rules file: {rules_path}"


# ── Integration with compile_rules_digest ───────────────────────


class TestDigestIntegration:
    def test_frontend_domain_in_digest(self) -> None:
        from src.ops.compile_rules_digest import _resolve_domain
        assert _resolve_domain("web/apps/mfe-shell/src/Home.tsx") == "frontend"

    def test_database_domain_in_digest(self) -> None:
        from src.ops.compile_rules_digest import _resolve_domain
        assert _resolve_domain("db/migrations/001.sql") == "database"

    def test_existing_domains_preserved(self) -> None:
        from src.ops.compile_rules_digest import _resolve_domain
        assert _resolve_domain("src/ops/manage.py") == "src-ops"
        assert _resolve_domain("schemas/test.schema.v1.json") == "schemas"
        assert _resolve_domain("policies/policy_test.v1.json") == "policies"
        assert _resolve_domain("ci/validate.py") == "ci"
        assert _resolve_domain("AGENTS.md") == "cross-repo"
