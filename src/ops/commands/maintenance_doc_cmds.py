from __future__ import annotations

import argparse
import json
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root, warn
from src.ops.reaper import parse_bool as parse_reaper_bool


def cmd_doc_graph(args: argparse.Namespace) -> int:
    root = repo_root()
    ws_arg = str(args.workspace_root).strip()
    if not ws_arg:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    ws_path = Path(ws_arg)
    if not ws_path.is_absolute():
        ws_path = (root / ws_path).resolve()

    mode = str(args.mode).strip().lower()
    if mode not in {"report", "strict"}:
        warn("FAIL error=INVALID_MODE")
        return 2

    out_arg = str(args.out).strip() if args.out else ".cache/reports/doc_graph_report.v1.json"
    out_path = Path(out_arg)
    if not out_path.is_absolute():
        out_path = (ws_path / out_path).resolve()

    from src.ops.doc_graph import run_doc_graph

    res = run_doc_graph(
        repo_root=root,
        workspace_root=ws_path,
        out_json=out_path,
        mode=mode,
    )
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    if mode == "strict" and res.get("status") == "FAIL":
        return 2
    return 0


def _ensure_workspace_root(root: Path, ws_path: Path) -> tuple[bool, str | None]:
    if ws_path.exists() and ws_path.is_dir():
        return (True, None)
    try:
        from src.ops.roadmap_cli import cmd_workspace_bootstrap
    except Exception:
        return (False, "BOOTSTRAP_UNAVAILABLE")

    buf = StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        rc = cmd_workspace_bootstrap(argparse.Namespace(out=str(ws_path)))
    if rc != 0:
        return (False, "BOOTSTRAP_FAILED")
    return (True, None)


def cmd_doc_nav_check(args: argparse.Namespace) -> int:
    root = repo_root()
    ws_arg = str(args.workspace_root).strip()
    if not ws_arg:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    ws_path = Path(ws_arg)
    if not ws_path.is_absolute():
        ws_path = (root / ws_path).resolve()

    ok, err = _ensure_workspace_root(root, ws_path)
    if not ok:
        print(json.dumps({"status": "FAIL", "error_code": err}, ensure_ascii=False, sort_keys=True))
        return 2

    detail = parse_reaper_bool(str(args.detail))
    strict = parse_reaper_bool(str(args.strict))
    chat = parse_reaper_bool(str(args.chat))
    mode = "strict" if strict else "report"

    from src.ops.doc_graph import run_doc_graph

    doc_out_name = "doc_graph_report.strict.v1.json" if strict else "doc_graph_report.v1.json"
    doc_out = ws_path / ".cache" / "reports" / doc_out_name
    doc_report = run_doc_graph(repo_root=root, workspace_root=ws_path, out_json=doc_out, mode=mode)

    sys_out_path = ws_path / ".cache" / "reports" / "system_status.v1.json"
    if not strict:
        from src.ops.system_status_report import run_system_status

        sys_result = run_system_status(workspace_root=ws_path, core_root=root, dry_run=False)
        sys_out = sys_result.get("out_json") if isinstance(sys_result, dict) else None
        sys_out_path = (
            Path(str(sys_out))
            if isinstance(sys_out, str)
            else (ws_path / ".cache" / "reports" / "system_status.v1.json")
        )
    sys_obj: dict[str, Any] = {}
    try:
        sys_obj = json.loads(sys_out_path.read_text(encoding="utf-8"))
    except Exception:
        sys_obj = {}

    counts = doc_report.get("counts") if isinstance(doc_report, dict) else {}
    broken_refs = int(counts.get("broken_refs", 0))
    ambiguity = int(counts.get("ambiguity_count", counts.get("ambiguity", 0)))
    orphan_critical = int(counts.get("orphan_critical", 0))
    critical_nav_gaps = int(counts.get("critical_nav_gaps", 0))
    workspace_bound_refs = int(counts.get("workspace_bound_refs_count", 0))
    external_pointer_refs = int(counts.get("external_pointer_refs_count", 0))
    placeholder_refs = int(counts.get("placeholder_refs_count", 0))
    doc_status = doc_report.get("status") if isinstance(doc_report, dict) else "WARN"
    if doc_status not in {"OK", "WARN", "FAIL"}:
        doc_status = "WARN"

    cockpit_sections = sys_obj.get("sections") if isinstance(sys_obj, dict) else {}
    readiness = ""
    if isinstance(cockpit_sections, dict):
        readiness = str(cockpit_sections.get("readiness", {}).get("status", ""))
    core_lock_obj = cockpit_sections.get("core_lock") if isinstance(cockpit_sections, dict) else {}
    core_lock = "ENABLED" if isinstance(core_lock_obj, dict) and core_lock_obj.get("enabled") else "DISABLED"
    project_boundary_obj = cockpit_sections.get("project_boundary") if isinstance(cockpit_sections, dict) else {}
    project_boundary = str(project_boundary_obj.get("status", "WARN")) if isinstance(project_boundary_obj, dict) else "WARN"

    status = "OK"
    if doc_status == "FAIL" or critical_nav_gaps > 0:
        status = "FAIL"
    elif doc_status == "WARN" or str(sys_obj.get("overall_status", "")) in {"WARN", "NOT_READY"}:
        status = "WARN"

    top_broken = doc_report.get("broken_refs") if detail and isinstance(doc_report, dict) else []
    top_orphans = doc_report.get("orphan_critical") if detail and isinstance(doc_report, dict) else []
    top_placeholders = doc_report.get("top_placeholders") if detail and isinstance(doc_report, dict) else []
    if not isinstance(top_broken, list):
        top_broken = []
    if not isinstance(top_orphans, list):
        top_orphans = []
    if not isinstance(top_placeholders, list):
        top_placeholders = []

    notes = ["PROGRAM_LED=true", f"detail={str(detail).lower()}", f"strict={str(strict).lower()}"]
    if strict:
        notes.append(f"strict_report_path={str(Path('.cache') / 'reports' / doc_out_name)}")

    payload = {
        "status": status,
        "workspace_root": str(ws_path),
        "doc_graph": {
            "status": doc_status,
            "broken_refs": broken_refs,
            "ambiguity": ambiguity,
            "orphan_critical": orphan_critical,
            "critical_nav_gaps": critical_nav_gaps,
            "workspace_bound_refs": workspace_bound_refs,
            "external_pointer_refs": external_pointer_refs,
            "placeholder_refs_count": placeholder_refs,
            "top_broken": top_broken if detail else [],
            "top_orphans": top_orphans if detail else [],
            "top_placeholders": top_placeholders if detail else [],
        },
        "cockpit": {
            "overall_status": str(sys_obj.get("overall_status", "")),
            "readiness": readiness,
            "core_lock": core_lock,
            "project_boundary": project_boundary,
        },
        "evidence_paths": [
            str(Path(".cache") / "reports" / doc_out_name),
            str(Path(".cache") / "reports" / "system_status.v1.json"),
        ],
        "notes": notes,
    }

    if chat:
        print("PREVIEW:")
        if strict:
            print("PROGRAM-LED: doc-graph (strict) çalıştırıldı; cockpit refresh yapılmadı; kullanıcı komut yazmadı.")
        else:
            print("PROGRAM-LED: doc-graph + system-status çalıştırıldı; kullanıcı komut yazmadı.")
        print(f"workspace_root={payload.get('workspace_root')}")
        print("RESULT:")
        print(
            "status="
            + str(status)
            + f" broken_refs={broken_refs} ambiguity={ambiguity} orphan_critical={orphan_critical} critical_nav_gaps={critical_nav_gaps}"
        )
        print("EVIDENCE:")
        for p in payload.get("evidence_paths", []):
            print(str(p))
        print("ACTIONS:")
        actions: list[str] = []
        if critical_nav_gaps > 0:
            actions.append(f"critical_nav_gaps={critical_nav_gaps}")
        if broken_refs > 0:
            actions.append(f"broken_refs={broken_refs}")
        if ambiguity > 0:
            actions.append(f"ambiguity={ambiguity}")
        if orphan_critical > 0:
            actions.append(f"orphan_critical={orphan_critical}")
        for item in actions[:5]:
            print(item)
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    if status == "FAIL":
        return 2
    return 0
