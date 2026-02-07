from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _must(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"planner_build_contract_test failed: {message}")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.prj_planner.planner_build import (
        run_planner_apply_selection,
        run_planner_build_plan,
        run_planner_show_plan,
    )

    ws = repo_root / ".cache" / "ws_prj_planner_build_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    show_before = run_planner_show_plan(workspace_root=ws, plan_id=None, latest=True)
    _must(show_before.get("status") == "IDLE", "show before build must be IDLE")
    _must(show_before.get("error_code") == "PLAN_NOT_FOUND", "show before build error_code mismatch")

    build_payload = run_planner_build_plan(workspace_root=ws, mode="plan_first", out="latest")
    _must(build_payload.get("status") == "OK", "build status must be OK")
    plan_rel = str(build_payload.get("plan_path") or "")
    summary_rel = str(build_payload.get("summary_path") or "")
    _must(bool(plan_rel), "plan_path missing")
    _must(bool(summary_rel), "summary_path missing")

    plan_path = ws / plan_rel
    _must(plan_path.exists(), "plan file missing")

    plan_obj = _load_json(plan_path)
    required_top = [
        "version",
        "plan_id",
        "created_at",
        "scope",
        "inputs",
        "decision",
        "steps",
        "evidence_paths",
    ]
    for key in required_top:
        _must(key in plan_obj, f"plan field missing: {key}")
    _must(plan_obj.get("version") == "v1", "plan version mismatch")
    _must(isinstance(plan_obj.get("steps"), list), "plan steps must be list")

    step_schema_path = repo_root / "schemas" / "planner-step.schema.v1.json"
    step_validator = Draft202012Validator(_load_json(step_schema_path))
    for step in plan_obj.get("steps", []):
        step_validator.validate(step)

    show_after = run_planner_show_plan(workspace_root=ws, plan_id=None, latest=True)
    _must(show_after.get("status") == "OK", "show after build must be OK")
    _must(bool(show_after.get("plan_id")), "show after build plan_id missing")
    _must(bool(show_after.get("plan_path")), "show after build plan_path missing")
    _must(bool(show_after.get("summary_path")), "show after build summary_path missing")

    apply_payload = run_planner_apply_selection(workspace_root=ws, plan_id=None, latest=True)
    _must(apply_payload.get("status") in {"OK", "IDLE"}, "apply status must be OK or IDLE")
    selection_rel = str(apply_payload.get("selection_path") or "")
    _must(bool(selection_rel), "selection_path missing")
    selection_path = ws / selection_rel
    _must(selection_path.exists(), "selection file missing")
    selection_obj = _load_json(selection_path)
    _must(selection_obj.get("version") == "v1", "selection version mismatch")

    print(
        json.dumps(
            {
                "status": "OK",
                "plan_id": show_after.get("plan_id"),
                "selection_count": apply_payload.get("selected_count"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
