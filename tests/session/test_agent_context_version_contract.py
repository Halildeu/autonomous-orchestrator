"""Contract tests for agent_context_version module."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.session.agent_context_version import (
    compute_agent_context_version,
    load_agent_context_version,
    verify_agent_context_version,
    write_agent_context_version,
)


def _setup_workspace(tmp: Path) -> Path:
    """Create a minimal workspace with some bootstrap files."""
    ws = tmp / "ws"
    ws.mkdir()
    (ws / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    docs = ws / "docs" / "OPERATIONS"
    docs.mkdir(parents=True)
    (docs / "CODEX-UX.md").write_text("# CODEX-UX\n", encoding="utf-8")
    layer = ws / "docs"
    (layer / "LAYER-MODEL-LOCK.v1.md").write_text("# LAYER\n", encoding="utf-8")
    rm = ws / "roadmaps" / "SSOT"
    rm.mkdir(parents=True)
    (rm / "roadmap.v1.json").write_text("{}", encoding="utf-8")
    return ws


def test_compute_returns_valid_record() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = _setup_workspace(Path(tmp))
        record = compute_agent_context_version(workspace_root=ws)

        assert record["version"] == "v1"
        assert record["status"] == "CURRENT"
        assert len(record["aggregate_sha256"]) == 64
        assert isinstance(record["files"], list)
        assert len(record["files"]) > 0

        for f in record["files"]:
            assert "path" in f
            assert "sha256" in f
            assert "exists" in f


def test_compute_with_agent_tag() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = _setup_workspace(Path(tmp))
        record = compute_agent_context_version(workspace_root=ws, agent_tag="codex")
        assert record["agent_tag"] == "codex"


def test_missing_file_tracked_as_not_exists() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        ws.mkdir()
        record = compute_agent_context_version(workspace_root=ws)
        for f in record["files"]:
            assert f["exists"] is False
            assert f["sha256"] == ""


def test_verify_detects_stale_context() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = _setup_workspace(Path(tmp))

        v1 = compute_agent_context_version(workspace_root=ws)
        write_agent_context_version(workspace_root=ws, record=v1)

        # Mutate a tracked file
        (ws / "AGENTS.md").write_text("# CHANGED\n", encoding="utf-8")

        v2 = verify_agent_context_version(workspace_root=ws, previous=v1)
        assert v2["status"] == "STALE_CONTEXT"
        assert "AGENTS.md" in v2["stale_files"]


def test_verify_returns_current_when_unchanged() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = _setup_workspace(Path(tmp))

        v1 = compute_agent_context_version(workspace_root=ws)
        write_agent_context_version(workspace_root=ws, record=v1)

        v2 = verify_agent_context_version(workspace_root=ws, previous=v1)
        assert v2["status"] == "CURRENT"
        assert v2["stale_files"] == []


def test_aggregate_sha256_changes_on_file_change() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = _setup_workspace(Path(tmp))

        v1 = compute_agent_context_version(workspace_root=ws)
        (ws / "AGENTS.md").write_text("# CHANGED\n", encoding="utf-8")
        v2 = compute_agent_context_version(workspace_root=ws)

        assert v1["aggregate_sha256"] != v2["aggregate_sha256"]


def test_write_and_load_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = _setup_workspace(Path(tmp))
        record = compute_agent_context_version(workspace_root=ws, agent_tag="claude")
        write_agent_context_version(workspace_root=ws, record=record)

        loaded = load_agent_context_version(workspace_root=ws)
        assert loaded is not None
        assert loaded["aggregate_sha256"] == record["aggregate_sha256"]
        assert loaded["agent_tag"] == "claude"


def test_load_returns_none_when_missing() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        ws.mkdir()
        assert load_agent_context_version(workspace_root=ws) is None


def test_schema_validation() -> None:
    """Validate output against the JSON Schema."""
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "agent-context-version.schema.v1.json"
    if not schema_path.exists():
        return
    from jsonschema import Draft202012Validator

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    with tempfile.TemporaryDirectory() as tmp:
        ws = _setup_workspace(Path(tmp))
        record = compute_agent_context_version(workspace_root=ws, agent_tag="codex")
        errors = list(validator.iter_errors(record))
        assert errors == [], f"Schema errors: {[e.message for e in errors]}"
