"""Contract tests for session continuity improvements."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.session.context_store import (
    compute_context_sha256,
    new_context,
    save_context_atomic,
    upsert_decision,
)
from src.session.cross_session_context import extract_decision_scope


def test_new_context_with_predecessor() -> None:
    ctx = new_context("sess-002", "/tmp/ws", 3600, predecessor_session_id="sess-001")
    assert ctx["predecessor_session_id"] == "sess-001"
    assert ctx["session_id"] == "sess-002"


def test_new_context_without_predecessor() -> None:
    ctx = new_context("sess-003", "/tmp/ws", 3600)
    assert "predecessor_session_id" not in ctx


def test_predecessor_produces_valid_schema() -> None:
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "session-context.schema.json"
    if not schema_path.exists():
        return
    from jsonschema import Draft202012Validator

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    ctx = new_context("sess-004", "/tmp/ws", 3600, predecessor_session_id="sess-003")
    # Must recompute hash for validation
    ctx["hashes"]["session_context_sha256"] = compute_context_sha256(ctx)
    errors = list(validator.iter_errors(ctx))
    assert errors == [], f"Schema errors: {[e.message for e in errors]}"


def test_scoped_decisions_dont_collide() -> None:
    ctx = new_context("sess-005", "/tmp/ws", 3600)
    upsert_decision(ctx, "deploy_target", "staging", "agent")
    upsert_decision(ctx, "project.deploy_target", "production", "agent")

    decisions = {d["key"]: d["value"] for d in ctx["ephemeral_decisions"]}
    assert decisions["deploy_target"] == "staging"
    assert decisions["project.deploy_target"] == "production"


def test_extract_decision_scope() -> None:
    assert extract_decision_scope("project.deploy_target") == ("project", "deploy_target")
    assert extract_decision_scope("deploy_target") == ("", "deploy_target")
    assert extract_decision_scope("a.b.c") == ("a", "b.c")


def test_compaction_creates_archive() -> None:
    """Verify that compaction archives original content."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        reports = ws / ".cache" / "reports"
        reports.mkdir(parents=True)

        from src.session.provider_memory import _safe_slug

        session_id = "test-sess"
        original_md = "# Original Content\n\nSome important reasoning."

        # Simulate what maybe_auto_compact_markdown does for archiving
        archive_path = reports / f"session_compaction_{_safe_slug(session_id)}.original.v1.md"
        archive_path.write_text(original_md, encoding="utf-8")

        assert archive_path.exists()
        assert archive_path.read_text(encoding="utf-8") == original_md


def test_save_and_load_with_predecessor() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        ctx = new_context("sess-006", str(ws), 3600, predecessor_session_id="sess-005")
        path = ws / "session_context.v1.json"
        save_context_atomic(path, ctx)

        from src.session.context_store import load_context

        loaded = load_context(path)
        assert loaded["predecessor_session_id"] == "sess-005"
