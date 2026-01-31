from __future__ import annotations

import argparse
import json
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root, warn
from src.ops.reaper import parse_bool as parse_reaper_bool


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

    build_res = build_context_pack(workspace_root=ws, request_id=manual_request_id, mode="summary")
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
            status = "IDLE"
            error_code = "NO_PLAN_FOUND"

    payload = {
        "status": status,
        "error_code": error_code,
        "workspace_root": str(ws),
        "request_id": manual_request_id,
        "context_pack_path": pack_rel,
        "context_router_result_path": str(Path(".cache") / "reports" / "context_pack_router_result.v1.json"),
        "work_intake_path": work_intake_path,
        "system_status_path": str(sys_rel) if isinstance(sys_rel, Path) else None,
        "notes": ["PROGRAM_LED=true"],
    }

    if chat:
        print("PREVIEW:")
        print("PROGRAM-LED: manual-request-submit + context-pack-build + context-pack-route + work-intake-check + system-status")
        print(f"workspace_root={payload.get('workspace_root')}")
        if manual_request_id:
            print(f"request_id={manual_request_id}")
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
