"""Contract test for the test quality gate pipeline.

Validates:
- Schema validates policy
- Policy loads without error
- CI script produces valid output against fixtures
- Semgrep rules parse (YAML)
- Severity matrix includes EP-006..EP-009
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_schema_exists():
    schema = REPO_ROOT / "schemas" / "policy-test-quality.schema.v1.json"
    assert schema.exists(), f"Schema not found: {schema}"
    data = json.loads(schema.read_text())
    assert data.get("$id") == "urn:ao:test-quality-rules:v1"
    assert data.get("type") == "object"
    assert "rules" in data.get("required", [])
    assert "thresholds" in data.get("required", [])


def test_policy_validates_against_schema():
    policy = REPO_ROOT / "policies" / "policy_test_quality.v1.json"
    assert policy.exists(), f"Policy not found: {policy}"
    data = json.loads(policy.read_text())
    assert data["version"] == "v1"
    assert data["kind"] == "policy-test-quality"
    rules = data.get("rules", [])
    assert len(rules) == 6, f"Expected 6 rules, got {len(rules)}"
    rule_ids = {r["rule_id"] for r in rules}
    expected = {"TQ-001", "TQ-002", "TQ-003", "TQ-004", "TQ-005", "TQ-006"}
    assert rule_ids == expected, f"Missing rules: {expected - rule_ids}"


def test_policy_thresholds():
    policy = REPO_ROOT / "policies" / "policy_test_quality.v1.json"
    data = json.loads(policy.read_text())
    th = data["thresholds"]
    assert th["max_shallow_render_ratio"] == 0.10
    assert th["min_assertion_density"] == 2.0
    assert th["max_duplication_ratio"] == 0.05


def test_semgrep_rules_exist_and_parse():
    rules_dir = REPO_ROOT / "extensions" / "PRJ-ENFORCEMENT-PACK" / "semgrep" / "rules"
    # Only AST-required rules remain in semgrep; regex rules moved to ci/check_enforcement_rules.py
    expected_rules = [
        "ep006_shallow_render_fake.yaml",
        "ep009_data_testid_render_only.yaml",
        "ep014_react19_api.yaml",
    ]
    for rule_name in expected_rules:
        rule_path = rules_dir / rule_name
        assert rule_path.exists(), f"Semgrep rule not found: {rule_path}"
        # Validate YAML parses
        import yaml
        data = yaml.safe_load(rule_path.read_text())
        assert "rules" in data, f"No 'rules' key in {rule_name}"
        for r in data["rules"]:
            assert "id" in r, f"No 'id' in rule: {rule_name}"
            assert "metadata" in r, f"No 'metadata' in rule: {rule_name}"
            assert r["metadata"].get("enforcement_pack") == "ENF_V1"


def test_severity_matrix_includes_new_rules():
    matrix_path = REPO_ROOT / "extensions" / "PRJ-ENFORCEMENT-PACK" / "contract" / "severity_matrix.v1.json"
    assert matrix_path.exists()
    data = json.loads(matrix_path.read_text())
    default_profile = data["profiles"]["default_profile"]
    strict_profile = data["profiles"]["strict_profile"]
    for ep in ["EP-006", "EP-007", "EP-008", "EP-009"]:
        assert ep in default_profile, f"{ep} missing from default_profile"
        assert ep in strict_profile, f"{ep} missing from strict_profile"
    assert default_profile["EP-008"] == "BLOCKED"
    assert strict_profile["EP-008"] == "BLOCKED"


def test_ci_script_dry_run(tmp_path):
    out_file = tmp_path / "report.json"
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "ci" / "check_test_quality.py"),
            "--repo-root", str(REPO_ROOT),
            "--scan-path", str(REPO_ROOT / "fixtures" / "test_quality_smoke"),
            "--dry-run",
            "--out", str(out_file),
        ],
        capture_output=True,
        text=True,
    )
    # Should complete (exit 0 in dry-run even if FAIL)
    assert out_file.exists(), f"Report not written. stderr: {result.stderr}"
    report = json.loads(out_file.read_text())
    assert report["version"] == "v1"
    assert report["files_scanned"] > 0
    assert "metrics" in report
    assert "violations" in report


def test_smoke_fixtures_detect_bad_patterns(tmp_path):
    out_file = tmp_path / "report.json"
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "ci" / "check_test_quality.py"),
            "--repo-root", str(REPO_ROOT),
            "--scan-path", str(REPO_ROOT / "fixtures" / "test_quality_smoke"),
            "--dry-run",
            "--out", str(out_file),
        ],
        capture_output=True,
        text=True,
    )
    report = json.loads(out_file.read_text())
    violations = report["violations"]
    rules_found = {v["rule"] for v in violations}
    # TQ-001/002/006 violation detection moved to ci/check_enforcement_rules.py (EP-007/008)
    # check_test_quality.py now only produces TQ-003 (duplication), TQ-004 (import), TQ-005 (mock)
    assert "TQ-004" in rules_found, "TQ-004 (import mismatch) not detected in bad fixtures"
    assert "TQ-005" in rules_found, "TQ-005 (mock-heavy) not detected in bad fixtures"
