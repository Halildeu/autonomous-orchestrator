from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from src.ops.system_status_sections_extensions import (
    _airunner_section,
    _airunner_proof_section,
    _auto_heal_section,
    _extensions_section,
    _pm_suite_section,
    _release_section,
)
from src.ops.system_status_sections_intake import (
    _decisions_section,
    _work_intake_exec_section as _work_intake_exec_section_base,
    _work_intake_section,
)
from src.ops.system_status_sections_benchmark import _benchmark_status
from src.ops.portfolio_budget import script_budget_actions_from_report
from src.ops.system_status_sections_git_helpers import _git_status_lines, _parse_git_status_paths
def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
def _parse_iso(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except Exception:
        return None
def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
def _work_intake_exec_section(workspace_root: Path) -> dict[str, Any] | None:
    section = _work_intake_exec_section_base(workspace_root)
    if not isinstance(section, dict):
        return section
    actionability_path = workspace_root / ".cache" / "reports" / "doer_actionability.v1.json"
    if actionability_path.exists():
        section["last_doer_actionability_path"] = _rel_to_workspace(actionability_path, workspace_root)
    exec_rel = section.get("exec_report_path") if isinstance(section.get("exec_report_path"), str) else ""
    exec_abs = (workspace_root / exec_rel).resolve() if exec_rel else None
    if exec_abs and exec_abs.exists():
        section["last_doer_exec_path"] = exec_rel
    else:
        fallback_exec = workspace_root / ".cache" / "reports" / "work_intake_exec_ticket.v1.json"
        if fallback_exec.exists():
            section["last_doer_exec_path"] = _rel_to_workspace(fallback_exec, workspace_root)
    applied = int(section.get("applied_count", 0) or 0)
    planned = int(section.get("planned_count", 0) or 0)
    skipped = int(section.get("skipped_count", 0) or 0)
    skipped_by_reason = section.get("skipped_by_reason") if isinstance(section.get("skipped_by_reason"), dict) else {}
    normalized_skipped = {
        str(k): int(v)
        for k, v in skipped_by_reason.items()
        if isinstance(k, str) and isinstance(v, int) and v >= 0
    }
    if skipped > 0 and not normalized_skipped:
        normalized_skipped = {"UNKNOWN": skipped}
    if "last_doer_exec_path" in section:
        section["last_doer_counts"] = {
            "applied": applied,
            "planned": planned,
            "skipped": skipped,
            "skipped_by_reason": {k: normalized_skipped[k] for k in sorted(normalized_skipped)},
        }
    return section
def _doer_section(workspace_root: Path) -> dict[str, Any] | None:
    actionability_path = workspace_root / ".cache" / "reports" / "doer_actionability.v1.json"
    exec_path = workspace_root / ".cache" / "reports" / "work_intake_exec_ticket.v1.json"
    run_path = workspace_root / ".cache" / "reports" / "airunner_run.v1.json"
    if not (actionability_path.exists() or exec_path.exists() or run_path.exists()):
        return None
    exec_counts: dict[str, Any] | None = None
    exec_mtime: float | None = None
    if exec_path.exists():
        try:
            exec_obj = _load_json(exec_path)
        except Exception:
            exec_obj = {}
        if isinstance(exec_obj, dict):
            skipped_val = int(exec_obj.get("skipped_count") or 0)
            raw_skipped = exec_obj.get("skipped_by_reason") if isinstance(exec_obj.get("skipped_by_reason"), dict) else {}
            normalized_skipped = {
                str(k): int(v)
                for k, v in raw_skipped.items()
                if isinstance(k, str) and isinstance(v, int) and v >= 0
            }
            if skipped_val > 0 and not normalized_skipped:
                normalized_skipped = {"UNKNOWN": skipped_val}
            exec_counts = {
                "applied": int(exec_obj.get("applied_count") or 0),
                "planned": int(exec_obj.get("planned_count") or 0),
                "skipped": skipped_val,
                "skipped_by_reason": {k: normalized_skipped[k] for k in sorted(normalized_skipped)},
            }
        try:
            exec_mtime = exec_path.stat().st_mtime
        except Exception:
            exec_mtime = None
    run_counts: dict[str, Any] | None = None
    run_mtime: float | None = None
    if run_path.exists():
        try:
            run_obj = _load_json(run_path)
        except Exception:
            run_obj = {}
        if isinstance(run_obj, dict):
            doer_counts = run_obj.get("doer_counts") if isinstance(run_obj.get("doer_counts"), dict) else {}
            fallback_counts = run_obj.get("doer_processed_count") if isinstance(run_obj.get("doer_processed_count"), dict) else {}
            source = doer_counts if doer_counts else fallback_counts
            skipped_val = int(source.get("skipped") or 0)
            raw_skipped = source.get("skipped_by_reason") if isinstance(source.get("skipped_by_reason"), dict) else {}
            normalized_skipped = {
                str(k): int(v)
                for k, v in raw_skipped.items()
                if isinstance(k, str) and isinstance(v, int) and v >= 0
            }
            if skipped_val > 0 and not normalized_skipped:
                normalized_skipped = {"UNKNOWN": skipped_val}
            if source:
                run_counts = {
                    "applied": int(source.get("applied") or 0),
                    "planned": int(source.get("planned") or 0),
                    "skipped": skipped_val,
                    "skipped_by_reason": {k: normalized_skipped[k] for k in sorted(normalized_skipped)},
                }
        try:
            run_mtime = run_path.stat().st_mtime
        except Exception:
            run_mtime = None
    last_counts: dict[str, Any] | None = None
    if exec_counts and run_counts:
        if run_mtime is not None and exec_mtime is not None and run_mtime >= exec_mtime:
            last_counts = run_counts
        else:
            last_counts = exec_counts
    elif run_counts:
        last_counts = run_counts
    elif exec_counts:
        last_counts = exec_counts
    if last_counts is None:
        return None
    rel_actionability = str(Path(".cache") / "reports" / "doer_actionability.v1.json")
    rel_exec = str(Path(".cache") / "reports" / "work_intake_exec_ticket.v1.json")
    rel_run = str(Path(".cache") / "reports" / "airunner_run.v1.json")
    return {
        "last_actionability_path": rel_actionability,
        "last_exec_report_path": rel_exec,
        "last_run_path": rel_run,
        "last_counts": last_counts,
    }
def _pack_index_status(workspace_root: Path) -> tuple[str, list[str], int, int, str, str, list[str], str]:
    path = workspace_root / ".cache" / "index" / "pack_capability_index.v1.json"
    rel_path = str(Path(".cache") / "index" / "pack_capability_index.v1.json")
    if not path.exists():
        return ("WARN", [], 0, 0, rel_path, "", ["missing"], "")
    try:
        obj = _load_json(path)
    except Exception:
        return ("WARN", [], 0, 0, rel_path, "", ["invalid_json"], "")
    packs = obj.get("packs") if isinstance(obj, dict) else None
    pack_ids: list[str] = []
    if isinstance(packs, list):
        for p in packs:
            if isinstance(p, dict) and isinstance(p.get("pack_id"), str):
                pack_ids.append(p["pack_id"])
    pack_ids = sorted(set(pack_ids))
    hard_conflicts = obj.get("hard_conflicts") if isinstance(obj, dict) else None
    soft_conflicts = obj.get("soft_conflicts") if isinstance(obj, dict) else None
    hard_count = len(hard_conflicts) if isinstance(hard_conflicts, list) else 0
    soft_count = len(soft_conflicts) if isinstance(soft_conflicts, list) else 0
    hashes = obj.get("hashes") if isinstance(obj, dict) else None
    index_hash = hashes.get("index_sha256") if isinstance(hashes, dict) else ""
    status = "OK"
    if hard_count:
        status = "FAIL"
    elif soft_count:
        status = "WARN"
    return (status, pack_ids, hard_count, soft_count, rel_path, str(index_hash), [], "")
def _pack_validation_report(workspace_root: Path) -> tuple[str | None, int, int, str, list[str]]:
    path = workspace_root / ".cache" / "index" / "pack_validation_report.json"
    rel_path = str(Path(".cache") / "index" / "pack_validation_report.json")
    if not path.exists():
        return (None, 0, 0, "", [])
    try:
        obj = _load_json(path)
    except Exception:
        return ("WARN", 0, 0, rel_path, ["invalid_pack_validation_report"])
    status = obj.get("status") if isinstance(obj, dict) else None
    if status not in {"OK", "WARN", "FAIL"}:
        status = "WARN"
    hard_conflicts = obj.get("hard_conflicts") if isinstance(obj, dict) else None
    soft_conflicts = obj.get("soft_conflicts") if isinstance(obj, dict) else None
    hard_count = len(hard_conflicts) if isinstance(hard_conflicts, list) else 0
    soft_count = len(soft_conflicts) if isinstance(soft_conflicts, list) else 0
    warnings = obj.get("warnings") if isinstance(obj, dict) else None
    notes = [str(w) for w in warnings if isinstance(w, str)] if isinstance(warnings, list) else []
    return (str(status), hard_count, soft_count, rel_path, notes)
def _pack_selection_trace(workspace_root: Path) -> tuple[list[str], str, list[str]]:
    path = workspace_root / ".cache" / "index" / "pack_selection_trace.v1.json"
    rel_path = str(Path(".cache") / "index" / "pack_selection_trace.v1.json")
    if not path.exists():
        return ([], rel_path, ["missing_selection_trace"])
    try:
        obj = _load_json(path)
    except Exception:
        return ([], rel_path, ["invalid_selection_trace"])
    selected = obj.get("selected_pack_ids") if isinstance(obj, dict) else None
    selected_ids = [x for x in selected if isinstance(x, str)] if isinstance(selected, list) else []
    return (sorted(set(selected_ids)), rel_path, [])
def _doc_graph_section(core_root: Path, workspace_root: Path, *, allow_write: bool) -> dict[str, Any] | None:
    report_path = workspace_root / ".cache" / "reports" / "doc_graph_report.v1.json"
    rel_path = str(Path(".cache") / "reports" / "doc_graph_report.v1.json")
    report_obj: dict[str, Any] | None = None
    if report_path.exists():
        try:
            report_obj = _load_json(report_path)
        except Exception:
            report_obj = None
    elif allow_write:
        try:
            from src.ops.doc_graph import run_doc_graph
            report_obj = run_doc_graph(
                repo_root=core_root,
                workspace_root=workspace_root,
                out_json=report_path,
                mode="report",
            )
        except Exception:
            report_obj = None
    else:
        try:
            from src.ops.doc_graph import generate_doc_graph_report, _load_policy
            policy = _load_policy(core_root, workspace_root)
            report_obj = generate_doc_graph_report(
                repo_root=core_root,
                workspace_root=workspace_root,
                policy=policy,
            )
        except Exception:
            report_obj = None
    if not isinstance(report_obj, dict):
        return None
    counts = report_obj.get("counts") if isinstance(report_obj.get("counts"), dict) else {}
    broken_count = int(counts.get("broken_refs", 0))
    orphan_count = int(counts.get("orphan_critical", 0))
    ambiguity_count = int(counts.get("ambiguity", counts.get("ambiguity_count", 0)))
    critical_nav_gaps = int(counts.get("critical_nav_gaps", 0))
    placeholder_count = int(counts.get("placeholder_refs_count", 0))
    placeholders_baseline = report_obj.get("placeholders_baseline")
    placeholders_delta = report_obj.get("placeholders_delta")
    placeholders_warn_mode = report_obj.get("placeholders_warn_mode")
    status = report_obj.get("status") if isinstance(report_obj.get("status"), str) else "WARN"
    if status not in {"OK", "WARN", "FAIL"}:
        status = "WARN"
    broken = report_obj.get("broken_refs") if isinstance(report_obj.get("broken_refs"), list) else []
    orphans = report_obj.get("orphan_critical") if isinstance(report_obj.get("orphan_critical"), list) else []
    top_broken: list[dict[str, Any]] = []
    for item in broken[:10]:
        if isinstance(item, dict):
            top_broken.append(
                {
                    "source": str(item.get("source", "")),
                    "target": str(item.get("target", "")),
                    "kind": str(item.get("kind", "")),
                }
            )
    top_orphan: list[dict[str, Any]] = []
    for item in orphans[:10]:
        if isinstance(item, dict):
            top_orphan.append(
                {
                    "path": str(item.get("path", "")),
                    "reason": str(item.get("reason", "")),
                }
            )
    notes = report_obj.get("notes") if isinstance(report_obj.get("notes"), list) else []
    notes_list = [str(n) for n in notes if isinstance(n, str)]
    placeholders_delta_val = placeholders_delta if isinstance(placeholders_delta, int) else None
    has_nav_issues = any(
        value > 0
        for value in (
            broken_count,
            orphan_count,
            ambiguity_count,
            critical_nav_gaps,
        )
    )
    if placeholders_delta_val == 0:
        if "placeholders_delta_zero=true" not in notes_list:
            notes_list.append("placeholders_delta_zero=true")
    if status != "FAIL":
        if placeholders_delta_val is not None and placeholders_delta_val > 0 and status == "OK":
            status = "WARN"
            if "placeholders_delta_warn=true" not in notes_list:
                notes_list.append("placeholders_delta_warn=true")
        if placeholders_delta_val == 0 and status == "WARN" and not has_nav_issues:
            status = "OK"
            if "placeholders_delta_no_warn=true" not in notes_list:
                notes_list.append("placeholders_delta_no_warn=true")
    payload: dict[str, Any] = {
        "status": status,
        "report_path": rel_path,
        "broken_refs": broken_count,
        "placeholder_refs_count": placeholder_count,
        "orphan_critical": orphan_count,
        "ambiguity": ambiguity_count,
        "critical_nav_gaps": critical_nav_gaps,
        "top_broken": top_broken,
        "top_orphan": top_orphan,
        "notes": notes_list,
    }
    if isinstance(placeholders_baseline, int):
        payload["placeholders_baseline"] = placeholders_baseline
    if isinstance(placeholders_delta, int):
        payload["placeholders_delta"] = placeholders_delta
    if isinstance(placeholders_warn_mode, str):
        payload["placeholders_warn_mode"] = placeholders_warn_mode
    return payload
def _formats_status(workspace_root: Path) -> tuple[str, list[str]]:
    path = workspace_root / ".cache" / "index" / "formats.v1.json"
    if not path.exists():
        return ("WARN", [])
    try:
        obj = _load_json(path)
    except Exception:
        return ("WARN", [])
    formats = obj.get("formats") if isinstance(obj, dict) else None
    ids: list[str] = []
    if isinstance(formats, list):
        for f in formats:
            if isinstance(f, dict) and isinstance(f.get("id"), str):
                ids.append(f["id"])
    ids = sorted(set(ids))
    return ("OK", ids)
def _session_status(workspace_root: Path) -> tuple[str, dict[str, Any]]:
    path = workspace_root / ".cache" / "sessions" / "default" / "session_context.v1.json"
    if not path.exists():
        return (
            "WARN",
            {"session_id": "default", "ttl_seconds": 0, "expires_at": "", "session_context_hash": ""},
        )
    try:
        obj = _load_json(path)
    except Exception:
        return (
            "WARN",
            {"session_id": "default", "ttl_seconds": 0, "expires_at": "", "session_context_hash": ""},
        )
    ttl = obj.get("ttl_seconds") if isinstance(obj, dict) else None
    expires_at = obj.get("expires_at") if isinstance(obj, dict) else None
    hashes = obj.get("hashes") if isinstance(obj, dict) else None
    sha = hashes.get("session_context_sha256") if isinstance(hashes, dict) else None
    ttl_i = int(ttl) if isinstance(ttl, int) else 0
    expires_s = str(expires_at) if isinstance(expires_at, str) else ""
    sha_s = str(sha) if isinstance(sha, str) else ""
    return ("OK", {"session_id": "default", "ttl_seconds": ttl_i, "expires_at": expires_s, "session_context_hash": sha_s})
def _quality_status(workspace_root: Path) -> tuple[str, str]:
    path = workspace_root / ".cache" / "index" / "quality_gate_report.v1.json"
    if not path.exists():
        return ("WARN", "missing")
    try:
        obj = _load_json(path)
    except Exception:
        return ("FAIL", "invalid_json")
    status = obj.get("status") if isinstance(obj, dict) else None
    if status not in {"OK", "WARN", "FAIL"}:
        status = "WARN"
    summary = f"status={status}"
    return (str(status), summary)
def _integrity_status(workspace_root: Path) -> dict[str, Any]:
    path = workspace_root / ".cache" / "reports" / "integrity_verify.v1.json"
    rel = str(Path(".cache") / "reports" / "integrity_verify.v1.json")
    if not path.exists():
        return {
            "status": "WARN",
            "last_verify_path": rel,
            "verify_on_read_result": "WARN",
            "mismatch_count": 0,
        }
    try:
        obj = _load_json(path)
    except Exception:
        return {
            "status": "WARN",
            "last_verify_path": rel,
            "verify_on_read_result": "WARN",
            "mismatch_count": 0,
        }
    verify = obj.get("verify_on_read_result") if isinstance(obj, dict) else None
    mismatch_count = obj.get("mismatch_count") if isinstance(obj, dict) else None
    status = "OK" if verify == "PASS" else "WARN"
    return {
        "status": status,
        "last_verify_path": rel,
        "verify_on_read_result": verify if verify in {"PASS", "WARN", "FAIL"} else "WARN",
        "mismatch_count": int(mismatch_count or 0),
    }
def _pdca_status(workspace_root: Path) -> dict[str, Any]:
    report_path = workspace_root / ".cache" / "reports" / "pdca_recheck_report.v1.json"
    cursor_path = workspace_root / ".cache" / "index" / "pdca_cursor.v1.json"
    rel_report = str(Path(".cache") / "reports" / "pdca_recheck_report.v1.json")
    rel_cursor = str(Path(".cache") / "index" / "pdca_cursor.v1.json")
    status = "WARN"
    regressions_count = 0
    quota_state = "UNKNOWN"
    cooldown_state = "UNKNOWN"
    if report_path.exists():
        try:
            obj = _load_json(report_path)
            rep_status = obj.get("status") if isinstance(obj, dict) else None
            status = rep_status if rep_status in {"OK", "WARN"} else "WARN"
            regressions_count = int(obj.get("regressions_count") or 0) if isinstance(obj, dict) else 0
            quota_state = str(obj.get("quota_state") or "UNKNOWN") if isinstance(obj, dict) else "UNKNOWN"
            cooldown_state = str(obj.get("cooldown_state") or "UNKNOWN") if isinstance(obj, dict) else "UNKNOWN"
        except Exception:
            status = "WARN"
    cursor_state = "MISSING"
    if cursor_path.exists():
        try:
            obj = _load_json(cursor_path)
            gen = obj.get("generated_at") if isinstance(obj, dict) else None
            ts = _parse_iso(gen) if isinstance(gen, str) else None
            if ts is None:
                cursor_state = "STALE"
            else:
                delta_days = (datetime.now(timezone.utc) - ts).days
                cursor_state = "FRESH" if delta_days < 2 else "STALE"
        except Exception:
            cursor_state = "STALE"
    return {
        "status": status,
        "last_recheck_path": rel_report,
        "regressions_count": int(regressions_count),
        "quota_state": quota_state,
        "cooldown_state": cooldown_state,
        "cursor_state": f"{cursor_state} ({rel_cursor})",
    }
def _spec_core_status(core_root: Path) -> tuple[str, list[str], list[str], list[str]]:
    required_paths = [
        "schemas/spec-core.schema.json",
        "schemas/spec-capability.schema.json",
    ]
    example_paths = ["capabilities/CAP-PR-PACKAGER.v1.json"]
    missing: list[str] = []
    notes: list[str] = []
    for rel in required_paths:
        if not (core_root / rel).exists():
            missing.append(rel)
    for rel in example_paths:
        if not (core_root / rel).exists():
            missing.append(rel)
    # Lightweight validation: ensure capability example declares meta.kind == CAPABILITY.
    example_path = core_root / "capabilities" / "CAP-PR-PACKAGER.v1.json"
    if example_path.exists():
        try:
            obj = _load_json(example_path)
            meta = obj.get("meta") if isinstance(obj, dict) else None
            kind = meta.get("kind") if isinstance(meta, dict) else None
            if kind != "CAPABILITY":
                notes.append("CAPABILITY_KIND_MISMATCH")
        except Exception:
            notes.append("CAPABILITY_EXAMPLE_INVALID_JSON")
    status = "OK" if not missing and not notes else "WARN"
    return (status, required_paths, example_paths, notes)
def _harvest_status(workspace_root: Path) -> tuple[str, int, list[str]]:
    path = workspace_root / ".cache" / "learning" / "public_candidates.v1.json"
    if not path.exists():
        return ("WARN", 0, [])
    try:
        obj = _load_json(path)
    except Exception:
        return ("FAIL", 0, [])
    candidates = obj.get("candidates") if isinstance(obj, dict) else None
    if not isinstance(candidates, list):
        return ("FAIL", 0, [])
    kinds_set: set[str] = set()
    for c in candidates:
        if isinstance(c, dict):
            k = c.get("kind")
            if isinstance(k, str):
                kinds_set.add(k)
    kinds = sorted(kinds_set)
    return ("OK", len(candidates), kinds)
def _advisor_status(workspace_root: Path, max_suggestions: int) -> tuple[str, int, list[str]]:
    path = workspace_root / ".cache" / "learning" / "advisor_suggestions.v1.json"
    if not path.exists():
        return ("WARN", 0, [])
    try:
        obj = _load_json(path)
    except Exception:
        return ("FAIL", 0, [])
    suggestions = obj.get("suggestions") if isinstance(obj, dict) else None
    if not isinstance(suggestions, list):
        return ("FAIL", 0, [])
    kinds_set: set[str] = set()
    for s in suggestions[: max_suggestions if max_suggestions > 0 else len(suggestions)]:
        if isinstance(s, dict):
            k = s.get("kind")
            if isinstance(k, str):
                kinds_set.add(k)
    kinds = sorted(kinds_set)
    return ("OK", len(suggestions), kinds)
def _pack_advisor_status(workspace_root: Path, max_suggestions: int) -> tuple[str, int, list[str], list[str]]:
    path = workspace_root / ".cache" / "learning" / "pack_advisor_suggestions.v1.json"
    if not path.exists():
        return ("WARN", 0, [], [])
    try:
        obj = _load_json(path)
    except Exception:
        return ("FAIL", 0, [], [])
    suggestions = obj.get("suggestions") if isinstance(obj, dict) else None
    if not isinstance(suggestions, list):
        return ("FAIL", 0, [], [])
    kinds_set: set[str] = set()
    pack_ids_set: set[str] = set()
    limit = max_suggestions if max_suggestions > 0 else len(suggestions)
    for s in suggestions[:limit]:
        if isinstance(s, dict):
            k = s.get("kind")
            pid = s.get("pack_id")
            if isinstance(k, str):
                kinds_set.add(k)
            if isinstance(pid, str):
                pack_ids_set.add(pid)
    return ("OK", len(suggestions), sorted(kinds_set), sorted(pack_ids_set))
def _readiness_status(workspace_root: Path) -> tuple[str, int, int]:
    path = workspace_root / ".cache" / "ops" / "autopilot_readiness.v1.json"
    if not path.exists():
        return ("NOT_READY", 1, 0)
    try:
        obj = _load_json(path)
    except Exception:
        return ("NOT_READY", 1, 0)
    status = obj.get("status") if isinstance(obj, dict) else None
    if status not in {"READY", "NOT_READY"}:
        status = "NOT_READY"
    checks = obj.get("checks") if isinstance(obj, dict) else None
    fails = len([c for c in checks if isinstance(c, dict) and c.get("status") == "FAIL"]) if isinstance(checks, list) else 0
    warns = len([c for c in checks if isinstance(c, dict) and c.get("status") == "WARN"]) if isinstance(checks, list) else 0
    return (str(status), int(fails), int(warns))
def _actions_status(workspace_root: Path, max_actions: int) -> tuple[str, int, list[dict[str, Any]]]:
    path = workspace_root / ".cache" / "roadmap_actions.v1.json"
    actions: list[Any] = []
    if path.exists():
        try:
            obj = _load_json(path)
        except Exception:
            return ("WARN", 0, [])
        actions = obj.get("actions") if isinstance(obj, dict) else None
        if not isinstance(actions, list):
            return ("WARN", 0, [])
    core_root = Path(__file__).resolve().parents[2]
    script_budget_actions = script_budget_actions_from_report(core_root)
    if script_budget_actions is not None:
        actions = [
            a
            for a in actions
            if not (
                isinstance(a, dict)
                and (str(a.get("kind") or "") == "SCRIPT_BUDGET" or str(a.get("source") or "") == "SCRIPT_BUDGET")
            )
        ]
        actions.extend(script_budget_actions)
    if not actions:
        return ("OK", 0, [])
    unresolved = [
        a
        for a in actions
        if isinstance(a, dict)
        and a.get("resolved") is not True
        and str(a.get("kind") or "") != "SYSTEM_STATUS_FAIL"
    ]
    unresolved.sort(key=lambda a: str(a.get("action_id") or ""))
    top = []
    for a in unresolved[: max_actions if max_actions > 0 else len(unresolved)]:
        top.append(
            {
                "kind": a.get("kind"),
                "milestone_hint": a.get("milestone_hint") or a.get("target_milestone") or "",
                "severity": a.get("severity") or "",
                "message": a.get("message") or "",
                "resolved": bool(a.get("resolved") is True),
            }
        )
    status = "OK" if not unresolved else "WARN"
    return (status, len(unresolved), top)
def _normalize_core_path(core_root: Path, raw: str) -> Path | None:
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = (core_root / path).resolve()
    else:
        path = path.resolve()
    return path if _is_within_root(path, core_root) else None
def _find_core_dirty_report(core_root: Path, workspace_root: Path) -> tuple[list[str] | None, Path | None]:
    candidates: list[Path] = []
    hint_path = workspace_root / ".cache" / "last_finish_evidence.v1.txt"
    if hint_path.exists():
        try:
            for line in hint_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                resolved = _normalize_core_path(core_root, line)
                if resolved is not None:
                    candidates.append(resolved)
                break
        except Exception:
            pass
    evidence_root = core_root / "evidence" / "roadmap_finish"
    if evidence_root.exists():
        dirs = [d for d in evidence_root.iterdir() if d.is_dir()]
        dirs.sort(key=lambda p: p.name, reverse=True)
        candidates.extend(dirs[:50])
    seen: set[Path] = set()
    for base in candidates:
        if base in seen:
            continue
        seen.add(base)
        report_path = base / "core_dirty_files.json"
        if not report_path.exists():
            continue
        try:
            obj = _load_json(report_path)
        except Exception:
            continue
        if isinstance(obj, list):
            return (obj, report_path)
    return (None, None)
def _write_core_unlock_compliance(
    *, core_root: Path, workspace_root: Path, allowlist: list[str], env_var: str, env_value: str, reason: str
) -> Path:
    report_path = workspace_root / ".cache" / "reports" / "core_unlock_compliance.v1.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = _git_status_lines(core_root) or []
    report = {
        "version": "v1",
        "generated_at": _now_iso8601(),
        "core_unlock_used": True,
        "core_unlock_env_var": env_var,
        "core_unlock_env_value": env_value,
        "core_unlock_reason": reason,
        "allowlist_used": sorted({str(x) for x in allowlist if isinstance(x, str) and str(x).strip()}),
        "changed_files": _parse_git_status_paths(lines),
        "gates_summary": {
            "validate_schemas": "UNKNOWN",
            "smoke_fast": "UNKNOWN",
            "script_budget": "UNKNOWN",
        },
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true"],
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report_path
def _core_integrity_section(core_root: Path, workspace_root: Path) -> dict[str, Any]:
    report, report_path = _find_core_dirty_report(core_root, workspace_root)
    if report_path is not None:
        dirty_lines = [str(x) for x in report if isinstance(x, str) and str(x).strip()]
        rel = report_path.relative_to(core_root).as_posix()
        status = "OK" if not dirty_lines else "FAIL"
        return {
            "status": status,
            "git_clean": not dirty_lines,
            "dirty_files_count": len(dirty_lines),
            "notes": [f"report_path={rel}"],
        }
    lines = _git_status_lines(core_root)
    if lines is None:
        return {
            "status": "WARN",
            "git_clean": False,
            "dirty_files_count": 0,
            "notes": ["git_unavailable"],
        }
    if lines:
        return {
            "status": "FAIL",
            "git_clean": False,
            "dirty_files_count": len(lines),
            "notes": ["git_dirty"],
        }
    return {
        "status": "OK",
        "git_clean": True,
        "dirty_files_count": 0,
        "notes": [],
    }
def _core_lock_section(core_root: Path, workspace_root: Path) -> dict[str, Any]:
    policy_path = workspace_root / "policies" / "policy_core_immutability.v1.json"
    if not policy_path.exists():
        policy_path = core_root / "policies" / "policy_core_immutability.v1.json"
    obj: dict[str, Any] = {}
    if policy_path.exists():
        try:
            loaded = _load_json(policy_path)
            if isinstance(loaded, dict):
                obj = loaded
        except Exception:
            obj = {}
    enabled = bool(obj.get("enabled", True))
    default_mode = str(obj.get("default_mode", "locked"))
    allow = obj.get("allow_core_writes_only_when", {}) if isinstance(obj.get("allow_core_writes_only_when"), dict) else {}
    env_var = str(allow.get("env_var", "CORE_UNLOCK"))
    env_value = str(allow.get("env_value", "1"))
    require_unlock_reason = bool(obj.get("require_unlock_reason", False))
    core_unlock_requested = str(os.environ.get(env_var, "")).strip() == env_value
    core_unlock_reason_present = bool(str(os.environ.get("CORE_UNLOCK_REASON", "")).strip())
    core_unlock_allowed = enabled and default_mode == "locked" and core_unlock_requested
    if require_unlock_reason and not core_unlock_reason_present:
        core_unlock_allowed = False
    core_write_mode = str(obj.get("core_write_mode", "locked"))
    allowlist = obj.get("ssot_write_allowlist", []) if isinstance(obj.get("ssot_write_allowlist"), list) else []
    allowlist_count = len([x for x in allowlist if isinstance(x, str) and x.strip()])
    evidence_paths: list[str] = []
    if core_unlock_requested and core_unlock_reason_present:
        reason = str(os.environ.get("CORE_UNLOCK_REASON", "")).strip()
        compliance_path = _write_core_unlock_compliance(
            core_root=core_root,
            workspace_root=workspace_root,
            allowlist=allowlist,
            env_var=env_var,
            env_value=env_value,
            reason=reason,
        )
        evidence_paths.append(_rel_to_workspace(compliance_path, workspace_root))
    gap_baseline = workspace_root / ".cache" / "reports" / "core_unlock_gap_baseline.v1.json"
    gap_closeout = workspace_root / ".cache" / "reports" / "core_unlock_gap_closeout.v1.json"
    if gap_baseline.exists():
        evidence_paths.append(_rel_to_workspace(gap_baseline, workspace_root))
    if gap_closeout.exists():
        evidence_paths.append(_rel_to_workspace(gap_closeout, workspace_root))
    actions_path = workspace_root / ".cache" / "roadmap_actions.v1.json"
    blocked: list[dict[str, Any]] = []
    if actions_path.exists():
        try:
            obj = _load_json(actions_path)
        except Exception:
            obj = None
        actions = obj.get("actions") if isinstance(obj, dict) else None
        if isinstance(actions, list):
            blocked = [
                a
                for a in actions
                if isinstance(a, dict) and str(a.get("kind") or "") == "CORE_TOUCHED" and not a.get("resolved")
            ]
    status = "WARN" if (not enabled or core_unlock_requested) else "OK"
    return {
        "status": status,
        "enabled": bool(enabled),
        "core_unlock_allowed": bool(core_unlock_allowed),
        "core_unlock_reason_present": bool(core_unlock_reason_present),
        "core_write_mode": core_write_mode,
        "ssot_write_allowlist_count": int(allowlist_count),
        "last_blocked_attempts": len(blocked),
        "evidence_paths": evidence_paths,
    }
def _project_boundary_section(workspace_root: Path) -> dict[str, Any]:
    project_root = workspace_root / "project" / "default"
    manifest = project_root / "project.manifest.v1.json"
    notes: list[str] = []
    if not project_root.exists():
        notes.append("project_root_missing")
    if not manifest.exists():
        notes.append("manifest_missing")
    status = "OK" if manifest.exists() else "WARN"
    return {
        "status": status,
        "project_root": _rel_to_workspace(project_root, workspace_root),
        "manifest_present": bool(manifest.exists()),
        "notes": notes,
    }
def _layer_boundary_section(workspace_root: Path) -> dict[str, Any] | None:
    report_path = workspace_root / ".cache" / "reports" / "layer_boundary_report.v1.json"
    if not report_path.exists():
        return None
    rel = _rel_to_workspace(report_path, workspace_root)
    try:
        obj = _load_json(report_path)
    except Exception:
        return {
            "status": "WARN",
            "report_path": rel,
            "mode": "report",
            "enforcement_mode": "",
            "would_block_count": 0,
            "notes": ["report_invalid"],
        }
    status = obj.get("status") if isinstance(obj, dict) else None
    status_str = status if status in {"OK", "WARN", "FAIL"} else "WARN"
    mode = obj.get("mode") if isinstance(obj, dict) else None
    mode_str = mode if mode in {"report", "strict"} else "report"
    enforcement_mode = obj.get("enforcement_mode") if isinstance(obj, dict) else ""
    would_block = obj.get("would_block") if isinstance(obj, dict) else None
    count = len(would_block) if isinstance(would_block, list) else 0
    notes = obj.get("notes") if isinstance(obj, dict) else None
    return {
        "status": status_str,
        "report_path": rel,
        "mode": mode_str,
        "enforcement_mode": str(enforcement_mode or ""),
        "would_block_count": int(count),
        "notes": notes if isinstance(notes, list) else [],
    }
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
def _project_focus(bench_status: str, actions_top: list[dict[str, Any]]) -> str:
    if bench_status != "OK":
        return "M10_CLOSEOUT"
    for a in actions_top:
        if isinstance(a, dict) and str(a.get("kind") or "") == "SCRIPT_BUDGET":
            return "PRJ-M0-MAINTAINABILITY"
    return "PRJ-KERNEL-API"
def _projects_section(
    core_root: Path,
    workspace_root: Path,
    *,
    bench_status: str,
    actions_top: list[dict[str, Any]],
    actions_count: int,
) -> dict[str, Any]:
    notes: list[str] = []
    projects = _load_project_manifests(core_root)
    active_projects = [p.get("project_id") for p in projects if isinstance(p.get("project_id"), str)]
    active_projects = [str(x) for x in active_projects if x]
    active_projects.sort()
    top_debts: list[dict[str, Any]] = []
    for a in actions_top:
        if not isinstance(a, dict):
            continue
        top_debts.append(
            {
                "kind": str(a.get("kind") or ""),
                "milestone_hint": str(a.get("milestone_hint") or ""),
                "severity": str(a.get("severity") or ""),
                "message": str(a.get("message") or ""),
            }
        )
    next_focus = _project_focus(bench_status, actions_top)
    report_path = workspace_root / ".cache" / "reports" / "portfolio_status.v1.json"
    if report_path.exists():
        try:
            obj = _load_json(report_path)
        except Exception:
            obj = {}
        if isinstance(obj, dict):
            rep_active = obj.get("active_projects")
            if isinstance(rep_active, list) and all(isinstance(x, str) for x in rep_active):
                active_projects = sorted(rep_active)
            rep_debts = obj.get("top_project_debts")
            if isinstance(rep_debts, list):
                top_debts = [
                    {
                        "kind": str(d.get("kind") or ""),
                        "milestone_hint": str(d.get("milestone_hint") or ""),
                        "severity": str(d.get("severity") or ""),
                        "message": str(d.get("message") or ""),
                    }
                    for d in rep_debts
                    if isinstance(d, dict)
                ]
            rep_focus = obj.get("next_project_focus")
            if isinstance(rep_focus, str) and rep_focus:
                next_focus = rep_focus
            rep_notes = obj.get("notes")
            if isinstance(rep_notes, list):
                notes = [str(n) for n in rep_notes if isinstance(n, str)]
    else:
        notes.append("portfolio_status_missing")
    projects_count = len(active_projects) if active_projects else len(projects)
    status = "OK" if projects_count > 0 and actions_count == 0 else "WARN"
    return {
        "status": status,
        "projects_count": projects_count,
        "active_projects": active_projects,
        "top_project_debts": top_debts,
        "next_project_focus": next_focus,
        "notes": notes,
    }
def _rel_to_workspace(path: Path, workspace_root: Path) -> str:
    try:
        return path.relative_to(workspace_root).as_posix()
    except Exception:
        return str(path)
def _repo_hygiene_section(
    *,
    core_root: Path,
    workspace_root: Path,
    include_suggestions: bool,
    allow_write: bool,
) -> dict[str, Any] | None:
    report_path = workspace_root / ".cache" / "repo_hygiene" / "report.json"
    report_obj: dict[str, Any] | None = None
    notes: list[str] = []
    if include_suggestions and allow_write:
        from src.ops.repo_hygiene import run_repo_hygiene
        report_obj = run_repo_hygiene(
            repo_root=core_root,
            layout_path=core_root / "docs" / "OPERATIONS" / "repo-layout.v1.json",
            out_path=report_path,
            mode="suggest",
        )
        notes.append("CHG_DRAFTS_ENABLED")
    elif report_path.exists():
        try:
            obj = _load_json(report_path)
            report_obj = obj if isinstance(obj, dict) else None
        except Exception:
            report_obj = None
            notes.append("REPORT_INVALID_JSON")
    else:
        if include_suggestions and not allow_write:
            notes.append("SUGGESTIONS_DISABLED_DRY_RUN")
        if allow_write:
            from src.ops.repo_hygiene import run_repo_hygiene
            report_obj = run_repo_hygiene(
                repo_root=core_root,
                layout_path=core_root / "docs" / "OPERATIONS" / "repo-layout.v1.json",
                out_path=report_path,
                mode="report",
            )
        else:
            from src.ops.repo_hygiene import run_repo_hygiene
            report_obj = run_repo_hygiene(
                repo_root=core_root,
                layout_path=core_root / "docs" / "OPERATIONS" / "repo-layout.v1.json",
                out_path=None,
                mode="report",
            )
            notes.append("REPORT_NOT_WRITTEN_DRY_RUN")
    if not isinstance(report_obj, dict):
        return None
    summary = report_obj.get("summary") if isinstance(report_obj.get("summary"), dict) else {}
    findings = report_obj.get("findings") if isinstance(report_obj.get("findings"), list) else []
    top_findings: list[dict[str, str]] = []
    for f in findings[:5]:
        if not isinstance(f, dict):
            continue
        top_findings.append(
            {
                "kind": str(f.get("kind") or ""),
                "path": str(f.get("path") or ""),
                "severity": str(f.get("severity") or ""),
            }
        )
    status = report_obj.get("status") if isinstance(report_obj.get("status"), str) else "WARN"
    report_rel = _rel_to_workspace(report_path, workspace_root)
    return {
        "status": status if status in {"OK", "WARN"} else "WARN",
        "report_path": report_rel,
        "unexpected_top_level_dirs": int(summary.get("unexpected_top_level_dirs", 0)),
        "tracked_generated_files": int(summary.get("tracked_generated_files", 0)),
        "top_findings": top_findings,
        "notes": notes,
    }
