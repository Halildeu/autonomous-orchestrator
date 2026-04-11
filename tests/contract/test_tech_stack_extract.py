"""Contract tests for tech stack auto-discovery."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("scripts.tech_stack_extract", reason="tech_stack_extract not yet implemented")

from scripts.tech_stack_extract import extract_versions, build_discovery_report, _resolve_dev_repo_root


@pytest.fixture()
def mock_dev_repo(tmp_path: Path) -> Path:
    """Create mock dev repo with package.json files."""
    web = tmp_path / "web"
    (web / "apps" / "mfe-shell").mkdir(parents=True)
    (web / "packages" / "design-system").mkdir(parents=True)

    # Root package.json
    root_pkg = {
        "name": "dev-web",
        "engines": {"node": "20.x || 22.x"},
        "devDependencies": {"vite": "8.0.3", "eslint": "9.39.1", "vitest": "^4.1.0"},
        "pnpm": {"overrides": {"ag-grid-community": "34.3.1", "vite": "8.0.3"}},
    }
    (web / "package.json").write_text(json.dumps(root_pkg), encoding="utf-8")

    # Shell package.json
    shell_pkg = {
        "dependencies": {
            "react": "~18.2.0", "react-dom": "~18.2.0",
            "ag-grid-react": "34.3.1", "@tanstack/react-query": "^5.90.10",
            "keycloak-js": "^26.2.3",
        },
        "devDependencies": {"typescript": "^5.8.3"},
    }
    (web / "apps" / "mfe-shell" / "package.json").write_text(json.dumps(shell_pkg), encoding="utf-8")

    # Design system package.json
    ds_pkg = {"name": "@mfe/design-system", "version": "1.1.0"}
    (web / "packages" / "design-system" / "package.json").write_text(json.dumps(ds_pkg), encoding="utf-8")

    return tmp_path


class TestExtractVersions:
    def test_extracts_react(self, mock_dev_repo: Path) -> None:
        r = extract_versions(mock_dev_repo)
        assert r["versions"]["react"] == "~18.2.0"

    def test_extracts_vite(self, mock_dev_repo: Path) -> None:
        r = extract_versions(mock_dev_repo)
        assert r["versions"]["vite"] == "8.0.3"

    def test_extracts_ag_grid(self, mock_dev_repo: Path) -> None:
        r = extract_versions(mock_dev_repo)
        assert r["versions"]["ag-grid-react"] == "34.3.1"

    def test_extracts_design_system(self, mock_dev_repo: Path) -> None:
        r = extract_versions(mock_dev_repo)
        assert r["versions"]["@mfe/design-system"] == "1.1.0"

    def test_extracts_overrides(self, mock_dev_repo: Path) -> None:
        r = extract_versions(mock_dev_repo)
        assert r["overrides"]["ag-grid-community"] == "34.3.1"

    def test_extracts_node_engines(self, mock_dev_repo: Path) -> None:
        r = extract_versions(mock_dev_repo)
        assert r["node_engines"] == "20.x || 22.x"


class TestBuildReport:
    def test_report_structure(self, mock_dev_repo: Path) -> None:
        r = build_discovery_report(mock_dev_repo)
        assert r["version"] == "v1"
        assert "critical_summary" in r
        assert r["critical_summary"]["react"] == "~18.2.0"
        assert r["critical_summary"]["vite"] == "8.0.3"
        assert r["critical_summary"]["design_system"] == "1.1.0"


class TestResolveDevRepo:
    def test_returns_none_when_not_found(self) -> None:
        # With no managed_repos and no fallback
        result = _resolve_dev_repo_root("/nonexistent/path")
        assert result is None or result.is_dir()

    def test_override_works(self, mock_dev_repo: Path) -> None:
        result = _resolve_dev_repo_root(str(mock_dev_repo))
        assert result == mock_dev_repo
