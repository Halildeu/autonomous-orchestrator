"""Contract tests for semantic drift validation."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.ops.drift_semantic_validator import (
    build_semantic_drift_report,
    detect_breaking_field_changes,
    validate_file_against_schema,
)


def _write(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def test_valid_file_against_schema() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        schemas = root / "schemas"
        schemas.mkdir()
        _write(schemas / "policy-test.schema.json", {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["version"],
            "properties": {"version": {"const": "v1"}},
        })
        policies = root / "policies"
        policies.mkdir()
        _write(policies / "policy_test.v1.json", {"version": "v1"})

        result = validate_file_against_schema(
            file_path=policies / "policy_test.v1.json",
            schemas_dir=schemas,
        )
        assert result["valid"] is True
        assert result["errors"] == []


def test_invalid_file_against_schema() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        schemas = root / "schemas"
        schemas.mkdir()
        _write(schemas / "policy-test.schema.json", {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["version"],
            "properties": {"version": {"const": "v1"}},
        })
        policies = root / "policies"
        policies.mkdir()
        _write(policies / "policy_test.v1.json", {"version": "v2"})

        result = validate_file_against_schema(
            file_path=policies / "policy_test.v1.json",
            schemas_dir=schemas,
        )
        assert result["valid"] is False
        assert len(result["errors"]) > 0


def test_no_schema_returns_valid() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        schemas = root / "schemas"
        schemas.mkdir()
        data = root / "data.json"
        _write(data, {"foo": "bar"})

        result = validate_file_against_schema(file_path=data, schemas_dir=schemas)
        assert result["valid"] is True
        assert result["schema_path"] is None


def test_detect_field_removed() -> None:
    prev = {"version": "v1", "mode": "strict", "level": 3}
    cur = {"version": "v1", "level": 3}
    breaks = detect_breaking_field_changes(current=cur, previous=prev)
    assert any(b["type"] == "FIELD_REMOVED" and "mode" in b["path"] for b in breaks)


def test_detect_type_changed() -> None:
    prev = {"version": "v1", "count": 5}
    cur = {"version": "v1", "count": "five"}
    breaks = detect_breaking_field_changes(current=cur, previous=prev)
    assert any(b["type"] == "TYPE_CHANGED" and "count" in b["path"] for b in breaks)


def test_no_breaking_changes() -> None:
    prev = {"version": "v1", "mode": "strict"}
    cur = {"version": "v1", "mode": "relaxed"}
    breaks = detect_breaking_field_changes(current=cur, previous=prev)
    assert breaks == []


def test_build_semantic_drift_report() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        ws = Path(tmp) / "ws"
        schemas = repo / "schemas"
        schemas.mkdir(parents=True)
        _write(schemas / "policy-test.schema.json", {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["version"],
            "properties": {"version": {"const": "v1"}},
        })
        policies = repo / "policies"
        policies.mkdir()
        _write(policies / "policy_test.v1.json", {"version": "v2"})  # invalid

        report = build_semantic_drift_report(
            repo_root=repo,
            workspace_root=ws,
            changed_files=["policies/policy_test.v1.json"],
            session_id="sess-001",
        )
        assert len(report["semantic_violations"]) > 0
        assert report["provenance"]["session_id"] == "sess-001"


def test_non_json_files_skipped() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        ws = Path(tmp) / "ws"
        repo.mkdir()
        (repo / "README.md").write_text("# test\n", encoding="utf-8")

        report = build_semantic_drift_report(
            repo_root=repo,
            workspace_root=ws,
            changed_files=["README.md"],
        )
        assert report["semantic_violations"] == []


def test_breaking_change_via_baseline() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        ws = Path(tmp) / "ws"
        (repo / "schemas").mkdir(parents=True)
        policies = repo / "policies"
        policies.mkdir()
        _write(policies / "policy_test.v1.json", {"version": "v1", "count": "five"})

        # Baseline had integer count
        baseline = ws / ".cache" / "drift_baseline" / "policies"
        baseline.mkdir(parents=True)
        _write(baseline / "policy_test.v1.json", {"version": "v1", "count": 5})

        report = build_semantic_drift_report(
            repo_root=repo,
            workspace_root=ws,
            changed_files=["policies/policy_test.v1.json"],
        )
        type_changes = [v for v in report["semantic_violations"] if v.get("violation_type") == "TYPE_CHANGED"]
        assert len(type_changes) > 0
