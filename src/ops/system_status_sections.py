from __future__ import annotations
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged.get(key, {}), value)
        else:
            merged[key] = value
    return merged

def _iso_core_status(workspace_root: Path) -> tuple[str, list[str], list[str]]:
    base = workspace_root / "tenant" / "TENANT-DEFAULT"
    names = ["context.v1.md", "stakeholders.v1.md", "scope.v1.md", "criteria.v1.md"]
    paths = [str(Path("tenant") / "TENANT-DEFAULT" / n) for n in names]
    missing = [p for p, n in zip(paths, names) if not (base / n).exists()]
    status = "OK" if not missing else "WARN"
    return (status, missing, paths)


def _catalog_status(workspace_root: Path) -> tuple[str, list[str]]:
    path = workspace_root / ".cache" / "index" / "catalog.v1.json"
    if not path.exists():
        return ("WARN", [])
    try:
        obj = _load_json(path)
    except Exception:
        return ("WARN", [])
    packs = obj.get("packs") if isinstance(obj, dict) else None
    ids: list[str] = []
    if isinstance(packs, list):
        for p in packs:
            if isinstance(p, dict) and isinstance(p.get("pack_id"), str):
                ids.append(p["pack_id"])
    ids = sorted(set(ids))
    return ("OK", ids)

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

    return {
        "status": status,
        "report_path": rel_path,
        "broken_refs": broken_count,
        "placeholder_refs_count": placeholder_count,
        "orphan_critical": orphan_count,
        "ambiguity": ambiguity_count,
        "critical_nav_gaps": critical_nav_gaps,
        "top_broken": top_broken,
        "top_orphan": top_orphan,
        "notes": [],
    }


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


def _work_intake_section(workspace_root: Path) -> dict[str, Any] | None:
    intake_path = workspace_root / ".cache" / "index" / "work_intake.v1.json"
    if not intake_path.exists():
        return None
    rel_path = str(Path(".cache") / "index" / "work_intake.v1.json")
    try:
        obj = _load_json(intake_path)
    except Exception:
        return {
            "status": "WARN",
            "work_intake_path": rel_path,
            "items_count": 0,
            "counts_by_bucket": {"ROADMAP": 0, "PROJECT": 0, "TICKET": 0, "INCIDENT": 0},
            "top_next_actions": [],
            "next_intake_focus": "NONE",
            "by_bucket": {"ROADMAP": 0, "PROJECT": 0, "TICKET": 0, "INCIDENT": 0},
            "top_next": [],
        }
    items = obj.get("items") if isinstance(obj, dict) else None
    summary = obj.get("summary") if isinstance(obj, dict) else None
    items_count = len(items) if isinstance(items, list) else 0
    counts_by_bucket = summary.get("counts_by_bucket") if isinstance(summary, dict) else None
    top_next_actions = summary.get("top_next_actions") if isinstance(summary, dict) else None
    next_focus = summary.get("next_intake_focus") if isinstance(summary, dict) else None
    by_bucket = summary.get("by_bucket") if isinstance(summary, dict) else None
    top_next = summary.get("top_next") if isinstance(summary, dict) else None
    status = obj.get("status") if isinstance(obj, dict) else None
    status_str = status if status in {"OK", "WARN", "IDLE"} else "WARN"
    if not isinstance(counts_by_bucket, dict):
        counts_by_bucket = {"ROADMAP": 0, "PROJECT": 0, "TICKET": 0, "INCIDENT": 0}
    if not isinstance(top_next_actions, list):
        top_next_actions = []
    if not isinstance(next_focus, str):
        next_focus = "NONE"
    if not isinstance(by_bucket, dict):
        by_bucket = {"ROADMAP": 0, "PROJECT": 0, "TICKET": 0, "INCIDENT": 0}
    if not isinstance(top_next, list):
        top_next = []
    return {
        "status": status_str,
        "work_intake_path": rel_path,
        "items_count": int(items_count),
        "counts_by_bucket": counts_by_bucket,
        "top_next_actions": top_next_actions[:5],
        "next_intake_focus": next_focus,
        "by_bucket": by_bucket,
        "top_next": top_next[:5],
    }


def _work_intake_exec_section(workspace_root: Path) -> dict[str, Any] | None:
    exec_path = workspace_root / ".cache" / "reports" / "work_intake_exec_ticket.v1.json"
    if not exec_path.exists():
        return None
    rel_path = str(Path(".cache") / "reports" / "work_intake_exec_ticket.v1.json")
    try:
        obj = _load_json(exec_path)
    except Exception:
        return {
            "status": "WARN",
            "exec_report_path": rel_path,
            "policy_source": "missing",
            "policy_hash": "",
            "applied_count": 0,
            "planned_count": 0,
            "idle_count": 0,
        }
    policy_source = str(obj.get("policy_source") or "missing") if isinstance(obj, dict) else "missing"
    policy_hash = str(obj.get("policy_hash") or "") if isinstance(obj, dict) else ""
    applied_count = int(obj.get("applied_count") or 0) if isinstance(obj, dict) else 0
    planned_count = int(obj.get("planned_count") or 0) if isinstance(obj, dict) else 0
    idle_count = int(obj.get("idle_count") or 0) if isinstance(obj, dict) else 0
    status = "OK" if policy_hash else "WARN"
    return {
        "status": status,
        "exec_report_path": rel_path,
        "policy_source": policy_source,
        "policy_hash": policy_hash,
        "applied_count": applied_count,
        "planned_count": planned_count,
        "idle_count": idle_count,
    }


def _benchmark_status(workspace_root: Path) -> dict[str, Any]:
    catalog_path = workspace_root / ".cache" / "index" / "north_star_catalog.v1.json"
    assessment_path = workspace_root / ".cache" / "index" / "assessment.v1.json"
    assessment_raw_path = workspace_root / ".cache" / "index" / "assessment_raw.v1.json"
    assessment_eval_path = workspace_root / ".cache" / "index" / "assessment_eval.v1.json"
    integrity_path = workspace_root / ".cache" / "reports" / "integrity_verify.v1.json"
    scorecard_path = workspace_root / ".cache" / "reports" / "benchmark_scorecard.v1.json"
    gap_path = workspace_root / ".cache" / "index" / "gap_register.v1.json"
    rel_catalog = str(Path(".cache") / "index" / "north_star_catalog.v1.json")
    rel_assessment = str(Path(".cache") / "index" / "assessment.v1.json")
    rel_assessment_raw = str(Path(".cache") / "index" / "assessment_raw.v1.json")
    rel_assessment_eval = str(Path(".cache") / "index" / "assessment_eval.v1.json")
    rel_integrity = str(Path(".cache") / "reports" / "integrity_verify.v1.json")
    rel_scorecard = str(Path(".cache") / "reports" / "benchmark_scorecard.v1.json")
    rel_gap = str(Path(".cache") / "index" / "gap_register.v1.json")

    status = "OK"
    notes: list[str] = []
    controls_count = 0
    metrics_count = 0
    gaps_count = 0
    maturity_avg = 0.0
    gaps_by_severity = {"low": 0, "medium": 0, "high": 0}
    top_next_actions: list[dict[str, str]] = []

    if not catalog_path.exists():
        status = "WARN"
        notes.append("missing_north_star_catalog")
    else:
        try:
            obj = _load_json(catalog_path)
            controls = obj.get("controls") if isinstance(obj, dict) else None
            metrics = obj.get("metrics") if isinstance(obj, dict) else None
            controls_count = len(controls) if isinstance(controls, list) else 0
            metrics_count = len(metrics) if isinstance(metrics, list) else 0
        except Exception:
            status = "FAIL"
            notes.append("invalid_north_star_catalog")

    if not assessment_path.exists() and not assessment_eval_path.exists():
        status = "WARN" if status != "FAIL" else status
        notes.append("missing_assessment")

    if not assessment_raw_path.exists():
        status = "WARN" if status != "FAIL" else status
        notes.append("missing_assessment_raw")

    if not assessment_eval_path.exists():
        status = "WARN" if status != "FAIL" else status
        notes.append("missing_assessment_eval")

    if not integrity_path.exists():
        status = "WARN" if status != "FAIL" else status
        notes.append("missing_integrity_verify")

    if not scorecard_path.exists():
        status = "WARN" if status != "FAIL" else status
        notes.append("missing_scorecard")

    gap_list: list[dict[str, Any]] = []
    if not gap_path.exists():
        status = "WARN" if status != "FAIL" else status
        notes.append("missing_gap_register")
    else:
        try:
            obj = _load_json(gap_path)
            gaps = obj.get("gaps") if isinstance(obj, dict) else None
            gaps_count = len(gaps) if isinstance(gaps, list) else 0
            if isinstance(gaps, list):
                for g in gaps:
                    if isinstance(g, dict):
                        gap_list.append(g)
        except Exception:
            status = "FAIL"
            notes.append("invalid_gap_register")

    total_items = controls_count + metrics_count
    if total_items > 0:
        maturity_avg = max(0.0, 1.0 - (gaps_count / float(total_items)))
    else:
        notes.append("no_controls_or_metrics")

    def _priority(value: str) -> int:
        return {"high": 0, "medium": 1, "low": 2}.get(value, 1)

    def _effort_priority(value: str) -> int:
        return {"low": 0, "medium": 1, "high": 2}.get(value, 1)

    regression_ids: set[str] = set()
    regression_path = workspace_root / ".cache" / "index" / "regression_index.v1.json"
    if regression_path.exists():
        try:
            obj = _load_json(regression_path)
            regs = obj.get("regressions") if isinstance(obj, dict) else None
            if isinstance(regs, list):
                for r in regs:
                    gid = r.get("gap_id") if isinstance(r, dict) else None
                    if isinstance(gid, str) and gid:
                        regression_ids.add(gid)
        except Exception:
            regression_ids = set()

    actions: list[tuple[int, int, int, int, str, dict[str, str]]] = []
    for g in gap_list:
        gap_id = g.get("id") if isinstance(g.get("id"), str) else ""
        severity = g.get("severity") if isinstance(g.get("severity"), str) else "medium"
        risk_class = g.get("risk_class") if isinstance(g.get("risk_class"), str) else severity
        effort = g.get("effort") if isinstance(g.get("effort"), str) else "medium"
        is_regression = gap_id in regression_ids
        if severity in gaps_by_severity:
            gaps_by_severity[severity] += 1
        else:
            gaps_by_severity["medium"] += 1
        actions.append(
            (
                _priority(severity),
                _priority(risk_class),
                0 if is_regression else 1,
                _effort_priority(effort),
                gap_id,
                {"gap_id": gap_id, "severity": severity, "risk_class": risk_class, "effort": effort},
            )
        )

    actions.sort(key=lambda item: (item[0], item[2], item[3], item[4]))
    top_next_actions = [a[5] for a in actions[:5] if a[5].get("gap_id")]

    assessment_path_rel = rel_assessment_eval if assessment_eval_path.exists() else rel_assessment

    return {
        "status": status,
        "controls_count": controls_count,
        "metrics_count": metrics_count,
        "gaps_count": gaps_count,
        "maturity_avg": round(maturity_avg, 4),
        "gaps_by_severity": gaps_by_severity,
        "gaps_summary": gaps_by_severity,
        "top_next_actions": top_next_actions,
        "catalog_path": rel_catalog,
        "assessment_path": assessment_path_rel,
        "last_assessment_raw_path": rel_assessment_raw,
        "last_assessment_eval_path": rel_assessment_eval,
        "last_integrity_verify_path": rel_integrity,
        "scorecard_path": rel_scorecard,
        "gap_register_path": rel_gap,
        "notes": notes,
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
    if not path.exists():
        return ("OK", 0, [])
    try:
        obj = _load_json(path)
    except Exception:
        return ("WARN", 0, [])
    actions = obj.get("actions") if isinstance(obj, dict) else None
    if not isinstance(actions, list):
        return ("WARN", 0, [])
    unresolved = [a for a in actions if isinstance(a, dict) and a.get("resolved") is not True]
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


def _find_auto_heal_report(core_root: Path, workspace_root: Path) -> tuple[dict[str, Any] | None, Path | None]:
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
        report_path = base / "artifact_completeness_report.json"
        if not report_path.exists():
            continue
        try:
            obj = _load_json(report_path)
        except Exception:
            continue
        if isinstance(obj, dict):
            return (obj, report_path)
    return (None, None)


def _git_status_lines(core_root: Path) -> list[str] | None:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=core_root,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    return [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]


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
    core_unlock_requested = str(os.environ.get(env_var, "")).strip() == env_value
    core_unlock_allowed = enabled and default_mode == "locked" and core_unlock_requested
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
        "last_blocked_attempts": len(blocked),
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


def _extensions_section(workspace_root: Path) -> dict[str, Any]:
    rel_path = str(Path(".cache") / "index" / "extension_registry.v1.json")
    path = workspace_root / rel_path
    notes: list[str] = []
    help_rel = str(Path(".cache") / "reports" / "extension_help.v1.json")
    help_path = workspace_root / help_rel
    isolation_summary = {
        "status": "IDLE",
        "workspace_root_base": ".cache/extensions",
        "workspace_roots": [],
        "network_allowed": False,
        "last_run_path": "",
        "notes": ["extension_isolation_policy_missing"],
    }

    if not path.exists():
        return {
            "registry_status": "IDLE",
            "count_total": 0,
            "enabled_count": 0,
            "top_extensions": [],
            "last_registry_path": rel_path,
            "docs_coverage": {"total": 0, "with_docs_ref": 0, "with_ai_context_refs": 0},
            "tests_coverage": {"total": 0, "with_tests_entrypoints": 0, "with_tests_files": 0},
            "isolation_summary": isolation_summary,
            "last_extension_help_path": "",
            "notes": ["registry_missing"],
        }

    try:
        obj = _load_json(path)
    except Exception:
        return {
            "registry_status": "WARN",
            "count_total": 0,
            "enabled_count": 0,
            "top_extensions": [],
            "last_registry_path": rel_path,
            "docs_coverage": {"total": 0, "with_docs_ref": 0, "with_ai_context_refs": 0},
            "tests_coverage": {"total": 0, "with_tests_entrypoints": 0, "with_tests_files": 0},
            "isolation_summary": isolation_summary,
            "last_extension_help_path": "",
            "notes": ["invalid_registry_json"],
        }

    status = obj.get("status") if isinstance(obj, dict) else None
    if status not in {"OK", "WARN", "IDLE", "FAIL"}:
        status = "WARN"

    extensions = obj.get("extensions") if isinstance(obj, dict) else None
    entries = [e for e in extensions if isinstance(e, dict)] if isinstance(extensions, list) else []
    ext_ids = [str(e.get("extension_id")) for e in entries if isinstance(e.get("extension_id"), str)]
    ext_ids = sorted(set(ext_ids))

    counts = obj.get("counts") if isinstance(obj, dict) else None
    total = int(counts.get("total", len(ext_ids))) if isinstance(counts, dict) else len(ext_ids)
    enabled_count = int(counts.get("enabled", 0)) if isinstance(counts, dict) else 0
    if enabled_count == 0 and entries:
        enabled_count = len([e for e in entries if e.get("enabled") is True])

    obj_notes = obj.get("notes") if isinstance(obj, dict) else None
    if isinstance(obj_notes, list):
        notes = [str(n) for n in obj_notes if isinstance(n, str)]

    docs_coverage = {"total": total, "with_docs_ref": 0, "with_ai_context_refs": 0}
    tests_coverage = {"total": total, "with_tests_entrypoints": 0, "with_tests_files": 0}
    last_help_path = ""
    if help_path.exists():
        try:
            help_obj = _load_json(help_path)
        except Exception:
            notes.append("extension_help_invalid")
        else:
            coverage = help_obj.get("docs_coverage") if isinstance(help_obj, dict) else None
            if isinstance(coverage, dict):
                docs_coverage = {
                    "total": int(coverage.get("total", total)),
                    "with_docs_ref": int(coverage.get("with_docs_ref", 0)),
                    "with_ai_context_refs": int(coverage.get("with_ai_context_refs", 0)),
                }
                help_tests = help_obj.get("tests_coverage") if isinstance(help_obj, dict) else None
                if isinstance(help_tests, dict):
                    tests_coverage = {
                        "total": int(help_tests.get("total", total)),
                        "with_tests_entrypoints": int(help_tests.get("with_tests_entrypoints", 0)),
                        "with_tests_files": int(help_tests.get("with_tests_files", 0)),
                    }
                last_help_path = help_rel
            else:
                notes.append("extension_help_missing_coverage")
    else:
        repo_root = Path(__file__).resolve().parents[2]
        with_docs = 0
        with_ai = 0
        with_tests_entrypoints = 0
        with_tests_files = 0
        for entry in entries:
            manifest_path = entry.get("manifest_path")
            if not isinstance(manifest_path, str) or not manifest_path:
                continue
            path_obj = repo_root / manifest_path
            if not path_obj.exists():
                continue
            try:
                manifest = _load_json(path_obj)
            except Exception:
                continue
            if isinstance(manifest.get("docs_ref"), str) and manifest.get("docs_ref"):
                with_docs += 1
            ai_refs = manifest.get("ai_context_refs")
            if isinstance(ai_refs, list) and any(isinstance(x, str) and x for x in ai_refs):
                with_ai += 1
            tests_entrypoints = manifest.get("tests_entrypoints")
            if not isinstance(tests_entrypoints, list) or not tests_entrypoints:
                entrypoints = manifest.get("entrypoints") if isinstance(manifest.get("entrypoints"), dict) else {}
                tests_entrypoints = entrypoints.get("tests")
            tests_list = [t for t in tests_entrypoints if isinstance(t, str)] if isinstance(tests_entrypoints, list) else []
            if tests_list:
                with_tests_entrypoints += 1
                ext_root = path_obj.parent
                tests_ok = True
                for tpath in tests_list:
                    abs_path = repo_root / tpath
                    if not abs_path.exists():
                        tests_ok = False
                        break
                    rel_prefix = str(ext_root.relative_to(repo_root)).replace("\\\\", "/") + "/tests/"
                    if not str(tpath).startswith(rel_prefix):
                        tests_ok = False
                        break
                if tests_ok:
                    with_tests_files += 1
        docs_coverage = {"total": total, "with_docs_ref": with_docs, "with_ai_context_refs": with_ai}
        tests_coverage = {
            "total": total,
            "with_tests_entrypoints": with_tests_entrypoints,
            "with_tests_files": with_tests_files,
        }
        notes.append("extension_help_missing")

    policy_path = Path(__file__).resolve().parents[2] / "policies" / "policy_extension_isolation.v1.json"
    if policy_path.exists():
        try:
            policy_obj = _load_json(policy_path)
        except Exception:
            isolation_summary = {
                "status": "WARN",
                "workspace_root_base": ".cache/extensions",
                "workspace_roots": [],
                "network_allowed": False,
                "last_run_path": "",
                "notes": ["extension_isolation_policy_invalid"],
            }
        else:
            base = policy_obj.get("extension_workspace_root") if isinstance(policy_obj, dict) else ".cache/extensions"
            base = str(base) if isinstance(base, str) and base else ".cache/extensions"
            network_allowed = bool(policy_obj.get("network_allowed", False)) if isinstance(policy_obj, dict) else False
            workspace_roots = [str(Path(base) / ext_id) for ext_id in ext_ids]
            last_run_path = ""
            for ext_id in ext_ids:
                run_path = Path(".cache") / "reports" / f"extension_run.{ext_id}.v1.json"
                if (workspace_root / run_path).exists():
                    last_run_path = str(run_path)
                    break
            isolation_notes = []
            status = "OK"
            if network_allowed:
                status = "WARN"
                isolation_notes.append("network_allowed_true")
            isolation_summary = {
                "status": status,
                "workspace_root_base": base,
                "workspace_roots": workspace_roots,
                "network_allowed": False,
                "last_run_path": last_run_path,
                "notes": isolation_notes,
            }

    return {
        "registry_status": str(status),
        "count_total": total,
        "enabled_count": enabled_count,
        "top_extensions": ext_ids[:5],
        "last_registry_path": rel_path,
        "docs_coverage": docs_coverage,
        "tests_coverage": tests_coverage,
        "isolation_summary": isolation_summary,
        "last_extension_help_path": last_help_path,
        "notes": notes,
    }


def _airunner_section(workspace_root: Path) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    lock_path = workspace_root / ".cache" / "airunner" / "airunner_lock.v1.json"
    heartbeat_path = workspace_root / ".cache" / "airunner" / "airunner_heartbeat.v1.json"
    jobs_index_path = workspace_root / ".cache" / "airunner" / "jobs_index.v1.json"
    time_sinks_path = workspace_root / ".cache" / "reports" / "time_sinks.v1.json"

    notes: list[str] = []
    lock = {
        "status": "IDLE",
        "lock_path": str(Path(".cache") / "airunner" / "airunner_lock.v1.json"),
        "expires_at": "",
        "stale": False,
    }
    if lock_path.exists():
        try:
            obj = _load_json(lock_path)
        except Exception:
            notes.append("airunner_lock_invalid")
        else:
            expires_at = str(obj.get("expires_at") or "") if isinstance(obj, dict) else ""
            expires_dt = _parse_iso(expires_at)
            stale = bool(expires_dt and now >= expires_dt)
            lock = {
                "status": "OK" if not stale else "WARN",
                "lock_path": str(Path(".cache") / "airunner" / "airunner_lock.v1.json"),
                "expires_at": expires_at,
                "stale": stale,
            }
    else:
        notes.append("airunner_lock_missing")

    heartbeat = {
        "last_tick_id": "",
        "last_tick_at": "",
        "last_status": "",
        "age_seconds": 0,
        "heartbeat_path": str(Path(".cache") / "airunner" / "airunner_heartbeat.v1.json"),
    }
    if heartbeat_path.exists():
        try:
            hb = _load_json(heartbeat_path)
        except Exception:
            notes.append("airunner_heartbeat_invalid")
        else:
            last_tick_id = str(hb.get("last_tick_id") or "") if isinstance(hb, dict) else ""
            last_tick_at = str(hb.get("last_tick_at") or "") if isinstance(hb, dict) else ""
            last_status = str(hb.get("last_status") or "") if isinstance(hb, dict) else ""
            last_dt = _parse_iso(last_tick_at)
            age_seconds = int((now - last_dt).total_seconds()) if last_dt else 0
            heartbeat = {
                "last_tick_id": last_tick_id,
                "last_tick_at": last_tick_at,
                "last_status": last_status,
                "age_seconds": max(age_seconds, 0),
                "heartbeat_path": str(Path(".cache") / "airunner" / "airunner_heartbeat.v1.json"),
            }
    else:
        notes.append("airunner_heartbeat_missing")

    jobs_summary = {
        "total": 0,
        "by_status": {"QUEUED": 0, "RUNNING": 0, "PASS": 0, "FAIL": 0, "TIMEOUT": 0, "KILLED": 0, "SKIP": 0},
        "jobs_index_path": str(Path(".cache") / "airunner" / "jobs_index.v1.json"),
    }
    jobs_index_obj: dict[str, Any] | None = None
    if jobs_index_path.exists():
        try:
            idx = _load_json(jobs_index_path)
        except Exception:
            notes.append("airunner_jobs_index_invalid")
        else:
            jobs_index_obj = idx if isinstance(idx, dict) else None
            counts = idx.get("counts") if isinstance(idx, dict) else None
            if isinstance(counts, dict):
                jobs_summary = {
                    "total": int(counts.get("total", 0)),
                    "by_status": {
                        "QUEUED": int(counts.get("queued", 0)),
                        "RUNNING": int(counts.get("running", 0)),
                        "PASS": int(counts.get("pass", 0)),
                        "FAIL": int(counts.get("fail", 0)),
                        "TIMEOUT": int(counts.get("timeout", 0)),
                        "KILLED": int(counts.get("killed", 0)),
                        "SKIP": int(counts.get("skip", 0)),
                    },
                    "jobs_index_path": str(Path(".cache") / "airunner" / "jobs_index.v1.json"),
                }
    else:
        notes.append("airunner_jobs_index_missing")

    jobs_policy_summary = {
        "smoke_full": {
            "enabled": True,
            "timeout_seconds": 0,
            "poll_interval_seconds": 0,
            "max_concurrent": 1,
            "cooldown_seconds": 0,
        }
    }
    repo_root = Path(__file__).resolve().parents[2]
    policy_path = repo_root / "policies" / "policy_airunner_jobs.v1.json"
    override_path = workspace_root / ".cache" / "policy_overrides" / "policy_airunner_jobs.override.v1.json"
    policy_obj: dict[str, Any] = {}
    if policy_path.exists():
        try:
            policy_raw = _load_json(policy_path)
        except Exception:
            notes.append("airunner_jobs_policy_invalid")
        else:
            if isinstance(policy_raw, dict):
                policy_obj = _deep_merge(policy_obj, policy_raw)
    else:
        notes.append("airunner_jobs_policy_missing")
    if override_path.exists():
        try:
            override_raw = _load_json(override_path)
        except Exception:
            notes.append("airunner_jobs_policy_override_invalid")
        else:
            if isinstance(override_raw, dict):
                policy_obj = _deep_merge(policy_obj, override_raw)
                notes.append("airunner_jobs_policy_override_loaded")
    jobs_cfg = policy_obj.get("jobs") if isinstance(policy_obj.get("jobs"), dict) else {}
    smoke_cfg = jobs_cfg.get("smoke_full") if isinstance(jobs_cfg.get("smoke_full"), dict) else {}
    jobs_policy_summary = {
        "smoke_full": {
            "enabled": bool(smoke_cfg.get("enabled", True)),
            "timeout_seconds": int(smoke_cfg.get("timeout_seconds", jobs_cfg.get("timeout_seconds", 0) or 0) or 0),
            "poll_interval_seconds": int(
                smoke_cfg.get("poll_interval_seconds", jobs_cfg.get("poll_interval_seconds", 0) or 0) or 0
            ),
            "max_concurrent": int(smoke_cfg.get("max_concurrent", jobs_cfg.get("max_running", 1) or 1) or 1),
            "cooldown_seconds": int(smoke_cfg.get("cooldown_seconds", 0) or 0),
        }
    }

    last_smoke_full_job = {
        "job_id": "",
        "status": "",
        "failure_class": "",
        "signature_hash": "",
        "updated_at": "",
    }
    jobs_list = jobs_index_obj.get("jobs") if isinstance(jobs_index_obj, dict) else None
    if isinstance(jobs_list, list):
        candidates = []
        for job in jobs_list:
            if not isinstance(job, dict):
                continue
            if str(job.get("job_type") or job.get("kind") or "") != "SMOKE_FULL":
                continue
            updated_at = str(job.get("updated_at") or job.get("started_at") or job.get("created_at") or "")
            updated_dt = _parse_iso(updated_at) or datetime.fromtimestamp(0, tz=timezone.utc)
            candidates.append((updated_dt, str(job.get("job_id") or ""), job))
        if candidates:
            candidates.sort(key=lambda item: (item[0], item[1]))
            _, _, job = candidates[-1]
            last_smoke_full_job = {
                "job_id": str(job.get("job_id") or ""),
                "status": str(job.get("status") or ""),
                "failure_class": str(job.get("failure_class") or ""),
                "signature_hash": str(job.get("signature_hash") or ""),
                "updated_at": str(job.get("updated_at") or job.get("started_at") or job.get("created_at") or ""),
            }

    cooldown_summary = {
        "entries": 0,
        "suppressed_count": 0,
        "cooldown_path": str(Path(".cache") / "index" / "intake_cooldowns.v1.json"),
    }
    cooldown_path = workspace_root / ".cache" / "index" / "intake_cooldowns.v1.json"
    if cooldown_path.exists():
        try:
            cooldown_obj = _load_json(cooldown_path)
        except Exception:
            notes.append("airunner_cooldown_invalid")
        else:
            entries = cooldown_obj.get("entries") if isinstance(cooldown_obj, dict) else None
            if isinstance(entries, dict):
                count = 0
                suppressed_total = 0
                for key, entry in entries.items():
                    if not isinstance(key, str) or not isinstance(entry, dict):
                        continue
                    job_type = str(entry.get("job_type") or "")
                    if job_type != "SMOKE_FULL" and not key.startswith("SMOKE_FULL|"):
                        continue
                    count += 1
                    suppressed_total += int(entry.get("suppressed_count", 0) or 0)
                cooldown_summary = {
                    "entries": count,
                    "suppressed_count": suppressed_total,
                    "cooldown_path": str(Path(".cache") / "index" / "intake_cooldowns.v1.json"),
                }
    else:
        notes.append("airunner_cooldown_missing")

    time_sinks_summary = {
        "count": 0,
        "top": [],
        "report_path": str(Path(".cache") / "reports" / "time_sinks.v1.json"),
    }
    if time_sinks_path.exists():
        try:
            ts = _load_json(time_sinks_path)
        except Exception:
            notes.append("airunner_time_sinks_invalid")
        else:
            sinks = ts.get("sinks") if isinstance(ts, dict) else None
            if isinstance(sinks, list):
                top = [
                    {
                        "event_key": str(s.get("event_key") or ""),
                        "p95_ms": int(s.get("p95_ms") or 0),
                        "threshold_ms": int(s.get("threshold_ms") or 0),
                        "breach_count": int(s.get("breach_count") or 0),
                    }
                    for s in sinks
                    if isinstance(s, dict) and str(s.get("event_key") or "")
                ]
                top.sort(key=lambda s: (-int(s.get("breach_count", 0)), str(s.get("event_key"))))
                time_sinks_summary = {
                    "count": len(top),
                    "top": top[:5],
                    "report_path": str(Path(".cache") / "reports" / "time_sinks.v1.json"),
                }
    else:
        notes.append("airunner_time_sinks_missing")

    status = "IDLE"
    if heartbeat.get("last_tick_id") or jobs_summary.get("total") or time_sinks_summary.get("count"):
        status = "OK"
    if lock.get("status") == "WARN" or jobs_summary.get("by_status", {}).get("FAIL", 0) or jobs_summary.get("by_status", {}).get("TIMEOUT", 0) or jobs_summary.get("by_status", {}).get("KILLED", 0) or time_sinks_summary.get("count", 0):
        status = "WARN"

    return {
        "status": status,
        "lock": lock,
        "heartbeat": heartbeat,
        "jobs": jobs_summary,
        "jobs_policy": jobs_policy_summary,
        "last_smoke_full_job": last_smoke_full_job,
        "cooldown_summary": cooldown_summary,
        "time_sinks": time_sinks_summary,
        "notes": notes,
    }


def _release_section(workspace_root: Path) -> dict[str, Any]:
    plan_rel = str(Path(".cache") / "reports" / "release_plan.v1.json")
    manifest_rel = str(Path(".cache") / "reports" / "release_manifest.v1.json")
    notes_rel = str(Path(".cache") / "reports" / "release_notes.v1.md")
    plan_path = workspace_root / plan_rel
    manifest_path = workspace_root / manifest_rel
    notes_path = workspace_root / notes_rel

    status = "IDLE"
    next_channel = "rc"
    publish_allowed = False
    notes: list[str] = []
    dirty_tree = False
    channel = "rc"
    proposed_version = ""
    evidence_paths: list[str] = []
    publish_status = "SKIP"
    publish_reason = "NETWORK_PUBLISH_DISABLED"

    if plan_path.exists():
        try:
            plan = _load_json(plan_path)
        except Exception:
            status = "WARN"
            notes.append("plan_invalid_json")
            plan = {}
        if isinstance(plan, dict):
            plan_status = plan.get("status")
            if plan_status in {"OK", "WARN", "IDLE", "FAIL"}:
                status = str(plan_status)
            channel = str(plan.get("channel") or channel)
            if channel == "rc":
                next_channel = "final"
            elif channel == "final":
                next_channel = "rc"
            else:
                channel = "rc"
                next_channel = "rc"
            dirty_tree = bool(plan.get("dirty_tree", False))
            version_plan = plan.get("version_plan") if isinstance(plan.get("version_plan"), dict) else {}
            proposed_version = str(version_plan.get("channel_version", ""))
        evidence_paths.append(plan_rel)
    else:
        notes.append("plan_missing")

    if manifest_path.exists():
        try:
            manifest = _load_json(manifest_path)
        except Exception:
            notes.append("manifest_invalid_json")
            manifest = {}
        if isinstance(manifest, dict):
            manifest_status = manifest.get("status")
            if manifest_status in {"OK", "WARN", "IDLE", "FAIL"}:
                status = str(manifest_status) if status != "FAIL" else status
            publish_allowed = bool(manifest.get("publish_allowed", False))
            dirty_tree = bool(manifest.get("dirty_tree", dirty_tree))
            channel = str(manifest.get("channel", channel) or channel)
            proposed_version = str(manifest.get("release_version", proposed_version) or proposed_version)
        evidence_paths.append(manifest_rel)
    else:
        notes.append("manifest_missing")

    if notes_path.exists():
        evidence_paths.append(notes_rel)

    try:
        from src.prj_release_automation.release_engine import publish_release

        publish = publish_release(workspace_root=workspace_root, channel=channel, allow_network=False, trusted_context=False)
        if isinstance(publish, dict):
            publish_status = str(publish.get("status", publish_status))
            publish_reason = str(publish.get("error_code") or publish_reason)
    except Exception:
        publish_status = "WARN"
        publish_reason = "PUBLISH_STATUS_UNAVAILABLE"

    return {
        "status": status,
        "last_plan_path": plan_rel,
        "last_manifest_path": manifest_rel,
        "next_channel_suggestion": next_channel,
        "channel": channel,
        "proposed_version": proposed_version,
        "dirty_tree": dirty_tree,
        "evidence_paths": sorted(set(evidence_paths)),
        "publish": {
            "status": publish_status,
            "reason": publish_reason,
        },
        "publish_allowed": publish_allowed,
        "notes": notes,
    }


def _pm_suite_section() -> dict[str, Any]:
    extension_id = "PRJ-PM-SUITE"
    manifest_path = Path("extensions") / "PRJ-PM-SUITE" / "extension.manifest.v1.json"
    schema_paths = [
        Path("schemas") / "pm-project.schema.v1.json",
        Path("schemas") / "pm-work-item.schema.v1.json",
        Path("schemas") / "pm-workflow.schema.v1.json",
        Path("schemas") / "pm-board.schema.v1.json",
    ]
    policy_paths = [
        Path("policies") / "policy_pm_suite.v1.json",
        Path("schemas") / "policy-pm-suite.schema.v1.json",
    ]
    repo_root = Path(__file__).resolve().parents[2]
    notes: list[str] = []

    missing = []
    if not (repo_root / manifest_path).exists():
        missing.append("manifest_missing")
    for sp in schema_paths:
        if not (repo_root / sp).exists():
            missing.append(f"schema_missing:{sp}")
    for pp in policy_paths:
        if not (repo_root / pp).exists():
            missing.append(f"policy_missing:{pp}")

    if len(missing) == len(schema_paths) + len(policy_paths) + 1:
        status = "IDLE"
    elif missing:
        status = "WARN"
    else:
        status = "OK"

    notes.extend(missing)
    return {
        "status": status,
        "extension_id": extension_id,
        "manifest_path": str(manifest_path),
        "schema_paths": [str(p) for p in schema_paths],
        "policy_paths": [str(p) for p in policy_paths],
        "notes": notes,
    }


def _auto_heal_section(core_root: Path, workspace_root: Path) -> dict[str, Any] | None:
    report, report_path = _find_auto_heal_report(core_root, workspace_root)
    if report is None or report_path is None:
        return None

    missing = report.get("missing") if isinstance(report, dict) else None
    still_missing = report.get("still_missing") if isinstance(report, dict) else None
    healed = report.get("healed") if isinstance(report, dict) else None
    attempted = report.get("attempted_milestones") if isinstance(report, dict) else None

    missing_list = missing if isinstance(missing, list) else []
    still_list = still_missing if isinstance(still_missing, list) else []
    healed_list = healed if isinstance(healed, list) else []
    attempted_list = [str(x) for x in attempted] if isinstance(attempted, list) else []

    healed_ids = {str(x) for x in healed_list if isinstance(x, str)}
    top_healed: list[dict[str, str]] = []
    for item in missing_list:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "")
        if not item_id or item_id not in healed_ids:
            continue
        top_healed.append(
            {
                "id": item_id,
                "path": str(item.get("path") or ""),
                "owner_milestone": str(item.get("owner_milestone") or ""),
            }
        )
    top_healed.sort(key=lambda x: x.get("id") or "")
    top_healed = top_healed[:3]

    try:
        rel_path = str(report_path.relative_to(core_root))
    except Exception:
        rel_path = str(report_path)

    missing_count = len(missing_list)
    healed_count = len([x for x in healed_list if isinstance(x, str)])
    still_missing_count = len(still_list)
    status = "WARN" if still_missing_count > 0 else "OK"

    return {
        "status": status,
        "last_report_path": rel_path,
        "missing_count": missing_count,
        "healed_count": healed_count,
        "still_missing_count": still_missing_count,
        "attempted_milestones": attempted_list,
        "top_healed": top_healed,
        "notes": [],
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
