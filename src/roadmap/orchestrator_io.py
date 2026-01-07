from __future__ import annotations

from pathlib import Path
from typing import Any

from src.roadmap.evidence import write_integrity_manifest, write_json, write_text
from src.roadmap.orchestrator_helpers import (
    _atomic_write_text,
    _build_milestone_preview,
    _compile_preview_plan,
    _derive_actions_for_milestone,
    _eval_level_for_step,
    _render_deep_analysis,
)


def write_finish_preview_and_analysis(
    *,
    core_root: Path,
    roadmap_path: Path,
    run_dir: Path,
    roadmap_obj: dict[str, Any],
    milestone_id: str,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    plan = _compile_preview_plan(core_root=core_root, roadmap_path=roadmap_path, milestone_id=milestone_id)
    preview_obj = _build_milestone_preview(roadmap_obj=roadmap_obj, milestone_id=milestone_id, plan=plan)

    previews_dir = run_dir / "previews"
    previews_dir.mkdir(parents=True, exist_ok=True)
    write_json(previews_dir / f"{milestone_id}.json", preview_obj)

    steps = plan.get("steps") if isinstance(plan.get("steps"), list) else []
    for step in steps:
        if not isinstance(step, dict):
            continue
        tpl = step.get("template") if isinstance(step.get("template"), dict) else {}
        if _eval_level_for_step(tpl) != "deep":
            continue
        step_id = str(step.get("step_id") or "")
        if not step_id:
            continue
        analysis_text = _render_deep_analysis(step)
        write_text(run_dir / "steps" / step_id / "analysis.md", analysis_text)

    derived_actions: list[dict[str, Any]] = []
    derived_actions.extend(_derive_actions_for_milestone(milestone_id=milestone_id, preview=preview_obj))
    return (plan, preview_obj, derived_actions)


def write_finish_artifacts(
    *,
    core_root: Path,
    run_dir: Path,
    roadmap_path: Path,
    workspace_root: Path,
    state_path: Path,
    state_before: dict[str, Any],
    state_after: dict[str, Any],
    out: dict[str, Any],
    iterations: list[dict[str, Any]],
    logs: list[str],
    max_minutes: int,
    sleep_seconds: int,
    max_steps_per_iteration: int,
    auto_apply_chg: bool,
) -> None:
    write_json(
        run_dir / "input.json",
        {
            "roadmap": str(roadmap_path),
            "workspace_root": str(workspace_root),
            "state_path": str(state_path),
            "requested": {
                "max_minutes": int(max_minutes),
                "sleep_seconds": int(sleep_seconds),
                "max_steps_per_iteration": int(max_steps_per_iteration),
                "auto_apply_chg": bool(auto_apply_chg),
            },
        },
    )
    write_json(run_dir / "state_before.json", state_before)
    write_json(run_dir / "state_after.json", state_after)
    write_json(run_dir / "output.json", out)
    write_json(run_dir / "iterations.json", {"iterations": iterations})
    _atomic_write_text(
        workspace_root / ".cache" / "last_finish_evidence.v1.txt",
        str(run_dir.relative_to(core_root)),
    )
    write_text(run_dir / "logs.txt", "".join(logs))
    write_integrity_manifest(run_dir)
