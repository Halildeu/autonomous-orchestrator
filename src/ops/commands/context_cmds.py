from __future__ import annotations

import argparse
import json
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root, warn
from src.ops.reaper import parse_bool as parse_reaper_bool


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _rel_to_workspace(workspace_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        return str(path.as_posix())


def _write_workspace_json(*, workspace_root: Path, rel_path: Path, payload: dict[str, Any]) -> str:
    abs_path = (workspace_root / rel_path).resolve()
    abs_path.relative_to(workspace_root.resolve())
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return str(rel_path.as_posix())


def _resolve_manual_request_ref(*, workspace_root: Path, request_id_hint: str | None) -> tuple[str, str]:
    manual_dir = workspace_root / ".cache" / "index" / "manual_requests"
    request_id = str(request_id_hint or "").strip()
    if request_id:
        path = manual_dir / f"{request_id}.v1.json"
        if path.exists():
            return (request_id, _rel_to_workspace(workspace_root, path))
    if not manual_dir.exists():
        return (request_id, "")
    paths = sorted([p for p in manual_dir.glob("*.v1.json") if p.is_file()], key=lambda p: p.as_posix())
    if not paths:
        return (request_id, "")
    latest = paths[-1]
    latest_obj = _load_json_if_exists(latest)
    latest_id = latest_obj.get("request_id") if isinstance(latest_obj.get("request_id"), str) else latest.stem
    return (str(latest_id), _rel_to_workspace(workspace_root, latest))


def _find_manual_intake_item(*, intake_obj: dict[str, Any], request_id: str) -> dict[str, Any]:
    items = intake_obj.get("items") if isinstance(intake_obj.get("items"), list) else []
    candidates: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("source_type") or "") != "MANUAL_REQUEST":
            continue
        if str(item.get("source_ref") or "") != request_id:
            continue
        candidates.append(item)
    if not candidates:
        return {}
    candidates_sorted = sorted(
        candidates,
        key=lambda item: (str(item.get("created_at") or ""), str(item.get("intake_id") or "")),
        reverse=True,
    )
    return candidates_sorted[0]


def _load_exec_trace_for_intake(*, workspace_root: Path, intake_id: str) -> dict[str, Any]:
    exec_rel = Path(".cache") / "reports" / "work_intake_exec_ticket.v1.json"
    exec_path = workspace_root / exec_rel
    if not exec_path.exists():
        return {
            "report_path": "",
            "status": "IDLE",
            "matched_entry_found": False,
            "matched_entry_status": "IDLE",
            "applied_count": 0,
            "planned_count": 0,
            "idle_count": 0,
            "ignored_count": 0,
            "skipped_count": 0,
        }
    exec_obj = _load_json_if_exists(exec_path)
    entries = exec_obj.get("entries") if isinstance(exec_obj.get("entries"), list) else []
    matched_entry = None
    if intake_id:
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("intake_id") or "") == intake_id:
                matched_entry = entry
                break
    matched_status = str(matched_entry.get("status") or "") if isinstance(matched_entry, dict) else ""
    return {
        "report_path": str(exec_rel.as_posix()),
        "status": str(exec_obj.get("status") or "UNKNOWN"),
        "matched_entry_found": bool(matched_entry),
        "matched_entry_status": matched_status or "IDLE",
        "matched_entry_action_kind": str(matched_entry.get("action_kind") or "") if isinstance(matched_entry, dict) else "",
        "matched_entry_evidence_paths": matched_entry.get("evidence_paths") if isinstance(matched_entry, dict) else [],
        "applied_count": int(exec_obj.get("applied_count") or 0),
        "planned_count": int(exec_obj.get("planned_count") or 0),
        "idle_count": int(exec_obj.get("idle_count") or 0),
        "ignored_count": int(exec_obj.get("ignored_count") or 0),
        "skipped_count": int(exec_obj.get("skipped_count") or 0),
    }


def _load_context_orchestration_policy(*, core_root: Path, workspace_root: Path) -> dict[str, Any]:
    ws_policy = workspace_root / "policies" / "policy_context_orchestration.v1.json"
    core_policy = core_root / "policies" / "policy_context_orchestration.v1.json"
    for candidate in (ws_policy, core_policy):
        if not candidate.exists():
            continue
        obj = _load_json_if_exists(candidate)
        if obj:
            return obj
    return {}


def _resolve_required_input_path(*, required: str, core_root: Path, workspace_root: Path) -> Path:
    known_map = {
        "system_status.v1.json": workspace_root / ".cache" / "reports" / "system_status.v1.json",
        "work_intake.v1.json": workspace_root / ".cache" / "index" / "work_intake.v1.json",
        "session-context.schema.json": core_root / "schemas" / "session-context.schema.json",
        "context-pack.schema.v1.json": core_root / "schemas" / "context-pack.schema.v1.json",
    }
    if required in known_map:
        return known_map[required]
    if required.startswith(".cache/"):
        return workspace_root / Path(required)
    ws_candidate = workspace_root / Path(required)
    core_candidate = core_root / Path(required)
    if ws_candidate.exists():
        return ws_candidate
    if core_candidate.exists():
        return core_candidate
    if str(required).endswith(".schema.json"):
        return core_root / "schemas" / Path(required).name
    return ws_candidate


def _write_context_orchestration_artifacts(
    *,
    workspace_root: Path,
    core_root: Path,
    mode: str,
    strict_mode: bool,
    run_status: str,
    run_error_code: str | None,
    manual_request_id: str | None,
    manual_submit_res: dict[str, Any] | None,
    build_res: dict[str, Any],
    route_res: dict[str, Any],
    intake_obj: dict[str, Any],
    work_intake_path: str | None,
    system_status_path: str | None,
    system_status_obj: dict[str, Any],
) -> dict[str, str]:
    request_id_hint = str(manual_request_id or "").strip()
    if not request_id_hint:
        for source in (build_res, route_res):
            maybe_req = source.get("request_id") if isinstance(source, dict) else None
            if isinstance(maybe_req, str) and maybe_req.strip():
                request_id_hint = maybe_req.strip()
                break

    request_id, manual_request_path = _resolve_manual_request_ref(
        workspace_root=workspace_root,
        request_id_hint=request_id_hint or None,
    )
    matched_intake = _find_manual_intake_item(intake_obj=intake_obj, request_id=request_id)
    intake_id = str(matched_intake.get("intake_id") or "") if isinstance(matched_intake, dict) else ""

    context_pack_path = build_res.get("context_pack_path") if isinstance(build_res.get("context_pack_path"), str) else ""
    router_result_rel = str(Path(".cache") / "reports" / "context_pack_router_result.v1.json")
    work_intake_rel = str(work_intake_path) if isinstance(work_intake_path, str) and work_intake_path else ""
    system_status_rel = str(system_status_path) if isinstance(system_status_path, str) and system_status_path else ""

    exec_trace = _load_exec_trace_for_intake(workspace_root=workspace_root, intake_id=intake_id)
    system_overall = str(system_status_obj.get("overall_status") or "")
    if not system_overall and system_status_rel:
        sys_obj = _load_json_if_exists((workspace_root / system_status_rel).resolve())
        system_overall = str(sys_obj.get("overall_status") or "")

    trace_missing: list[str] = []
    if not request_id:
        trace_missing.append("request_id")
    if not context_pack_path:
        trace_missing.append("context_pack_path")
    if not work_intake_rel:
        trace_missing.append("work_intake_path")
    if not system_status_rel:
        trace_missing.append("system_status_path")
    trace_status = "OK" if not trace_missing else "WARN"

    trace_payload: dict[str, Any] = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "mode": mode,
        "status": trace_status,
        "request": {
            "request_id": request_id,
            "manual_request_path": manual_request_path,
            "submitted_in_run": bool(isinstance(manual_submit_res, dict) and manual_submit_res.get("request_id")),
            "submit_status": str(manual_submit_res.get("status") or "") if isinstance(manual_submit_res, dict) else "",
        },
        "routing": {
            "context_pack_path": context_pack_path,
            "context_router_result_path": router_result_rel,
            "bucket": str(route_res.get("bucket") or ""),
            "action": str(route_res.get("action") or ""),
            "severity": str(route_res.get("severity") or ""),
            "priority": str(route_res.get("priority") or ""),
            "router_status": str(route_res.get("status") or ""),
        },
        "intake": {
            "work_intake_path": work_intake_rel,
            "matched_intake_found": bool(matched_intake),
            "matched_intake_id": intake_id,
            "bucket": str(matched_intake.get("bucket") or "") if isinstance(matched_intake, dict) else "",
            "severity": str(matched_intake.get("severity") or "") if isinstance(matched_intake, dict) else "",
            "priority": str(matched_intake.get("priority") or "") if isinstance(matched_intake, dict) else "",
            "status": str(matched_intake.get("status") or "") if isinstance(matched_intake, dict) else "",
        },
        "execution": exec_trace,
        "system_status": {
            "system_status_path": system_status_rel,
            "overall_status": system_overall,
        },
        "missing": trace_missing,
        "notes": ["PROGRAM_LED=true", "trace=request_intake_to_exec"],
    }
    trace_rel = _write_workspace_json(
        workspace_root=workspace_root,
        rel_path=Path(".cache") / "reports" / "request_intake_to_exec_trace.v1.json",
        payload=trace_payload,
    )

    policy = _load_context_orchestration_policy(core_root=core_root, workspace_root=workspace_root)
    required_inputs = policy.get("inputs", {}).get("required") if isinstance(policy.get("inputs"), dict) else []
    required_inputs = [str(x) for x in required_inputs if isinstance(x, str) and x]
    input_checks: list[dict[str, Any]] = []
    missing_required_inputs: list[str] = []
    for req in required_inputs:
        target = _resolve_required_input_path(required=req, core_root=core_root, workspace_root=workspace_root)
        exists = target.exists()
        target_path = str(target.as_posix())
        try:
            target_path = target.relative_to(workspace_root).as_posix()
        except Exception:
            try:
                target_path = target.relative_to(core_root).as_posix()
            except Exception:
                target_path = str(target.as_posix())
        input_checks.append({"id": req, "path": target_path, "exists": exists})
        if not exists:
            missing_required_inputs.append(req)

    max_actions = 8
    limits = policy.get("limits") if isinstance(policy.get("limits"), dict) else {}
    if isinstance(limits.get("max_recommended_next_actions"), int):
        max_actions = max(1, int(limits.get("max_recommended_next_actions")))
    next_actions = route_res.get("next_actions") if isinstance(route_res.get("next_actions"), list) else []
    next_actions = [str(x) for x in next_actions if isinstance(x, str) and x][:max_actions]

    context_status = str(run_status or "WARN")
    if context_status not in {"OK", "WARN", "IDLE", "FAIL"}:
        context_status = "WARN"
    guardrails = policy.get("guardrails") if isinstance(policy.get("guardrails"), dict) else {}
    report_only_on_missing = bool(guardrails.get("report_only_on_missing_context", True))
    if missing_required_inputs and context_status == "OK":
        context_status = "WARN"
    if strict_mode and missing_required_inputs and not report_only_on_missing:
        context_status = "FAIL"

    status_payload: dict[str, Any] = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "extension_id": "PRJ-CONTEXT-ORCHESTRATION",
        "mode": mode,
        "strict_mode": strict_mode,
        "status": context_status,
        "single_gate_status": str(run_status or ""),
        "single_gate_error_code": str(run_error_code or ""),
        "request_id": request_id,
        "context_pack_id": str(route_res.get("context_pack_id") or build_res.get("context_pack_id") or ""),
        "bucket": str(route_res.get("bucket") or ""),
        "action": str(route_res.get("action") or ""),
        "required_inputs": input_checks,
        "missing_required_inputs": missing_required_inputs,
        "artifacts": {
            "request_intake_to_exec_trace_path": trace_rel,
            "context_pack_path": context_pack_path,
            "context_router_result_path": router_result_rel,
            "work_intake_path": work_intake_rel,
            "system_status_path": system_status_rel,
        },
        "next_actions": next_actions,
        "focus": policy.get("focus") if isinstance(policy.get("focus"), dict) else {},
        "limits": limits if isinstance(limits, dict) else {},
        "notes": ["PROGRAM_LED=true", "network_default=false"],
    }
    if missing_required_inputs:
        status_payload["notes"].append("missing_required_inputs=true")
    status_rel = _write_workspace_json(
        workspace_root=workspace_root,
        rel_path=Path(".cache") / "reports" / "context_orchestration_status.v1.json",
        payload=status_payload,
    )
    return {
        "request_id": request_id,
        "request_intake_to_exec_trace_path": trace_rel,
        "context_orchestration_status_path": status_rel,
    }


def cmd_manual_request_submit(args: argparse.Namespace) -> int:
    root = repo_root()
    workspace_arg = str(args.workspace_root).strip()
    if not workspace_arg:
        warn("FAIL error=WORKSPACE_ROOT_REQUIRED")
        return 2

    ws = Path(workspace_arg)
    ws = (root / ws).resolve() if not ws.is_absolute() else ws.resolve()
    if not ws.exists() or not ws.is_dir():
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    text = str(args.text or "")
    if args.text_file:
        text_path = Path(str(args.text_file))
        text_path = (root / text_path).resolve() if not text_path.is_absolute() else text_path.resolve()
        if not text_path.exists():
            warn("FAIL error=TEXT_FILE_MISSING")
            return 2
        text = text_path.read_text(encoding="utf-8")

    payload_in: dict[str, Any] = {}
    if args.in_json:
        in_path = Path(str(args.in_json))
        in_path = (root / in_path).resolve() if not in_path.is_absolute() else in_path.resolve()
        if not in_path.exists():
            warn("FAIL error=INPUT_JSON_MISSING")
            return 2
        try:
            payload_in = json.loads(in_path.read_text(encoding="utf-8"))
        except Exception:
            warn("FAIL error=INPUT_JSON_INVALID")
            return 2

    artifact_type = str(args.artifact_type or payload_in.get("artifact_type") or "")
    domain = str(args.domain or payload_in.get("domain") or "")
    kind = str(args.kind or payload_in.get("kind") or "unspecified")
    impact_scope = str(args.impact_scope or payload_in.get("impact_scope") or "workspace-only")
    requires_core_change = payload_in.get("requires_core_change")
    if args.requires_core_change is not None:
        requires_core_change = bool(args.requires_core_change)
    tenant_id = str(args.tenant_id or payload_in.get("tenant_id") or "") or None
    source_type = str(args.source_type or (payload_in.get("source") or {}).get("type") or "human")
    source_channel = str(args.source_channel or (payload_in.get("source") or {}).get("channel") or "") or None
    source_user_id = str(args.source_user_id or (payload_in.get("source") or {}).get("user_id") or "") or None

    if not text:
        text = str(payload_in.get("text") or "")
    if not text:
        warn("FAIL error=TEXT_REQUIRED")
        return 2
    if not artifact_type or not domain:
        warn("FAIL error=ARTIFACT_TYPE_DOMAIN_REQUIRED")
        return 2

    attachments = payload_in.get("attachments") if isinstance(payload_in.get("attachments"), list) else []
    if args.attachments_json:
        try:
            attachments = json.loads(str(args.attachments_json))
        except Exception:
            attachments = []
    constraints = payload_in.get("constraints") if isinstance(payload_in.get("constraints"), dict) else {}
    if args.constraints_json:
        try:
            constraints = json.loads(str(args.constraints_json))
        except Exception:
            constraints = constraints

    tags = payload_in.get("tags") if isinstance(payload_in.get("tags"), list) else []
    if args.tags:
        tags = [t for t in str(args.tags).split(",") if t.strip()]

    try:
        dry_run = parse_reaper_bool(str(args.dry_run))
    except ValueError:
        warn("FAIL error=INVALID_DRY_RUN")
        return 2

    from src.ops.manual_request_cli import submit_manual_request

    res = submit_manual_request(
        workspace_root=ws,
        text=text,
        artifact_type=artifact_type,
        domain=domain,
        kind=kind,
        impact_scope=impact_scope,
        tenant_id=tenant_id,
        source_type=source_type,
        source_channel=source_channel,
        source_user_id=source_user_id,
        attachments=attachments if isinstance(attachments, list) else None,
        constraints=constraints if isinstance(constraints, dict) else None,
        requires_core_change=requires_core_change if isinstance(requires_core_change, bool) else None,
        tags=tags if isinstance(tags, list) else None,
        dry_run=bool(dry_run),
    )
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") in {"OK", "IDLE"} else 2


def cmd_context_pack_build(args: argparse.Namespace) -> int:
    root = repo_root()
    workspace_arg = str(args.workspace_root).strip()
    if not workspace_arg:
        warn("FAIL error=WORKSPACE_ROOT_REQUIRED")
        return 2

    ws = Path(workspace_arg)
    ws = (root / ws).resolve() if not ws.is_absolute() else ws.resolve()
    if not ws.exists() or not ws.is_dir():
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    request_id = str(args.request_id or "").strip() or None
    mode = str(args.mode or "summary").strip().lower()
    if mode not in {"summary", "detail"}:
        warn("FAIL error=INVALID_MODE")
        return 2

    from src.ops.context_pack_router import build_context_pack

    res = build_context_pack(workspace_root=ws, request_id=request_id, mode=mode)
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") in {"OK", "WARN", "IDLE"} else 2


def cmd_context_pack_route(args: argparse.Namespace) -> int:
    root = repo_root()
    workspace_arg = str(args.workspace_root).strip()
    if not workspace_arg:
        warn("FAIL error=WORKSPACE_ROOT_REQUIRED")
        return 2

    ws = Path(workspace_arg)
    ws = (root / ws).resolve() if not ws.is_absolute() else ws.resolve()
    if not ws.exists() or not ws.is_dir():
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    pack_arg = str(args.context_pack or "").strip()
    context_pack_path = None
    if pack_arg:
        pack_path = Path(pack_arg)
        pack_path = (ws / pack_path).resolve() if not pack_path.is_absolute() else pack_path.resolve()
        context_pack_path = pack_path

    from src.ops.context_pack_router import build_context_pack, route_context_pack

    if context_pack_path is None and args.request_id:
        build_res = build_context_pack(workspace_root=ws, request_id=str(args.request_id), mode="detail")
        pack_rel = build_res.get("context_pack_path") if isinstance(build_res, dict) else None
        if isinstance(pack_rel, str) and pack_rel:
            context_pack_path = (ws / pack_rel).resolve()

    res = route_context_pack(workspace_root=ws, context_pack_path=context_pack_path)
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") in {"OK", "WARN", "IDLE"} else 2


def cmd_context_pack_triangulate(args: argparse.Namespace) -> int:
    root = repo_root()
    workspace_arg = str(args.workspace_root).strip()
    if not workspace_arg:
        warn("FAIL error=WORKSPACE_ROOT_REQUIRED")
        return 2

    ws = Path(workspace_arg)
    ws = (root / ws).resolve() if not ws.is_absolute() else ws.resolve()
    if not ws.exists() or not ws.is_dir():
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    responses_arg = str(args.responses or "").strip()
    responses = [r.strip() for r in responses_arg.split(",") if r.strip()]
    if not responses:
        warn("FAIL error=RESPONSES_REQUIRED")
        return 2

    out = str(args.out) if args.out else ""

    from src.ops.context_pack_triangulate import run_context_pack_triangulate

    res = run_context_pack_triangulate(workspace_root=ws, responses=responses, out=out or None)
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    status = res.get("status") if isinstance(res, dict) else None
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_context_router_check(args: argparse.Namespace) -> int:
    root = repo_root()
    workspace_arg = str(args.workspace_root).strip()
    if not workspace_arg:
        warn("FAIL error=WORKSPACE_ROOT_REQUIRED")
        return 2

    ws = Path(workspace_arg)
    ws = (root / ws).resolve() if not ws.is_absolute() else ws.resolve()
    if not ws.exists() or not ws.is_dir():
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    chat = parse_reaper_bool(str(args.chat))
    detail = parse_reaper_bool(str(args.detail))
    dry_run = getattr(args, "dry_run", "false")
    mode = str(args.mode or "report").strip().lower()
    if mode not in {"report", "strict"}:
        warn("FAIL error=INVALID_MODE")
        return 2
    strict_mode = mode == "strict"

    manual_request_id = str(args.request_id or "").strip() or None
    manual_submit_res = None
    if args.text or args.in_json or args.text_file:
        submit_ns = argparse.Namespace(
            workspace_root=str(ws),
            text=args.text,
            text_file=args.text_file,
            in_json=args.in_json,
            artifact_type=args.artifact_type,
            domain=args.domain,
            kind=args.kind,
            impact_scope=args.impact_scope,
            requires_core_change=args.requires_core_change,
            tenant_id=args.tenant_id,
            source_type=args.source_type,
            source_channel=args.source_channel,
            source_user_id=args.source_user_id,
            attachments_json=args.attachments_json,
            constraints_json=args.constraints_json,
            tags=args.tags,
            dry_run=dry_run,
        )
        buf = StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            cmd_manual_request_submit(submit_ns)
        try:
            manual_submit_res = json.loads(buf.getvalue().strip() or "{}")
        except Exception:
            manual_submit_res = None
        if isinstance(manual_submit_res, dict) and isinstance(manual_submit_res.get("request_id"), str):
            manual_request_id = str(manual_submit_res.get("request_id"))

    from src.ops.context_pack_router import build_context_pack, route_context_pack
    from src.ops.work_intake_from_sources import run_work_intake_build
    from src.ops.system_status_report import run_system_status

    build_mode = "detail" if strict_mode else "summary"
    build_res = build_context_pack(workspace_root=ws, request_id=manual_request_id, mode=build_mode)
    pack_rel = build_res.get("context_pack_path") if isinstance(build_res, dict) else None
    pack_path = (ws / pack_rel).resolve() if isinstance(pack_rel, str) and pack_rel else None
    route_res = route_context_pack(workspace_root=ws, context_pack_path=pack_path)

    intake_res = run_work_intake_build(workspace_root=ws)
    work_intake_path = intake_res.get("work_intake_path") if isinstance(intake_res, dict) else None
    intake_obj: dict[str, Any] = {}
    if isinstance(work_intake_path, str) and work_intake_path:
        intake_path_abs = (ws / work_intake_path).resolve()
        try:
            intake_obj = json.loads(intake_path_abs.read_text(encoding="utf-8"))
        except Exception:
            intake_obj = {}

    sys_res = run_system_status(workspace_root=ws, core_root=root, dry_run=False)
    sys_out = sys_res.get("out_json") if isinstance(sys_res, dict) else None
    sys_rel = None
    if isinstance(sys_out, str):
        sys_rel = Path(sys_out).resolve()
        try:
            sys_rel = sys_rel.relative_to(ws)
        except Exception:
            sys_rel = None

    status = str(route_res.get("status") or "WARN")
    error_code = route_res.get("error_code") if isinstance(route_res, dict) else None

    plan_policy = intake_obj.get("plan_policy") if isinstance(intake_obj.get("plan_policy"), str) else "optional"
    items = intake_obj.get("items") if isinstance(intake_obj.get("items"), list) else []
    if plan_policy == "required" and items:
        plan_dir = ws / ".cache" / "reports" / "chg"
        plans = list(plan_dir.glob("CHG-INTAKE-*.plan.json")) if plan_dir.exists() else []
        if not plans:
            status = "FAIL" if strict_mode else "IDLE"
            error_code = "NO_PLAN_FOUND"

    strict_doc_nav_rel = str(Path(".cache") / "reports" / "doc_graph_report.strict.v1.json")
    strict_doc_nav_path = ws / strict_doc_nav_rel
    if strict_mode:
        if not strict_doc_nav_path.exists():
            status = "FAIL"
            error_code = "DOC_NAV_STRICT_MISSING"
        elif status != "OK":
            status = "FAIL"
            if not isinstance(error_code, str) or not error_code:
                error_code = "STRICT_ROUTER_NOT_OK"

    system_status_rel = str(sys_rel) if isinstance(sys_rel, Path) else None
    artifacts = _write_context_orchestration_artifacts(
        workspace_root=ws,
        core_root=root,
        mode=mode,
        strict_mode=strict_mode,
        run_status=status,
        run_error_code=error_code if isinstance(error_code, str) else None,
        manual_request_id=manual_request_id,
        manual_submit_res=manual_submit_res if isinstance(manual_submit_res, dict) else None,
        build_res=build_res if isinstance(build_res, dict) else {},
        route_res=route_res if isinstance(route_res, dict) else {},
        intake_obj=intake_obj if isinstance(intake_obj, dict) else {},
        work_intake_path=work_intake_path if isinstance(work_intake_path, str) else None,
        system_status_path=system_status_rel,
        system_status_obj=sys_res if isinstance(sys_res, dict) else {},
    )
    resolved_request_id = str(artifacts.get("request_id") or manual_request_id or "")

    payload = {
        "status": status,
        "error_code": error_code,
        "workspace_root": str(ws),
        "request_id": resolved_request_id,
        "context_pack_path": pack_rel,
        "context_router_result_path": str(Path(".cache") / "reports" / "context_pack_router_result.v1.json"),
        "work_intake_path": work_intake_path,
        "system_status_path": system_status_rel,
        "request_intake_to_exec_trace_path": artifacts.get("request_intake_to_exec_trace_path"),
        "context_orchestration_status_path": artifacts.get("context_orchestration_status_path"),
        "notes": [
            f"mode={mode}",
            "PROGRAM_LED=true",
            f"build_mode={build_mode}",
            f"strict_doc_nav_path={strict_doc_nav_rel}" if strict_mode else "",
            "context_orchestration_artifacts=generated",
        ],
    }
    payload["notes"] = [str(x) for x in payload.get("notes", []) if isinstance(x, str) and x]

    if chat:
        print("PREVIEW:")
        print("PROGRAM-LED: manual-request-submit + context-pack-build + context-pack-route + work-intake-check + system-status")
        print(f"workspace_root={payload.get('workspace_root')}")
        print(f"mode={mode}")
        if resolved_request_id:
            print(f"request_id={resolved_request_id}")
        print("RESULT:")
        print(f"status={status} bucket={route_res.get('bucket')} action={route_res.get('action')}")
        if error_code:
            print(f"error_code={error_code}")
        print("EVIDENCE:")
        for p in [
            manual_submit_res.get("stored_path") if isinstance(manual_submit_res, dict) else None,
            pack_rel,
            payload.get("context_router_result_path"),
            work_intake_path,
            payload.get("system_status_path"),
            payload.get("request_intake_to_exec_trace_path"),
            payload.get("context_orchestration_status_path"),
        ]:
            if p:
                print(str(p))
        print("ACTIONS:")
        next_actions = route_res.get("next_actions") if isinstance(route_res.get("next_actions"), list) else []
        if not detail:
            next_actions = next_actions[:5]
        if next_actions:
            print("\n".join([str(x) for x in next_actions]))
        else:
            print("no_actions")
        print("NEXT:")
        print("Devam et / Durumu goster / Duraklat")

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def register_context_subcommands(parent: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    ap_manual = parent.add_parser("manual-request-submit", help="Submit manual request (workspace-scoped, program-led).")
    ap_manual.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_manual.add_argument("--text", default="", help="Request text (short).")
    ap_manual.add_argument("--text-file", default="", help="Path to request text file.")
    ap_manual.add_argument("--in", dest="in_json", default="", help="Path to JSON input payload (optional).")
    ap_manual.add_argument("--artifact-type", default="", help="Artifact type (required if --in not provided).")
    ap_manual.add_argument("--domain", default="", help="Domain label (required if --in not provided).")
    ap_manual.add_argument(
        "--kind",
        default="unspecified",
        help="support|question|minor_fix|feature|refactor|new_project|strategy|multi-quarter|context-router|doc-fix|note|unspecified",
    )
    ap_manual.add_argument(
        "--impact-scope",
        default="workspace-only",
        help="doc-only|workspace-only|core-change|external-change (default: workspace-only)",
    )
    ap_manual.add_argument("--requires-core-change", action="store_true", help="Flag: requires core change.")
    ap_manual.add_argument("--tenant-id", default="", help="Optional tenant id.")
    ap_manual.add_argument("--source-type", default="human", help="human|llm|system|api|webhook|ui|chat")
    ap_manual.add_argument("--source-channel", default="", help="Optional source channel.")
    ap_manual.add_argument("--source-user-id", default="", help="Optional source user id.")
    ap_manual.add_argument("--attachments-json", default="", help="JSON array for attachments (optional).")
    ap_manual.add_argument("--constraints-json", default="", help="JSON object for constraints (optional).")
    ap_manual.add_argument("--tags", default="", help="Comma-separated tags (optional).")
    ap_manual.add_argument("--dry-run", default="false", help="true|false (default: false).")
    ap_manual.set_defaults(func=cmd_manual_request_submit)

    ap_pack = parent.add_parser("context-pack-build", help="Build context pack (pointer graph).")
    ap_pack.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_pack.add_argument("--request-id", default="", help="Manual request id (optional).")
    ap_pack.add_argument("--mode", default="summary", help="summary|detail (default: summary).")
    ap_pack.set_defaults(func=cmd_context_pack_build)

    ap_route = parent.add_parser("context-pack-route", help="Route context pack to bucket/action.")
    ap_route.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_route.add_argument("--context-pack", default="", help="Path to context pack JSON (optional).")
    ap_route.add_argument("--request-id", default="", help="Manual request id (optional).")
    ap_route.set_defaults(func=cmd_context_pack_route)

    ap_triang = parent.add_parser(
        "context-pack-triangulate",
        help="Merge context pack candidates (3 responses) deterministically.",
    )
    ap_triang.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_triang.add_argument("--responses", required=True, help="Comma-separated response JSON paths.")
    ap_triang.add_argument("--out", default="", help="Optional output path for merged context pack JSON.")
    ap_triang.set_defaults(func=cmd_context_pack_triangulate)

    ap_router = parent.add_parser("context-router-check", help="Single gate: submit + build + route + intake + status.")
    ap_router.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_router.add_argument("--request-id", default="", help="Manual request id (optional).")
    ap_router.add_argument("--text", default="", help="Request text (short).")
    ap_router.add_argument("--text-file", default="", help="Path to request text file.")
    ap_router.add_argument("--in", dest="in_json", default="", help="Path to JSON input payload (optional).")
    ap_router.add_argument("--artifact-type", default="", help="Artifact type (required if --in not provided).")
    ap_router.add_argument("--domain", default="", help="Domain label (required if --in not provided).")
    ap_router.add_argument(
        "--kind",
        default="unspecified",
        help="support|question|minor_fix|feature|refactor|new_project|strategy|multi-quarter|context-router|doc-fix|note|unspecified",
    )
    ap_router.add_argument(
        "--impact-scope",
        default="workspace-only",
        help="doc-only|workspace-only|core-change|external-change (default: workspace-only)",
    )
    ap_router.add_argument("--requires-core-change", action="store_true", help="Flag: requires core change.")
    ap_router.add_argument("--tenant-id", default="", help="Optional tenant id.")
    ap_router.add_argument("--source-type", default="human", help="human|llm|system|api|webhook|ui|chat")
    ap_router.add_argument("--source-channel", default="", help="Optional source channel.")
    ap_router.add_argument("--source-user-id", default="", help="Optional source user id.")
    ap_router.add_argument("--attachments-json", default="", help="JSON array for attachments (optional).")
    ap_router.add_argument("--constraints-json", default="", help="JSON object for constraints (optional).")
    ap_router.add_argument("--tags", default="", help="Comma-separated tags (optional).")
    ap_router.add_argument("--mode", default="report", help="report|strict (default: report).")
    ap_router.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_router.add_argument("--detail", default="false", help="true|false (default: false).")
    ap_router.add_argument("--dry-run", default="false", help="true|false (default: false).")
    ap_router.set_defaults(func=cmd_context_router_check)

    ap_ns_bootstrap = parent.add_parser(
        "north-star-theme-bootstrap",
        help="Bootstrap theme/subtheme via LLM consult (subject open).",
    )
    ap_ns_bootstrap.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_ns_bootstrap.add_argument("--subject-id", required=True, help="Subject id (e.g., ethics_case_management).")
    ap_ns_bootstrap.add_argument(
        "--providers",
        default="",
        help="Comma-separated providers (default: openai,google,claude,deepseek,qwen,xai).",
    )
    ap_ns_bootstrap.add_argument("--approve", action="store_true", help="Mark result ACTIVE (default: PROPOSED).")
    from src.ops.north_star_theme_bootstrap import cmd_north_star_theme_bootstrap

    ap_ns_bootstrap.set_defaults(func=cmd_north_star_theme_bootstrap)

    ap_ns_seed = parent.add_parser(
        "north-star-theme-seed",
        help="Seed theme/subtheme suggestions via GPT-5.2 (PROPOSED only).",
    )
    ap_ns_seed.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_ns_seed.add_argument("--subject-id", required=True, help="Subject id (e.g., ethics_program).")
    ap_ns_seed.add_argument("--provider-id", default="openai", help="Provider id (default: openai).")
    ap_ns_seed.add_argument("--model", default="gpt-5.2", help="Model id (default: gpt-5.2).")
    ap_ns_seed.add_argument("--max-tokens", default="5000", help="Max tokens (default: 5000).")
    from src.ops.north_star_theme_suggestions import cmd_north_star_theme_seed

    ap_ns_seed.set_defaults(func=cmd_north_star_theme_seed)

    ap_ns_consult = parent.add_parser(
        "north-star-theme-consult",
        help="Consult LLMs for suggestions only (missing/merge/too few/too many).",
    )
    ap_ns_consult.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_ns_consult.add_argument("--subject-id", required=True, help="Subject id (e.g., ethics_program).")
    ap_ns_consult.add_argument(
        "--providers",
        default="",
        help="Comma-separated providers (default: openai,google,claude,deepseek,qwen,xai).",
    )
    ap_ns_consult.add_argument("--focus-type", default="", help="Optional focus type (theme|subtheme).")
    ap_ns_consult.add_argument("--focus-id", default="", help="Optional focus id.")
    ap_ns_consult.add_argument("--comment", default="", help="Optional user comment/context.")
    ap_ns_consult.add_argument("--max-tokens", default="2500", help="Max tokens (default: 2500).")
    from src.ops.north_star_theme_suggestions import cmd_north_star_theme_consult

    ap_ns_consult.set_defaults(func=cmd_north_star_theme_consult)

    ap_ns_apply = parent.add_parser(
        "north-star-theme-suggestion-apply",
        help="Apply suggestion (ACCEPT/REJECT/MERGE) with optional comment.",
    )
    ap_ns_apply.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_ns_apply.add_argument("--suggestion-id", required=True, help="Suggestion id.")
    ap_ns_apply.add_argument("--action", required=True, help="ACCEPT|REJECT|MERGE")
    ap_ns_apply.add_argument("--comment", default="", help="Optional reviewer comment.")
    ap_ns_apply.add_argument("--merge-target", default="", help="Optional merge target theme id.")
    from src.ops.north_star_theme_suggestions import cmd_north_star_theme_suggestion_apply

    ap_ns_apply.set_defaults(func=cmd_north_star_theme_suggestion_apply)

    ap_ns_ux = parent.add_parser(
        "north-star-ux-build",
        help="Build UX outputs from North Star subject catalog (ux-catalog, ux-blueprint, ux-interaction-matrix).",
    )
    ap_ns_ux.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_ns_ux.add_argument("--subject-id", required=True, help="Subject id (e.g., ui_kutuphane_sistemi).")
    ap_ns_ux.add_argument("--out-dir", default=".cache/index/ux", help="Output directory under workspace.")
    from src.ops.north_star_ux_build import cmd_north_star_ux_build

    ap_ns_ux.set_defaults(func=cmd_north_star_ux_build)
