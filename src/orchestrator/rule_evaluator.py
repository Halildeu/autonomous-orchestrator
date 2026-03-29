"""Generic rule composition evaluator.

Evaluates rule-composition.schema.v1.json expressions against policy data.
Supports AND/OR/NOT combinators, predicate evaluation, fail_action semantics,
priority-based conflict resolution, and dependency tracking.

Usage::

    from src.orchestrator.rule_evaluator import RuleEvaluator

    evaluator = RuleEvaluator(workspace_root=Path(".cache/ws_customer_default"))
    result = evaluator.evaluate_rule(rule_definition)
    # result.action: ALLOW | BLOCK | WARN | ESCALATE
    # result.passed: bool
    # result.fail_action: BLOCK | WARN | LOG (if evaluation itself fails)

    # Evaluate multiple rules with conflict detection
    results = evaluator.evaluate_rules(rule_definitions)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RuleResult:
    """Result of evaluating a single rule."""
    rule_id: str
    passed: bool
    action: str  # ALLOW | BLOCK | WARN | ESCALATE
    fail_action: str  # BLOCK | WARN | LOG (used when evaluation fails)
    priority: int
    evaluation_error: str | None = None
    trace: list[str] = field(default_factory=list)


@dataclass
class RuleSetResult:
    """Result of evaluating a set of rules with conflict detection."""
    results: list[RuleResult]
    effective_action: str  # Final action after conflict resolution
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    all_passed: bool = True


_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_policy_data(policy_ref: str, workspace_root: Path | None) -> dict[str, Any] | None:
    """Load a policy file by reference name."""
    candidates = []
    if workspace_root:
        candidates.append(workspace_root / "policies" / policy_ref)
    candidates.append(_REPO_ROOT / "policies" / policy_ref)

    for p in candidates:
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
    return None


def _resolve_field(data: dict[str, Any], field_path: str) -> Any:
    """Resolve a dotted field path in a dict (e.g. 'defaults.mode')."""
    parts = field_path.split(".")
    current: Any = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _compare(left: Any, operator: str, right: Any) -> bool:
    """Evaluate a comparison operator."""
    if operator == "eq":
        return left == right
    elif operator == "ne":
        return left != right
    elif operator == "gt":
        try:
            return float(left) > float(right)
        except (TypeError, ValueError):
            return False
    elif operator == "gte":
        try:
            return float(left) >= float(right)
        except (TypeError, ValueError):
            return False
    elif operator == "lt":
        try:
            return float(left) < float(right)
        except (TypeError, ValueError):
            return False
    elif operator == "lte":
        try:
            return float(left) <= float(right)
        except (TypeError, ValueError):
            return False
    elif operator == "in":
        if isinstance(right, list):
            return left in right
        return False
    elif operator == "not_in":
        if isinstance(right, list):
            return left not in right
        return True
    elif operator == "contains":
        if isinstance(left, (list, str)):
            return right in left
        return False
    return False


class RuleEvaluator:
    """Evaluates rule-composition expressions against policy data."""

    def __init__(self, *, workspace_root: Path | None = None):
        self._workspace_root = workspace_root
        self._policy_cache: dict[str, dict[str, Any] | None] = {}

    def _get_policy(self, policy_ref: str) -> dict[str, Any] | None:
        if policy_ref not in self._policy_cache:
            self._policy_cache[policy_ref] = _load_policy_data(policy_ref, self._workspace_root)
        return self._policy_cache[policy_ref]

    def _eval_expression(self, expr: dict[str, Any], trace: list[str]) -> bool:
        """Recursively evaluate an expression tree."""
        expr_type = expr.get("type", "")

        if expr_type == "predicate":
            return self._eval_predicate(expr, trace)
        elif expr_type == "AND":
            operands = expr.get("operands", [])
            results = []
            for i, op in enumerate(operands):
                r = self._eval_expression(op, trace)
                results.append(r)
                trace.append(f"AND[{i}]={r}")
            return all(results)
        elif expr_type == "OR":
            operands = expr.get("operands", [])
            results = []
            for i, op in enumerate(operands):
                r = self._eval_expression(op, trace)
                results.append(r)
                trace.append(f"OR[{i}]={r}")
            return any(results)
        elif expr_type == "NOT":
            operand = expr.get("operand", {})
            r = self._eval_expression(operand, trace)
            trace.append(f"NOT={not r}")
            return not r
        else:
            trace.append(f"UNKNOWN_TYPE={expr_type}")
            return False

    def _eval_predicate(self, pred: dict[str, Any], trace: list[str]) -> bool:
        """Evaluate a single predicate against policy data."""
        policy_ref = pred.get("policy_ref", "")
        field_path = pred.get("field", "")
        operator = pred.get("operator", "eq")
        expected = pred.get("value")

        policy_data = self._get_policy(policy_ref)
        if policy_data is None:
            trace.append(f"PREDICATE policy_not_found={policy_ref}")
            return False

        actual = _resolve_field(policy_data, field_path)
        result = _compare(actual, operator, expected)
        trace.append(f"PREDICATE {policy_ref}.{field_path} {operator} {expected} → actual={actual} → {result}")
        return result

    def evaluate_rule(self, rule: dict[str, Any]) -> RuleResult:
        """Evaluate a single rule definition."""
        rule_id = rule.get("rule_id", "UNKNOWN")
        action = rule.get("action", "BLOCK")
        fail_action = rule.get("fail_action", "BLOCK")
        priority = rule.get("priority", 50)
        expression = rule.get("expression", {})

        trace: list[str] = []

        try:
            passed = self._eval_expression(expression, trace)
        except Exception as e:
            logger.warning("rule_eval ERROR rule=%s error=%s", rule_id, e)
            # fail_action semantics: evaluation failure = fail-closed
            return RuleResult(
                rule_id=rule_id,
                passed=False,
                action=fail_action,  # Use fail_action, not action
                fail_action=fail_action,
                priority=priority,
                evaluation_error=str(e),
                trace=trace,
            )

        return RuleResult(
            rule_id=rule_id,
            passed=passed,
            action=action if passed else fail_action,
            fail_action=fail_action,
            priority=priority,
            trace=trace,
        )

    def evaluate_rules(self, rules: list[dict[str, Any]]) -> RuleSetResult:
        """Evaluate multiple rules with conflict detection and priority resolution."""
        results = [self.evaluate_rule(r) for r in rules]

        # Detect conflicts: rules with different actions at similar priority
        action_groups: dict[str, list[RuleResult]] = {}
        for r in results:
            action_groups.setdefault(r.action, []).append(r)

        conflicts: list[dict[str, Any]] = []
        if len(action_groups) > 1:
            for action_a, rules_a in action_groups.items():
                for action_b, rules_b in action_groups.items():
                    if action_a >= action_b:
                        continue
                    # Check if any pair has close priorities (diff <= 10)
                    for ra in rules_a:
                        for rb in rules_b:
                            if abs(ra.priority - rb.priority) <= 10:
                                conflicts.append({
                                    "rule_a": ra.rule_id,
                                    "action_a": ra.action,
                                    "priority_a": ra.priority,
                                    "rule_b": rb.rule_id,
                                    "action_b": rb.action,
                                    "priority_b": rb.priority,
                                })

        # Effective action: highest severity from failing rules, resolved by priority
        action_severity = {"LOG": 0, "ALLOW": 1, "WARN": 2, "ESCALATE": 3, "BLOCK": 4}
        effective = "ALLOW"
        for r in sorted(results, key=lambda x: x.priority):
            if not r.passed:
                if action_severity.get(r.action, 0) > action_severity.get(effective, 0):
                    effective = r.action

        all_passed = all(r.passed for r in results)
        if all_passed:
            effective = "ALLOW"

        return RuleSetResult(
            results=results,
            effective_action=effective,
            conflicts=conflicts,
            all_passed=all_passed,
        )

    def evaluate_policy_fail_actions(self, policy_paths: list[str] | None = None) -> list[dict[str, Any]]:
        """Evaluate fail_action from loaded policies — runtime enforcement.

        Scans policies for fail_action field and returns a summary of
        which policies have block/warn/log configured.
        """
        if policy_paths is None:
            policies_dir = _REPO_ROOT / "policies"
            policy_paths = [p.name for p in sorted(policies_dir.glob("policy_*.json"))]

        results: list[dict[str, Any]] = []
        for pname in policy_paths:
            data = self._get_policy(pname)
            if data is None:
                continue
            fa = data.get("fail_action")
            if fa:
                results.append({
                    "policy": pname,
                    "fail_action": fa,
                    "enabled": data.get("enabled", True),
                })

        return results
