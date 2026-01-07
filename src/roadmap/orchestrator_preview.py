from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _known_step_types() -> set[str]:
    # Must match roadmap executor dispatch table.
    return {
        "note",
        "workspace_root_guard",
        "write_file_allowlist",
        "create_file",
        "ensure_dir",
        "patch_file",
        "create_json_from_template",
        "add_schema_file",
        "add_ci_gate_script",
        "patch_policy_report_inject",
        "change_proposal_apply",
        "incubator_sanitize_scan",
        "run_cmd",
        "assert_paths_exist",
        "assert_core_paths_exist",
        "assert_pointer_target_exists",
        "iso_core_check",
    }


def _step_target_summary(tpl: dict[str, Any]) -> dict[str, Any]:
    t = tpl.get("type")
    if not isinstance(t, str):
        return {}
    if t in {
        "create_file",
        "ensure_dir",
        "patch_file",
        "create_json_from_template",
        "add_schema_file",
        "add_ci_gate_script",
        "patch_policy_report_inject",
    }:
        p = tpl.get("path") if "path" in tpl else tpl.get("target")
        return {"path": str(p) if isinstance(p, str) else None}
    if t == "assert_paths_exist":
        paths = tpl.get("paths")
        return {"paths_count": len(paths) if isinstance(paths, list) else 0}
    if t == "run_cmd":
        cmd = tpl.get("cmd")
        return {"cmd": str(cmd) if isinstance(cmd, str) else None}
    if t in {"note", "workspace_root_guard", "write_file_allowlist", "change_proposal_apply", "incubator_sanitize_scan", "iso_core_check"}:
        return {}
    return {}


def _risk_reasons_for_step(tpl: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    t = tpl.get("type")
    if not isinstance(t, str):
        return ["MISSING_TYPE"]

    if t == "run_cmd":
        reasons.append("RUN_CMD")
    if t in {"patch_file", "patch_policy_report_inject"}:
        reasons.append("PATCH")

    # Path-based risk: these prefixes represent control-plane/infra surface area.
    risky_prefixes = (
        "policies/",
        "schemas/",
        "ci/",
        "roadmaps/",
        "src/roadmap/",
        "src/tools/",
        "src/ops/",
    )
    target_path = None
    if isinstance(tpl.get("path"), str):
        target_path = tpl.get("path")
    if target_path is None and isinstance(tpl.get("target"), str):
        target_path = tpl.get("target")
    if isinstance(target_path, str):
        norm = target_path.replace("\\", "/").lstrip("/")
        for pref in risky_prefixes:
            if norm == pref.rstrip("/") or norm.startswith(pref):
                reasons.append(f"TOUCHES_{pref.rstrip('/').upper()}")
                break
    return reasons


def _eval_level_for_step(tpl: dict[str, Any]) -> str:
    # v0.2: deterministic heuristics only (no LLM).
    reasons = _risk_reasons_for_step(tpl)
    if any(r in {"RUN_CMD", "PATCH"} or r.startswith("TOUCHES_") for r in reasons):
        return "deep"
    return "short"


def _render_deep_analysis(step: dict[str, Any]) -> str:
    step_id = step.get("step_id")
    ms_id = step.get("milestone_id")
    phase = step.get("phase")
    tpl = step.get("template") if isinstance(step.get("template"), dict) else {}
    tpl_type = tpl.get("type")
    reasons = _risk_reasons_for_step(tpl)
    target = _step_target_summary(tpl)

    lines: list[str] = []
    lines.append("# Step Analysis (deep)\n")
    lines.append(f"- step_id: `{step_id}`\n")
    lines.append(f"- milestone_id: `{ms_id}`\n")
    lines.append(f"- phase: `{phase}`\n")
    lines.append(f"- template.type: `{tpl_type}`\n")
    if target:
        lines.append("\n## Target\n")
        lines.append("```json\n")
        lines.append(json.dumps(target, ensure_ascii=False, sort_keys=True, indent=2))
        lines.append("\n```\n")
    lines.append("\n## Risk Reasons\n")
    for r in reasons:
        lines.append(f"- {r}\n")
    lines.append("\n## Suggested Checks\n")
    lines.append("- `python ci/validate_schemas.py`\n")
    lines.append("- `python -m src.ops.manage smoke --level fast`\n")
    lines.append("- `python -m src.ops.manage policy-check --source fixtures`\n")
    return "".join(lines)


def _compile_preview_plan(*, core_root: Path, roadmap_path: Path, milestone_id: str) -> dict[str, Any]:
    from src.roadmap.compiler import compile_roadmap

    schema_path = core_root / "schemas" / "roadmap.schema.json"
    res = compile_roadmap(
        roadmap_path=roadmap_path,
        schema_path=schema_path,
        cache_root=core_root / ".cache",
        out_path=None,
        milestone_ids=[milestone_id],
    )
    return res.plan


def _build_milestone_preview(*, roadmap_obj: dict[str, Any], milestone_id: str, plan: dict[str, Any]) -> dict[str, Any]:
    title = ""
    for ms in roadmap_obj.get("milestones", []) if isinstance(roadmap_obj.get("milestones"), list) else []:
        if isinstance(ms, dict) and ms.get("id") == milestone_id:
            title = str(ms.get("title") or "")
            break

    steps = plan.get("steps") if isinstance(plan.get("steps"), list) else []
    known = _known_step_types()
    step_summaries: list[dict[str, Any]] = []
    unknown_types: list[str] = []
    for st in steps:
        if not isinstance(st, dict):
            continue
        tpl = st.get("template") if isinstance(st.get("template"), dict) else {}
        tpl_type = tpl.get("type")
        if isinstance(tpl_type, str) and tpl_type not in known and tpl_type not in unknown_types:
            unknown_types.append(tpl_type)
        eval_level = _eval_level_for_step(tpl)
        step_summaries.append(
            {
                "step_id": st.get("step_id"),
                "phase": st.get("phase"),
                "template_type": tpl_type,
                "eval_level": eval_level,
                "target": _step_target_summary(tpl),
                "risk_reasons": _risk_reasons_for_step(tpl),
            }
        )

    return {
        "milestone_id": milestone_id,
        "title": title,
        "steps_count": len(step_summaries),
        "unknown_step_types": sorted(unknown_types),
        "steps": step_summaries,
    }
