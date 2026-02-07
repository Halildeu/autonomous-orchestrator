from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.work_intake_from_sources import run_work_intake_build
from src.prj_airunner.auto_mode_dispatch import auto_mode_network_allowed, load_auto_mode_policy, plan_auto_mode_dispatch
from src.ops.work_intake_exec_ticket import (
    _load_doc_nav_report,
    _load_manual_request,
    _load_policy as _load_exec_policy,
    _match_any,
    _select_action,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel_to_workspace(path: Path, workspace_root: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _ensure_inside_workspace(workspace_root: Path, target: Path) -> None:
    workspace_root = workspace_root.resolve()
    target = target.resolve()
    target.relative_to(workspace_root)


def _priority_rank(value: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}.get(value, 99)


def _severity_rank(value: str) -> int:
    return {"S0": 0, "S1": 1, "S2": 2, "S3": 3, "S4": 4}.get(value, 99)


def _load_decisions_applied(workspace_root: Path) -> list[dict[str, Any]]:
    path = workspace_root / ".cache" / "index" / "decisions_applied.v1.jsonl"
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            items.append(obj)
    return items


def _decision_allows_auto_apply(decisions: list[dict[str, Any]], intake_id: str) -> bool:
    for item in decisions:
        source_intake_id = str(item.get("source_intake_id") or "")
        if source_intake_id != intake_id and source_intake_id != f"SEED:{intake_id}":
            continue
        if str(item.get("decision_kind") or "") != "AUTO_APPLY_ALLOW":
            continue
        option_id = str(item.get("option_id") or "")
        if option_id and option_id not in {"A", "KEEP"}:
            return True
    return False


def _manual_request_meta(workspace_root: Path, source_ref: str) -> dict[str, Any]:
    manual_request = _load_manual_request(workspace_root, source_ref)
    if not isinstance(manual_request, dict):
        return {}
    manual_scope_present = "impact_scope" in manual_request
    manual_kind = str(manual_request.get("kind") or "unspecified")
    manual_scope = str(manual_request.get("impact_scope") or "workspace-only")
    manual_requires_core_change = bool(manual_request.get("requires_core_change", False))
    constraints = manual_request.get("constraints") if isinstance(manual_request.get("constraints"), dict) else {}
    if not manual_requires_core_change and bool(constraints.get("requires_core_change", False)):
        manual_requires_core_change = True
    return {
        "manual_scope_present": manual_scope_present,
        "manual_kind": manual_kind,
        "manual_scope": manual_scope,
        "manual_requires_core_change": manual_requires_core_change,
    }


def _safe_only_candidate(
    *,
    item: dict[str, Any],
    policy: dict[str, Any],
    doc_nav_report: dict[str, Any],
    decisions_applied: list[dict[str, Any]],
    workspace_root: Path,
) -> bool:
    source_type = str(item.get("source_type") or "")
    source_ref = str(item.get("source_ref") or "")
    title = str(item.get("title") or "")
    intake_id = str(item.get("intake_id") or "")
    autopilot_allowed = bool(item.get("autopilot_allowed", False))

    decision_override = _decision_allows_auto_apply(decisions_applied, intake_id)
    effective_allowed = autopilot_allowed or decision_override

    manual_meta = _manual_request_meta(workspace_root, source_ref) if source_type == "MANUAL_REQUEST" else {}
    context = {
        "doc_nav_broken_refs": doc_nav_report.get("broken_refs", 0),
        "manual_request_kind": manual_meta.get("manual_kind", ""),
        "manual_request_impact_scope": manual_meta.get("manual_scope", ""),
        "path": source_ref if source_type == "SCRIPT_BUDGET" else "",
    }

    action_kind, plan_only, _ = _select_action(policy=policy, source_type=source_type, context=context)
    unsafe_kinds = {str(x) for x in (policy.get("unsafe_kinds") or []) if isinstance(x, str)}
    if not effective_allowed:
        plan_only = True
    if action_kind in unsafe_kinds:
        plan_only = True

    if source_type == "MANUAL_REQUEST" and action_kind == "WRITE_DOC_NOTE" and not plan_only:
        allowed_kinds = policy.get("safe_only_apply_manual_request_kinds")
        allowed_kinds = allowed_kinds if isinstance(allowed_kinds, list) else []
        allowed_scopes = policy.get("safe_only_apply_manual_request_scopes")
        allowed_scopes = allowed_scopes if isinstance(allowed_scopes, list) else []
        disallowed_scopes = {"core-change", "external-change"}
        if manual_meta.get("manual_kind") not in [str(x) for x in allowed_kinds if isinstance(x, str)]:
            plan_only = True
        if allowed_scopes and manual_meta.get("manual_scope") not in [str(x) for x in allowed_scopes if isinstance(x, str)]:
            plan_only = True
        if not manual_meta.get("manual_scope_present"):
            plan_only = True
        if manual_meta.get("manual_scope") in disallowed_scopes:
            plan_only = True
        if manual_meta.get("manual_requires_core_change"):
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

    return action_kind == "WRITE_DOC_NOTE" and not plan_only


def run_doer_actionability(*, workspace_root: Path, out: str = "auto") -> dict[str, Any]:
    core_root = _repo_root()
    build_res = run_work_intake_build(workspace_root=workspace_root)
    work_intake_path = build_res.get("work_intake_path") if isinstance(build_res, dict) else None
    if not isinstance(work_intake_path, str) or not work_intake_path:
        work_intake_path = ".cache/index/work_intake.v1.json"

    intake_path = (workspace_root / work_intake_path).resolve()
    status = "OK"
    error_code = None
    extra_notes: list[str] = []
    if not intake_path.exists():
        status = "IDLE"
        error_code = "WORK_INTAKE_MISSING"
        intake_obj = {}
        extra_notes.append("work_intake_missing")
    else:
        try:
            intake_obj = _load_json(intake_path)
        except Exception:
            intake_obj = {}
            status = "WARN"
            error_code = "WORK_INTAKE_INVALID"
            extra_notes.append("work_intake_invalid")
    items = intake_obj.get("items") if isinstance(intake_obj.get("items"), list) else []

    auto_mode_policy, _, _, _ = load_auto_mode_policy(workspace_root=workspace_root)
    auto_mode_mode = str(auto_mode_policy.get("mode") or "mixed")
    auto_mode_enabled = bool(auto_mode_policy.get("enabled", False))
    dispatch_plan = plan_auto_mode_dispatch(items=items, policy=auto_mode_policy, workspace_root=workspace_root)
    job_candidates = (
        dispatch_plan.get("job_candidates") if isinstance(dispatch_plan.get("job_candidates"), list) else []
    )

    exec_policy, _, _ = _load_exec_policy(core_root=core_root, workspace_root=workspace_root)
    doc_nav_report = _load_doc_nav_report(workspace_root)
    decisions_applied = _load_decisions_applied(workspace_root)

    tickets = [
        item
        for item in items
        if isinstance(item, dict)
        and str(item.get("bucket") or "") == "TICKET"
        and str(item.get("status") or "").upper() in {"OPEN", "PLANNED"}
    ]
    tickets.sort(
        key=lambda x: (
            _priority_rank(str(x.get("priority") or "")),
            _severity_rank(str(x.get("severity") or "")),
            str(x.get("intake_id") or ""),
        )
    )

    reason_counts = {
        "NOT_SELECTED": 0,
        "DECISION_NEEDED": 0,
        "NOT_SAFE_ONLY": 0,
        "NETWORK_DISABLED": 0,
        "POLICY_BLOCKED": 0,
    }
    sample_ids: dict[str, list[str]] = {k: [] for k in reason_counts}
    skip_reason_counts = {
        "DECISION_NEEDED": 0,
        "NOT_SAFE_ONLY": 0,
        "NETWORK_DISABLED": 0,
        "POLICY_BLOCKED": 0,
    }

    counts = {
        "total_intake": len(items),
        "candidate_total": 0,
        "selected": 0,
        "autopilot_allowed": 0,
        "decision_needed": 0,
        "safe_only": 0,
        "job_needed": 0,
        "network_blocked": 0,
        "policy_blocked": 0,
        "skipped": 0,
    }

    for item in tickets:
        intake_id = str(item.get("intake_id") or "")
        autopilot_allowed = bool(item.get("autopilot_allowed", False))
        autopilot_selected = bool(item.get("autopilot_selected", False))
        autopilot_reason = str(item.get("autopilot_reason") or "")

        if autopilot_allowed:
            counts["autopilot_allowed"] += 1
        if autopilot_selected:
            counts["selected"] += 1

        decision_override = _decision_allows_auto_apply(decisions_applied, intake_id)
        effective_allowed = autopilot_allowed or decision_override

        if not autopilot_selected:
            reason_counts["NOT_SELECTED"] += 1
            if intake_id and len(sample_ids["NOT_SELECTED"]) < 5:
                sample_ids["NOT_SELECTED"].append(intake_id)
            continue
        if not effective_allowed:
            reason = "DECISION_NEEDED"
            if autopilot_reason in {"REQUIRES_CORE_UNLOCK", "POLICY_BLOCKED"}:
                reason = "POLICY_BLOCKED"
            if autopilot_reason == "NETWORK_DISABLED":
                reason = "NETWORK_DISABLED"
            reason_counts[reason] += 1
            skip_reason_counts[reason] += 1
            if intake_id and len(sample_ids[reason]) < 5:
                sample_ids[reason].append(intake_id)
            if reason == "DECISION_NEEDED":
                counts["decision_needed"] += 1
            if reason == "POLICY_BLOCKED":
                counts["policy_blocked"] += 1
            if reason == "NETWORK_DISABLED":
                counts["network_blocked"] += 1
            continue

        if _safe_only_candidate(
            item=item,
            policy=exec_policy,
            doc_nav_report=doc_nav_report,
            decisions_applied=decisions_applied,
            workspace_root=workspace_root,
        ):
            counts["safe_only"] += 1
        else:
            reason_counts["NOT_SAFE_ONLY"] += 1
            skip_reason_counts["NOT_SAFE_ONLY"] += 1
            if intake_id and len(sample_ids["NOT_SAFE_ONLY"]) < 5:
                sample_ids["NOT_SAFE_ONLY"].append(intake_id)

    if auto_mode_enabled and job_candidates:
        counts["job_needed"] = len(job_candidates)
        for job in job_candidates:
            intake_id = str(job.get("intake_id") or "")
            extension_id = str(job.get("extension_id") or "")
            allow_network, _ = auto_mode_network_allowed(
                workspace_root=workspace_root, policy=auto_mode_policy, extension_id=extension_id
            )
            if not allow_network:
                counts["network_blocked"] += 1
                reason_counts["NETWORK_DISABLED"] += 1
                if intake_id and len(sample_ids["NETWORK_DISABLED"]) < 5:
                    sample_ids["NETWORK_DISABLED"].append(intake_id)

    counts["candidate_total"] = counts["selected"]
    counts["skipped"] = sum(skip_reason_counts.values())
    skipped_by_reason = {
        reason: skip_reason_counts[reason]
        for reason in sorted(skip_reason_counts)
        if skip_reason_counts[reason] > 0
    }
    if counts["skipped"] > 0 and not skipped_by_reason:
        skipped_by_reason = {"UNKNOWN": counts["skipped"]}

    top_blockers = [
        {"reason": reason, "count": count}
        for reason, count in sorted(reason_counts.items(), key=lambda x: (-x[1], x[0]))
        if count > 0
    ]
    sample_ids_by_reason = {
        reason: sample_ids[reason]
        for reason in sorted(sample_ids)
        if isinstance(sample_ids.get(reason), list) and sample_ids[reason]
    }

    report = {
        "version": "v1",
        "workspace_root": str(workspace_root),
        "generated_at": _now_iso(),
        "mode": {
            "auto_mode": auto_mode_mode if auto_mode_mode in {"selected_only", "mixed", "suggested_only"} else "mixed",
            "autopilot_apply": "selected_only",
        },
        "counts": counts,
        "top_blockers": top_blockers,
        "skipped_by_reason": skipped_by_reason,
        "sample_ids_by_reason": sample_ids_by_reason,
        "notes": ["PROGRAM_LED=true", "NO_WAIT=true"] + extra_notes,
    }

    rel_json = Path(".cache") / "reports" / "doer_actionability.v1.json"
    if out and str(out).strip().lower() not in {"auto", "default"}:
        rel_json = Path(str(out))
    json_path = rel_json if rel_json.is_absolute() else workspace_root / rel_json
    _ensure_inside_workspace(workspace_root, json_path)
    md_path = json_path.with_suffix(".md")
    _ensure_inside_workspace(workspace_root, md_path)

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(_dump_json(report), encoding="utf-8")

    md_lines = [
        "DOER ACTIONABILITY",
        "",
        f"generated_at: {report['generated_at']}",
        f"auto_mode: {report['mode']['auto_mode']}",
        f"autopilot_apply: {report['mode']['autopilot_apply']}",
        "",
        "counts:",
    ]
    for key in [
        "total_intake",
        "candidate_total",
        "selected",
        "autopilot_allowed",
        "skipped",
        "decision_needed",
        "safe_only",
        "job_needed",
        "network_blocked",
        "policy_blocked",
    ]:
        md_lines.append(f"- {key}: {report['counts'][key]}")
    if skipped_by_reason:
        md_lines.append("")
        md_lines.append("skipped_by_reason:")
        for reason in sorted(skipped_by_reason):
            md_lines.append(f"- {reason}: {skipped_by_reason[reason]}")
    if top_blockers:
        md_lines.append("")
        md_lines.append("top_blockers:")
        for entry in top_blockers:
            md_lines.append(f"- {entry['reason']}: {entry['count']}")
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    return {
        "status": status,
        "error_code": error_code,
        "workspace_root": str(workspace_root),
        "report_path": _rel_to_workspace(json_path, workspace_root),
        "report_md_path": _rel_to_workspace(md_path, workspace_root),
        "counts": counts,
        "mode": report["mode"],
        "top_blockers": top_blockers,
        "skipped_by_reason": skipped_by_reason,
        "sample_ids_by_reason": sample_ids_by_reason,
    }
