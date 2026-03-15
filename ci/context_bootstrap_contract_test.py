"""Contract tests for context bootstrap enforcement gate."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ci.check_context_bootstrap import run_bootstrap_check


def _setup_full_repo(root: Path) -> None:
    """Create all tier files."""
    # Tier 1
    cache = root / ".cache" / "ws_customer_default" / ".cache" / "reports"
    cache.mkdir(parents=True)
    (cache / "system_status.v1.json").write_text("{}", encoding="utf-8")
    (cache / "portfolio_status.v1.json").write_text("{}", encoding="utf-8")
    rm_cache = root / ".cache" / "ws_customer_default" / ".cache"
    (rm_cache / "roadmap_state.v1.json").write_text("{}", encoding="utf-8")
    # Tier 2
    (root / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    docs = root / "docs" / "OPERATIONS"
    docs.mkdir(parents=True)
    (docs / "CODEX-UX.md").write_text("# CODEX\n", encoding="utf-8")
    (root / "docs" / "LAYER-MODEL-LOCK.v1.md").write_text("# LAYER\n", encoding="utf-8")
    # Tier 3
    rm = root / "roadmaps" / "SSOT"
    rm.mkdir(parents=True)
    (rm / "roadmap.v1.json").write_text("{}", encoding="utf-8")


def test_all_present_returns_ok() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _setup_full_repo(root)

        result = run_bootstrap_check(repo_root=root, workspace_root=root)
        assert result["status"] == "OK"
        assert result["issues"] == [] or all("STALE" not in i and "MISSING" not in i for i in result["issues"])


def test_missing_tier1_returns_fail() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _setup_full_repo(root)
        # Remove tier 1 file
        (root / ".cache" / "ws_customer_default" / ".cache" / "reports" / "system_status.v1.json").unlink()

        result = run_bootstrap_check(repo_root=root, workspace_root=root)
        assert any("MISSING" in i for i in result["issues"])


def test_missing_tier2_returns_fail() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _setup_full_repo(root)
        (root / "AGENTS.md").unlink()

        result = run_bootstrap_check(repo_root=root, workspace_root=root)
        assert result["status"] == "FAIL"


def test_missing_tier3_returns_warn_not_fail() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _setup_full_repo(root)
        (root / "roadmaps" / "SSOT" / "roadmap.v1.json").unlink()

        result = run_bootstrap_check(repo_root=root, workspace_root=root)
        tier3 = [t for t in result["tiers"] if t["tier"] == 3][0]
        assert tier3["status"] == "WARN"


def test_schema_validation() -> None:
    """Validate output against the JSON Schema."""
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "context-bootstrap-report.schema.v1.json"
    if not schema_path.exists():
        return
    from jsonschema import Draft202012Validator

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _setup_full_repo(root)
        result = run_bootstrap_check(repo_root=root, workspace_root=root)
        errors = list(validator.iter_errors(result))
        assert errors == [], f"Schema errors: {[e.message for e in errors]}"
