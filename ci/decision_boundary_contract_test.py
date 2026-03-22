"""Contract test for Decision Boundary Matrix."""
from __future__ import annotations
import json, sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from src.orchestrator.decision_boundary import resolve_decision_boundary, enforce_decision_boundary
from src.tools.gateway import PolicyViolation

def _assert(cond, msg):
    if not cond: print(f"FAIL {msg}"); raise SystemExit(2)

def test_full_auto():
    policy = json.loads((_REPO_ROOT / "policies/policy_decision_boundaries.v1.json").read_text())
    b = resolve_decision_boundary(operation="session_renew", risk_score=0.1, policy=policy)
    _assert(b == "full_auto", f"expected full_auto, got {b}")
    print("OK test_full_auto")

def test_human_review():
    policy = json.loads((_REPO_ROOT / "policies/policy_decision_boundaries.v1.json").read_text())
    b = resolve_decision_boundary(operation="routing_bucket_change", risk_score=0.5, policy=policy)
    _assert(b == "human_review", f"expected human_review, got {b}")
    print("OK test_human_review")

def test_strict_deny():
    policy = json.loads((_REPO_ROOT / "policies/policy_decision_boundaries.v1.json").read_text())
    b = resolve_decision_boundary(operation="production_deploy", risk_score=0.1, policy=policy)
    _assert(b == "strict_deny", f"expected strict_deny, got {b}")
    print("OK test_strict_deny")

def test_risk_escalation():
    """full_auto operation but risk > max_risk_score → escalate to human_review."""
    policy = json.loads((_REPO_ROOT / "policies/policy_decision_boundaries.v1.json").read_text())
    b = resolve_decision_boundary(operation="session_renew", risk_score=0.5, policy=policy)
    _assert(b == "human_review", f"expected escalation to human_review, got {b}")
    print("OK test_risk_escalation")

def test_enforce_strict_deny_raises():
    try:
        enforce_decision_boundary(operation="production_deploy", risk_score=0.1)
        _assert(False, "expected PolicyViolation")
    except PolicyViolation as e:
        _assert(e.error_code == "DECISION_BOUNDARY_STRICT_DENY", f"wrong error code: {e.error_code}")
    print("OK test_enforce_strict_deny_raises")

def test_unknown_operation_defaults():
    policy = json.loads((_REPO_ROOT / "policies/policy_decision_boundaries.v1.json").read_text())
    b = resolve_decision_boundary(operation="unknown_operation", risk_score=0.1, policy=policy)
    _assert(b == "human_review", f"expected default human_review, got {b}")
    print("OK test_unknown_operation_defaults")

def main():
    test_full_auto()
    test_human_review()
    test_strict_deny()
    test_risk_escalation()
    test_enforce_strict_deny_raises()
    test_unknown_operation_defaults()
    print(json.dumps({"status": "OK", "tests_passed": 6}, sort_keys=True))
    return 0

if __name__ == "__main__": raise SystemExit(main())
