from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.ops.preflight_stamp import run_preflight_stamp
from src.prj_airunner.airunner_tick_helpers import _canonical_json, _hash_text
from src.prj_airunner.airunner_tick_utils import _dump_json, _load_json, _now_iso, _rel_to_workspace


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged.get(key, {}), value)
        else:
            merged[key] = value
    return merged


def _policy_defaults() -> dict[str, Any]:
    return {
        "version": "v1",
        "enabled": False,
        "max_runtime_seconds_per_day": 3600,
        "schedule": {
            "mode": "interval",
            "interval_seconds": 900,
            "jitter_seconds": 0,
            "active_hours": {"tz": "Europe/Istanbul", "start": "09:00", "end": "19:00"},
            "weekday_only": False,
        },
        "lock_ttl_seconds": 900,
        "heartbeat_interval_seconds": 300,
        "watchdog": {
            "enabled": True,
            "heartbeat_stale_seconds": 1200,
            "action": "CLEAR_STALE_LOCK_THEN_POLL_ONLY",
            "max_recoveries_per_day": 3,
        },
        "job_policy": {
            "max_running_jobs": 1,
            "poll_interval_seconds": 60,
            "closeout_ttl_days": 7,
            "keep_last_n": 50,
        },
        "limits": {"max_ticks_per_run": 1, "max_actions_per_tick": 1, "max_plans_per_tick": 1},
        "single_gate": {"allowed_ops": [], "require_strict_isolation": True},
        "notes": [],
    }


def _load_policy(workspace_root: Path) -> tuple[dict[str, Any], str, str, list[str]]:
    core_root = _repo_root()
    notes: list[str] = []
    core_policy_path = core_root / "policies" / "policy_airunner.v1.json"
    override_path = workspace_root / ".cache" / "policy_overrides" / "policy_airunner.override.v1.json"
    policy = _policy_defaults()
    policy_source = "core"

    if core_policy_path.exists():
        try:
            obj = _load_json(core_policy_path)
            if isinstance(obj, dict):
                policy = _deep_merge(policy, obj)
        except Exception:
            notes.append("core_policy_invalid")
    else:
        notes.append("core_policy_missing")

    if override_path.exists():
        try:
            obj = _load_json(override_path)
            if isinstance(obj, dict):
                policy = _deep_merge(policy, obj)
                policy_source = "core+workspace_override"
        except Exception:
            notes.append("override_policy_invalid")

    policy_hash = _hash_text(_canonical_json(policy))
    return policy, policy_source, policy_hash, notes


def _run_fast_gate(workspace_root: Path) -> dict[str, Any]:
    res = run_preflight_stamp(workspace_root=workspace_root, mode="read")
    gates = res.get("gates") if isinstance(res.get("gates"), dict) else {}
    script_budget = gates.get("script_budget") if isinstance(gates.get("script_budget"), dict) else {}
    report_path = res.get("report_path") if isinstance(res, dict) else ""
    return {
        "preflight_overall": str(res.get("overall") or ""),
        "preflight_reason": str(res.get("error_code") or ""),
        "preflight_stamp_path": str(report_path or ""),
        "report_path": str(report_path or ""),
        "require_pass_for_apply": bool(res.get("require_pass_for_apply", True)),
        "validate_schemas": str(gates.get("validate_schemas") or "MISSING"),
        "smoke_fast": str(gates.get("smoke_fast") or "MISSING"),
        "script_budget": str(script_budget.get("status") or "MISSING"),
        "hard_exceeded": int(script_budget.get("hard_exceeded", 0) or 0),
        "soft_exceeded": int(script_budget.get("soft_exceeded", 0) or 0),
        "status": str(res.get("status") or ""),
    }


def _write_tick_report(report: dict[str, Any], workspace_root: Path) -> tuple[str, str]:
    out_json = workspace_root / ".cache" / "reports" / "airunner_tick.v1.json"
    out_md = workspace_root / ".cache" / "reports" / "airunner_tick.v1.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(_dump_json(report), encoding="utf-8")

    md_lines = [
        "AIRUNNER TICK",
        "",
        f"Status: {report.get('status')}",
        f"Policy source: {report.get('policy_source')}",
        f"Policy hash: {report.get('policy_hash')}",
        f"Applied: {report.get('actions', {}).get('applied', 0)}",
        f"Planned: {report.get('actions', {}).get('planned', 0)}",
        f"Idle: {report.get('actions', {}).get('idle', 0)}",
        "",
        "Evidence:",
    ]
    for p in report.get("evidence_paths", []):
        md_lines.append(f"- {p}")
    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    rel_json = _rel_to_workspace(out_json, workspace_root) or str(out_json)
    rel_md = _rel_to_workspace(out_md, workspace_root) or str(out_md)
    return rel_json, rel_md


def _emit_idle_tick(
    *,
    workspace_root: Path,
    policy_source: str,
    policy_hash: str,
    notes: list[str],
    error_code: str,
    tick_id_seed: dict[str, Any],
    active_meta: dict[str, Any],
    extra_notes: list[str] | None = None,
) -> dict[str, Any]:
    merged_notes = list(notes)
    if extra_notes:
        merged_notes.extend([str(x) for x in extra_notes if isinstance(x, str) and str(x).strip()])
    report = {
        "version": "v1",
        "generated_at": _now_iso(),
        "status": "IDLE",
        "error_code": error_code,
        "tick_id": _hash_text(_canonical_json(tick_id_seed)),
        "workspace_root": str(workspace_root),
        "policy_source": policy_source,
        "policy_hash": policy_hash,
        "ops_called": [],
        "actions": {"applied": 0, "planned": 0, "idle": 0},
        "evidence_paths": [],
        "notes": merged_notes + ["PROGRAM_LED=true", "STRICT_ISOLATED=true", "NETWORK=false"],
    }
    report.update(active_meta)
    rel_json, rel_md = _write_tick_report(report, workspace_root)
    return {
        "status": "IDLE",
        "policy_source": policy_source,
        "policy_hash": policy_hash,
        "report_path": rel_json,
        "report_md_path": rel_md,
    }
