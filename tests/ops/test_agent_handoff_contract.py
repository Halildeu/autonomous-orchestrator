"""Contract tests for agent handoff protocol."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.ops.work_item_claims import (
    acquire_claim,
    get_active_claim,
    list_claims_by_agent,
    load_claims,
    release_claim,
)


def test_acquire_with_agent_tag() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        result = acquire_claim(
            workspace_root=ws,
            work_item_id="TASK-001",
            owner_tag="codex",
            agent_tag="codex",
            ttl_seconds=600,
        )
        assert result["status"] == "ACQUIRED"
        assert result["claim"]["agent_tag"] == "codex"


def test_agent_b_gets_locked() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        acquire_claim(
            workspace_root=ws,
            work_item_id="TASK-001",
            owner_tag="codex",
            agent_tag="codex",
            ttl_seconds=600,
        )
        result = acquire_claim(
            workspace_root=ws,
            work_item_id="TASK-001",
            owner_tag="claude",
            agent_tag="claude",
            ttl_seconds=600,
        )
        assert result["status"] == "LOCKED"


def test_release_then_other_agent_can_claim() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        acquire_claim(
            workspace_root=ws,
            work_item_id="TASK-001",
            owner_tag="codex",
            agent_tag="codex",
            ttl_seconds=600,
        )
        rel = release_claim(workspace_root=ws, work_item_id="TASK-001", agent_tag="codex")
        assert rel["status"] == "RELEASED"

        result = acquire_claim(
            workspace_root=ws,
            work_item_id="TASK-001",
            owner_tag="claude",
            agent_tag="claude",
            ttl_seconds=600,
        )
        assert result["status"] == "ACQUIRED"


def test_release_agent_mismatch() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        acquire_claim(
            workspace_root=ws,
            work_item_id="TASK-001",
            owner_tag="codex",
            agent_tag="codex",
            ttl_seconds=600,
        )
        result = release_claim(workspace_root=ws, work_item_id="TASK-001", agent_tag="claude")
        assert result["status"] == "AGENT_MISMATCH"


def test_list_claims_by_agent() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        acquire_claim(workspace_root=ws, work_item_id="T1", owner_tag="codex", agent_tag="codex", ttl_seconds=600)
        acquire_claim(workspace_root=ws, work_item_id="T2", owner_tag="claude", agent_tag="claude", ttl_seconds=600)
        acquire_claim(workspace_root=ws, work_item_id="T3", owner_tag="codex", agent_tag="codex", ttl_seconds=600)

        codex_claims = list_claims_by_agent(ws, "codex")
        assert len(codex_claims) == 2
        claude_claims = list_claims_by_agent(ws, "claude")
        assert len(claude_claims) == 1


def test_force_release_ignores_agent_tag() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        acquire_claim(workspace_root=ws, work_item_id="TASK-001", owner_tag="codex", agent_tag="codex", ttl_seconds=600)
        result = release_claim(workspace_root=ws, work_item_id="TASK-001", agent_tag="claude", force=True)
        assert result["status"] == "RELEASED_FORCED"


def test_schema_validation() -> None:
    """Validate agent-handoff-status schema is well-formed."""
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "agent-handoff-status.schema.v1.json"
    if not schema_path.exists():
        return
    from jsonschema import Draft202012Validator

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
