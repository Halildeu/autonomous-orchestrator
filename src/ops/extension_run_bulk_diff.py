from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.ops.extension_run import build_extension_run_report


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _list_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({str(v).strip() for v in value if isinstance(v, str) and str(v).strip()})


def _sanitize_token(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", str(value or "").strip()).strip("-")
    return cleaned[:64] if cleaned else "X"


def _safe_status(value: Any) -> str:
    raw = str(value or "").strip().upper()
    allowed = {"OK", "WARN", "FAIL", "IDLE", "UNKNOWN", "BLOCKED", "SKIPPED"}
    return raw if raw in allowed else "UNKNOWN"


def _normalize_path_for_report(path_value: Any, workspace_root: Path, core_root: Path) -> str:
    if not isinstance(path_value, str) or not path_value:
        return ""
    p = Path(path_value)
    if not p.is_absolute():
        return str(p.as_posix())
    try:
        return str(p.resolve().relative_to(workspace_root.resolve()).as_posix())
    except Exception:
        pass
    try:
        return str(p.resolve().relative_to(core_root.resolve()).as_posix())
    except Exception:
        return str(p.as_posix())


def _discover_ops_single_gate_extensions(
    *, core_root: Path, extension_ids_filter: set[str] | None
) -> list[dict[str, Any]]:
    ext_root = core_root / "extensions"
    if not ext_root.exists():
        return []

    rows: list[dict[str, Any]] = []
    for manifest_path in sorted(ext_root.rglob("extension.manifest.v1.json")):
        try:
            manifest = _load_json(manifest_path)
        except Exception:
            continue
        if not isinstance(manifest, dict):
            continue

        extension_id = str(manifest.get("extension_id") or "").strip()
        if not extension_id:
            continue
        if isinstance(extension_ids_filter, set) and extension_id not in extension_ids_filter:
            continue

        entrypoints = manifest.get("entrypoints") if isinstance(manifest.get("entrypoints"), dict) else {}
        ops_single_gate = _list_str(entrypoints.get("ops_single_gate"))
        if not ops_single_gate:
            continue
        rows.append(
            {
                "extension_id": extension_id,
                "manifest_path": str(manifest_path.relative_to(core_root).as_posix()),
                "owner": str(manifest.get("owner") or "CORE"),
                "ops_single_gate": ops_single_gate,
            }
        )

    rows.sort(key=lambda x: str(x.get("extension_id") or ""))
    return rows


def _closure_priority(strict_status: str, status_changed: bool) -> str:
    if strict_status == "FAIL":
        return "P1"
    if status_changed:
        return "P2"
    return "P3"


def _closure_eta(strict_status: str, status_changed: bool) -> str:
    base = datetime.now(timezone.utc).date()
    days = 4
    if strict_status == "FAIL":
        days = 2 if status_changed else 3
    elif strict_status == "WARN":
        days = 4 if status_changed else 5
    return (base + timedelta(days=days)).isoformat()


def _closure_tasks(extension_id: str, gate: str) -> list[str]:
    if extension_id == "PRJ-M0-MAINTAINABILITY" and gate == "script-budget":
        return [
            "script-budget raporunda hard/soft asim yapan scriptleri owner bazli ayikla.",
            "Hard-exceeded kalemleri moduller arasi ortak yardimciya tasiyarak limit altina indir.",
            "script-budget + extension-run-bulk-diff strict tekrar kosup FAIL farkini kapat.",
        ]
    return [
        "Single-gate ciktisindaki FAIL/WARN sebebini kanit dosyasindan netlestir.",
        "Minimal kod/policy duzeltmesini uygulayip strict kosuyu tekrar et.",
        "Kapanis kanitini matrix raporuna geri yaz.",
    ]


def _build_chg_draft_payload(
    *,
    chg_id: str,
    row: dict[str, Any],
    workspace_root: Path,
    matrix_rel: str,
) -> dict[str, Any]:
    extension_id = str(row.get("extension_id") or "")
    gate = str(row.get("gate") or "")
    owner = str(row.get("owner") or "CORE")
    eta = str(row.get("eta") or "")
    strict_status = str(row.get("strict_status") or "")
    report_status = str(row.get("report_status") or "")
    strict_gate_status = str(row.get("strict_single_gate_status") or "")
    strict_report_path = str(row.get("strict_report_path") or "")
    priority = str(row.get("priority") or "P3")
    tasks = _closure_tasks(extension_id, gate)
    return {
        "version": "v1",
        "chg_id": chg_id,
        "generated_at": _now_iso8601(),
        "source": "extension-run-bulk-diff",
        "workspace_root": str(workspace_root),
        "extension_id": extension_id,
        "gate": gate,
        "owner": owner,
        "eta": eta,
        "priority": priority,
        "status_snapshot": {
            "report_status": report_status,
            "strict_status": strict_status,
            "strict_single_gate_status": strict_gate_status,
        },
        "objective": f"{extension_id}/{gate} strict {strict_status} durumunu kapatmak",
        "constraints": [
            "network_default=false",
            "report_only_or_no_side_effect_on_diagnosis",
            "workspace_scoped_evidence",
        ],
        "steps": tasks,
        "acceptance_tests": [
            f"extension-run --extension-id {extension_id} --mode strict",
            "extension-run-bulk-diff --chat false",
        ],
        "evidence_paths": [
            matrix_rel,
            strict_report_path,
        ],
        "notes": ["AUTO_GENERATED=true", "PROGRAM_LED=true"],
    }


def _write_chg_drafts(
    *,
    workspace_root: Path,
    rows: list[dict[str, Any]],
    matrix_rel: str,
) -> list[dict[str, Any]]:
    if not rows:
        return []

    outdir = workspace_root / ".cache" / "reports" / "chg"
    outdir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")

    drafts: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for row in rows:
        extension_id = _sanitize_token(str(row.get("extension_id") or "EXT"))
        gate = _sanitize_token(str(row.get("gate") or "gate"))
        chg_id_base = f"CHG-{date_str}-EXT-{extension_id}-{gate}"
        chg_id = chg_id_base
        dedup_idx = 2
        while chg_id in used_ids:
            chg_id = f"{chg_id_base}-{dedup_idx}"
            dedup_idx += 1
        used_ids.add(chg_id)

        plan_rel = Path(".cache") / "reports" / "chg" / f"{chg_id}.plan.json"
        md_rel = Path(".cache") / "reports" / "chg" / f"{chg_id}.plan.md"
        plan_path = workspace_root / plan_rel
        md_path = workspace_root / md_rel

        payload = _build_chg_draft_payload(
            chg_id=chg_id,
            row=row,
            workspace_root=workspace_root,
            matrix_rel=matrix_rel,
        )
        plan_path.write_text(_dump_json(payload), encoding="utf-8")

        md_lines = [
            f"# {chg_id} Execution Draft",
            "",
            f"- extension_id: {payload.get('extension_id')}",
            f"- gate: {payload.get('gate')}",
            f"- owner: {payload.get('owner')}",
            f"- eta: {payload.get('eta')}",
            f"- priority: {payload.get('priority')}",
            "",
            "## Objective",
            f"- {payload.get('objective')}",
            "",
            "## Steps",
        ]
        for step in payload.get("steps", []):
            md_lines.append(f"- {step}")
        md_lines.extend(["", "## Acceptance Tests"])
        for item in payload.get("acceptance_tests", []):
            md_lines.append(f"- {item}")
        md_lines.extend(["", "## Evidence"])
        for item in payload.get("evidence_paths", []):
            if isinstance(item, str) and item:
                md_lines.append(f"- {item}")
        md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

        drafts.append(
            {
                "chg_id": chg_id,
                "extension_id": payload.get("extension_id"),
                "gate": payload.get("gate"),
                "owner": payload.get("owner"),
                "eta": payload.get("eta"),
                "priority": payload.get("priority"),
                "plan_path": str(plan_rel.as_posix()),
                "plan_md_path": str(md_rel.as_posix()),
            }
        )
    return drafts


def run_extension_run_bulk_diff(
    *,
    workspace_root: Path,
    extension_ids: list[str] | None = None,
    emit_chg: bool = True,
    chat: bool = True,
) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    core_root = _repo_root()
    extension_ids_filter = {str(x).strip() for x in extension_ids or [] if isinstance(x, str) and str(x).strip()}
    if not extension_ids_filter:
        extension_ids_filter = None

    ext_rows = _discover_ops_single_gate_extensions(core_root=core_root, extension_ids_filter=extension_ids_filter)
    if not ext_rows:
        out_json = workspace_root / ".cache" / "reports" / "extension_run_ops_single_gate_diff_matrix.v1.json"
        out_md = workspace_root / ".cache" / "reports" / "extension_run_ops_single_gate_diff_matrix.v1.md"
        out_json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": "v1",
            "generated_at": _now_iso8601(),
            "workspace_root": str(workspace_root),
            "status": "IDLE",
            "error_code": "NO_OPS_SINGLE_GATE_EXTENSIONS",
            "summary": {
                "total_extensions": 0,
                "mode_diff_count": 0,
                "strict_fail_count": 0,
                "strict_warn_count": 0,
                "strict_ok_count": 0,
                "strict_attention_count": 0,
            },
            "rows": [],
            "closure_plan": [],
            "chg_drafts": [],
        }
        out_json.write_text(_dump_json(payload), encoding="utf-8")
        out_md.write_text("# Extension Run Ops Single Gate Diff Matrix (v1)\n\n- status: IDLE\n", encoding="utf-8")
        payload["report_path"] = str(out_json.relative_to(workspace_root).as_posix())
        payload["summary_path"] = str(out_md.relative_to(workspace_root).as_posix())
        if chat:
            print("PREVIEW:")
            print("PROGRAM-LED: extension-run-bulk-diff; user_command=false")
            print(f"workspace_root={workspace_root}")
            print("RESULT:")
            print("status=IDLE")
            print("EVIDENCE:")
            print(payload["report_path"])
            print(payload["summary_path"])
            print("ACTIONS:")
            print("no_actions")
            print("NEXT:")
            print("Devam et")
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return payload

    rows: list[dict[str, Any]] = []
    for ext in ext_rows:
        extension_id = str(ext.get("extension_id") or "")
        owner = str(ext.get("owner") or "CORE")
        report_payload = build_extension_run_report(
            workspace_root=workspace_root,
            extension_id=extension_id,
            mode="report",
        )
        strict_payload = build_extension_run_report(
            workspace_root=workspace_root,
            extension_id=extension_id,
            mode="strict",
        )

        report_status = _safe_status(report_payload.get("status"))
        strict_status = _safe_status(strict_payload.get("status"))
        report_gate_status = _safe_status(report_payload.get("single_gate_status"))
        strict_gate_status = _safe_status(strict_payload.get("single_gate_status"))
        gate = str(strict_payload.get("selected_single_gate") or report_payload.get("selected_single_gate") or "")
        status_changed = report_status != strict_status
        strict_attention = strict_status in {"WARN", "FAIL"}
        priority = _closure_priority(strict_status, status_changed)
        eta = _closure_eta(strict_status, status_changed)

        rows.append(
            {
                "extension_id": extension_id,
                "manifest_path": str(ext.get("manifest_path") or ""),
                "owner": owner,
                "gate": gate,
                "report_status": report_status,
                "strict_status": strict_status,
                "report_single_gate_status": report_gate_status,
                "strict_single_gate_status": strict_gate_status,
                "status_changed": bool(status_changed),
                "strict_attention": bool(strict_attention),
                "report_error_code": str(report_payload.get("error_code") or ""),
                "strict_error_code": str(strict_payload.get("error_code") or ""),
                "strict_single_gate_error_code": str(strict_payload.get("single_gate_error_code") or ""),
                "report_path": _normalize_path_for_report(report_payload.get("report_path"), workspace_root, core_root),
                "strict_report_path": _normalize_path_for_report(strict_payload.get("report_path"), workspace_root, core_root),
                "priority": priority,
                "eta": eta,
            }
        )

    rows.sort(key=lambda x: str(x.get("extension_id") or ""))
    mode_diff_rows = [r for r in rows if bool(r.get("status_changed"))]
    strict_attention_rows = [r for r in rows if bool(r.get("strict_attention"))]

    closure_plan: list[dict[str, Any]] = []
    for row in mode_diff_rows:
        closure_plan.append(
            {
                "extension_id": str(row.get("extension_id") or ""),
                "gate": str(row.get("gate") or ""),
                "owner": str(row.get("owner") or "CORE"),
                "eta": str(row.get("eta") or ""),
                "priority": str(row.get("priority") or "P3"),
                "reason": f"mode_diff({row.get('report_status')}->{row.get('strict_status')})",
                "tasks": _closure_tasks(str(row.get("extension_id") or ""), str(row.get("gate") or "")),
            }
        )

    summary = {
        "total_extensions": len(rows),
        "mode_diff_count": len(mode_diff_rows),
        "strict_fail_count": len([r for r in rows if str(r.get("strict_status")) == "FAIL"]),
        "strict_warn_count": len([r for r in rows if str(r.get("strict_status")) == "WARN"]),
        "strict_ok_count": len([r for r in rows if str(r.get("strict_status")) == "OK"]),
        "strict_attention_count": len(strict_attention_rows),
    }

    out_json = workspace_root / ".cache" / "reports" / "extension_run_ops_single_gate_diff_matrix.v1.json"
    out_md = workspace_root / ".cache" / "reports" / "extension_run_ops_single_gate_diff_matrix.v1.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)

    matrix_rel = str(out_json.relative_to(workspace_root).as_posix())
    chg_drafts: list[dict[str, Any]] = []
    if emit_chg and strict_attention_rows:
        chg_drafts = _write_chg_drafts(workspace_root=workspace_root, rows=strict_attention_rows, matrix_rel=matrix_rel)

    status = "OK"
    error_code = ""
    if strict_attention_rows:
        status = "WARN"
        error_code = "STRICT_ATTENTION_REQUIRED"

    payload: dict[str, Any] = {
        "version": "v1",
        "generated_at": _now_iso8601(),
        "workspace_root": str(workspace_root),
        "status": status,
        "error_code": error_code,
        "summary": summary,
        "rows": rows,
        "closure_plan": closure_plan,
        "chg_drafts": chg_drafts,
    }
    payload["report_path"] = str(out_json.relative_to(workspace_root).as_posix())
    payload["summary_path"] = str(out_md.relative_to(workspace_root).as_posix())
    out_json.write_text(_dump_json(payload), encoding="utf-8")

    md_lines = [
        "# Extension Run Ops Single Gate Diff Matrix (v1)",
        "",
        f"- workspace_root: {workspace_root}",
        f"- total_extensions: {summary['total_extensions']}",
        f"- mode_diff_count: {summary['mode_diff_count']}",
        f"- strict_fail_count: {summary['strict_fail_count']}",
        f"- strict_warn_count: {summary['strict_warn_count']}",
        f"- strict_ok_count: {summary['strict_ok_count']}",
        f"- strict_attention_count: {summary['strict_attention_count']}",
        "",
        "| extension_id | gate | owner | report_status | strict_status | report_gate_status | strict_gate_status | diff |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        diff = "MODE_DIFF" if bool(row.get("status_changed")) else "UNCHANGED"
        md_lines.append(
            f"| {row.get('extension_id')} | {row.get('gate')} | {row.get('owner')} | "
            f"{row.get('report_status')} | {row.get('strict_status')} | "
            f"{row.get('report_single_gate_status')} | {row.get('strict_single_gate_status')} | {diff} |"
        )

    md_lines.extend(["", "## Auto Closure Plan (mode_diff)"])
    if closure_plan:
        for item in closure_plan:
            md_lines.append("")
            md_lines.append(f"### {item.get('extension_id')} / {item.get('gate')}")
            md_lines.append(f"- owner: {item.get('owner')}")
            md_lines.append(f"- eta: {item.get('eta')}")
            md_lines.append(f"- priority: {item.get('priority')}")
            md_lines.append(f"- reason: {item.get('reason')}")
            md_lines.append("- tasks:")
            for task in item.get("tasks", []):
                md_lines.append(f"  - {task}")
    else:
        md_lines.append("- mode farkı bulunmadı.")

    md_lines.extend(["", "## Auto CHG Drafts (strict WARN/FAIL)"])
    if chg_drafts:
        for draft in chg_drafts:
            md_lines.append(
                f"- {draft.get('chg_id')} owner={draft.get('owner')} eta={draft.get('eta')} "
                f"priority={draft.get('priority')} plan={draft.get('plan_path')}"
            )
    else:
        md_lines.append("- strict WARN/FAIL bulunmadı.")

    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    if chat:
        print("PREVIEW:")
        print("PROGRAM-LED: extension-run-bulk-diff; user_command=false")
        print(f"workspace_root={workspace_root}")
        print("RESULT:")
        print(f"status={status}")
        print(f"mode_diff_count={summary['mode_diff_count']}")
        print(f"strict_attention_count={summary['strict_attention_count']}")
        print("EVIDENCE:")
        print(payload["report_path"])
        print(payload["summary_path"])
        if chg_drafts:
            print(chg_drafts[0].get("plan_path", ""))
        print("ACTIONS:")
        print("extension-run --mode strict")
        print("work-intake-check")
        print("system-status")
        print("NEXT:")
        print("Devam et")
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))

    return payload
