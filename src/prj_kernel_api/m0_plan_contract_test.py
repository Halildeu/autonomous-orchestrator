"""Contract test for PRJ-KERNEL-API M0 plan discovery/generation (offline)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from src.prj_kernel_api.m0_plan import ensure_manage_split_plan


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_plan(path: Path) -> None:
    plan = {
        "chg_id": "CHG-M0-002-manage_split",
        "plan_only": True,
        "target_files": ["src/ops/manage.py"],
        "constraints": ["behavior_preserving=true"],
        "steps": ["extract commands modules", "dispatcher refactor"],
        "invariants": ["cli_surface_unchanged"],
        "acceptance_tests": ["validate_schemas", "smoke_fast"],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _assert_result(result: dict) -> Path:
    plan_path = result.get("plan_path")
    if not isinstance(plan_path, str) or not plan_path:
        raise SystemExit("M0 plan test failed: plan_path missing.")
    path = Path(plan_path)
    if not path.exists():
        raise SystemExit("M0 plan test failed: canonical plan missing.")
    return path


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    ws = repo_root / ".cache" / "ws_m0_plan_demo"
    if ws.exists():
        shutil.rmtree(ws)

    # Case 1: no plan present -> generated.
    result_generated = ensure_manage_split_plan(str(ws))
    plan_path = _assert_result(result_generated)
    if result_generated.get("plan_source") != "generated":
        raise SystemExit("M0 plan test failed: expected generated plan_source.")

    # Case 2: discovered plan should be canonicalized deterministically.
    shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)
    source_plan = ws / "incubator" / "debt_chg" / "CHG-20260104-M0-002-manage_split.plan.json"
    _write_plan(source_plan)
    result_discovered = ensure_manage_split_plan(str(ws))
    plan_path = _assert_result(result_discovered)
    if result_discovered.get("plan_source") != "discovered":
        raise SystemExit("M0 plan test failed: expected discovered plan_source.")

    canonical = ws / ".cache" / "reports" / "chg" / "CHG-M0-002-manage_split.plan.json"
    if plan_path.resolve() != canonical.resolve():
        raise SystemExit("M0 plan test failed: canonical plan path mismatch.")

    discovered_payload = _load_json(canonical)
    if discovered_payload.get("chg_id") != "CHG-M0-002-manage_split":
        raise SystemExit("M0 plan test failed: canonical plan content mismatch.")

    print(
        json.dumps(
            {
                "status": "OK",
                "generated_plan": str((ws / ".cache" / "reports" / "chg" / "CHG-M0-002-manage_split.plan.json")),
                "discovered_plan": str(canonical),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
