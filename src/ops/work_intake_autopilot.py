from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged.get(key, {}), value)
        else:
            merged[key] = value
    return merged


def _autopilot_defaults() -> dict[str, Any]:
    return {
        "version": "v1",
        "defaults": {
            "selected_default": False,
            "max_apply_per_tick": 2,
            "max_plans_per_tick": 5,
            "max_poll_per_tick": 1,
        },
        "auto_select": {
            "enabled": False,
            "max_select": 3,
            "allow_buckets": ["TICKET"],
            "allow_source_types": ["MANUAL_REQUEST", "DOC_NAV", "SCRIPT_BUDGET", "JOB_STATUS"],
            "require_impact_scope": "doc-only",
            "deny_if_requires_core_change": True,
            "rank_rule": "priority asc -> severity asc -> intake_id asc",
        },
        "selection_rules": [],
        "apply_guards": {
            "require_evidence_paths": True,
            "deny_buckets": ["INCIDENT"],
            "deny_when": {"network_required": True},
        },
    }


def _load_autopilot_policy(*, core_root: Path, workspace_root: Path) -> tuple[dict[str, Any], str, list[str]]:
    notes: list[str] = []
    policy = _autopilot_defaults()
    policy_source = "core"

    core_policy = core_root / "policies" / "policy_autopilot_apply.v1.json"
    if core_policy.exists():
        try:
            obj = _load_json(core_policy)
            if isinstance(obj, dict):
                policy = _deep_merge(policy, obj)
        except Exception:
            notes.append("autopilot_policy_invalid")
    else:
        notes.append("autopilot_policy_missing")

    override_path = workspace_root / ".cache" / "policy_overrides" / "policy_autopilot_apply.override.v1.json"
    if override_path.exists():
        try:
            obj = _load_json(override_path)
            if isinstance(obj, dict):
                policy = _deep_merge(policy, obj)
                policy_source = "core+workspace_override"
        except Exception:
            notes.append("autopilot_policy_override_invalid")

    if policy.get("version") != "v1":
        notes.append("autopilot_policy_version_mismatch")
        policy = _autopilot_defaults()
        policy_source = "core"

    return policy, policy_source, notes


def _load_autopilot_selection(workspace_root: Path, notes: list[str]) -> set[str]:
    selection_path = workspace_root / ".cache" / "index" / "work_intake_selection.v1.json"
    if not selection_path.exists():
        return set()
    try:
        obj = _load_json(selection_path)
    except Exception:
        notes.append("autopilot_selection_invalid")
        return set()
    selected = obj.get("selected_ids")
    if not isinstance(selected, list):
        selected = obj.get("intake_ids")
    if not isinstance(selected, list):
        notes.append("autopilot_selection_missing")
        return set()
    return {str(x) for x in selected if isinstance(x, str) and x.strip()}


def _match_autopilot_when(when: dict[str, Any], item: dict[str, Any], source: dict[str, Any]) -> bool:
    if "bucket" in when and str(item.get("bucket") or "") != str(when.get("bucket") or ""):
        return False
    if "source_type" in when and str(source.get("source_type") or "") != str(when.get("source_type") or ""):
        return False
    if "impact_scope" in when:
        scope = str(source.get("manual_request_impact_scope") or "")
        if scope != str(when.get("impact_scope") or ""):
            return False
    if "kind_in" in when:
        kind = str(source.get("manual_request_kind") or "")
        allowed = [str(x) for x in when.get("kind_in", []) if isinstance(x, str)]
        if kind not in allowed:
            return False
    if "broken_refs_gt" in when:
        broken = int(source.get("broken_refs", 0))
        if broken <= int(when.get("broken_refs_gt", 0)):
            return False
    if "path_prefix_in" in when:
        path = str(source.get("path") or "")
        prefixes = [str(x) for x in when.get("path_prefix_in", []) if isinstance(x, str)]
        if not any(path.startswith(pref) for pref in prefixes):
            return False
    if "hard_exceeded_eq" in when:
        hard = int(source.get("hard_exceeded", 0))
        if hard != int(when.get("hard_exceeded_eq", 0)):
            return False
    if "job_status_in" in when:
        status = str(source.get("job_status") or "")
        allowed = [str(x) for x in when.get("job_status_in", []) if isinstance(x, str)]
        if status not in allowed:
            return False
    if "requires_core_change" in when:
        required = bool(when.get("requires_core_change"))
        if bool(source.get("manual_request_requires_core_change", False)) != required:
            return False
    if "network_required" in when:
        required = bool(when.get("network_required"))
        if bool(source.get("network_required", False)) != required:
            return False
    return True


def _autopilot_labels(
    item: dict[str, Any],
    source: dict[str, Any],
    policy: dict[str, Any],
    selected_ids: set[str],
) -> tuple[bool, bool, str, list[str]]:
    allowed = False
    selected = False
    reason = ""
    notes: list[str] = []
    rules = policy.get("selection_rules")
    if isinstance(rules, list):
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            when = rule.get("when") if isinstance(rule.get("when"), dict) else {}
            set_obj = rule.get("set") if isinstance(rule.get("set"), dict) else {}
            if not _match_autopilot_when(when, item, source):
                continue
            allowed = bool(set_obj.get("autopilot_allowed", False))
            reason = str(set_obj.get("autopilot_reason") or "").strip()
            if reason:
                notes.append(f"autopilot_reason:{reason}")
            break

    if item.get("intake_id") in selected_ids:
        selected = True
        notes.append("autopilot_selected")
    else:
        selected = bool(policy.get("defaults", {}).get("selected_default", False))
    return allowed, selected, reason, sorted(set(notes))
