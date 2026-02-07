from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _rel_path(workspace_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(workspace_root.resolve()).as_posix())
    except Exception:
        return str(path.as_posix())


def _merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged.get(key, {}), value)
        else:
            merged[key] = value
    return merged


def _planner_policy(workspace_root: Path) -> tuple[dict[str, Any], str]:
    core_path = _repo_root() / "policies" / "policy_planner.v1.json"
    override_path = workspace_root / ".cache" / "policy_overrides" / "policy_planner.override.v1.json"

    base_policy = {
        "version": "v1",
        "limits": {
            "max_steps": 12,
            "max_plan_bytes": 65536,
            "max_chg_drafts": 5,
            "max_selected_items": 3,
            "max_reason_lines": 40,
        },
    }
    policy_source = "defaults"

    if core_path.exists():
        try:
            obj = _load_json(core_path)
            if isinstance(obj, dict):
                base_policy = _merge_dict(base_policy, obj)
                policy_source = str(core_path.relative_to(_repo_root()))
        except Exception:
            policy_source = "defaults_invalid_core_policy"

    if override_path.exists():
        try:
            override_obj = _load_json(override_path)
            if isinstance(override_obj, dict):
                base_policy = _merge_dict(base_policy, override_obj)
                policy_source = str(Path(".cache") / "policy_overrides" / "policy_planner.override.v1.json")
        except Exception:
            pass

    return base_policy, policy_source


def _safe_int(value: Any, default: int, minimum: int = 0) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    if parsed < minimum:
        return minimum
    return parsed


def _effective_limits(policy_obj: dict[str, Any]) -> dict[str, int]:
    raw_limits = policy_obj.get("limits") if isinstance(policy_obj.get("limits"), dict) else {}
    return {
        "max_steps": _safe_int(raw_limits.get("max_steps"), 12, minimum=1),
        "max_plan_bytes": _safe_int(raw_limits.get("max_plan_bytes"), 65536, minimum=1024),
        "max_chg_drafts": _safe_int(raw_limits.get("max_chg_drafts"), 5, minimum=0),
        "max_selected_items": _safe_int(raw_limits.get("max_selected_items"), 3, minimum=0),
        "max_reason_lines": _safe_int(raw_limits.get("max_reason_lines"), 40, minimum=1),
    }


def _sanitize_plan_id(raw: str) -> str:
    candidate = re.sub(r"[^A-Za-z0-9_-]+", "-", str(raw or "").strip()).strip("-")
    if not candidate:
        candidate = f"PLN-{_now_compact()}"
    return candidate[:120]


def _collect_inputs(workspace_root: Path) -> tuple[dict[str, str], list[str]]:
    expected = {
        "work_intake_path": Path(".cache") / "index" / "work_intake.v1.json",
        "system_status_path": Path(".cache") / "reports" / "system_status.v1.json",
        "assessment_eval_path": Path(".cache") / "reports" / "assessment_eval.v1.json",
        "gap_register_path": Path(".cache") / "reports" / "gap_register.v1.json",
    }
    notes: list[str] = []
    resolved: dict[str, str] = {}
    for key, rel in expected.items():
        abs_path = workspace_root / rel
        resolved[key] = str(rel.as_posix())
        if not abs_path.exists():
            notes.append(f"input_missing:{rel.as_posix()}")
    return resolved, notes


def _collect_selection_candidates(workspace_root: Path, max_selected_items: int) -> tuple[list[str], list[str], list[str]]:
    intake_path = workspace_root / ".cache" / "index" / "work_intake.v1.json"
    if not intake_path.exists():
        return [], [], ["work_intake_missing"]
    try:
        intake_obj = _load_json(intake_path)
    except Exception:
        return [], [], ["work_intake_invalid_json"]
    if not isinstance(intake_obj, dict):
        return [], [], ["work_intake_invalid_object"]

    items = intake_obj.get("items") if isinstance(intake_obj.get("items"), list) else []
    selected_ids: list[str] = []
    selected_extensions: list[str] = []
    notes: list[str] = []

    for item in items:
        if not isinstance(item, dict):
            continue
        intake_id = str(item.get("intake_id") or item.get("id") or "").strip()
        if intake_id and intake_id not in selected_ids:
            selected_ids.append(intake_id)
        suggested_extension = str(item.get("suggested_extension") or "").strip()
        if suggested_extension and suggested_extension not in selected_extensions:
            selected_extensions.append(suggested_extension)
        suggested_extensions = item.get("suggested_extensions")
        if isinstance(suggested_extensions, list):
            for ext in suggested_extensions:
                ext_id = str(ext).strip() if isinstance(ext, str) else ""
                if ext_id and ext_id not in selected_extensions:
                    selected_extensions.append(ext_id)
        if max_selected_items > 0 and len(selected_ids) >= max_selected_items:
            break

    if max_selected_items == 0:
        selected_ids = []
        selected_extensions = []
        notes.append("selection_disabled_by_policy")
    else:
        selected_ids = selected_ids[:max_selected_items]
        selected_extensions = selected_extensions[: max(1, max_selected_items)]

    if not selected_ids:
        notes.append("selection_empty")
    return selected_ids, selected_extensions, notes


def _build_steps(*, selected_extensions: list[str], limits: dict[str, int]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = [
        {
            "step_id": "S01",
            "type": "sync_snapshot",
            "ops": ["work-intake-check", "system-status"],
            "expected_outputs": [
                ".cache/index/work_intake.v1.json",
                ".cache/reports/system_status.v1.json",
            ],
            "notes": ["program_led"],
        }
    ]

    for ext_id in selected_extensions:
        if len(steps) >= limits.get("max_steps", 12):
            break
        steps.append(
            {
                "step_id": f"S{len(steps) + 1:02d}",
                "type": "single_gate_probe",
                "ops": [f"extension-run --extension-id {ext_id} --mode report"],
                "expected_outputs": [f".cache/reports/extension_run.{ext_id}.v1.json"],
                "notes": ["dispatch_probe"],
            }
        )

    if len(steps) < 2 and len(steps) < limits.get("max_steps", 12):
        steps.append(
            {
                "step_id": "S02",
                "type": "selection_seed",
                "ops": ["work-intake-select --mode clear", "planner-apply-selection --latest true"],
                "expected_outputs": [".cache/index/work_intake_selection.v1.json"],
                "notes": ["fallback_step"],
            }
        )

    return steps[: limits.get("max_steps", 12)]


def _write_plan_summary(*, workspace_root: Path, plan: dict[str, Any], plan_rel: str) -> str:
    summary_path = workspace_root / ".cache" / "reports" / "planner_plan_summary.v1.md"
    decision = plan.get("decision") if isinstance(plan.get("decision"), dict) else {}
    steps = plan.get("steps") if isinstance(plan.get("steps"), list) else []
    why = decision.get("why") if isinstance(decision.get("why"), list) else []
    selected_ids = decision.get("selected_intake_ids") if isinstance(decision.get("selected_intake_ids"), list) else []
    selected_extensions = (
        decision.get("selected_extensions") if isinstance(decision.get("selected_extensions"), list) else []
    )

    lines = [
        "# Planner Plan Summary",
        "",
        f"- plan_id: {plan.get('plan_id', '')}",
        f"- created_at: {plan.get('created_at', '')}",
        f"- mode: {plan.get('scope', {}).get('mode', '') if isinstance(plan.get('scope'), dict) else ''}",
        f"- plan_path: {plan_rel}",
        f"- selected_intake_ids: {', '.join([str(x) for x in selected_ids]) if selected_ids else '-'}",
        f"- selected_extensions: {', '.join([str(x) for x in selected_extensions]) if selected_extensions else '-'}",
        "",
        "## Why",
    ]
    if why:
        for item in why:
            lines.append(f"- {item}")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("## Steps")
    for step in steps:
        if not isinstance(step, dict):
            continue
        ops = step.get("ops") if isinstance(step.get("ops"), list) else []
        ops_str = ", ".join([str(op) for op in ops if isinstance(op, str) and op]) or "-"
        lines.append(f"- {step.get('step_id', '')}: {step.get('type', '')} -> {ops_str}")

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return _rel_path(workspace_root, summary_path)


def _resolve_plan_path(workspace_root: Path, plan_id: str | None, latest: bool) -> Path | None:
    plan_dir = workspace_root / ".cache" / "index" / "plans"
    if not plan_dir.exists():
        return None

    if plan_id:
        candidate = plan_dir / f"{_sanitize_plan_id(plan_id)}.v1.json"
        if candidate.exists():
            return candidate
        return None

    if latest:
        latest_path = plan_dir / "latest.v1.json"
        if latest_path.exists():
            return latest_path

    candidates = sorted([p for p in plan_dir.glob("*.v1.json") if p.name != "latest.v1.json"])
    if candidates:
        return candidates[-1]
    return None


def run_planner_build_plan(*, workspace_root: Path, mode: str = "plan_first", out: str = "latest") -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    policy_obj, policy_source = _planner_policy(workspace_root)
    limits = _effective_limits(policy_obj)
    inputs, input_notes = _collect_inputs(workspace_root)
    selected_ids, selected_extensions, selection_notes = _collect_selection_candidates(
        workspace_root, limits["max_selected_items"]
    )
    steps = _build_steps(selected_extensions=selected_extensions, limits=limits)

    requested = str(out or "").strip().lower()
    plan_id = _sanitize_plan_id(out if requested not in {"", "latest"} else f"PLN-{_now_compact()}")
    plan_dir = workspace_root / ".cache" / "index" / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plan_dir / f"{plan_id}.v1.json"
    latest_path = plan_dir / "latest.v1.json"

    why = [
        "policy_limits_applied",
        "selection_seeded_from_work_intake",
        "single_gate_first_execution",
    ]
    why = why[: limits["max_reason_lines"]]

    plan_obj: dict[str, Any] = {
        "version": "v1",
        "plan_id": plan_id,
        "created_at": _now_iso8601(),
        "scope": {
            "workspace_root": str(workspace_root),
            "mode": str(mode or "plan_first"),
        },
        "inputs": inputs,
        "decision": {
            "why": why,
            "selected_intake_ids": selected_ids,
            "selected_extensions": selected_extensions,
            "limits_applied": limits,
        },
        "steps": steps,
        "evidence_paths": [
            _rel_path(workspace_root, plan_path),
            _rel_path(workspace_root, latest_path),
            ".cache/reports/planner_plan_summary.v1.md",
        ],
        "notes": [
            f"policy_source={policy_source}",
            f"mode={str(mode or 'plan_first')}",
            "PROGRAM_LED=true",
        ]
        + input_notes
        + selection_notes,
    }

    dumped = _dump_json(plan_obj)
    max_bytes = limits["max_plan_bytes"]
    while len(dumped.encode("utf-8")) > max_bytes and len(plan_obj["steps"]) > 1:
        plan_obj["steps"] = plan_obj["steps"][:-1]
        dumped = _dump_json(plan_obj)

    plan_path.write_text(dumped, encoding="utf-8")
    latest_path.write_text(dumped, encoding="utf-8")
    plan_rel = _rel_path(workspace_root, plan_path)
    summary_rel = _write_plan_summary(workspace_root=workspace_root, plan=plan_obj, plan_rel=plan_rel)

    return {
        "status": "OK",
        "plan_id": plan_id,
        "plan_path": plan_rel,
        "summary_path": summary_rel,
        "selection_path": str(Path(".cache") / "index" / "work_intake_selection.v1.json"),
        "policy_path": policy_source,
        "notes": sorted({str(n) for n in plan_obj.get("notes", []) if isinstance(n, str) and n}),
    }


def run_planner_show_plan(*, workspace_root: Path, plan_id: str | None = None, latest: bool = True) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    plan_path = _resolve_plan_path(workspace_root, plan_id, latest)
    default_selection_path = str(Path(".cache") / "index" / "work_intake_selection.v1.json")
    if plan_path is None:
        return {
            "status": "IDLE",
            "error_code": "PLAN_NOT_FOUND",
            "plan_id": "",
            "plan_path": "",
            "summary_path": "",
            "selection_path": default_selection_path,
            "notes": ["planner_plan_missing"],
        }

    try:
        plan_obj = _load_json(plan_path)
    except Exception:
        return {
            "status": "WARN",
            "error_code": "PLAN_INVALID_JSON",
            "plan_id": "",
            "plan_path": _rel_path(workspace_root, plan_path),
            "summary_path": "",
            "selection_path": default_selection_path,
            "notes": ["planner_plan_invalid_json"],
        }
    if not isinstance(plan_obj, dict):
        return {
            "status": "WARN",
            "error_code": "PLAN_INVALID_OBJECT",
            "plan_id": "",
            "plan_path": _rel_path(workspace_root, plan_path),
            "summary_path": "",
            "selection_path": default_selection_path,
            "notes": ["planner_plan_invalid_object"],
        }

    plan_rel = _rel_path(workspace_root, plan_path)
    summary_rel = _write_plan_summary(workspace_root=workspace_root, plan=plan_obj, plan_rel=plan_rel)
    selected_ids = (
        plan_obj.get("decision", {}).get("selected_intake_ids")
        if isinstance(plan_obj.get("decision"), dict)
        else []
    )
    selected_count = len(selected_ids) if isinstance(selected_ids, list) else 0

    return {
        "status": "OK",
        "plan_id": str(plan_obj.get("plan_id") or ""),
        "plan_path": plan_rel,
        "summary_path": summary_rel,
        "selection_path": default_selection_path,
        "selected_count": int(selected_count),
        "notes": ["PROGRAM_LED=true", "planner_show_plan_wired=true"],
    }


def run_planner_apply_selection(
    *, workspace_root: Path, plan_id: str | None = None, latest: bool = True
) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    shown = run_planner_show_plan(workspace_root=workspace_root, plan_id=plan_id, latest=latest)
    status = str(shown.get("status") or "WARN")
    if status != "OK":
        return {
            "status": status,
            "error_code": shown.get("error_code"),
            "plan_id": shown.get("plan_id", ""),
            "plan_path": shown.get("plan_path", ""),
            "selection_path": shown.get("selection_path", ""),
            "selected_ids": [],
            "selected_count": 0,
            "notes": ["planner_apply_selection_skipped"],
        }

    plan_path = workspace_root / str(shown.get("plan_path") or "")
    try:
        plan_obj = _load_json(plan_path)
    except Exception:
        return {
            "status": "WARN",
            "error_code": "PLAN_INVALID_JSON",
            "plan_id": shown.get("plan_id", ""),
            "plan_path": shown.get("plan_path", ""),
            "selection_path": shown.get("selection_path", ""),
            "selected_ids": [],
            "selected_count": 0,
            "notes": ["planner_apply_selection_plan_invalid"],
        }

    decision = plan_obj.get("decision") if isinstance(plan_obj, dict) and isinstance(plan_obj.get("decision"), dict) else {}
    selected_ids_raw = decision.get("selected_intake_ids") if isinstance(decision.get("selected_intake_ids"), list) else []
    selected_ids = sorted({str(item).strip() for item in selected_ids_raw if isinstance(item, str) and str(item).strip()})

    selection_rel = Path(".cache") / "index" / "work_intake_selection.v1.json"
    selection_path = workspace_root / selection_rel
    content_hash = hashlib.sha256(
        json.dumps(selected_ids, ensure_ascii=True, sort_keys=True).encode("utf-8")
    ).hexdigest()
    selection_obj = {
        "version": "v1",
        "generated_at": _now_iso8601(),
        "workspace_root": str(workspace_root),
        "selected_ids": selected_ids,
        "content_hash": content_hash,
        "notes": ["PROGRAM_LED=true", "source=planner_apply_selection"],
    }
    selection_path.parent.mkdir(parents=True, exist_ok=True)
    selection_path.write_text(_dump_json(selection_obj), encoding="utf-8")

    final_status = "OK" if selected_ids else "IDLE"
    final_error = None if selected_ids else "NO_SELECTED_IDS"
    return {
        "status": final_status,
        "error_code": final_error,
        "plan_id": shown.get("plan_id", ""),
        "plan_path": shown.get("plan_path", ""),
        "summary_path": shown.get("summary_path", ""),
        "selection_path": str(selection_rel.as_posix()),
        "selected_ids": selected_ids,
        "selected_count": len(selected_ids),
        "notes": ["planner_apply_selection_wired=true"],
    }
