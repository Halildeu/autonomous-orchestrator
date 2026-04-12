"""Contract tests for PRJ-ZANZIBAR-OPENFGA extension."""
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]


class TestZanzibarManifest:
    """Validate project manifest integrity."""

    def setup_method(self):
        manifest_path = ROOT / "roadmaps" / "PROJECTS" / "PRJ-ZANZIBAR-OPENFGA" / "project.manifest.v1.json"
        assert manifest_path.exists(), f"Missing: {manifest_path}"
        self.manifest = json.loads(manifest_path.read_text())

    def test_manifest_version(self):
        assert self.manifest["version"] == "v1"

    def test_manifest_project_id(self):
        assert self.manifest["project_id"] == "PRJ-ZANZIBAR-OPENFGA"

    def test_manifest_has_12_success_metrics(self):
        metrics = self.manifest["success_metrics"]
        assert len(metrics) == 12, f"Expected 12 SK, got {len(metrics)}: {metrics}"

    def test_manifest_sk6_references_d002(self):
        """SK-6 must reference D-002 (permission-service deprecation), not D-003."""
        metrics = self.manifest["success_metrics"]
        sk6 = [m for m in metrics if "legacy" in m.lower() or "transformed" in m.lower()]
        for m in sk6:
            assert "d002" in m.lower() or "d_002" in m.lower(), (
                f"SK-6 metric '{m}' should reference D-002, not D-003"
            )

    def test_manifest_milestone_phases(self):
        milestones = self.manifest["target_milestones"]
        required = ["FAZ-0", "FAZ-1", "FAZ-1.5", "FAZ-2", "FAZ-3", "FAZ-3.5", "FAZ-4", "FAZ-5"]
        for faz in required:
            assert faz in milestones, f"Missing milestone: {faz}"


class TestZanzibarDecisions:
    """Validate decision registry integrity."""

    def setup_method(self):
        decisions_path = ROOT / "decisions" / "topics" / "zanzibar-openfga.v1.json"
        assert decisions_path.exists(), f"Missing: {decisions_path}"
        self.decisions = json.loads(decisions_path.read_text())

    def test_has_7_decisions(self):
        assert len(self.decisions["decisions"]) == 7

    def test_all_decisions_final(self):
        for d in self.decisions["decisions"]:
            assert d["status"] == "FINAL", f"{d['decision_id']} is {d['status']}, expected FINAL"

    def test_decision_ids_sequential(self):
        ids = [d["decision_id"] for d in self.decisions["decisions"]]
        expected = [f"D-{i:03d}" for i in range(1, 8)]
        assert ids == expected, f"Expected {expected}, got {ids}"

    def test_d002_is_deprecation(self):
        d002 = [d for d in self.decisions["decisions"] if d["decision_id"] == "D-002"][0]
        assert "kaldır" in d002["statement"].lower() or "deprecat" in d002["statement"].lower()

    def test_d003_is_architecture(self):
        d003 = [d for d in self.decisions["decisions"] if d["decision_id"] == "D-003"][0]
        assert "katman" in d003["statement"].lower() or "layer" in d003["statement"].lower()


class TestZanzibarRoadmap:
    """Validate roadmap.v1.json integrity."""

    def setup_method(self):
        roadmap_path = ROOT / "roadmaps" / "PROJECTS" / "PRJ-ZANZIBAR-OPENFGA" / "roadmap.v1.json"
        assert roadmap_path.exists(), f"Missing: {roadmap_path}"
        self.roadmap = json.loads(roadmap_path.read_text())

    def test_roadmap_id(self):
        assert self.roadmap["roadmap_id"] == "PRJ-ZANZIBAR-OPENFGA"

    def test_has_milestones(self):
        assert len(self.roadmap["milestones"]) >= 8

    def test_done_milestones(self):
        done = [m for m in self.roadmap["milestones"] if m["status"] == "done"]
        assert len(done) >= 6, f"Expected >= 6 done milestones, got {len(done)}"

    def test_milestone_ids_match_manifest(self):
        roadmap_ids = {m["id"] for m in self.roadmap["milestones"]}
        expected = {"FAZ-0", "FAZ-1", "FAZ-1.5", "FAZ-2", "FAZ-3", "FAZ-3.5", "FAZ-4", "FAZ-5"}
        assert expected.issubset(roadmap_ids), f"Missing: {expected - roadmap_ids}"


class TestZanbibarExtension:
    """Validate extension manifest itself."""

    def setup_method(self):
        ext_path = ROOT / "extensions" / "PRJ-ZANZIBAR-OPENFGA" / "extension.manifest.v1.json"
        assert ext_path.exists(), f"Missing: {ext_path}"
        self.ext = json.loads(ext_path.read_text())

    def test_extension_id(self):
        assert self.ext["extension_id"] == "PRJ-ZANZIBAR-OPENFGA"

    def test_enabled(self):
        assert self.ext["enabled"] is True

    def test_ai_context_refs_include_decisions(self):
        refs = self.ext["ai_context_refs"]
        assert any("zanzibar-openfga" in r for r in refs)
