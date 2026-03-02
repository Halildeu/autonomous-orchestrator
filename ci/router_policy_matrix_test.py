from __future__ import annotations

import json
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _clone_json(obj: object) -> object:
    return json.loads(json.dumps(obj))


def _assert_route(*, policy: dict, context: dict, expected_bucket: str, reason_prefix: str | None = None) -> None:
    from src.ops.context_pack_router import route_request

    bucket, reasons = route_request(policy=policy, context=context)
    if bucket != expected_bucket:
        raise SystemExit(f"Router policy test failed: expected {expected_bucket}, got {bucket}.")
    if not isinstance(reasons, list):
        raise SystemExit("Router policy test failed: reasons must be list.")
    if reason_prefix is not None:
        if not reasons or not isinstance(reasons[0], str) or not reasons[0].startswith(reason_prefix):
            raise SystemExit(f"Router policy test failed: expected reason prefix {reason_prefix}, got {reasons!r}.")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    policy_path = repo_root / "policies" / "policy_context_pack_router.v1.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))

    contexts = [
        (
            {"doc_nav": {"critical_nav_gaps": 1}, "integrity": {"status": "OK"}, "script_budget": {"hard_exceeded": 0, "soft_only": False}, "pdca": {"regression_count": 0}, "gap": {"severity": "LOW", "effort": "S"}, "manual_request": {"kind": "support"}, "target_path": ""},
            "INCIDENT",
        ),
        (
            {"doc_nav": {"critical_nav_gaps": 0}, "integrity": {"status": "OK"}, "script_budget": {"hard_exceeded": 0, "soft_only": False}, "pdca": {"regression_count": 0}, "gap": {"severity": "LOW", "effort": "S"}, "manual_request": {"kind": "strategy"}, "target_path": ""},
            "ROADMAP",
        ),
        (
            {"doc_nav": {"critical_nav_gaps": 0}, "integrity": {"status": "OK"}, "script_budget": {"hard_exceeded": 0, "soft_only": False}, "pdca": {"regression_count": 0}, "gap": {"severity": "LOW", "effort": "S"}, "manual_request": {"kind": "support"}, "target_path": ""},
            "TICKET",
        ),
        (
            {"doc_nav": {"critical_nav_gaps": 0}, "integrity": {"status": "OK"}, "script_budget": {"hard_exceeded": 2, "soft_only": False}, "pdca": {"regression_count": 0}, "gap": {"severity": "LOW", "effort": "S"}, "manual_request": {"kind": "support"}, "target_path": ""},
            "INCIDENT",
        ),
    ]

    for ctx, expected in contexts:
        _assert_route(policy=policy, context=ctx, expected_bucket=expected, reason_prefix="rule:")

    dsl_only_policy = _clone_json(policy)
    if not isinstance(dsl_only_policy, dict):
        raise SystemExit("Router policy test failed: policy clone failed.")
    routing = dsl_only_policy.get("routing")
    if not isinstance(routing, dict):
        raise SystemExit("Router policy test failed: routing missing.")
    for rule_key in ("incident_rules", "roadmap_rules", "project_rules", "ticket_rules"):
        rules = routing.get(rule_key)
        if not isinstance(rules, list):
            continue
        for rule in rules:
            if isinstance(rule, dict):
                rule.pop("if", None)

    _assert_route(
        policy=dsl_only_policy,
        context={
            "doc_nav": {"critical_nav_gaps": 0},
            "integrity": {"status": "OK"},
            "script_budget": {"hard_exceeded": 0, "soft_only": False},
            "pdca": {"regression_count": 0},
            "gap": {"severity": "LOW", "effort": "S"},
            "manual_request": {"kind": "support"},
            "target_path": "",
        },
        expected_bucket="TICKET",
        reason_prefix="rule:",
    )

    fallback_policy = _clone_json(policy)
    if not isinstance(fallback_policy, dict):
        raise SystemExit("Router policy test failed: fallback policy clone failed.")
    fallback_routing = fallback_policy.get("routing")
    if not isinstance(fallback_routing, dict):
        raise SystemExit("Router policy test failed: fallback routing missing.")
    ticket_rules = fallback_routing.get("ticket_rules")
    if not isinstance(ticket_rules, list) or not ticket_rules:
        raise SystemExit("Router policy test failed: ticket rules missing.")
    ticket_rules[0] = {
        "id": "TEST_LEGACY_FALLBACK",
        "if": "manual_request.kind in ['support']",
        "when": {"op": "eq", "left": {"var": "manual_request.kind"}, "right": "question"},
        "then": "TICKET",
    }

    fallback_context = {
        "doc_nav": {"critical_nav_gaps": 0},
        "integrity": {"status": "OK"},
        "script_budget": {"hard_exceeded": 0, "soft_only": False},
        "pdca": {"regression_count": 0},
        "gap": {"severity": "LOW", "effort": "L"},
        "manual_request": {"kind": "support"},
        "target_path": "scripts/",
    }

    _assert_route(policy=fallback_policy, context=fallback_context, expected_bucket="TICKET", reason_prefix="rule:TEST_LEGACY_FALLBACK")

    strict_policy = _clone_json(fallback_policy)
    if not isinstance(strict_policy, dict):
        raise SystemExit("Router policy test failed: strict policy clone failed.")
    strict_routing = strict_policy.get("routing")
    if not isinstance(strict_routing, dict):
        raise SystemExit("Router policy test failed: strict routing missing.")
    strict_engine = strict_routing.get("rule_engine")
    if not isinstance(strict_engine, dict):
        raise SystemExit("Router policy test failed: strict engine missing.")
    strict_engine["legacy_compat"] = False
    strict_routing["default_bucket"] = "PROJECT"

    _assert_route(policy=strict_policy, context=fallback_context, expected_bucket="PROJECT")

    legacy_policy = _clone_json(policy)
    if not isinstance(legacy_policy, dict):
        raise SystemExit("Router policy test failed: legacy policy clone failed.")
    legacy_routing = legacy_policy.get("routing")
    if not isinstance(legacy_routing, dict):
        raise SystemExit("Router policy test failed: legacy routing missing.")
    legacy_engine = legacy_routing.get("rule_engine")
    if not isinstance(legacy_engine, dict):
        raise SystemExit("Router policy test failed: legacy engine missing.")
    legacy_engine["engine"] = "legacy_expr"

    _assert_route(
        policy=legacy_policy,
        context={
            "doc_nav": {"critical_nav_gaps": 0},
            "integrity": {"status": "OK"},
            "script_budget": {"hard_exceeded": 0, "soft_only": False},
            "pdca": {"regression_count": 0},
            "gap": {"severity": "LOW", "effort": "S"},
            "manual_request": {"kind": "strategy"},
            "target_path": "",
        },
        expected_bucket="ROADMAP",
        reason_prefix="rule:",
    )

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
