"""Contract tests for the generic rule evaluator."""
from __future__ import annotations

from pathlib import Path

from src.orchestrator.rule_evaluator import RuleEvaluator, RuleResult, RuleSetResult


def test_predicate_eq():
    """Predicate with eq operator evaluates correctly against real policy."""
    ev = RuleEvaluator()
    rule = {
        "rule_id": "RULE-TEST-EQ",
        "expression": {
            "type": "predicate",
            "policy_ref": "policy_autonomy.v1.json",
            "field": "defaults.mode",
            "operator": "eq",
            "value": "human_review",
        },
        "action": "ALLOW",
        "fail_action": "BLOCK",
        "priority": 50,
    }
    result = ev.evaluate_rule(rule)
    assert result.passed is True
    assert result.action == "ALLOW"
    assert result.rule_id == "RULE-TEST-EQ"


def test_predicate_gt():
    """Predicate with gt operator."""
    ev = RuleEvaluator()
    rule = {
        "rule_id": "RULE-TEST-GT",
        "expression": {
            "type": "predicate",
            "policy_ref": "policy_autonomy.v1.json",
            "field": "defaults.success_threshold",
            "operator": "gt",
            "value": 0.5,
        },
        "action": "ALLOW",
        "fail_action": "WARN",
        "priority": 50,
    }
    result = ev.evaluate_rule(rule)
    assert result.passed is True  # 0.8 > 0.5


def test_and_expression():
    """AND combinator: all operands must be true."""
    ev = RuleEvaluator()
    rule = {
        "rule_id": "RULE-TEST-AND",
        "expression": {
            "type": "AND",
            "operands": [
                {
                    "type": "predicate",
                    "policy_ref": "policy_autonomy.v1.json",
                    "field": "defaults.mode",
                    "operator": "eq",
                    "value": "human_review",
                },
                {
                    "type": "predicate",
                    "policy_ref": "policy_autonomy.v1.json",
                    "field": "fail_action",
                    "operator": "eq",
                    "value": "block",
                },
            ],
        },
        "action": "ALLOW",
        "fail_action": "BLOCK",
        "priority": 10,
    }
    result = ev.evaluate_rule(rule)
    assert result.passed is True
    assert "AND[0]=True" in result.trace
    assert "AND[1]=True" in result.trace


def test_or_expression():
    """OR combinator: at least one operand must be true."""
    ev = RuleEvaluator()
    rule = {
        "rule_id": "RULE-TEST-OR",
        "expression": {
            "type": "OR",
            "operands": [
                {
                    "type": "predicate",
                    "policy_ref": "policy_autonomy.v1.json",
                    "field": "defaults.mode",
                    "operator": "eq",
                    "value": "full_auto",  # False
                },
                {
                    "type": "predicate",
                    "policy_ref": "policy_autonomy.v1.json",
                    "field": "defaults.mode",
                    "operator": "eq",
                    "value": "human_review",  # True
                },
            ],
        },
        "action": "ALLOW",
        "fail_action": "BLOCK",
        "priority": 50,
    }
    result = ev.evaluate_rule(rule)
    assert result.passed is True


def test_not_expression():
    """NOT combinator: negates operand."""
    ev = RuleEvaluator()
    rule = {
        "rule_id": "RULE-TEST-NOT",
        "expression": {
            "type": "NOT",
            "operand": {
                "type": "predicate",
                "policy_ref": "policy_autonomy.v1.json",
                "field": "defaults.mode",
                "operator": "eq",
                "value": "full_auto",
            },
        },
        "action": "ALLOW",
        "fail_action": "BLOCK",
        "priority": 50,
    }
    result = ev.evaluate_rule(rule)
    assert result.passed is True  # NOT(False) = True


def test_fail_action_on_missing_policy():
    """Missing policy triggers fail_action, not action."""
    ev = RuleEvaluator()
    rule = {
        "rule_id": "RULE-MISSING",
        "expression": {
            "type": "predicate",
            "policy_ref": "policy_nonexistent.v1.json",
            "field": "foo",
            "operator": "eq",
            "value": "bar",
        },
        "action": "ALLOW",
        "fail_action": "WARN",
        "priority": 50,
    }
    result = ev.evaluate_rule(rule)
    assert result.passed is False
    assert result.action == "WARN"  # fail_action, not action


def test_conflict_detection():
    """Multiple rules with conflicting actions detected."""
    ev = RuleEvaluator()
    rules = [
        {
            "rule_id": "RULE-ALLOW",
            "expression": {"type": "predicate", "policy_ref": "policy_autonomy.v1.json", "field": "defaults.mode", "operator": "eq", "value": "human_review"},
            "action": "ALLOW",
            "fail_action": "BLOCK",
            "priority": 50,
        },
        {
            "rule_id": "RULE-BLOCK",
            "expression": {"type": "predicate", "policy_ref": "policy_autonomy.v1.json", "field": "fail_action", "operator": "eq", "value": "warn"},
            "action": "BLOCK",
            "fail_action": "BLOCK",
            "priority": 50,
        },
    ]
    result = ev.evaluate_rules(rules)
    assert isinstance(result, RuleSetResult)
    # RULE-BLOCK fails (fail_action is "block" not "warn") → BLOCK action applies
    assert not result.all_passed


def test_policy_fail_actions_scan():
    """Scan all policies for fail_action field."""
    ev = RuleEvaluator()
    results = ev.evaluate_policy_fail_actions()
    assert len(results) > 0
    # All results should have fail_action
    for r in results:
        assert r["fail_action"] in ("block", "warn", "log")
