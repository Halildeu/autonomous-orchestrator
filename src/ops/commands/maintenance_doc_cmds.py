from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
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


def _load_doc_nav_summary_timeout(core_root: Path, ws_path: Path) -> int:
    candidates = [
        ws_path / "policies" / "policy_doc_graph.v1.json",
        core_root / "policies" / "policy_doc_graph.v1.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        try:
            timeout = int(obj.get("summary_timeout_seconds", 5))
        except Exception:
            timeout = 5
        return max(1, min(60, timeout))
    return 5


def _load_doc_nav_strict_timeout(core_root: Path, ws_path: Path) -> int:
    candidates = [
        ws_path / "policies" / "policy_doc_graph.v1.json",
        core_root / "policies" / "policy_doc_graph.v1.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        try:
            timeout = int(obj.get("strict_timeout_seconds", 180))
        except Exception:
            timeout = 180
        return max(0, min(600, timeout))
    return 180


def _load_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _build_min_doc_graph_report(*, repo_root: Path, ws_path: Path) -> dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "version": "v1",
        "generated_at": now,
        "repo_root": str(repo_root),
        "workspace_root": str(ws_path),
        "status": "WARN",
        "counts": {
            "scanned_files": 0,
            "reference_count": 0,
            "broken_refs": 0,
            "orphan_critical": 0,
            "ambiguity": 0,
            "ambiguity_count": 0,
            "critical_nav_gaps": 0,
            "workspace_bound_refs_count": 0,
            "external_pointer_refs_count": 0,
            "placeholder_refs_count": 0,
            "archive_refs_count": 0,
        },
        "ref_summary": {
            "missing_file": 0,
            "wrong_path": 0,
            "deprecated": 0,
            "archive_ref": 0,
            "workspace_bound": 0,
            "external_pointer": 0,
            "plan_only_placeholder": 0,
        },
        "broken_refs": [],
        "top_placeholders": [],
        "orphan_critical": [],
        "ambiguities": [],
        "entrypoints": {},
        "notes": [],
    }


def _write_doc_graph_report(*, report: dict[str, Any], out_json: Path) -> None:
    from src.ops.doc_graph import write_doc_graph_report

    out_md = out_json.with_suffix(".v1.md") if out_json.name.endswith(".v1.json") else out_json.with_suffix(".md")
    write_doc_graph_report(report=report, out_json=out_json, out_md=out_md)


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
    summary_timeout_fallback = False
    summary_error_code = None
    strict_timeout_fallback = False
    strict_error_code = None
    if strict:
        doc_report = {}
        timeout_seconds = _load_doc_nav_strict_timeout(root, ws_path)
        if timeout_seconds == 0:
            strict_timeout_fallback = True
            strict_error_code = "STRICT_TIMEOUT_FALLBACK"
        else:
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        run_doc_graph, repo_root=root, workspace_root=ws_path, out_json=doc_out, mode=mode
                    )
                    doc_report = future.result(timeout=timeout_seconds)
            except FuturesTimeoutError:
                strict_timeout_fallback = True
                strict_error_code = "STRICT_TIMEOUT_FALLBACK"
            except Exception:
                doc_report = {}
        if strict_timeout_fallback:
            fallback_report = _load_json_if_exists(doc_out)
            if fallback_report is None:
                fallback_report = _build_min_doc_graph_report(repo_root=root, ws_path=ws_path)
            notes = fallback_report.get("notes") if isinstance(fallback_report.get("notes"), list) else []
            notes = [*notes, "strict_timeout_fallback=true"]
            fallback_report["notes"] = notes
            _write_doc_graph_report(report=fallback_report, out_json=doc_out)
            doc_report = fallback_report
    else:
        doc_report = _load_json_if_exists(doc_out)
        if doc_report is None:
            strict_path = ws_path / ".cache" / "reports" / "doc_graph_report.strict.v1.json"
            strict_report = _load_json_if_exists(strict_path)
            if strict_report is not None:
                summary_timeout_fallback = True
                summary_error_code = "SUMMARY_TIMEOUT_FALLBACK"
                doc_report = strict_report
                notes = doc_report.get("notes") if isinstance(doc_report.get("notes"), list) else []
                if "summary_timeout_fallback_to_strict=true" not in notes:
                    notes = [*notes, "summary_timeout_fallback_to_strict=true"]
                doc_report["notes"] = notes
                _write_doc_graph_report(report=doc_report, out_json=doc_out)
            else:
                doc_report = {}
                timeout_seconds = _load_doc_nav_summary_timeout(root, ws_path)
                try:
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(
                            run_doc_graph, repo_root=root, workspace_root=ws_path, out_json=doc_out, mode=mode
                        )
                        doc_report = future.result(timeout=timeout_seconds)
                except FuturesTimeoutError:
                    summary_timeout_fallback = True
                    summary_error_code = "SUMMARY_TIMEOUT_FALLBACK"
                except Exception:
                    doc_report = {}
                if summary_timeout_fallback:
                    strict_path = ws_path / ".cache" / "reports" / "doc_graph_report.strict.v1.json"
                    doc_report = _load_json_if_exists(strict_path)
                    if doc_report is None:
                        doc_report = _build_min_doc_graph_report(repo_root=root, ws_path=ws_path)
                    notes = doc_report.get("notes") if isinstance(doc_report.get("notes"), list) else []
                    notes = [*notes, "summary_timeout_fallback_to_strict=true"]
                    doc_report["notes"] = notes
                    _write_doc_graph_report(report=doc_report, out_json=doc_out)

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
    placeholders_baseline = doc_report.get("placeholders_baseline") if isinstance(doc_report, dict) else None
    placeholders_delta = doc_report.get("placeholders_delta") if isinstance(doc_report, dict) else None
    placeholders_warn_mode = doc_report.get("placeholders_warn_mode") if isinstance(doc_report, dict) else None
    if not isinstance(placeholders_baseline, int):
        placeholders_baseline = placeholder_refs
    if not isinstance(placeholders_delta, int):
        placeholders_delta = max(0, placeholder_refs - placeholders_baseline)
    if not isinstance(placeholders_warn_mode, str):
        placeholders_warn_mode = "threshold"
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
    if summary_timeout_fallback or strict_timeout_fallback:
        if doc_status == "FAIL":
            doc_status = "WARN"
        if status == "FAIL":
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
    if summary_timeout_fallback:
        notes.append("summary_timeout_fallback_to_strict=true")
    if strict_timeout_fallback:
        notes.append("strict_timeout_fallback=true")
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
            "placeholders_baseline": placeholders_baseline,
            "placeholders_delta": placeholders_delta,
            "placeholders_warn_mode": placeholders_warn_mode,
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
    if strict_error_code or summary_error_code:
        payload["error_code"] = strict_error_code or summary_error_code

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


def cmd_doc_nav_job_start(args: argparse.Namespace) -> int:
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

    strict = parse_reaper_bool(str(getattr(args, "strict", "true")))
    detail = parse_reaper_bool(str(getattr(args, "detail", "false")))
    chat = parse_reaper_bool(str(getattr(args, "chat", "false")))

    from src.ops.doc_nav_jobs import doc_nav_job_start

    payload = doc_nav_job_start(workspace_root=ws_path, strict=bool(strict), detail=bool(detail))
    if chat and isinstance(payload, dict):
        preview_lines = [
            "PROGRAM-LED: doc-nav-job-start",
            f"workspace_root={ws_path}",
            f"strict={strict}",
            f"detail={detail}",
        ]
        result_lines = [
            f"status={payload.get('status')}",
            f"job_id={payload.get('job_id')}",
        ]
        evidence_lines = [str(payload.get("job_report_path") or ""), str(payload.get("jobs_index_path") or "")]
        actions_lines = ["doc-nav-job-poll", "doc-nav-check"]
        next_lines = ["Devam et", "Durumu goster", "Duraklat"]

        print("PREVIEW:")
        print("\n".join(preview_lines))
        print("RESULT:")
        print("\n".join(result_lines))
        print("EVIDENCE:")
        print("\n".join([e for e in evidence_lines if e]))
        print("ACTIONS:")
        print("\n".join(actions_lines))
        print("NEXT:")
        print("\n".join(next_lines))

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") in {"OK", "ALREADY_RUNNING"} else 2


def cmd_doc_nav_job_poll(args: argparse.Namespace) -> int:
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

    job_id = str(getattr(args, "job_id", "") or "").strip()
    if not job_id:
        warn("FAIL error=JOB_ID_REQUIRED")
        return 2

    chat = parse_reaper_bool(str(getattr(args, "chat", "false")))

    from src.ops.doc_nav_jobs import doc_nav_job_poll

    payload = doc_nav_job_poll(workspace_root=ws_path, job_id=job_id)
    if chat and isinstance(payload, dict):
        preview_lines = [
            "PROGRAM-LED: doc-nav-job-poll",
            f"workspace_root={ws_path}",
            f"job_id={job_id}",
        ]
        result_lines = [
            f"status={payload.get('status')}",
            f"report_status={payload.get('report_status') or payload.get('status')}",
        ]
        evidence_lines = [str(payload.get("job_report_path") or ""), str(payload.get("jobs_index_path") or "")]
        actions_lines = ["doc-nav-job-poll", "doc-nav-check"]
        next_lines = ["Devam et", "Durumu goster", "Duraklat"]

        print("PREVIEW:")
        print("\n".join(preview_lines))
        print("RESULT:")
        print("\n".join(result_lines))
        print("EVIDENCE:")
        print("\n".join([e for e in evidence_lines if e]))
        print("ACTIONS:")
        print("\n".join(actions_lines))
        print("NEXT:")
        print("\n".join(next_lines))

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") in {"OK", "WARN", "FAIL", "RUNNING"} else 2
