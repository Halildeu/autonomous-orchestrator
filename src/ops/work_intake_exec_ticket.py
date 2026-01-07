from __future__ import annotations

import fnmatch
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _ensure_inside_workspace(workspace_root: Path, target: Path) -> None:
    workspace_root = workspace_root.resolve()
    target = target.resolve()
    target.relative_to(workspace_root)


def _sha8(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]


def _policy_hash(policy: dict[str, Any]) -> str:
    payload = json.dumps(policy, ensure_ascii=True, sort_keys=True, indent=None, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _priority_rank(value: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}.get(value, 99)


def _severity_rank(value: str) -> int:
    return {"S0": 0, "S1": 1, "S2": 2, "S3": 3, "S4": 4}.get(value, 99)


def _match_any(patterns: list[str], value: str) -> bool:
    for pattern in patterns:
        if not isinstance(pattern, str) or not pattern:
            continue
        if pattern.endswith("/**") and value.startswith(pattern[:-3]):
            return True
        if fnmatch.fnmatch(value, pattern):
            return True
    return False


def _merge_policy(defaults: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(defaults)
    if isinstance(override, dict):
        merged.update(override)
    return merged


def _load_policy(*, core_root: Path, workspace_root: Path) -> tuple[dict[str, Any], str, str]:
    defaults = {
        "version": "v1",
        "enabled": True,
        "apply_scope": "WORKSPACE_ONLY",
        "allow_workspace_override": False,
        "safe_only_apply_manual_request_kinds": [],
        "safe_only_apply_manual_request_scopes": [],
        "safe_only_apply_gap_types": [],
        "safe_only_apply_script_budget_sources": [],
        "forbidden_safe_only_path_prefixes": [],
        "require_impact_scope": "",
        "applied_requires_evidence_path": False,
        "unsafe_kinds": ["MOVE", "DELETE", "REFACTOR", "CODEGEN"],
        "action_rules": [
            {
                "id": "doc_nav_broken_refs",
                "source_type": "DOC_NAV",
                "when": {"broken_refs_gt": 0},
                "action_kind": "WRITE_DOC_NOTE",
            },
            {
                "id": "manual_request_doc_fix",
                "source_type": "MANUAL_REQUEST",
                "when": {"manual_request_kind_in": ["doc-fix", "note"]},
                "action_kind": "WRITE_DOC_NOTE",
            },
            {
                "id": "script_budget_docs_ci",
                "source_type": "SCRIPT_BUDGET",
                "when": {"path_prefix_in": ["docs/", "ci/", "smoke_helpers/"]},
                "action_kind": "NOOP",
                "plan_only": True,
            },
        ],
        "default_action": {"action_kind": "NOOP", "plan_only": True},
    }

    ws_policy = workspace_root / "policies" / "policy_work_intake_exec.v1.json"
    core_policy = core_root / "policies" / "policy_work_intake_exec.v1.json"
    core_obj: dict[str, Any] | None = None
    if core_policy.exists():
        try:
            obj = _load_json(core_policy)
            if isinstance(obj, dict):
                core_obj = obj
        except Exception:
            core_obj = None

    policy = _merge_policy(defaults, core_obj)
    policy_source = "core"

    allow_override = bool(policy.get("allow_workspace_override", False))
    if allow_override and ws_policy.exists():
        try:
            obj = _load_json(ws_policy)
        except Exception:
            obj = None
        if isinstance(obj, dict):
            policy = _merge_policy(defaults, obj)
            policy_source = "workspace_override"

    return policy, policy_source, _policy_hash(policy)


def _load_doc_nav_report(workspace_root: Path) -> dict[str, Any]:
    strict_path = workspace_root / ".cache" / "reports" / "doc_graph_report.strict.v1.json"
    summary_path = workspace_root / ".cache" / "reports" / "doc_graph_report.v1.json"
    path = strict_path if strict_path.exists() else summary_path
    if not path.exists():
        return {"broken_refs": 0, "critical_nav_gaps": 0, "broken_ref_items": []}
    try:
        obj = _load_json(path)
    except Exception:
        return {"broken_refs": 0, "critical_nav_gaps": 0, "broken_ref_items": []}
    counts = obj.get("counts") if isinstance(obj, dict) else None
    if not isinstance(counts, dict):
        return {"broken_refs": 0, "critical_nav_gaps": 0, "broken_ref_items": []}
    broken_items = obj.get("broken_refs") if isinstance(obj, dict) else None
    if not isinstance(broken_items, list):
        broken_items = []
    return {
        "broken_refs": int(counts.get("broken_refs", 0)),
        "critical_nav_gaps": int(counts.get("critical_nav_gaps", 0)),
        "broken_ref_items": broken_items,
    }


def _load_manual_request(workspace_root: Path, request_id: str) -> dict[str, Any] | None:
    if not request_id:
        return None
    path = workspace_root / ".cache" / "index" / "manual_requests" / f"{request_id}.v1.json"
    if not path.exists():
        return None
    try:
        obj = _load_json(path)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _matches_when(*, when: dict[str, Any], source_type: str, context: dict[str, Any]) -> bool:
    if not isinstance(when, dict):
        return False
    if "broken_refs_gt" in when:
        val = int(context.get("doc_nav_broken_refs", 0))
        if val <= int(when.get("broken_refs_gt", 0)):
            return False
    if "manual_request_kind_in" in when:
        kind = str(context.get("manual_request_kind", ""))
        allowed = [str(x) for x in when.get("manual_request_kind_in", []) if isinstance(x, str)]
        if kind not in allowed:
            return False
    if "manual_request_impact_scope_in" in when:
        scope = str(context.get("manual_request_impact_scope", ""))
        allowed = [str(x) for x in when.get("manual_request_impact_scope_in", []) if isinstance(x, str)]
        if scope not in allowed:
            return False
    if "path_prefix_in" in when:
        path = str(context.get("path", ""))
        prefixes = [str(x) for x in when.get("path_prefix_in", []) if isinstance(x, str)]
        if not any(path.startswith(pref) for pref in prefixes):
            return False
    return True


def _select_action(
    *,
    policy: dict[str, Any],
    source_type: str,
    context: dict[str, Any],
) -> tuple[str, bool, str]:
    rules = policy.get("action_rules") if isinstance(policy.get("action_rules"), list) else []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if str(rule.get("source_type")) != source_type:
            continue
        when = rule.get("when") if isinstance(rule.get("when"), dict) else {}
        if not _matches_when(when=when, source_type=source_type, context=context):
            continue
        action_kind = str(rule.get("action_kind") or "NOOP")
        plan_only = bool(rule.get("plan_only", False))
        return (action_kind, plan_only, str(rule.get("id") or "rule"))
    default_action = policy.get("default_action") if isinstance(policy.get("default_action"), dict) else {}
    action_kind = str(default_action.get("action_kind") or "NOOP")
    plan_only = bool(default_action.get("plan_only", True))
    return (action_kind, plan_only, "default")


def _write_note(
    *,
    workspace_root: Path,
    note_id: str,
    title: str,
    reason: str,
    source_ref: str | None,
    plan_path: str | None = None,
) -> str:
    notes_dir = workspace_root / ".cache" / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    note_path = notes_dir / f"{note_id}.v1.md"
    _ensure_inside_workspace(workspace_root, note_path)
    lines = [
        "WORK INTAKE NOTE",
        "",
        f"Item: {note_id}",
        f"Title: {title}",
        f"Reason: {reason}",
    ]
    if source_ref:
        lines.append(f"Source: {source_ref}")
    if plan_path:
        lines.append(f"Plan: {plan_path}")
    lines.append("")
    note_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(Path(".cache") / "notes" / f"{note_id}.v1.md")


def _write_gap_coverage_report(
    *, workspace_root: Path, gap_id: str, title: str, reason: str
) -> tuple[str, str]:
    base = f"gap_coverage_apply.{gap_id}.v1"
    out_json = workspace_root / ".cache" / "reports" / f"{base}.json"
    out_md = workspace_root / ".cache" / "reports" / f"{base}.md"
    _ensure_inside_workspace(workspace_root, out_json)
    _ensure_inside_workspace(workspace_root, out_md)
    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "gap_id": gap_id,
        "title": title,
        "reason": reason,
        "notes": ["safe-only", "workspace-only", "no_repo_writes"],
    }
    _write_json(out_json, payload)
    out_md.write_text(
        "\n".join(
            [
                "GAP COVERAGE SAFE-ONLY APPLY",
                "",
                f"Gap: {gap_id}",
                f"Title: {title}",
                f"Reason: {reason}",
                "",
                "Safe-only note; no repo writes.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return (str(Path(".cache") / "reports" / f"{base}.json"), str(Path(".cache") / "reports" / f"{base}.md"))


def _write_doc_fix_suggestions(
    *, workspace_root: Path, request_id: str, title: str, reason: str
) -> tuple[str, str]:
    base = f"doc_fix_suggestions.{request_id}.v1"
    out_json = workspace_root / ".cache" / "reports" / f"{base}.json"
    out_md = workspace_root / ".cache" / "reports" / f"{base}.md"
    _ensure_inside_workspace(workspace_root, out_json)
    _ensure_inside_workspace(workspace_root, out_md)
    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "request_id": request_id,
        "title": title,
        "reason": reason,
        "suggestions": [
            {"id": "SUG-001", "summary": "Review related docs for outdated references."},
            {"id": "SUG-002", "summary": "Update broken or stale links and headers."},
            {"id": "SUG-003", "summary": "Add a short clarification note where needed."},
        ],
    }
    _write_json(out_json, payload)
    out_md.write_text(
        "\n".join(
            [
                "DOC FIX SUGGESTIONS",
                "",
                f"Request: {request_id}",
                f"Title: {title}",
                f"Reason: {reason}",
                "",
                "Suggestions:",
                "- Review related docs for outdated references.",
                "- Update broken or stale links and headers.",
                "- Add a short clarification note where needed.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return (str(Path(".cache") / "reports" / f"{base}.json"), str(Path(".cache") / "reports" / f"{base}.md"))


def _write_doc_nav_fix_plan(
    *, workspace_root: Path, broken_refs: list[Any]
) -> tuple[str, str]:
    out_json = workspace_root / ".cache" / "reports" / "doc_nav_fix_plan.v1.json"
    out_md = workspace_root / ".cache" / "reports" / "doc_nav_fix_plan.v1.md"
    _ensure_inside_workspace(workspace_root, out_json)
    _ensure_inside_workspace(workspace_root, out_md)
    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "broken_refs": broken_refs,
        "plan_only": True,
        "notes": ["workspace-only", "safe-only", "no_repo_writes"],
    }
    _write_json(out_json, payload)
    out_md.write_text(
        "\n".join(
            [
                "DOC NAV FIX PLAN",
                "",
                f"Broken refs: {len(broken_refs)}",
                "",
                "Plan-only list; no repo writes.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return (str(Path(".cache") / "reports" / "doc_nav_fix_plan.v1.json"), str(Path(".cache") / "reports" / "doc_nav_fix_plan.v1.md"))


def _ensure_plan(
    *, workspace_root: Path, intake_id: str, source_type: str, source_ref: str, title: str
) -> str:
    chg_id = f"CHG-INTAKE-{_sha8(intake_id)}"
    plan_rel = Path(".cache") / "reports" / "chg" / f"{chg_id}.plan.json"
    plan_path = workspace_root / plan_rel
    _ensure_inside_workspace(workspace_root, plan_path)
    if not plan_path.exists():
        plan_obj = {
            "chg_id": chg_id,
            "generated_at": _now_iso(),
            "intake_id": intake_id,
            "plan_only": True,
            "scope": "work_intake_ticket",
            "source_ref": source_ref,
            "source_type": source_type,
            "steps": [
                {"kind": "ANALYZE", "summary": f"Inspect intake item {intake_id} for safe-only workspace actions."},
                {"kind": "PLAN_ONLY", "summary": "Draft plan; no changes applied without safe-only executor."},
            ],
            "title": title,
        }
        _write_json(plan_path, plan_obj)
        md_path = plan_path.with_suffix(".plan.md")
        md_path.write_text(
            "\n".join(
                [
                    f"CHG PLAN: {chg_id}",
                    "",
                    f"Item: {intake_id}",
                    f"Source: {source_ref}",
                    "",
                    "Plan-only steps drafted.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    return str(plan_rel.as_posix())


def run_work_intake_exec_ticket(*, workspace_root: Path, limit: int) -> dict[str, Any]:
    core_root = Path(__file__).resolve().parents[2]
    policy, policy_source, policy_hash = _load_policy(core_root=core_root, workspace_root=workspace_root)

    if not bool(policy.get("enabled", True)):
        return {"status": "IDLE", "error_code": "POLICY_DISABLED"}

    apply_scope = str(policy.get("apply_scope") or "WORKSPACE_ONLY")
    if apply_scope != "WORKSPACE_ONLY":
        return {"status": "IDLE", "error_code": "INVALID_APPLY_SCOPE"}

    work_intake_path = workspace_root / ".cache" / "index" / "work_intake.v1.json"
    if not work_intake_path.exists():
        return {"status": "IDLE", "error_code": "WORK_INTAKE_MISSING"}
    try:
        work_intake = _load_json(work_intake_path)
    except Exception:
        return {"status": "WARN", "error_code": "WORK_INTAKE_INVALID"}
    items = work_intake.get("items") if isinstance(work_intake.get("items"), list) else []

    ticket_items = [
        item
        for item in items
        if isinstance(item, dict)
        and item.get("bucket") == "TICKET"
        and str(item.get("status") or "").upper() in {"OPEN", "PLANNED"}
    ]
    ticket_items.sort(
        key=lambda x: (
            _priority_rank(str(x.get("priority"))),
            _severity_rank(str(x.get("severity"))),
            str(x.get("intake_id") or ""),
        )
    )
    selected = ticket_items[: max(0, int(limit))]

    doc_nav_report = _load_doc_nav_report(workspace_root)
    unsafe_kinds = {str(x) for x in (policy.get("unsafe_kinds") or []) if isinstance(x, str)}

    entries: list[dict[str, Any]] = []
    applied = 0
    planned = 0
    idle = 0

    for item in selected:
        intake_id = str(item.get("intake_id") or "")
        source_type = str(item.get("source_type") or "")
        source_ref = str(item.get("source_ref") or "")
        title = str(item.get("title") or "")

        manual_request = _load_manual_request(workspace_root, source_ref) if source_type == "MANUAL_REQUEST" else None
        manual_scope_present = isinstance(manual_request, dict) and "impact_scope" in manual_request
        manual_kind = str(manual_request.get("kind") or "unspecified") if isinstance(manual_request, dict) else ""
        manual_scope = (
            str(manual_request.get("impact_scope") or "workspace-only") if isinstance(manual_request, dict) else "workspace-only"
        )
        manual_requires_core_change = (
            bool(manual_request.get("requires_core_change", False)) if isinstance(manual_request, dict) else False
        )
        if isinstance(manual_request, dict):
            constraints = manual_request.get("constraints") if isinstance(manual_request.get("constraints"), dict) else {}
            if not manual_requires_core_change and bool(constraints.get("requires_core_change", False)):
                manual_requires_core_change = True
        context = {
            "doc_nav_broken_refs": doc_nav_report.get("broken_refs", 0),
            "manual_request_kind": manual_kind,
            "manual_request_impact_scope": manual_scope,
            "path": source_ref if source_type == "SCRIPT_BUDGET" else "",
        }

        action_kind, plan_only, rule_id = _select_action(
            policy=policy, source_type=source_type, context=context
        )
        if action_kind in unsafe_kinds:
            plan_only = True
        if source_type == "MANUAL_REQUEST" and action_kind == "WRITE_DOC_NOTE" and not plan_only:
            allowed_kinds = policy.get("safe_only_apply_manual_request_kinds")
            allowed_kinds = allowed_kinds if isinstance(allowed_kinds, list) else []
            allowed_scopes = policy.get("safe_only_apply_manual_request_scopes")
            allowed_scopes = allowed_scopes if isinstance(allowed_scopes, list) else []
            disallowed_scopes = {"core-change", "external-change"}
            if manual_kind not in [str(x) for x in allowed_kinds if isinstance(x, str)]:
                plan_only = True
            if allowed_scopes and manual_scope not in [str(x) for x in allowed_scopes if isinstance(x, str)]:
                plan_only = True
            if not manual_scope_present:
                plan_only = True
            if manual_scope in disallowed_scopes:
                plan_only = True
            if manual_requires_core_change:
                plan_only = True
        gap_type = ""
        if source_type == "GAP":
            src_upper = source_ref.upper()
            title_upper = title.upper()
            if "COVERAGE" in src_upper or "COVERAGE" in title_upper:
                gap_type = "COVERAGE"
        if source_type == "GAP" and not plan_only:
            allowed_gap_types = policy.get("safe_only_apply_gap_types")
            allowed_gap_types = allowed_gap_types if isinstance(allowed_gap_types, list) else []
            if gap_type and gap_type in [str(x) for x in allowed_gap_types if isinstance(x, str)]:
                action_kind = "WRITE_DOC_NOTE"
                plan_only = False
            else:
                plan_only = True
        if source_type == "SCRIPT_BUDGET" and not plan_only:
            allowed_sources = policy.get("safe_only_apply_script_budget_sources")
            allowed_sources = allowed_sources if isinstance(allowed_sources, list) else []
            forbidden_prefixes = policy.get("forbidden_safe_only_path_prefixes")
            forbidden_prefixes = forbidden_prefixes if isinstance(forbidden_prefixes, list) else []
            path_val = source_ref
            if _match_any([str(x) for x in forbidden_prefixes if isinstance(x, str)], path_val):
                plan_only = True
            elif _match_any([str(x) for x in allowed_sources if isinstance(x, str)], path_val):
                action_kind = "WRITE_DOC_NOTE"
                plan_only = False
            else:
                plan_only = True

        entry: dict[str, Any] = {
            "intake_id": intake_id,
            "bucket": item.get("bucket"),
            "priority": item.get("priority"),
            "severity": item.get("severity"),
            "source_type": source_type,
            "source_ref": source_ref,
            "title": title,
            "action_kind": action_kind,
            "apply_scope": "WORKSPACE_ONLY",
            "rule_id": rule_id,
        }

        if action_kind == "WRITE_DOC_NOTE" and not plan_only:
            if source_type == "MANUAL_REQUEST" and manual_kind in {"doc-fix", "doc-link-fix", "doc-metadata", "note"}:
                if manual_kind == "note":
                    note_path = _write_note(
                        workspace_root=workspace_root,
                        note_id=source_ref or intake_id,
                        title=title,
                        reason="SAFE_ONLY_NOTE",
                        source_ref=source_ref,
                    )
                    entry["status"] = "APPLIED"
                    entry["note_path"] = note_path
                    entry["evidence_paths"] = [note_path]
                else:
                    json_path, md_path = _write_doc_fix_suggestions(
                        workspace_root=workspace_root,
                        request_id=source_ref or intake_id,
                        title=title,
                        reason=f"SAFE_ONLY_{manual_kind.upper().replace('-', '_')}",
                    )
                    entry["status"] = "APPLIED"
                    entry["doc_fix_suggestions_path"] = json_path
                    entry["doc_fix_suggestions_md_path"] = md_path
                    entry["evidence_paths"] = [json_path, md_path]
            elif source_type == "DOC_NAV":
                broken_refs = doc_nav_report.get("broken_ref_items", [])
                if doc_nav_report.get("broken_refs", 0) > 0:
                    json_path, md_path = _write_doc_nav_fix_plan(
                        workspace_root=workspace_root,
                        broken_refs=broken_refs if isinstance(broken_refs, list) else [],
                    )
                    entry["status"] = "APPLIED"
                    entry["doc_nav_fix_plan_path"] = json_path
                    entry["doc_nav_fix_plan_md_path"] = md_path
                    entry["evidence_paths"] = [json_path, md_path]
                else:
                    entry["status"] = "IDLE"
                    entry["reason"] = "NO_BROKEN_REFS"
            elif source_type == "GAP" and gap_type == "COVERAGE":
                json_path, md_path = _write_gap_coverage_report(
                    workspace_root=workspace_root,
                    gap_id=source_ref or intake_id,
                    title=title,
                    reason="SAFE_ONLY_GAP_COVERAGE",
                )
                entry["status"] = "APPLIED"
                entry["gap_coverage_path"] = json_path
                entry["gap_coverage_md_path"] = md_path
                entry["evidence_paths"] = [json_path, md_path]
            elif source_type == "SCRIPT_BUDGET":
                plan_path = _ensure_plan(
                    workspace_root=workspace_root,
                    intake_id=intake_id,
                    source_type=source_type,
                    source_ref=source_ref,
                    title=title,
                )
                note_path = _write_note(
                    workspace_root=workspace_root,
                    note_id=intake_id,
                    title=title,
                    reason="SAFE_ONLY_SCRIPT_BUDGET",
                    source_ref=source_ref,
                    plan_path=plan_path,
                )
                entry["status"] = "APPLIED"
                entry["note_path"] = note_path
                entry["plan_path"] = plan_path
                entry["evidence_paths"] = [note_path, plan_path]
            else:
                note_path = _write_note(
                    workspace_root=workspace_root,
                    note_id=intake_id,
                    title=title,
                    reason="SAFE_ONLY_NOTE",
                    source_ref=source_ref,
                )
                entry["status"] = "APPLIED"
                entry["note_path"] = note_path
                entry["evidence_paths"] = [note_path]
        if entry.get("status") == "APPLIED":
            if bool(policy.get("applied_requires_evidence_path", False)):
                evidence = entry.get("evidence_paths")
                if not isinstance(evidence, list) or not evidence:
                    entry["status"] = "IDLE"
                    entry["reason"] = "MISSING_EVIDENCE"
                    idle += 1
                else:
                    applied += 1
            else:
                applied += 1
        elif entry.get("status") == "IDLE":
            idle += 1
        else:
            plan_path = _ensure_plan(
                workspace_root=workspace_root,
                intake_id=intake_id,
                source_type=source_type,
                source_ref=source_ref,
                title=title,
            )
            entry["status"] = "PLANNED"
            entry["plan_path"] = plan_path
            entry["reason"] = "PLAN_ONLY"
            entry["evidence_paths"] = [plan_path]
            planned += 1

        entries.append(entry)

    report = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "selection_rule": "bucket=TICKET sort by priority,severity,intake_id",
        "policy_source": policy_source,
        "policy_hash": policy_hash,
        "applied_count": applied,
        "planned_count": planned,
        "idle_count": idle,
        "entries": entries,
        "notes": ["CORE_LOCK=ENABLED", "SAFE_ONLY_REQUESTED=true", "WORKSPACE_ONLY=true"],
    }

    out_json = workspace_root / ".cache" / "reports" / "work_intake_exec_ticket.v1.json"
    out_md = workspace_root / ".cache" / "reports" / "work_intake_exec_ticket.v1.md"
    _ensure_inside_workspace(workspace_root, out_json)
    _ensure_inside_workspace(workspace_root, out_md)
    _write_json(out_json, report)

    md_lines = [
        "WORK INTAKE TICKET EXECUTION",
        "",
        "Selection: bucket=TICKET sort by priority,severity,intake_id",
        f"Policy source: {policy_source}",
        f"Policy hash: {policy_hash}",
        f"Applied: {applied}",
        f"Planned: {planned}",
        f"Idle: {idle}",
        "",
    ]
    for entry in entries:
        line = f"- {entry.get('intake_id')} status={entry.get('status')}"
        if entry.get("note_path"):
            line += f" note={entry.get('note_path')}"
        if entry.get("plan_path"):
            line += f" plan={entry.get('plan_path')}"
        md_lines.append(line)
    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    return {
        "status": "OK",
        "work_intake_exec_path": str(Path(".cache") / "reports" / "work_intake_exec_ticket.v1.json"),
        "work_intake_exec_md_path": str(Path(".cache") / "reports" / "work_intake_exec_ticket.v1.md"),
        "applied_count": applied,
        "planned_count": planned,
        "idle_count": idle,
        "entries_count": len(entries),
    }
