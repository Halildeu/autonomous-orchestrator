from __future__ import annotations

import ast
import json
from typing import Any


def _get_context_value(context: dict[str, Any], path: str) -> Any:
    current: Any = context
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _parse_in_list(raw: str) -> list[str]:
    try:
        value = ast.literal_eval(raw)
    except Exception:
        return []
    if isinstance(value, list):
        return [str(x) for x in value if isinstance(x, (str, int))]
    return []


def _eval_clause(clause: str, context: dict[str, Any]) -> bool:
    clause = clause.strip()
    if not clause:
        return False
    if " in " in clause:
        left, right = clause.split(" in ", 1)
        left = left.strip()
        values = _parse_in_list(right.strip())
        current = _get_context_value(context, left)
        if left == "target_path":
            return any(isinstance(current, str) and current.startswith(str(v)) for v in values)
        return str(current) in [str(v) for v in values]
    if "==" in clause:
        left, right = clause.split("==", 1)
        current = _get_context_value(context, left.strip())
        right_val = right.strip().strip("'\"")
        return str(current) == right_val
    if ">" in clause:
        left, right = clause.split(">", 1)
        current = _get_context_value(context, left.strip())
        try:
            return int(current) > int(right.strip())
        except Exception:
            return False
    current = _get_context_value(context, clause)
    return bool(current)


def _eval_expr(expr: str, context: dict[str, Any]) -> bool:
    parts = [p.strip() for p in expr.split(" and ") if p.strip()]
    if not parts:
        return False
    return all(_eval_clause(p, context) for p in parts)


def _is_var_ref(obj: Any) -> bool:
    return isinstance(obj, dict) and set(obj.keys()) == {"var"} and isinstance(obj.get("var"), str) and bool(obj.get("var"))


def _resolve_operand(operand: Any, context: dict[str, Any]) -> Any:
    if _is_var_ref(operand):
        return _get_context_value(context, str(operand.get("var")))
    return operand


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _eval_mini_dsl(expr: dict[str, Any], context: dict[str, Any]) -> bool:
    if not isinstance(expr, dict):
        return False
    op = str(expr.get("op") or "").strip().lower()
    if not op:
        return False

    if op == "and":
        items = expr.get("items") if isinstance(expr.get("items"), list) else []
        dsl_items = [item for item in items if isinstance(item, dict)]
        if not dsl_items or len(dsl_items) != len(items):
            return False
        return all(_eval_mini_dsl(item, context) for item in dsl_items)
    if op == "or":
        items = expr.get("items") if isinstance(expr.get("items"), list) else []
        dsl_items = [item for item in items if isinstance(item, dict)]
        if not dsl_items or len(dsl_items) != len(items):
            return False
        return any(_eval_mini_dsl(item, context) for item in dsl_items)
    if op == "not":
        item = expr.get("item")
        return isinstance(item, dict) and not _eval_mini_dsl(item, context)

    if op == "exists":
        value = _resolve_operand(expr.get("value"), context)
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        return True
    if op == "truthy":
        return bool(_resolve_operand(expr.get("value"), context))

    left = _resolve_operand(expr.get("left"), context)
    right = _resolve_operand(expr.get("right"), context)

    if op == "eq":
        left_num = _to_float(left)
        right_num = _to_float(right)
        if left_num is not None and right_num is not None:
            return left_num == right_num
        return str(left) == str(right)

    if op == "gt":
        left_num = _to_float(left)
        right_num = _to_float(right)
        if left_num is None or right_num is None:
            return False
        return left_num > right_num

    if op == "in":
        if not isinstance(right, list):
            return False
        return str(left) in [str(x) for x in right]

    if op == "starts_with":
        if not isinstance(left, str):
            return False
        if isinstance(right, str):
            return left.startswith(right)
        if isinstance(right, list):
            return any(left.startswith(str(prefix)) for prefix in right)
        return False

    return False


def legacy_clause_to_mini_dsl(clause: str) -> dict[str, Any]:
    clause = clause.strip()
    if not clause:
        return {"op": "truthy", "value": False}
    if " in " in clause:
        left, right = clause.split(" in ", 1)
        left = left.strip()
        values = _parse_in_list(right.strip())
        if left == "target_path":
            return {"op": "starts_with", "left": {"var": left}, "right": values}
        return {"op": "in", "left": {"var": left}, "right": values}
    if "==" in clause:
        left, right = clause.split("==", 1)
        right_val = right.strip().strip("'\"")
        return {"op": "eq", "left": {"var": left.strip()}, "right": right_val}
    if ">" in clause:
        left, right = clause.split(">", 1)
        right_raw = right.strip()
        try:
            right_value: Any = int(right_raw)
        except Exception:
            right_value = right_raw
        return {"op": "gt", "left": {"var": left.strip()}, "right": right_value}
    return {"op": "truthy", "value": {"var": clause}}


def legacy_expr_to_mini_dsl(expr: str) -> dict[str, Any]:
    parts = [p.strip() for p in expr.split(" and ") if p.strip()]
    if not parts:
        return {"op": "truthy", "value": False}
    if len(parts) == 1:
        return legacy_clause_to_mini_dsl(parts[0])
    return {"op": "and", "items": [legacy_clause_to_mini_dsl(part) for part in parts]}


def _rule_reason(rule: dict[str, Any], *, fallback_expr: str = "") -> str:
    rid = rule.get("id") if isinstance(rule.get("id"), str) else ""
    if rid:
        return f"rule:{rid}"
    expr = rule.get("if") if isinstance(rule.get("if"), str) else ""
    if expr:
        return expr
    if fallback_expr:
        return fallback_expr
    when = rule.get("when")
    if isinstance(when, dict):
        return f"dsl:{json.dumps(when, ensure_ascii=True, sort_keys=True)}"
    return "rule:unknown"


def _eval_rule(rule: dict[str, Any], *, context: dict[str, Any], dsl_enabled: bool, legacy_compat: bool) -> bool:
    if dsl_enabled:
        when = rule.get("when")
        if isinstance(when, dict) and when:
            if _eval_mini_dsl(when, context):
                return True
            if not legacy_compat:
                return False
        expr = rule.get("if") if isinstance(rule.get("if"), str) else ""
        if expr:
            try:
                if _eval_mini_dsl(legacy_expr_to_mini_dsl(expr), context):
                    return True
            except Exception:
                pass
            if legacy_compat:
                return _eval_expr(expr, context)
            return False
        return False

    expr = rule.get("if") if isinstance(rule.get("if"), str) else ""
    return _eval_expr(expr, context) if expr else False


def route_request(*, policy: dict[str, Any], context: dict[str, Any]) -> tuple[str, list[str]]:
    routing = policy.get("routing") if isinstance(policy.get("routing"), dict) else {}
    incident_rules = routing.get("incident_rules") if isinstance(routing.get("incident_rules"), list) else []
    roadmap_rules = routing.get("roadmap_rules") if isinstance(routing.get("roadmap_rules"), list) else []
    project_rules = routing.get("project_rules") if isinstance(routing.get("project_rules"), list) else []
    ticket_rules = routing.get("ticket_rules") if isinstance(routing.get("ticket_rules"), list) else []
    default_bucket = routing.get("default_bucket") if isinstance(routing.get("default_bucket"), str) else "TICKET"
    engine_cfg = routing.get("rule_engine") if isinstance(routing.get("rule_engine"), dict) else {}
    engine = str(engine_cfg.get("engine") or "mini_dsl").strip().lower()
    dsl_enabled = engine in {"mini_dsl", "cel_adapter", "cel_like"}
    legacy_compat = bool(engine_cfg.get("legacy_compat", True))

    for rules in (incident_rules, roadmap_rules, project_rules, ticket_rules):
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            if _eval_rule(rule, context=context, dsl_enabled=dsl_enabled, legacy_compat=legacy_compat):
                bucket = rule.get("then") if isinstance(rule.get("then"), str) else default_bucket
                return bucket, [_rule_reason(rule)]

    return default_bucket, []


def bucket_defaults(bucket: str) -> tuple[str, str, str]:
    bucket = bucket or "TICKET"
    severity_map = {"INCIDENT": "S1", "PROJECT": "S2", "ROADMAP": "S2", "TICKET": "S3"}
    priority_map = {"INCIDENT": "P1", "PROJECT": "P2", "ROADMAP": "P2", "TICKET": "P3"}
    action_map = {"INCIDENT": "APPLY_SAFE_ONLY", "PROJECT": "PLAN", "ROADMAP": "PLAN", "TICKET": "PLAN"}
    return severity_map.get(bucket, "S3"), priority_map.get(bucket, "P3"), action_map.get(bucket, "PLAN")
