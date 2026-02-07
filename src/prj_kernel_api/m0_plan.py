"""Program-led M0 plan discovery/generation (workspace-scoped, deterministic)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

CANONICAL_DIR = ".cache/reports/chg"
CANONICAL_NAME = "CHG-M0-002-manage_split.plan.json"
DISCOVERY_REPORT = "m0_manage_split_discovery.v1.json"
GENERATED_REPORT = "m0_manage_split_generated.v1.json"


def _write_json_atomic(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _matches_plan_name(filename: str) -> bool:
    lower = filename.lower()
    if not lower.endswith(".json"):
        return False
    if "m0" in lower and "manage" in lower and "split" in lower:
        return True
    if "manage_split" in lower and "m0" in lower and lower.endswith(".plan.json"):
        return True
    return False


def _collect_matches(base: Path, *, recursive: bool, limit: int | None = None) -> List[Path]:
    matches: List[Path] = []
    if not base.exists():
        return matches
    if recursive:
        for path in base.rglob("*"):
            if path.is_file() and _matches_plan_name(path.name):
                matches.append(path)
    else:
        for path in base.iterdir():
            if path.is_file() and _matches_plan_name(path.name):
                matches.append(path)
    ordered = sorted(matches, key=lambda p: str(p))
    if limit is not None:
        return ordered[:limit]
    return ordered


def discover_manage_split_plans(workspace_root: str) -> List[Path]:
    ws = Path(workspace_root)
    search_roots = [
        ws / ".cache" / "reports" / "chg",
        ws / ".cache" / "reports",
        ws / ".cache" / "debt_chg",
        ws / "incubator" / "debt_chg",
    ]
    for root in search_roots:
        found = _collect_matches(root, recursive=False)
        if found:
            return found
    return _collect_matches(ws / ".cache" / "reports", recursive=True, limit=200)


def _validate_plan(plan: Dict[str, Any]) -> None:
    required = ["chg_id", "target_files", "constraints", "steps", "invariants", "acceptance_tests"]
    missing = [key for key in required if key not in plan]
    if missing:
        raise ValueError(f"PLAN_INVALID: missing {', '.join(missing)}")


def _canonical_plan(workspace_root: str) -> Path:
    return Path(workspace_root) / CANONICAL_DIR / CANONICAL_NAME


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _copy_if_needed(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and _read_text(dest) == _read_text(src):
        return
    dest.write_text(_read_text(src), encoding="utf-8")


def _generate_plan() -> Dict[str, Any]:
    return {
        "chg_id": "CHG-M0-002-manage_split",
        "plan_only": True,
        "target_files": ["src/ops/manage.py"],
        "constraints": [
            "behavior_preserving=true",
            "no_orchestrator_edits=true",
            "ci_smoke_no_growth=true",
            "no_network=true",
        ],
        "steps": [
            "extract roadmap_cmds/status_cmds/debt_cmds/hygiene_cmds modules",
            "convert manage.py into dispatcher",
        ],
        "invariants": ["cli_surface_unchanged", "output_json_shapes_unchanged"],
        "acceptance_tests": [
            "validate_schemas",
            "smoke_fast",
            "smoke_full",
            "script_budget",
            "portfolio_status",
            "system_status",
            "project_status",
        ],
    }


def ensure_manage_split_plan(workspace_root: str) -> Dict[str, Any]:
    ws = Path(workspace_root)
    canonical = _canonical_plan(workspace_root)
    found = discover_manage_split_plans(workspace_root)
    if found:
        chosen = found[0]
        _copy_if_needed(chosen, canonical)
        report = {
            "status": "OK",
            "found_paths": [str(p) for p in found],
            "chosen": str(chosen),
            "copy_to": str(canonical),
        }
        report_path = ws / CANONICAL_DIR / DISCOVERY_REPORT
        _write_json_atomic(report_path, report)
        return {
            "plan_path": str(canonical),
            "plan_source": "discovered",
            "discovery_report_path": str(report_path),
        }

    plan = _generate_plan()
    _validate_plan(plan)
    _write_json_atomic(canonical, plan)
    report = {
        "status": "OK",
        "generated": True,
        "plan_path": str(canonical),
    }
    report_path = ws / CANONICAL_DIR / GENERATED_REPORT
    _write_json_atomic(report_path, report)
    return {
        "plan_path": str(canonical),
        "plan_source": "generated",
        "discovery_report_path": None,
    }
