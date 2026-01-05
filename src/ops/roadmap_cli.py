from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.reaper import parse_bool as parse_reaper_bool


def repo_root() -> Path:
    # src/ops/roadmap_cli.py -> ops -> src -> repo root
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
        return (0, [])
    try:
        obj = _load_json(path)
    except Exception:
        return (0, [])
    actions = obj.get("actions") if isinstance(obj, dict) else None
    if not isinstance(actions, list):
        return (0, [])
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
    overall = obj.get("overall_status") if isinstance(obj, dict) else None
    return (overall if isinstance(overall, str) else None, str(status_path))


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


def _portfolio_next_focus(bench_status: str | None, actions_top: list[dict[str, Any]]) -> str:
    if bench_status and bench_status != "OK":
        return "M10_CLOSEOUT"
    for a in actions_top:
        if isinstance(a, dict) and str(a.get("kind") or "") == "SCRIPT_BUDGET":
            return "PRJ-M0-MAINTAINABILITY"
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


def cmd_roadmap_plan(args: argparse.Namespace) -> int:
    root = repo_root()
    roadmap_path = _resolve_under_root(root, Path(str(args.roadmap)))
    if not roadmap_path.exists():
        warn(f"ERROR: roadmap not found: {roadmap_path}")
        return 2

    workspace_root = _resolve_under_root(root, Path(str(getattr(args, "workspace_root", ".") or ".")))

    out_path = _resolve_under_root(root, Path(str(args.out)))

    try:
        from src.roadmap.compiler import compile_roadmap
    except Exception as e:
        warn("ERROR: failed to import roadmap compiler: " + str(e))
        return 2

    schema_path = root / "schemas" / "roadmap.schema.json"
    if not schema_path.exists():
        warn("ERROR: missing schemas/roadmap.schema.json")
        return 2

    milestone_ids: list[str] | None = None
    single = getattr(args, "milestone", None)
    multi = getattr(args, "milestones", None)
    if single and multi:
        warn("ERROR: provide only one of --milestone or --milestones")
        return 2
    if single:
        milestone_ids = [str(single)]
    elif multi:
        parts = [p.strip() for p in str(multi).split(",")]
        milestone_ids = [p for p in parts if p]

    try:
        res = compile_roadmap(
            roadmap_path=roadmap_path,
            schema_path=schema_path,
            cache_root=root / ".cache",
            out_path=out_path,
            milestone_ids=milestone_ids,
        )
    except Exception as e:
        warn("FAIL error=" + str(e))
        return 2

    payload = {
        "status": "OK",
        "run_id": res.plan_id,
        "plan_path": str(out_path.relative_to(root)) if out_path.is_relative_to(root) else str(out_path),
        "workspace_root": str(workspace_root.relative_to(root)) if workspace_root.is_relative_to(root) else str(workspace_root),
        "milestones": res.plan.get("milestones", []),
        "milestones_included": res.milestones_included,
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_roadmap_apply(args: argparse.Namespace) -> int:
    root = repo_root()
    roadmap_path = _resolve_under_root(root, Path(str(args.roadmap)))
    if not roadmap_path.exists():
        warn(f"ERROR: roadmap not found: {roadmap_path}")
        return 2

    workspace_root = _resolve_under_root(root, Path(str(getattr(args, "workspace_root", ".") or ".")))

    try:
        dry_run = parse_reaper_bool(str(args.dry_run))
    except ValueError:
        warn("ERROR: invalid --dry-run (expected true|false)")
        return 2

    dry_run_mode = str(getattr(args, "dry_run_mode", "simulate") or "simulate")
    if dry_run_mode not in {"simulate", "readonly"}:
        warn("ERROR: invalid --dry-run-mode (expected simulate|readonly)")
        return 2

    milestone_ids: list[str] | None = None
    single = getattr(args, "milestone", None)
    multi = getattr(args, "milestones", None)
    if single and multi:
        warn("ERROR: provide only one of --milestone or --milestones")
        return 2
    if single:
        milestone_ids = [str(single)]
    elif multi:
        parts = [p.strip() for p in str(multi).split(",")]
        milestone_ids = [p for p in parts if p]

    try:
        from src.roadmap.executor import apply_roadmap
    except Exception as e:
        warn("ERROR: failed to import roadmap executor: " + str(e))
        return 2

    try:
        payload = apply_roadmap(
            roadmap_path=roadmap_path,
            core_root=root,
            workspace_root=workspace_root,
            cache_root=root / ".cache",
            evidence_root=root / "evidence" / "roadmap",
            dry_run=dry_run,
            dry_run_mode=dry_run_mode,
            milestone_ids=milestone_ids,
        )
    except Exception as e:
        warn("FAIL error=" + str(e))
        return 2

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") == "OK" else 2


def cmd_roadmap_status(args: argparse.Namespace) -> int:
    root = repo_root()
    roadmap_path = _resolve_under_root(root, Path(str(args.roadmap)))
    workspace_root = _resolve_under_root(root, Path(str(getattr(args, "workspace_root", ".") or ".")))
    from src.roadmap.orchestrator import status as roadmap_status

    payload = roadmap_status(roadmap_path=roadmap_path, workspace_root=workspace_root)
    chat = _parse_bool_flag(str(getattr(args, "chat", "false") or "false"), flag_name="chat")
    if not chat:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    next_mid = payload.get("next_milestone") if isinstance(payload, dict) else None
    preview_obj = _extract_milestone_preview(roadmap_path, milestone_id=(str(next_mid) if isinstance(next_mid, str) else None))
    actions_count, actions_top = _read_actions_top(workspace_root, limit=3)

    preview_lines = [
        f"- next_milestone: {preview_obj.get('next_milestone')}",
        f"- title: {preview_obj.get('title')}",
        f"- deliverables_count: {preview_obj.get('deliverables_count')}",
        f"- gates_count: {preview_obj.get('gates_count')}",
    ]
    result_lines = [
        f"- status: {payload.get('status')}",
        f"- completed_count: {payload.get('completed_count')}",
        f"- bootstrapped: {payload.get('bootstrapped')}",
    ]
    last_result = payload.get("last_result") if isinstance(payload, dict) else None
    last_evidence = last_result.get("evidence_path") if isinstance(last_result, dict) else None
    evidence_lines = [
        f"- workspace_root: {str(workspace_root.relative_to(root)) if workspace_root.is_relative_to(root) else str(workspace_root)}",
        f"- state_path: {payload.get('state_path')}",
        f"- last_evidence: {last_evidence}",
    ]
    actions_lines = [f"- actions_count: {actions_count}"]
    for a in actions_top:
        actions_lines.append(
            f"- {a.get('action_id')} {a.get('kind')} ({a.get('milestone_hint')}): {a.get('message')}"
        )
    next_lines = []
    if isinstance(next_mid, str) and next_mid:
        next_lines.append(f"- Say: “Devam et” (bir sonraki milestone: {next_mid})")
        next_lines.append("- Say: “Duraklat” (otomatik ilerlemeyi durdur)")
        next_lines.append("- Say: “Durumu göster” (özet)")
    else:
        next_lines.append("- Roadmap DONE. Say: “Yeni milestone ekle” (CHG ile) veya “Durumu göster”.")

    final_json = {
        "status": payload.get("status"),
        "next_milestone": next_mid,
        "completed_count": payload.get("completed_count"),
        "evidence": [x for x in [last_evidence] if isinstance(x, str) and x],
        "actions_top": actions_top,
        "workspace_root": str(workspace_root.relative_to(root)) if workspace_root.is_relative_to(root) else str(workspace_root),
    }
    _print_chat_block(
        preview="\n".join(preview_lines),
        result="\n".join(result_lines),
        evidence="\n".join(evidence_lines),
        actions="\n".join(actions_lines),
        next_steps="\n".join(next_lines),
        final_json=final_json,
    )
    return 0


def cmd_project_status(args: argparse.Namespace) -> int:
    root = repo_root()
    roadmap_path = _resolve_under_root(root, Path(str(args.roadmap)))
    workspace_root = _resolve_under_root(root, Path(str(args.workspace_root)))
    mode = str(getattr(args, "mode", "autopilot_chat") or "autopilot_chat").strip()

    try:
        from src.roadmap.orchestrator import status as roadmap_status
    except Exception as e:
        warn("ERROR: failed to import roadmap status: " + str(e))
        return 2

    state_path = workspace_root / ".cache" / "roadmap_state.v1.json"
    status_payload = roadmap_status(roadmap_path=roadmap_path, workspace_root=workspace_root, state_path=state_path)
    next_mid = status_payload.get("next_milestone") if isinstance(status_payload, dict) else None
    preview_obj = _extract_milestone_preview(roadmap_path, milestone_id=str(next_mid) if next_mid else None)

    actions_count, actions_top = _read_actions_top(workspace_root, limit=5)
    overall_status, system_status_path = _read_system_status_summary(workspace_root)
    last_finish = _read_last_finish_evidence(workspace_root)

    completed = status_payload.get("completed") if isinstance(status_payload, dict) else None
    completed_count = len(completed) if isinstance(completed, list) else 0
    quarantine_until = status_payload.get("quarantine_until") if isinstance(status_payload, dict) else None
    backoff_seconds = status_payload.get("backoff_seconds") if isinstance(status_payload, dict) else None

    core_policy_path = workspace_root / "policies" / "policy_core_immutability.v1.json"
    if not core_policy_path.exists():
        core_policy_path = root / "policies" / "policy_core_immutability.v1.json"
    core_policy = {}
    if core_policy_path.exists():
        try:
            core_policy = json.loads(core_policy_path.read_text(encoding="utf-8"))
        except Exception:
            core_policy = {}
    core_enabled = bool(core_policy.get("enabled", True))
    core_mode = str(core_policy.get("default_mode", "locked"))
    allow_obj = core_policy.get("allow_core_writes_only_when", {}) if isinstance(core_policy.get("allow_core_writes_only_when"), dict) else {}
    core_env_var = str(allow_obj.get("env_var", "CORE_UNLOCK"))
    core_env_value = str(allow_obj.get("env_value", "1"))
    core_unlock_requested = str(os.environ.get(core_env_var, "")).strip() == core_env_value
    core_lock = "ENABLED" if core_enabled and core_mode == "locked" else "DISABLED"

    project_root = workspace_root / "project" / "default"
    project_manifest = project_root / "project.manifest.v1.json"
    project_manifest_present = project_manifest.exists()
    project_id = None
    if project_manifest_present:
        try:
            obj = json.loads(project_manifest.read_text(encoding="utf-8"))
            pid = obj.get("project_id") if isinstance(obj, dict) else None
            project_id = str(pid) if isinstance(pid, str) and pid.strip() else None
        except Exception:
            project_id = None

    if quarantine_until:
        result_status = "BLOCKED"
    elif next_mid is None:
        result_status = "DONE_WITH_DEBT" if actions_count > 0 else "DONE"
    else:
        result_status = "OK"

    preview_line = f"next_milestone={preview_obj.get('next_milestone')} title={preview_obj.get('title')}"
    result_line = (
        f"status={result_status} overall={overall_status or 'unknown'} "
        f"backoff_seconds={backoff_seconds} quarantine_until={quarantine_until} "
        f"core_lock={core_lock} core_unlock_requested={core_unlock_requested}"
    )
    evidence_parts: list[str] = []
    if last_finish:
        evidence_parts.append(f"finish_evidence={last_finish}")
    if system_status_path:
        evidence_parts.append(f"system_status={system_status_path}")
    evidence_line = " ".join(evidence_parts) if evidence_parts else "no_evidence_available"

    actions_lines: list[str] = []
    for a in actions_top:
        actions_lines.append(
            f"{a.get('kind')} milestone={a.get('milestone_hint')} severity={a.get('severity')} message={a.get('message')}"
        )
    actions_line = "\n".join(actions_lines) if actions_lines else "no_actions"

    next_steps = "\n".join(
        [
            "Devam et (bir adim ilerlet)",
            "Bitir (otomatik tamamla)",
            "Duraklat (otomatik ilerleme durur)",
            "Durumu goster (ozet)",
        ]
    )

    final_json = {
        "status": result_status,
        "next_milestone": preview_obj.get("next_milestone"),
        "completed_count": completed_count,
        "evidence": [p for p in [last_finish, system_status_path] if p],
        "actions_top": actions_top,
        "workspace_root": str(workspace_root),
        "core_lock": core_lock,
        "core_unlock_requested": core_unlock_requested,
        "project_root": str(project_root),
        "project_manifest_present": project_manifest_present,
        "project_id": project_id,
    }

    if mode == "autopilot_chat":
        _print_chat_block(
            preview=preview_line,
            result=result_line,
            evidence=evidence_line,
            actions=actions_line,
            next_steps=next_steps,
            final_json=final_json,
        )
        return 0

    print(json.dumps(final_json, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_portfolio_status(args: argparse.Namespace) -> int:
    root = repo_root()
    workspace_root = _resolve_under_root(root, Path(str(args.workspace_root)))
    mode = str(getattr(args, "mode", "autopilot_chat") or "autopilot_chat").strip()

    projects = _load_project_manifests(root)
    active_projects = [p.get("project_id") for p in projects if isinstance(p.get("project_id"), str)]
    active_projects = [str(x) for x in active_projects if x]
    active_projects.sort()

    actions_count, actions_top = _read_actions_top(workspace_root, limit=5)
    bench_status = None
    sys_path = workspace_root / ".cache" / "reports" / "system_status.v1.json"
    if sys_path.exists():
        try:
            obj = _load_json(sys_path)
        except Exception:
            obj = {}
        if isinstance(obj, dict):
            sections = obj.get("sections") if isinstance(obj.get("sections"), dict) else {}
            bench = sections.get("benchmark") if isinstance(sections, dict) else None
            if isinstance(bench, dict) and isinstance(bench.get("status"), str):
                bench_status = bench.get("status")

    next_focus = _portfolio_next_focus(str(bench_status or "WARN"), actions_top)
    status = "OK" if active_projects and actions_count == 0 else "WARN"

    report = {
        "version": "v1",
        "generated_at": _now_iso8601(),
        "workspace_root": str(workspace_root),
        "projects_count": len(active_projects),
        "active_projects": active_projects,
        "projects": projects,
        "top_project_debts": actions_top,
        "next_project_focus": next_focus,
        "notes": [],
    }

    out_path = workspace_root / ".cache" / "reports" / "portfolio_status.v1.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    final_json = {
        "status": status,
        "projects_count": len(active_projects),
        "active_projects": active_projects,
        "top_project_debts": actions_top,
        "next_project_focus": next_focus,
        "report_path": str(out_path.relative_to(workspace_root)) if out_path.is_relative_to(workspace_root) else str(out_path),
    }

    if mode == "autopilot_chat":
        preview_lines = [
            f"projects_count={len(active_projects)}",
            f"next_project_focus={next_focus}",
        ]
        result_lines = [
            f"status={status}",
            f"bench_status={bench_status or 'unknown'}",
        ]
        evidence_lines = [f"portfolio_status={final_json.get('report_path')}"]
        actions_lines = []
        for a in actions_top:
            actions_lines.append(
                f"{a.get('kind')} milestone={a.get('milestone_hint')} severity={a.get('severity')} message={a.get('message')}"
            )
        actions_text = "\n".join(actions_lines) if actions_lines else "no_actions"
        next_steps = "\n".join(
            [
                "Devam et (bir adim ilerlet)",
                "Durumu goster (ozet)",
                "Duraklat (otomatik ilerleme durur)",
            ]
        )
        _print_chat_block(
            preview="\n".join(preview_lines),
            result="\n".join(result_lines),
            evidence="\n".join(evidence_lines),
            actions=actions_text,
            next_steps=next_steps,
            final_json=final_json,
        )
        return 0

    print(json.dumps(final_json, ensure_ascii=False, sort_keys=True))
    return 0

def cmd_roadmap_follow(args: argparse.Namespace) -> int:
    root = repo_root()
    roadmap_path = _resolve_under_root(root, Path(str(args.roadmap)))
    workspace_root = _resolve_under_root(root, Path(str(getattr(args, "workspace_root", ".") or ".")))

    until = str(getattr(args, "until", "") or "").strip() or None
    max_steps = int(getattr(args, "max_steps", 1) or 1)
    from src.roadmap.orchestrator import follow as roadmap_follow

    payload = roadmap_follow(
        roadmap_path=roadmap_path,
        workspace_root=workspace_root,
        until=until,
        max_steps=max_steps,
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") in {"OK", "DONE"} else 2


def cmd_roadmap_finish(args: argparse.Namespace) -> int:
    root = repo_root()
    roadmap_path = _resolve_under_root(root, Path(str(args.roadmap)))
    workspace_root = _resolve_under_root(root, Path(str(getattr(args, "workspace_root", ".") or ".")))

    max_minutes = int(getattr(args, "max_minutes", 120) or 120)
    sleep_seconds = int(getattr(args, "sleep_seconds", 120) or 120)
    max_steps_per_iteration = int(getattr(args, "max_steps_per_iteration", 3) or 3)
    auto_apply_chg = bool(str(getattr(args, "auto_apply_chg", "false") or "false").strip().lower() in {"1", "true", "yes"})
    chat = _parse_bool_flag(str(getattr(args, "chat", "false") or "false"), flag_name="chat")

    from src.roadmap.orchestrator import finish as roadmap_finish

    payload = roadmap_finish(
        roadmap_path=roadmap_path,
        workspace_root=workspace_root,
        max_minutes=max_minutes,
        sleep_seconds=sleep_seconds,
        max_steps_per_iteration=max_steps_per_iteration,
        auto_apply_chg=auto_apply_chg,
    )
    if not chat:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0 if payload.get("status") in {"DONE", "DONE_WITH_DEBT", "OK"} else 2

    evidence_paths = payload.get("evidence") if isinstance(payload, dict) else None
    evidence_root = None
    if isinstance(evidence_paths, list) and evidence_paths and isinstance(evidence_paths[0], str):
        evidence_root = (root / evidence_paths[0]).resolve()

    ran_milestones: list[str] = []
    last_follow_evidence: str | None = None
    if isinstance(evidence_root, Path) and evidence_root.exists():
        it_path = evidence_root / "iterations.json"
        try:
            it_obj = _load_json(it_path) if it_path.exists() else {}
        except Exception:
            it_obj = {}
        iterations = it_obj.get("iterations") if isinstance(it_obj, dict) else None
        if isinstance(iterations, list):
            for it in iterations:
                if not isinstance(it, dict):
                    continue
                mid = it.get("milestone_id")
                if isinstance(mid, str):
                    ran_milestones.append(mid)
                follow = it.get("follow")
                if isinstance(follow, dict):
                    ev = follow.get("evidence")
                    if isinstance(ev, list) and ev and isinstance(ev[-1], str):
                        last_follow_evidence = ev[-1]

    actions_count, actions_top = _read_actions_top(workspace_root, limit=3)

    preview_lines = [
        f"- ran_milestones: {', '.join(ran_milestones) if ran_milestones else '(none)'}",
        f"- next_milestone: {payload.get('next_milestone')}",
    ]
    result_lines = [
        f"- status: {payload.get('status')}",
        f"- iterations: {payload.get('iterations')}",
        f"- completed_count: {len(payload.get('completed', [])) if isinstance(payload.get('completed'), list) else None}",
        f"- error_code: {payload.get('error_code')}",
    ]
    evidence_lines = [
        f"- workspace_root: {str(workspace_root.relative_to(root)) if workspace_root.is_relative_to(root) else str(workspace_root)}",
        f"- finish_evidence: {evidence_paths[0] if isinstance(evidence_paths, list) and evidence_paths else None}",
        f"- last_follow_evidence: {last_follow_evidence}",
    ]
    actions_lines = [f"- actions_count: {actions_count}"]
    for a in actions_top:
        actions_lines.append(
            f"- {a.get('action_id')} {a.get('kind')} ({a.get('milestone_hint')}): {a.get('message')}"
        )

    next_lines = []
    if payload.get("status") == "DONE_WITH_DEBT":
        next_lines.append("- Roadmap DONE (with debt). Say: “Durumu göster” (aksiyonları gör) veya “Yeni milestone ekle (CHG)”.")
    elif payload.get("status") == "DONE":
        next_lines.append("- Roadmap DONE. Say: “Durumu göster” veya “Yeni milestone ekle (CHG)”.")
    elif payload.get("status") == "BLOCKED":
        next_lines.append("- BLOCKED. Say: “Durumu göster” (aksiyonları gör) veya “Devam et” (yeniden dene).")
    else:
        next_lines.append("- Say: “Devam et” (kalan milestone’ları ilerlet).")

    final_json = {
        "status": payload.get("status"),
        "next_milestone": payload.get("next_milestone"),
        "completed_count": len(payload.get("completed", [])) if isinstance(payload.get("completed"), list) else None,
        "evidence": [p for p in (evidence_paths or []) if isinstance(p, str)],
        "actions_top": actions_top,
        "workspace_root": str(workspace_root.relative_to(root)) if workspace_root.is_relative_to(root) else str(workspace_root),
    }
    _print_chat_block(
        preview="\n".join(preview_lines),
        result="\n".join(result_lines),
        evidence="\n".join(evidence_lines),
        actions="\n".join(actions_lines),
        next_steps="\n".join(next_lines),
        final_json=final_json,
    )
    return 0 if payload.get("status") in {"DONE", "DONE_WITH_DEBT", "OK"} else 2


def cmd_roadmap_pause(args: argparse.Namespace) -> int:
    root = repo_root()
    workspace_root = _resolve_under_root(root, Path(str(getattr(args, "workspace_root", ".") or ".")))
    reason = str(getattr(args, "reason", "") or "").strip() or "paused"
    from src.roadmap.orchestrator import pause as roadmap_pause

    payload = roadmap_pause(workspace_root=workspace_root, reason=reason)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") == "OK" else 2


def cmd_roadmap_resume(args: argparse.Namespace) -> int:
    root = repo_root()
    workspace_root = _resolve_under_root(root, Path(str(getattr(args, "workspace_root", ".") or ".")))
    from src.roadmap.orchestrator import resume as roadmap_resume

    payload = roadmap_resume(workspace_root=workspace_root)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") == "OK" else 2


def cmd_roadmap_change_new(args: argparse.Namespace) -> int:
    root = repo_root()
    out_path = _resolve_under_root(root, Path(str(args.out)))
    out_path.parent.mkdir(parents=True, exist_ok=True)

    change_id = out_path.stem
    if not change_id.startswith("CHG-") or len(change_id) < 4:
        warn("FAIL error=INVALID_CHANGE_ID hint=Filename must be like CHG-YYYYMMDD-001.json")
        return 2

    ms_id = str(args.milestone).strip()
    if not ms_id:
        warn("FAIL error=INVALID_MILESTONE")
        return 2

    change_type = str(args.type).strip()
    if change_type not in {"add", "remove", "modify"}:
        warn("FAIL error=INVALID_TYPE")
        return 2

    obj = {
        "change_id": change_id,
        "version": "v1",
        "type": change_type,
        "risk_level": "low",
        "target": {"milestone_id": ms_id},
        "rationale": "TODO: describe why this change is needed.",
        "patches": [
            {
                "op": "append_milestone_note",
                "milestone_id": ms_id,
                "note": "TODO: add note content (this is a placeholder).",
            }
        ],
        "gates": ["python ci/validate_schemas.py", "python -m src.ops.manage smoke --level fast"],
    }

    out_path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    out_s = str(out_path.relative_to(root)) if out_path.is_relative_to(root) else str(out_path)
    print(json.dumps({"status": "OK", "out": out_s}, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_roadmap_change_apply(args: argparse.Namespace) -> int:
    root = repo_root()

    change_path = _resolve_under_root(root, Path(str(args.change)))
    if not change_path.exists():
        warn(f"FAIL change={change_path} error=FILE_NOT_FOUND")
        return 2

    roadmap_path = Path(str(getattr(args, "roadmap", "roadmaps/SSOT/roadmap.v1.json") or "roadmaps/SSOT/roadmap.v1.json"))
    roadmap_path = _resolve_under_root(root, roadmap_path)
    if not roadmap_path.exists():
        warn(f"FAIL roadmap={roadmap_path} error=FILE_NOT_FOUND")
        return 2

    change_schema = root / "schemas" / "roadmap-change.schema.json"
    roadmap_schema = root / "schemas" / "roadmap.schema.json"
    if not change_schema.exists():
        warn("FAIL error=MISSING_SCHEMA file=schemas/roadmap-change.schema.json")
        return 2
    if not roadmap_schema.exists():
        warn("FAIL error=MISSING_SCHEMA file=schemas/roadmap.schema.json")
        return 2

    try:
        from src.roadmap.change_proposals import apply_change_to_roadmap_obj, load_json, validate_change
        from src.roadmap.compiler import validate_roadmap
    except Exception as e:
        warn("FAIL error=IMPORT_FAILED message=" + str(e))
        return 2

    try:
        change_obj = load_json(change_path)
    except Exception:
        warn(f"FAIL change={change_path} error=JSON_INVALID")
        return 2

    errors = validate_change(change_obj, change_schema)
    if errors:
        warn("FAIL error=CHANGE_SCHEMA_INVALID message=" + "; ".join(errors))
        return 2

    try:
        roadmap_obj = load_json(roadmap_path)
    except Exception:
        warn(f"FAIL roadmap={roadmap_path} error=JSON_INVALID")
        return 2

    r_errors = validate_roadmap(roadmap_obj, roadmap_schema)
    if r_errors:
        warn("FAIL error=ROADMAP_SCHEMA_INVALID message=" + "; ".join(r_errors))
        return 2

    try:
        updated = apply_change_to_roadmap_obj(roadmap_obj=roadmap_obj, change_obj=change_obj)
    except Exception as e:
        warn("FAIL error=CHANGE_APPLY_FAILED message=" + str(e))
        return 2

    r2_errors = validate_roadmap(updated, roadmap_schema)
    if r2_errors:
        warn("FAIL error=ROADMAP_SCHEMA_INVALID_AFTER_CHANGE message=" + "; ".join(r2_errors))
        return 2

    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text(json.dumps(updated, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    env = os.environ.copy()
    env["ORCH_ROADMAP_RUNNER"] = "1"
    proc_v = subprocess.run([sys.executable, "ci/validate_schemas.py"], cwd=root, text=True, capture_output=True, env=env)
    if proc_v.returncode != 0:
        warn("FAIL error=GATE_VALIDATE_SCHEMAS_FAILED")
        return 2

    proc_smoke = subprocess.run(
        [sys.executable, "-m", "src.ops.manage", "smoke", "--level", "fast"],
        cwd=root,
        text=True,
        capture_output=True,
        env=env,
    )
    if proc_smoke.returncode != 0:
        warn("FAIL error=GATE_SMOKE_FAILED")
        return 2

    print(
        json.dumps(
            {
                "status": "OK",
                "roadmap": str(roadmap_path.relative_to(root)) if roadmap_path.is_relative_to(root) else str(roadmap_path),
                "change": str(change_path.relative_to(root)) if change_path.is_relative_to(root) else str(change_path),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def cmd_workspace_bootstrap(args: argparse.Namespace) -> int:
    root = repo_root()
    src = root / "templates" / "workspace_template"
    if not src.exists() or not src.is_dir():
        warn("FAIL error=TEMPLATE_NOT_FOUND file=templates/workspace_template")
        return 2

    out_root = _resolve_under_root(root, Path(str(args.out)))
    out_root.mkdir(parents=True, exist_ok=True)

    created_files = 0
    for p in sorted(src.rglob("*"), key=lambda x: x.as_posix()):
        rel = p.relative_to(src)
        target = out_root / rel
        if p.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if target.exists():
            warn(f"FAIL error=FILE_EXISTS file={target}")
            return 2
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(p.read_bytes())
        created_files += 1

    print(
        json.dumps(
            {
                "status": "OK",
                "out": str(out_root.relative_to(root)) if out_root.is_relative_to(root) else str(out_root),
                "files_created": created_files,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def cmd_workspace_sanitize(args: argparse.Namespace) -> int:
    root = repo_root()
    ws_root = _resolve_under_root(root, Path(str(args.root)))
    if not ws_root.exists() or not ws_root.is_dir():
        warn(f"FAIL error=WORKSPACE_ROOT_INVALID root={ws_root}")
        return 2

    mode = str(getattr(args, "mode", "customer_clean") or "customer_clean")
    if mode not in {"customer_clean"}:
        warn("FAIL error=INVALID_MODE")
        return 2

    deleted: list[str] = []

    def safe_unlink(path: Path) -> None:
        try:
            path.unlink()
        except Exception:
            return

    def safe_rmtree(path: Path) -> None:
        import shutil

        try:
            shutil.rmtree(path)
        except Exception:
            return

    for rel in [".cache", "evidence", "dist", "exports"]:
        p = ws_root / rel
        if p.exists():
            safe_rmtree(p)
            deleted.append(rel + "/")

    dlq_dir = ws_root / "dlq"
    if dlq_dir.exists() and dlq_dir.is_dir():
        for fp in sorted(dlq_dir.glob("*.json"), key=lambda x: x.name):
            safe_unlink(fp)
            deleted.append(f"dlq/{fp.name}")

    print(
        json.dumps(
            {
                "status": "OK",
                "mode": mode,
                "root": str(ws_root.relative_to(root)) if ws_root.is_relative_to(root) else str(ws_root),
                "deleted_count": len(deleted),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def cmd_promote_scan(args: argparse.Namespace) -> int:
    root = repo_root()
    scan_root = _resolve_under_root(root, Path(str(args.root)))
    if not scan_root.exists() or not scan_root.is_dir():
        warn(f"FAIL error=SCAN_ROOT_INVALID root={scan_root}")
        return 2

    try:
        from src.roadmap.sanitize import findings_fingerprint, scan_directory
    except Exception as e:
        warn("FAIL error=IMPORT_FAILED message=" + str(e))
        return 2

    ok, findings = scan_directory(root=scan_root)
    payload = {
        "status": "OK" if ok else "FAIL",
        "error_code": None if ok else "SANITIZE_VIOLATION",
        "root": str(scan_root.relative_to(root)) if scan_root.is_relative_to(root) else str(scan_root),
        "findings_count": len(findings),
        "findings_fingerprint": findings_fingerprint(findings),
        "examples": [{"path": f.path, "rule": f.rule} for f in findings[:10]],
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if ok else 2


def register_roadmap_subcommands(sub: argparse._SubParsersAction) -> None:
    ap_rm_plan = sub.add_parser("roadmap-plan", help="Compile a roadmap into a deterministic plan.json.")
    ap_rm_plan.add_argument("--roadmap", required=True, help="Path to roadmaps/<...>/roadmap.v1.json")
    ap_rm_plan.add_argument("--out", default=".cache/roadmap_plan.json", help="Output plan path (default: .cache/roadmap_plan.json)")
    ap_rm_plan.add_argument("--workspace-root", default=".", help="Workspace root for path resolution (default: .)")
    ap_rm_plan.add_argument("--milestone", help="Compile only one milestone id (e.g., M2).")
    ap_rm_plan.add_argument("--milestones", help="Compile a comma-separated set of milestone ids (e.g., M2,M3).")
    ap_rm_plan.set_defaults(func=cmd_roadmap_plan)

    ap_rm_apply = sub.add_parser("roadmap-apply", help="Apply a roadmap (dry-run supported; writes roadmap evidence).")
    ap_rm_apply.add_argument("--roadmap", required=True, help="Path to roadmaps/<...>/roadmap.v1.json")
    ap_rm_apply.add_argument("--dry-run", default="true", help="true|false (default: true)")
    ap_rm_apply.add_argument("--dry-run-mode", default="simulate", help="simulate|readonly (default: simulate)")
    ap_rm_apply.add_argument("--workspace-root", default=".", help="Workspace root for path resolution (default: .)")
    ap_rm_apply.add_argument("--milestone", help="Apply only one milestone id (e.g., M2).")
    ap_rm_apply.add_argument("--milestones", help="Apply a comma-separated set of milestone ids (e.g., M2,M3).")
    ap_rm_apply.set_defaults(func=cmd_roadmap_apply)

    ap_rm_status = sub.add_parser("roadmap-status", help="Show current roadmap follow state (next milestone, backoff/quarantine).")
    ap_rm_status.add_argument("--roadmap", required=True, help="Path to roadmaps/<...>/roadmap.v1.json")
    ap_rm_status.add_argument("--workspace-root", required=True, help="Workspace root for state file.")
    ap_rm_status.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_rm_status.set_defaults(func=cmd_roadmap_status)

    ap_proj = sub.add_parser("project-status", help="Show roadmap + cockpit status (AUTOPILOT CHAT format).")
    ap_proj.add_argument("--roadmap", required=True, help="Path to roadmaps/<...>/roadmap.v1.json")
    ap_proj.add_argument("--workspace-root", required=True, help="Workspace root for state/actions/reports.")
    ap_proj.add_argument("--mode", default="autopilot_chat", help="autopilot_chat (default).")
    ap_proj.set_defaults(func=cmd_project_status)

    ap_portfolio = sub.add_parser("portfolio-status", help="Show portfolio status summary (AUTOPILOT CHAT format).")
    ap_portfolio.add_argument("--workspace-root", required=True, help="Workspace root for reports and actions.")
    ap_portfolio.add_argument("--mode", default="autopilot_chat", help="autopilot_chat (default).")
    ap_portfolio.set_defaults(func=cmd_portfolio_status)

    ap_rm_follow = sub.add_parser("roadmap-follow", help="Advance roadmap by running next milestone (readonly dry-run -> apply -> gates).")
    ap_rm_follow.add_argument("--roadmap", required=True, help="Path to roadmaps/<...>/roadmap.v1.json")
    ap_rm_follow.add_argument("--workspace-root", required=True, help="Workspace root for state file and writes.")
    ap_rm_follow.add_argument("--until", default=None, help="Stop after reaching this milestone id (optional).")
    ap_rm_follow.add_argument("--max-steps", type=int, default=1, help="How many milestones to advance (default: 1).")
    ap_rm_follow.set_defaults(func=cmd_roadmap_follow)

    ap_rm_finish = sub.add_parser("roadmap-finish", help="Auto-advance roadmap until DONE/BLOCKED (local, no network).")
    ap_rm_finish.add_argument("--roadmap", required=True, help="Path to roadmaps/<...>/roadmap.v1.json")
    ap_rm_finish.add_argument("--workspace-root", required=True, help="Workspace root for state file and writes.")
    ap_rm_finish.add_argument("--max-minutes", dest="max_minutes", type=int, default=120, help="Max runtime minutes (default: 120).")
    ap_rm_finish.add_argument("--sleep-seconds", dest="sleep_seconds", type=int, default=120, help="Backoff sleep seconds (default: 120).")
    ap_rm_finish.add_argument("--max-steps-per-iteration", dest="max_steps_per_iteration", type=int, default=3, help="Max milestones per loop iteration (default: 3).")
    ap_rm_finish.add_argument("--auto-apply-chg", default="false", help="true|false (default: false).")
    ap_rm_finish.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_rm_finish.set_defaults(func=cmd_roadmap_finish)

    ap_rm_pause = sub.add_parser("roadmap-pause", help="Pause roadmap execution for a workspace (ops kill-switch).")
    ap_rm_pause.add_argument("--workspace-root", required=True, help="Workspace root for state file.")
    ap_rm_pause.add_argument("--reason", default="paused", help="Reason string (default: paused).")
    ap_rm_pause.set_defaults(func=cmd_roadmap_pause)

    ap_rm_resume = sub.add_parser("roadmap-resume", help="Resume roadmap execution for a workspace.")
    ap_rm_resume.add_argument("--workspace-root", required=True, help="Workspace root for state file.")
    ap_rm_resume.set_defaults(func=cmd_roadmap_resume)

    ap_rm_chg_new = sub.add_parser("roadmap-change-new", help="Create a new roadmap change proposal JSON (schema-valid template).")
    ap_rm_chg_new.add_argument("--type", required=True, choices=["add", "remove", "modify"])
    ap_rm_chg_new.add_argument("--milestone", required=True, help="Target milestone id (e.g., M2).")
    ap_rm_chg_new.add_argument("--out", required=True, help="Output change path (e.g., roadmaps/SSOT/changes/CHG-YYYYMMDD-001.json)")
    ap_rm_chg_new.set_defaults(func=cmd_roadmap_change_new)

    ap_rm_chg_apply = sub.add_parser("roadmap-change-apply", help="Apply a roadmap change proposal (fail-closed; runs gates).")
    ap_rm_chg_apply.add_argument("--change", required=True, help="Path to a roadmap change JSON file.")
    ap_rm_chg_apply.add_argument("--roadmap", default="roadmaps/SSOT/roadmap.v1.json", help="Target roadmap file (default: roadmaps/SSOT/roadmap.v1.json).")
    ap_rm_chg_apply.set_defaults(func=cmd_roadmap_change_apply)

    ap_ws_boot = sub.add_parser("workspace-bootstrap", help="Create a new workspace root from templates/workspace_template.")
    ap_ws_boot.add_argument("--out", required=True, help="Target workspace directory (created if missing).")
    ap_ws_boot.set_defaults(func=cmd_workspace_bootstrap)

    ap_ws_sanitize = sub.add_parser("workspace-sanitize", help="Sanitize a workspace root for sharing (local-only; no network).")
    ap_ws_sanitize.add_argument("--root", required=True, help="Workspace root to sanitize.")
    ap_ws_sanitize.add_argument("--mode", default="customer_clean", help="Sanitize mode (default: customer_clean).")
    ap_ws_sanitize.set_defaults(func=cmd_workspace_sanitize)

    ap_promote = sub.add_parser("promote-scan", help="Scan incubator items for tenant/private tokens (fail-closed).")
    ap_promote.add_argument("--root", required=True, help="Path to incubator root directory to scan.")
    ap_promote.set_defaults(func=cmd_promote_scan)
