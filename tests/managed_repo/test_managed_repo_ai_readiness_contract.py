"""Contract tests for managed repo AI-readiness gaps (GAP-1 through GAP-5)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# GAP-4: AGENTS.md template exists and is valid
# ---------------------------------------------------------------------------

def test_agents_template_exists() -> None:
    template = Path(__file__).resolve().parents[2] / "templates" / "AGENTS.managed.md"
    assert template.exists(), f"Template missing: {template}"
    content = template.read_text(encoding="utf-8")
    assert "# AGENTS.md" in content
    assert "Customer-friendly mode" in content
    assert "Context Bootstrap" in content
    assert "Multi-Agent" in content


def test_agents_template_has_sync_metadata() -> None:
    template = Path(__file__).resolve().parents[2] / "templates" / "AGENTS.managed.md"
    content = template.read_text(encoding="utf-8")
    assert "Sync Metadata" in content
    assert "standards.lock" in content


# ---------------------------------------------------------------------------
# GAP-1: AGENTS.md generator works
# ---------------------------------------------------------------------------

def test_generate_agents_md_dry_run() -> None:
    import sys
    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root / "scripts"))
    from generate_managed_repo_agents_md import generate_agents_md

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp)
        result = generate_agents_md(
            source_root=repo_root,
            target_root=target,
            repo_slug="test-repo",
            apply=False,
        )
        assert result["status"] == "OK"
        assert result["action"] == "would_create"
        # File should NOT be created in dry-run
        assert not (target / "AGENTS.md").exists()


def test_generate_agents_md_apply() -> None:
    import sys
    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root / "scripts"))
    from generate_managed_repo_agents_md import generate_agents_md

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp)
        result = generate_agents_md(
            source_root=repo_root,
            target_root=target,
            repo_slug="test-repo",
            apply=True,
        )
        assert result["status"] == "OK"
        assert result["action"] == "created"
        agents_md = target / "AGENTS.md"
        assert agents_md.exists()
        content = agents_md.read_text(encoding="utf-8")
        assert "# AGENTS.md" in content


def test_generate_agents_md_skip_existing() -> None:
    import sys
    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root / "scripts"))
    from generate_managed_repo_agents_md import generate_agents_md

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp)
        (target / "AGENTS.md").write_text("# Existing", encoding="utf-8")
        result = generate_agents_md(
            source_root=repo_root,
            target_root=target,
            apply=False,
        )
        assert result["status"] == "OK"
        assert result["action"] == "skip_exists"


# ---------------------------------------------------------------------------
# GAP-2: .codex config in standards.lock
# ---------------------------------------------------------------------------

def test_codex_config_in_standards_lock() -> None:
    lock_path = Path(__file__).resolve().parents[2] / "standards.lock"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    required = lock.get("required_files", [])
    assert ".codex/config.toml" in required
    assert ".codex/README.md" in required

    sync = lock.get("managed_repo_sync", {})
    codex_sync = sync.get("codex_config_sync", [])
    assert ".codex/config.toml" in codex_sync


def test_codex_config_exists() -> None:
    config = Path(__file__).resolve().parents[2] / ".codex" / "config.toml"
    assert config.exists(), f"Missing: {config}"
    content = config.read_text(encoding="utf-8")
    assert "sandbox_mode" in content


# ---------------------------------------------------------------------------
# GAP-3: Context bootstrap init works
# ---------------------------------------------------------------------------

def test_bootstrap_init_dry_run() -> None:
    import sys
    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root / "scripts"))
    from init_managed_repo_context_bootstrap import init_bootstrap

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp)
        result = init_bootstrap(target_root=target, apply=False)
        assert result["mode"] == "dry-run"
        actions = result["actions"]
        assert any(a["action"] == "would_create" for a in actions)


def test_bootstrap_init_apply_creates_structure() -> None:
    import sys
    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root / "scripts"))
    from init_managed_repo_context_bootstrap import init_bootstrap

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp)
        result = init_bootstrap(target_root=target, apply=True)
        assert result["mode"] == "apply"

        # Tier 1: workspace cache should exist
        reports = target / ".cache" / "ws_customer_default" / ".cache" / "reports"
        assert reports.exists()

        # Tier 1: Seed files should exist
        assert (reports / "system_status.v1.json").exists()
        assert (reports / "portfolio_status.v1.json").exists()

        # Verify seed content
        status = json.loads((reports / "system_status.v1.json").read_text(encoding="utf-8"))
        assert status["status"] == "BOOTSTRAP"
        assert status["version"] == "v1"

        # Tier 3: governance dir should exist
        assert (target / "docs" / "OPERATIONS").exists()

        # Report should exist
        report = target / ".cache" / "reports" / "context_bootstrap_init.v1.json"
        assert report.exists()


def test_bootstrap_seed_idempotent() -> None:
    import sys
    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root / "scripts"))
    from init_managed_repo_context_bootstrap import init_bootstrap

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp)
        # First run
        init_bootstrap(target_root=target, apply=True)
        # Second run should not overwrite
        result = init_bootstrap(target_root=target, apply=True)
        tier1_actions = [a for a in result["actions"] if a.get("tier") == 1]
        # All tier 1 items should report "exists"
        assert all(a["action"] == "exists" for a in tier1_actions)


# ---------------------------------------------------------------------------
# GAP-5: Search adapter in standards.lock
# ---------------------------------------------------------------------------

def test_search_adapter_in_standards_lock() -> None:
    lock_path = Path(__file__).resolve().parents[2] / "standards.lock"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    required = lock.get("required_files", [])
    assert "extensions/PRJ-SEARCH/search_adapter.py" in required
    assert "extensions/PRJ-SEARCH/search_adapter_core.py" in required

    sync = lock.get("managed_repo_sync", {})
    search_sync = sync.get("search_adapter_sync", [])
    assert "extensions/PRJ-SEARCH/search_adapter.py" in search_sync
    assert len(search_sync) >= 5  # At least 5 adapter files


def test_search_adapter_files_exist() -> None:
    ext_dir = Path(__file__).resolve().parents[2] / "extensions" / "PRJ-SEARCH"
    assert (ext_dir / "search_adapter.py").exists()
    assert (ext_dir / "search_adapter_core.py").exists()
    assert (ext_dir / "search_adapter_query.py").exists()
    assert (ext_dir / "search_adapter_index.py").exists()
    assert (ext_dir / "extension.manifest.v1.json").exists()


# ---------------------------------------------------------------------------
# Integration: standards.lock coherence
# ---------------------------------------------------------------------------

def test_standards_lock_managed_repo_sync_complete() -> None:
    lock_path = Path(__file__).resolve().parents[2] / "standards.lock"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    sync = lock.get("managed_repo_sync", {})

    # All new sync config keys should be present
    assert "agents_md_generator" in sync
    assert "agents_md_template" in sync
    assert "bootstrap_init_script" in sync
    assert "codex_config_sync" in sync
    assert "search_adapter_sync" in sync


def test_standards_lock_all_sync_files_exist() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    lock_path = repo_root / "standards.lock"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    sync = lock.get("managed_repo_sync", {})

    # Check generator script exists
    assert (repo_root / sync["agents_md_generator"]).exists()
    assert (repo_root / sync["agents_md_template"]).exists()
    assert (repo_root / sync["bootstrap_init_script"]).exists()

    # Check all codex config sync files exist
    for rel in sync.get("codex_config_sync", []):
        assert (repo_root / rel).exists(), f"Missing: {rel}"

    # Check all search adapter sync files exist
    for rel in sync.get("search_adapter_sync", []):
        assert (repo_root / rel).exists(), f"Missing: {rel}"
