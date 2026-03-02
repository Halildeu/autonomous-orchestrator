from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.portfolio_budget import script_budget_actions_from_report
from src.ops.reaper import parse_bool as parse_reaper_bool


def repo_root() -> Path:
    # src/ops/roadmap_cli_helpers.py -> ops -> src -> repo root
    return Path(__file__).resolve().parents[2]


def warn(msg: str) -> None:
    print(msg, file=sys.stderr)


def _resolve_under_root(root: Path, p: Path) -> Path:
    return (root / p).resolve() if not p.is_absolute() else p.resolve()


def _parse_bool_flag(value: str, *, flag_name: str) -> bool:
    try:
        return bool(parse_reaper_bool(str(value)))
    except Exception as e:
        raise ValueError(f"INVALID_{flag_name.upper()}: expected true|false") from e


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _extract_milestone_preview(roadmap_path: Path, *, milestone_id: str | None) -> dict[str, Any]:
    if milestone_id is None:
        return {"next_milestone": None}
    try:
        obj = _load_json(roadmap_path)
    except Exception:
        return {"next_milestone": milestone_id, "title": None, "deliverables_count": None, "gates_count": None}

    milestones = obj.get("milestones") if isinstance(obj, dict) else None
    if not isinstance(milestones, list):
        return {"next_milestone": milestone_id, "title": None, "deliverables_count": None, "gates_count": None}

    for ms in milestones:
        if not isinstance(ms, dict):
            continue
        if ms.get("id") != milestone_id:
            continue
        deliverables = ms.get("steps") if isinstance(ms.get("steps"), list) else ms.get("deliverables")
        if not isinstance(deliverables, list):
            deliverables = []
        gates = ms.get("gates") if isinstance(ms.get("gates"), list) else []
        return {
            "next_milestone": milestone_id,
            "title": ms.get("title"),
            "deliverables_count": len(deliverables),
            "gates_count": len(gates),
        }

    return {"next_milestone": milestone_id, "title": None, "deliverables_count": None, "gates_count": None}


def _read_actions_top(workspace_root: Path, *, limit: int = 3) -> tuple[int, list[dict[str, Any]]]:
    path = workspace_root / ".cache" / "roadmap_actions.v1.json"
    if not path.exists():
        actions: list[dict[str, Any]] = []
    else:
        try:
            obj = _load_json(path)
        except Exception:
            obj = {}
        actions = obj.get("actions") if isinstance(obj, dict) else None
        if not isinstance(actions, list):
            actions = []
    actions = actions if isinstance(actions, list) else []
    actions = [a for a in actions if not (isinstance(a, dict) and a.get("resolved") is True)]
    script_budget_actions = script_budget_actions_from_report(repo_root())
    if script_budget_actions is not None:
        actions = [
            a
            for a in actions
            if not (isinstance(a, dict) and (str(a.get("kind") or "") == "SCRIPT_BUDGET" or str(a.get("source") or "") == "SCRIPT_BUDGET"))
        ]
        actions.extend(script_budget_actions)
    actions = [
        a
        for a in actions
        if not (isinstance(a, dict) and str(a.get("kind") or "") == "SYSTEM_STATUS_FAIL")
    ]
    cleaned: list[dict[str, Any]] = []
    for a in actions:
        if not isinstance(a, dict):
            continue
        cleaned.append(
            {
                "action_id": a.get("action_id"),
                "severity": a.get("severity"),
                "kind": a.get("kind"),
                "milestone_hint": a.get("milestone_hint"),
                "message": (str(a.get("message"))[:200] if a.get("message") is not None else None),
            }
        )
    cleaned.sort(key=lambda x: str(x.get("action_id") or ""))
    return (len(cleaned), cleaned[: max(0, int(limit))])


def _read_system_status_summary(workspace_root: Path) -> tuple[str | None, str | None]:
    status_path = workspace_root / ".cache" / "reports" / "system_status.v1.json"
    if not status_path.exists():
        return (None, None)
    try:
        obj = _load_json(status_path)
    except Exception:
        return (None, str(status_path))
    if not isinstance(obj, dict):
        return (None, str(status_path))
    overall = obj.get("overall_status")
    if not isinstance(overall, str):
        overall = None
    return (overall, str(status_path))


def _read_work_intake_focus(workspace_root: Path) -> tuple[str | None, str | None]:
    intake_path = workspace_root / ".cache" / "index" / "work_intake.v1.json"
    if not intake_path.exists():
        return (None, None)
    try:
        obj = _load_json(intake_path)
    except Exception:
        return (None, str(intake_path))
    if not isinstance(obj, dict):
        return (None, str(intake_path))
    focus = obj.get("next_intake_focus")
    if not isinstance(focus, str):
        focus = None
    return (focus, str(intake_path))


def _manual_request_counts(workspace_root: Path) -> tuple[int, dict[str, int]]:
    intake_path = workspace_root / ".cache" / "index" / "work_intake.v1.json"
    counts_by_bucket = {"INCIDENT": 0, "TICKET": 0, "PROJECT": 0, "ROADMAP": 0}
    if not intake_path.exists():
        return (0, counts_by_bucket)
    try:
        obj = _load_json(intake_path)
    except Exception:
        return (0, counts_by_bucket)
    items = obj.get("items") if isinstance(obj, dict) else None
    if not isinstance(items, list):
        return (0, counts_by_bucket)
    total = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("source_type")) != "MANUAL_REQUEST":
            continue
        bucket = item.get("bucket")
        if bucket in counts_by_bucket:
            counts_by_bucket[bucket] += 1
        total += 1
    return (total, counts_by_bucket)


def _read_last_finish_evidence(workspace_root: Path) -> str | None:
    path = workspace_root / ".cache" / "last_finish_evidence.v1.txt"
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return None


def _load_project_manifests(core_root: Path) -> list[dict[str, Any]]:
    projects_root = core_root / "roadmaps" / "PROJECTS"
    if not projects_root.exists():
        return []
    manifests = sorted(projects_root.rglob("project.manifest.v1.json"))
    results: list[dict[str, Any]] = []
    for path in manifests:
        rel = path.relative_to(core_root).as_posix()
        data: dict[str, Any] = {}
        try:
            obj = _load_json(path)
            if isinstance(obj, dict):
                data = obj
        except Exception:
            data = {}
        project_id = data.get("project_id")
        if not isinstance(project_id, str) or not project_id.strip():
            project_id = path.parent.name
        results.append(
            {
                "project_id": str(project_id),
                "title": data.get("title"),
                "version": data.get("version"),
                "manifest_path": rel,
            }
        )
    results.sort(key=lambda x: str(x.get("project_id") or ""))
    return results


def _read_extension_registry(workspace_root: Path) -> tuple[list[dict[str, Any]], str | None, str]:
    registry_path = workspace_root / ".cache" / "index" / "extension_registry.v1.json"
    if not registry_path.exists():
        return ([], None, "MISSING")
    try:
        obj = _load_json(registry_path)
    except Exception:
        return ([], str(registry_path), "INVALID")
    extensions = obj.get("extensions") if isinstance(obj, dict) else None
    entries = [e for e in extensions if isinstance(e, dict)] if isinstance(extensions, list) else []
    entries.sort(key=lambda x: str(x.get("extension_id") or ""))
    status = obj.get("status") if isinstance(obj, dict) else None
    status_str = str(status) if status in {"OK", "WARN", "IDLE", "FAIL"} else "WARN"
    return (entries, str(registry_path), status_str)


def _portfolio_next_focus(
    bench_status: str | None,
    actions_top: list[dict[str, Any]],
    extensions: list[str],
) -> str:
    if bench_status and bench_status != "OK":
        return "M10_CLOSEOUT"
    for a in actions_top:
        if isinstance(a, dict) and str(a.get("kind") or "") == "SCRIPT_BUDGET":
            return "PRJ-M0-MAINTAINABILITY"
    if extensions:
        return extensions[0]
    return "PRJ-KERNEL-API"


def _print_chat_block(*, preview: str, result: str, evidence: str, actions: str, next_steps: str, final_json: dict[str, Any]) -> None:
    # Human-readable block (no secrets, no shell commands for the user).
    print("PREVIEW:")
    print(preview.rstrip() + ("\n" if preview and not preview.endswith("\n") else ""))
    print("RESULT:")
    print(result.rstrip() + ("\n" if result and not result.endswith("\n") else ""))
    print("EVIDENCE:")
    print(evidence.rstrip() + ("\n" if evidence and not evidence.endswith("\n") else ""))
    print("ACTIONS:")
    print(actions.rstrip() + ("\n" if actions and not actions.endswith("\n") else ""))
    print("NEXT:")
    print(next_steps.rstrip() + ("\n" if next_steps and not next_steps.endswith("\n") else ""))

    # Machine-readable final line (single-line JSON).
    print(json.dumps(final_json, ensure_ascii=False, sort_keys=True))
