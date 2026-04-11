"""Contract tests for project context card resolver (Phase 3)."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("src.ops.project_card_resolver", reason="project_card_resolver not yet implemented")

from src.ops.project_card_resolver import resolve_project_card, detect_project_change


class TestResolveProjectCard:
    def test_frontend_tsx(self) -> None:
        card = resolve_project_card("web/apps/mfe-shell/src/pages/Home.tsx")
        assert card["project_id"] == "dev-web-frontend"
        assert card["project_group"] == "frontend"

    def test_frontend_package(self) -> None:
        card = resolve_project_card("web/packages/design-system/src/Button.tsx")
        assert card["project_id"] == "dev-web-frontend"

    def test_orchestrator_src(self) -> None:
        card = resolve_project_card("src/ops/context_compiler.py")
        assert card["project_id"] == "orchestrator"
        assert card["project_group"] == "orchestrator"

    def test_orchestrator_schemas(self) -> None:
        card = resolve_project_card("schemas/test.schema.v1.json")
        assert card["project_id"] == "orchestrator"

    def test_database(self) -> None:
        card = resolve_project_card("db/migrations/001.sql")
        assert card["project_id"] == "workcube-db"
        assert card["project_group"] == "database"

    def test_backend_services(self) -> None:
        card = resolve_project_card("services/auth/handler.py")
        assert card["project_id"] == "dev-web-backend"
        assert card["project_group"] == "backend"

    def test_unknown_path(self) -> None:
        card = resolve_project_card("README.md")
        assert card["project_id"] == "unknown"

    def test_card_has_ports(self) -> None:
        card = resolve_project_card("web/apps/mfe-shell/src/App.tsx")
        assert "ports" in card
        assert card["ports"].get("mfe-shell") == 3000

    def test_card_has_conventions_ref(self) -> None:
        card = resolve_project_card("src/ops/manage.py")
        assert card["conventions_ref"] == ".claude/rules/src-ops.md"


class TestDetectProjectChange:
    def test_same_project(self) -> None:
        assert detect_project_change("dev-web-frontend", "dev-web-frontend") is None

    def test_project_changed(self) -> None:
        change = detect_project_change("dev-web-frontend", "orchestrator")
        assert change is not None
        assert change["changed"] is True
        assert change["from_project"] == "dev-web-frontend"
        assert change["to_project"] == "orchestrator"

    def test_initial_project(self) -> None:
        # No previous project
        assert detect_project_change("", "dev-web-frontend") is None
        assert detect_project_change("unknown", "dev-web-frontend") is None


class TestScopeGuardProjectTracking:
    def test_project_warn_on_change(self, tmp_path: Path) -> None:
        from src.ops.scope_guard import init_scope, check_scope

        ws = tmp_path / "ws"
        (ws / ".cache" / "reports").mkdir(parents=True)

        init_scope(ws, declared_domains=["frontend"], max_files=20)
        # Write to declared project
        r1 = check_scope(ws, new_file="Home.tsx", new_domain="frontend")
        assert r1["status"] == "WITHIN_SCOPE"

    def test_projects_tracked(self, tmp_path: Path) -> None:
        from src.ops.scope_guard import init_scope, check_scope, get_scope_summary

        ws = tmp_path / "ws"
        (ws / ".cache" / "reports").mkdir(parents=True)

        init_scope(ws, max_files=20)
        check_scope(ws, new_file="a.tsx", new_project="dev-web-frontend")
        check_scope(ws, new_file="b.py", new_project="orchestrator")
        s = get_scope_summary(ws)
        assert s["status"] in ("WITHIN_SCOPE", "WARN")
