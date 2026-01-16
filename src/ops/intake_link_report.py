from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from src.ops.commands.common import repo_root


def _resolve_workspace_root(workspace_arg: str | Path) -> Path | None:
    root = repo_root()
    ws = Path(str(workspace_arg or "").strip())
    if not str(ws):
        return None
    ws = (root / ws).resolve() if not ws.is_absolute() else ws.resolve()
    if not ws.exists() or not ws.is_dir():
        return None
    return ws


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _stringify(value: Any) -> str:
    return str(value) if value is not None else ""


def _match_ref(value: Any, req_id: str) -> bool:
    if not isinstance(req_id, str) or not req_id.strip():
        return False
    text = _stringify(value)
    if not text:
        return False
    return text == req_id or req_id in text


def _suggested_extensions(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if isinstance(v, str) and v.strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalize_matches(items: Iterable[dict[str, Any]], req_id: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        source_ref = item.get("source_ref") or item.get("ref")
        source = item.get("source") if isinstance(item.get("source"), dict) else {}
        source_nested_ref = source.get("ref") if isinstance(source, dict) else None
        if not (
            _match_ref(source_ref, req_id)
            or _match_ref(source_nested_ref, req_id)
            or _match_ref(item.get("source_ref"), req_id)
        ):
            continue
        intake_id = _stringify(item.get("intake_id") or item.get("id"))
        matches.append(
            {
                "intake_id": intake_id,
                "bucket": _stringify(item.get("bucket")),
                "priority": _stringify(item.get("priority")),
                "severity": _stringify(item.get("severity")),
                "title": _stringify(item.get("title")),
                "source_type": _stringify(item.get("source_type") or source.get("type")),
                "source_ref": _stringify(source_ref or source_nested_ref),
                "suggested_extension": _suggested_extensions(item.get("suggested_extension")),
            }
        )
    matches.sort(key=lambda m: m.get("intake_id", ""))
    return matches


def _normalize_evidence(paths: Iterable[Path | str]) -> list[str]:
    out: list[str] = []
    for path in paths:
        value = str(path or "").strip()
        if value:
            out.append(value)
    return sorted(set(out))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path: Path, payload: dict[str, Any], matches: list[dict[str, Any]]) -> None:
    lines: list[str] = []
    lines.append("# UI Chat Gateway Intake Link")
    lines.append("")
    lines.append(f"- req_id: `{payload.get('req_id')}`")
    lines.append(f"- match_count: **{payload.get('match_count')}**")
    plan_path = payload.get("plan_path")
    if plan_path:
        lines.append(f"- plan_path: `{plan_path}`")
    if matches:
        lines.append("")
        lines.append("## Matches")
        for item in matches:
            intake_id = item.get("intake_id")
            bucket = item.get("bucket")
            priority = item.get("priority")
            title = item.get("title")
            lines.append(f"- {intake_id} [{bucket}/{priority}] {title}")
    else:
        lines.append("")
        lines.append("No matching intake items found for this REQ.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _plan_path_for(req_id: str) -> str:
    safe_req = req_id.replace("/", "_")
    return f".cache/reports/chg/CHG-{safe_req}-UI-CHAT-GATEWAY-PROMOTE-PROJECT-v0.1.plan.json"


def _build_plan_payload(req_id: str, link_report_path: str) -> dict[str, Any]:
    return {
        "version": "v0.1",
        "kind": "PLAN_ONLY",
        "goal": "Promote the Chat Gateway intake item to PROJECT (tracking only).",
        "inputs": {
            "req_id": req_id,
            "intake_link_report": link_report_path,
        },
        "recommended_mechanism_order": [
            "1) Decision-first: if ROUTE_OVERRIDE decision kind exists, apply it to bucket=PROJECT",
            "2) Otherwise: create a route override seed (workspace-only) and rebuild decision inbox",
            "3) Otherwise: keep as-is but tag suggested_extension=['PRJ-UI-COCKPIT-LITE'] in a plan-only follow-up",
        ],
        "postchecks": [
            "work-intake-check --mode strict",
            "decision-inbox-build/show",
            "system-status",
            "ui-snapshot-bundle",
            "doc-nav-check --strict",
        ],
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "NO_APPLY=true"],
    }


def run_intake_link_report(
    *,
    workspace_root: Path | str,
    req_id: str,
    write_plan: bool = False,
) -> dict[str, Any]:
    ws = _resolve_workspace_root(str(workspace_root))
    if ws is None:
        return {"status": "FAIL", "error_code": "WORKSPACE_ROOT_INVALID"}

    req_id = str(req_id or "").strip()
    if not req_id:
        return {"status": "FAIL", "error_code": "REQ_ID_REQUIRED"}

    work_intake_path = ws / ".cache" / "index" / "work_intake.v1.json"
    if not work_intake_path.exists():
        return {"status": "FAIL", "error_code": "WORK_INTAKE_MISSING"}

    intake = _load_json(work_intake_path)
    items = intake.get("items") if isinstance(intake, dict) else []
    matches = _normalize_matches(items or [], req_id)

    report_path = ws / ".cache" / "reports" / "ui_chat_gateway_intake_link.v1.json"
    report_md_path = ws / ".cache" / "reports" / "ui_chat_gateway_intake_link.v1.md"

    evidence_paths = _normalize_evidence(
        [
            work_intake_path.relative_to(ws).as_posix(),
        ]
    )

    plan_path = None
    if write_plan:
        plan_rel = _plan_path_for(req_id)
        plan_abs = ws / plan_rel
        plan_payload = _build_plan_payload(req_id, report_path.relative_to(ws).as_posix())
        _write_json(plan_abs, plan_payload)
        plan_path = plan_rel
        evidence_paths = _normalize_evidence(evidence_paths + [plan_rel])

    payload = {
        "version": "v1",
        "req_id": req_id,
        "match_count": len(matches),
        "matches": matches,
        "plan_path": plan_path,
        "evidence_paths": evidence_paths,
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true"],
    }

    _write_json(report_path, payload)
    _write_md(report_md_path, payload, matches)

    status = "OK" if matches else "WARN"
    return {
        "status": status,
        "req_id": req_id,
        "report_path": report_path.relative_to(ws).as_posix(),
        "report_md_path": report_md_path.relative_to(ws).as_posix(),
        "plan_path": plan_path,
        "match_count": len(matches),
    }
