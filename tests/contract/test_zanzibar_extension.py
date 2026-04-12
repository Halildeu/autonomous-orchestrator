"""Contract tests for PRJ-ZANZIBAR-OPENFGA extension."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class TestZanzibarExtensionManifest:
    """Extension manifest structure and references."""

    manifest_path = REPO_ROOT / "extensions" / "PRJ-ZANZIBAR-OPENFGA" / "extension.manifest.v1.json"

    def test_manifest_exists(self):
        assert self.manifest_path.exists(), "Extension manifest missing"

    def test_manifest_valid_json(self):
        manifest = _load_json(self.manifest_path)
        assert isinstance(manifest, dict)

    def test_extension_id(self):
        manifest = _load_json(self.manifest_path)
        assert manifest["extension_id"] == "PRJ-ZANZIBAR-OPENFGA"

    def test_status_active(self):
        manifest = _load_json(self.manifest_path)
        assert manifest["status"] == "active"

    def test_ai_context_refs_exist(self):
        manifest = _load_json(self.manifest_path)
        for ref in manifest.get("ai_context_refs", []):
            ref_path = REPO_ROOT / ref
            assert ref_path.exists(), f"ai_context_ref missing: {ref}"

    def test_context_integration_enabled(self):
        manifest = _load_json(self.manifest_path)
        assert manifest.get("context_integration", {}).get("enabled") is True


class TestZanzibarDecisionTopic:
    """Decision topic integrity."""

    topic_path = REPO_ROOT / "decisions" / "topics" / "zanbibar-openfga.v1.json"
    alt_topic_path = REPO_ROOT / "decisions" / "topics" / "zanzibar-openfga.v1.json"

    def test_decision_topic_exists(self):
        assert self.topic_path.exists() or self.alt_topic_path.exists(), \
            "Decision topic missing"

    def test_decisions_all_final(self):
        path = self.topic_path if self.topic_path.exists() else self.alt_topic_path
        topic = _load_json(path)
        decisions = topic.get("decisions", [])
        assert len(decisions) >= 7, f"Expected 7+ decisions, got {len(decisions)}"
        for d in decisions:
            assert d.get("status") == "FINAL", \
                f"Decision {d.get('id')} not FINAL: {d.get('status')}"


class TestZanzibarProjectManifest:
    """Project manifest in roadmaps/PROJECTS."""

    manifest_path = REPO_ROOT / "roadmaps" / "PROJECTS" / "PRJ-ZANZIBAR-OPENFGA" / "project.manifest.v1.json"

    def test_project_manifest_exists(self):
        assert self.manifest_path.exists(), "Project manifest missing"

    def test_risk_category_high(self):
        manifest = _load_json(self.manifest_path)
        assert manifest.get("risk_category") == "high"

    def test_layer_scope_l3(self):
        manifest = _load_json(self.manifest_path)
        assert manifest.get("layer_scope") == "L3"
