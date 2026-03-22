"""Contract test for AI Output Quality Gates."""
from __future__ import annotations
import json, sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from src.orchestrator.quality_gate import run_quality_gates, quality_gate_summary

def _assert(cond, msg):
    if not cond: print(f"FAIL {msg}"); raise SystemExit(2)

def test_valid_output_passes():
    output = {"text": "This is a valid summary with enough content.", "status": "OK"}
    results = run_quality_gates(output=output, policy={"enabled": True, "gates": {
        "schema_valid": {"enabled": True, "on_fail": "retry"},
        "output_not_empty": {"enabled": True, "on_fail": "reject", "min_output_chars": 10},
    }})
    _assert(all(r.passed for r in results), "all gates should pass")
    print("OK test_valid_output_passes")

def test_empty_output_rejected():
    output = {"text": "", "status": "OK"}
    results = run_quality_gates(output=output, policy={"enabled": True, "gates": {
        "output_not_empty": {"enabled": True, "on_fail": "reject", "min_output_chars": 10},
    }})
    failed = [r for r in results if not r.passed]
    _assert(len(failed) == 1, f"expected 1 failure, got {len(failed)}")
    _assert(failed[0].action == "reject", f"expected reject, got {failed[0].action}")
    print("OK test_empty_output_rejected")

def test_non_dict_output_fails_schema():
    results = run_quality_gates(output="not a dict", policy={"enabled": True, "gates": {
        "schema_valid": {"enabled": True, "on_fail": "retry"},
        "output_not_empty": {"enabled": False},
        "consistency_check": {"enabled": False},
        "regression_check": {"enabled": False},
    }})
    failed = [r for r in results if not r.passed]
    _assert(len(failed) >= 1, f"schema gate should fail for non-dict, got {len(failed)} failures")
    _assert(any(r.gate_id == "schema_valid" for r in failed), "schema_valid gate should fail")
    print("OK test_non_dict_output_fails_schema")

def test_gates_disabled():
    results = run_quality_gates(output={}, policy={"enabled": False, "gates": {}})
    _assert(len(results) == 1, "disabled gates should return single pass")
    _assert(results[0].passed, "disabled gates should pass")
    print("OK test_gates_disabled")

def test_quality_summary():
    from src.orchestrator.quality_gate import QualityGateResult
    results = [
        QualityGateResult(True, "schema_valid", "pass", ""),
        QualityGateResult(False, "output_not_empty", "reject", "too short"),
    ]
    summary = quality_gate_summary(results)
    _assert(summary["total_gates"] == 2, "expected 2 gates")
    _assert(summary["passed"] == 1, "expected 1 passed")
    _assert(summary["failed"] == 1, "expected 1 failed")
    _assert(not summary["all_passed"], "should not be all passed")
    print("OK test_quality_summary")

def main():
    test_valid_output_passes()
    test_empty_output_rejected()
    test_non_dict_output_fails_schema()
    test_gates_disabled()
    test_quality_summary()
    print(json.dumps({"status": "OK", "tests_passed": 5}, sort_keys=True))
    return 0

if __name__ == "__main__": raise SystemExit(main())
