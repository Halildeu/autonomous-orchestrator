from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .system_status_context_router import build_context_router_section, context_router_md_lines
from .system_status_sections_extensions import (
    _airunner_auto_run_section,
    _auto_loop_section,
    _cockpit_lite_section,
    _deploy_section,
    _github_ops_section,
    _network_live_section,
)
from .system_status_sections import (
    _actions_status,
    _airunner_section,
    _airunner_proof_section,
    _advisor_status,
    _auto_heal_section,
    _benchmark_status,
    _core_integrity_section,
    _core_lock_section,
    _doc_graph_section,
    _doer_section,
    _extensions_section,
    _formats_status,
    _harvest_status,
    _integrity_status,
    _layer_boundary_section,
    _module_delivery_section,
    _pack_advisor_status,
    _pack_index_status,
    _pack_selection_trace,
    _pack_validation_report,
    _pdca_status,
    _project_boundary_section,
    _projects_section,
    _pm_suite_section,
    _quality_status,
    _readiness_status,
    _release_section,
    _repo_hygiene_section,
    _session_status,
    _spec_core_status,
    _decisions_section,
    _work_intake_exec_section,
    _work_intake_section,
)
from .system_status_sections_intake import _doer_loop_section
from .system_status_sections_catalog import _catalog_status, _iso_core_status
from .managed_repo_standards import build_managed_repo_standards_summary
from .drift_scoreboard import build_drift_scoreboard, build_drift_scoreboard_summary
from .error_observability_report import (
    DEFAULT_ERROR_OBSERVABILITY_REPORT,
    build_error_observability_report,
    project_error_observability_section,
    write_error_observability_report,
)


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _airunner_status_for_overall(airunner_section: dict[str, Any]) -> str:
    air_status = str(airunner_section.get("status") or "WARN")
    if air_status != "IDLE":
        return air_status

    auto_mode = airunner_section.get("auto_mode") if isinstance(airunner_section.get("auto_mode"), dict) else {}
    auto_mode_effective = bool(auto_mode.get("auto_mode_effective", False))
    jobs = airunner_section.get("jobs") if isinstance(airunner_section.get("jobs"), dict) else {}
    jobs_total = int(jobs.get("total", 0) or 0)

    # Auto-mode kapali ve kuyruk bos ise airunner IDLE normal kabul edilir.
    if not auto_mode_effective and jobs_total == 0:
        return "OK"
    return "WARN"


def _core_integrity_status_for_overall(
    core_integrity_section: dict[str, Any],
    *,
    dirty_mode: str,
) -> str:
    """
    Core integrity detayini section bazinda korur, fakat dirty_mode=warn ise
    gelistirme sirasindaki git-dirty durumu overall'i gereksiz WARN yapmasin.
    """
    status = str(core_integrity_section.get("status") or "WARN")
    if status != "WARN":
        return status
    if str(dirty_mode or "").strip().lower() != "warn":
        return status
    notes = core_integrity_section.get("notes")
    if not isinstance(notes, list):
        return status
    notes_set = {str(n) for n in notes if isinstance(n, str)}
    if "git_dirty_live" in notes_set and "core_integrity_dirty_mode=warn" in notes_set:
        return "OK"
    return status


def _parse_iso(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except Exception:
        return False


def _parse_bool(value: str) -> bool:
    v = str(value).strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError("expected true|false")


def _resolve_workspace_path(workspace_root: Path, rel: str) -> Path | None:
    path = (workspace_root / rel).resolve()
    return path if _is_within_root(path, workspace_root) else None


@dataclass(frozen=True)
class SystemStatusPolicy:
    enabled: bool
    out_json: str
    out_md: str
    max_actions: int
    max_suggestions: int
    include_repo_hygiene_suggestions: bool
    core_integrity_dirty_mode: str
    on_fail: str


def _load_policy(core_root: Path, workspace_root: Path) -> SystemStatusPolicy:
    defaults = SystemStatusPolicy(
        enabled=True,
        out_json=".cache/reports/system_status.v1.json",
        out_md=".cache/reports/system_status.v1.md",
        max_actions=10,
        max_suggestions=10,
        include_repo_hygiene_suggestions=False,
        core_integrity_dirty_mode="fail",
        on_fail="warn",
    )

    ws_policy = workspace_root / "policies" / "policy_system_status.v1.json"
    core_policy = core_root / "policies" / "policy_system_status.v1.json"
    policy_path = ws_policy if ws_policy.exists() else core_policy
    if not policy_path.exists():
        return defaults

    try:
        obj = _load_json(policy_path)
    except Exception:
        return defaults
    if not isinstance(obj, dict):
        return defaults

    enabled = bool(obj.get("enabled", defaults.enabled))
    out_json = obj.get("out_json", defaults.out_json)
    if not isinstance(out_json, str) or not out_json.strip():
        out_json = defaults.out_json

    out_md = obj.get("out_md", defaults.out_md)
    if not isinstance(out_md, str) or not out_md.strip():
        out_md = defaults.out_md

    def _int_or_default(val: Any, dflt: int) -> int:
        try:
            return max(0, int(val))
        except Exception:
            return dflt

    max_actions = _int_or_default(obj.get("max_actions", defaults.max_actions), defaults.max_actions)
    max_suggestions = _int_or_default(obj.get("max_suggestions", defaults.max_suggestions), defaults.max_suggestions)

    include_repo_hygiene_suggestions = bool(
        obj.get("include_repo_hygiene_suggestions", defaults.include_repo_hygiene_suggestions)
    )

    core_integrity_dirty_mode = str(
        obj.get("core_integrity_dirty_mode", defaults.core_integrity_dirty_mode)
    ).strip()
    if core_integrity_dirty_mode not in {"fail", "warn"}:
        core_integrity_dirty_mode = defaults.core_integrity_dirty_mode

    on_fail = obj.get("on_fail", defaults.on_fail)
    if on_fail not in {"warn", "block"}:
        on_fail = defaults.on_fail

    return SystemStatusPolicy(
        enabled=enabled,
        out_json=str(out_json),
        out_md=str(out_md),
        max_actions=max_actions,
        max_suggestions=max_suggestions,
        include_repo_hygiene_suggestions=include_repo_hygiene_suggestions,
        core_integrity_dirty_mode=core_integrity_dirty_mode,
        on_fail=str(on_fail),
    )


def _validate_schema(core_root: Path, obj: dict[str, Any]) -> list[str]:
    schema_path = core_root / "schemas" / "system-status.schema.json"
    if not schema_path.exists():
        return ["SCHEMA_MISSING"]
    try:
        schema = _load_json(schema_path)
        Draft202012Validator(schema).validate(obj)
        return []
    except Exception as e:
        return [str(e)[:200]]

def build_system_status(
    *,
    workspace_root: Path,
    core_root: Path,
    policy: SystemStatusPolicy,
    dry_run: bool,
) -> dict[str, Any]:
    iso_status, iso_missing, iso_paths = _iso_core_status(workspace_root)
    spec_status, spec_paths, spec_examples, spec_notes = _spec_core_status(core_root)
    core_integrity = _core_integrity_section(
        core_root,
        workspace_root,
        dirty_mode=policy.core_integrity_dirty_mode,
    )
    core_lock = _core_lock_section(core_root, workspace_root)
    project_boundary = _project_boundary_section(workspace_root)
    layer_boundary = _layer_boundary_section(workspace_root)
    cat_status, pack_ids = _catalog_status(workspace_root)
    pack_status, pack_index_ids, hard_conflicts_count, soft_conflicts_count, pack_index_path, pack_index_hash, pack_notes, pack_report_path = _pack_index_status(workspace_root)
    pack_val_status, pack_val_hard, pack_val_soft, pack_val_path, pack_val_notes = _pack_validation_report(workspace_root)
    selected_pack_ids, selection_trace_path, selection_notes = _pack_selection_trace(workspace_root)
    fmt_status, format_ids = _formats_status(workspace_root)
    sess_status, sess_details = _session_status(workspace_root)
    qual_status, qual_summary = _quality_status(workspace_root)
    integrity_section = _integrity_status(workspace_root)
    bench = _benchmark_status(workspace_root)
    bench_status = str(bench.get("status") or "WARN")
    pdca_section = _pdca_status(workspace_root)
    work_intake_section = _work_intake_section(workspace_root)
    work_intake_exec_section = _work_intake_exec_section(workspace_root)
    doer_section = _doer_section(workspace_root)
    auto_loop_section = _auto_loop_section(workspace_root)
    airunner_auto_run_section = _airunner_auto_run_section(workspace_root)
    deploy_section = _deploy_section(workspace_root)
    module_delivery_section = _module_delivery_section(workspace_root)
    decisions_section = _decisions_section(workspace_root)
    context_router_section = build_context_router_section(workspace_root)
    managed_repo_standards = build_managed_repo_standards_summary(
        workspace_root=workspace_root,
        core_root=core_root,
        max_repos=100,
    )
    drift_scoreboard = build_drift_scoreboard(
        workspace_root=workspace_root,
        core_root=core_root,
        managed_repo_standards_summary=managed_repo_standards,
        max_repos=100,
    )
    drift_scoreboard_summary = build_drift_scoreboard_summary(drift_scoreboard)
    harvest_status, candidates_count, harvest_kinds = _harvest_status(workspace_root)
    adv_status, suggestions_count, adv_kinds = _advisor_status(workspace_root, policy.max_suggestions)
    pack_adv_status, pack_adv_count, pack_adv_kinds, pack_adv_pack_ids = _pack_advisor_status(
        workspace_root, policy.max_suggestions
    )
    read_status, read_fails, read_warns = _readiness_status(workspace_root)
    act_status, act_count, act_top = _actions_status(workspace_root, policy.max_actions)
    error_observability_report = build_error_observability_report(workspace_root=workspace_root)
    error_observability_report_path = DEFAULT_ERROR_OBSERVABILITY_REPORT.as_posix()
    if not dry_run:
        error_observability_report_path = write_error_observability_report(
            workspace_root=workspace_root,
            report=error_observability_report,
            out_path=workspace_root / DEFAULT_ERROR_OBSERVABILITY_REPORT,
        )
    error_observability_section = project_error_observability_section(
        error_observability_report,
        report_path=error_observability_report_path,
    )
    projects_section = _projects_section(
        core_root,
        workspace_root,
        bench_status=bench_status,
        actions_top=act_top,
        actions_count=int(act_count),
    )
    extensions_section = _extensions_section(workspace_root)
    cockpit_lite_section = _cockpit_lite_section(workspace_root)
    network_live_section = _network_live_section(workspace_root)
    github_ops_section = _github_ops_section(workspace_root)
    airunner_section = _airunner_section(workspace_root)
    airunner_proof_section = _airunner_proof_section(workspace_root)
    pm_suite_section = _pm_suite_section()
    release_section = _release_section(workspace_root)
    auto_heal = _auto_heal_section(core_root, workspace_root)
    repo_hygiene = _repo_hygiene_section(
        core_root=core_root,
        workspace_root=workspace_root,
        include_suggestions=policy.include_repo_hygiene_suggestions,
        allow_write=not dry_run,
    )
    doc_graph = _doc_graph_section(core_root, workspace_root, allow_write=not dry_run)

    overall = "OK"
    if pack_val_status in {"OK", "WARN", "FAIL"}:
        pack_status = str(pack_val_status)
        hard_conflicts_count = int(pack_val_hard)
        soft_conflicts_count = int(pack_val_soft)
        pack_report_path = pack_val_path
        pack_notes = sorted(set(pack_notes + pack_val_notes))

    section_statuses = [
        iso_status,
        spec_status,
        _core_integrity_status_for_overall(
            core_integrity,
            dirty_mode=policy.core_integrity_dirty_mode,
        ),
        str(core_lock.get("status") or "WARN"),
        str(projects_section.get("status") or "WARN"),
        cat_status,
        pack_status,
        fmt_status,
        sess_status,
        qual_status,
        str(integrity_section.get("status") or "WARN"),
        bench_status,
        str(pdca_section.get("status") or "WARN"),
        harvest_status,
        adv_status,
        pack_adv_status,
        act_status,
    ]
    section_statuses.append(str(project_boundary.get("status") or "WARN"))
    if isinstance(layer_boundary, dict):
        section_statuses.append(str(layer_boundary.get("status") or "WARN"))
    if isinstance(auto_heal, dict):
        section_statuses.append(str(auto_heal.get("status") or "WARN"))
    if isinstance(repo_hygiene, dict):
        section_statuses.append(str(repo_hygiene.get("status") or "WARN"))
    if isinstance(doc_graph, dict):
        section_statuses.append(str(doc_graph.get("status") or "WARN"))
    if isinstance(work_intake_section, dict):
        work_intake_status = str(work_intake_section.get("status") or "WARN")
        section_statuses.append("WARN" if work_intake_status == "IDLE" else work_intake_status)
    if isinstance(work_intake_exec_section, dict):
        exec_status = str(work_intake_exec_section.get("status") or "WARN")
        section_statuses.append("WARN" if exec_status == "IDLE" else exec_status)
    if isinstance(context_router_section, dict):
        router_status = str(context_router_section.get("status") or "WARN")
        section_statuses.append("WARN" if router_status == "IDLE" else router_status)
    if isinstance(managed_repo_standards, dict):
        mrs_status = str(managed_repo_standards.get("status") or "WARN")
        section_statuses.append("WARN" if mrs_status == "IDLE" else mrs_status)
    if isinstance(drift_scoreboard_summary, dict):
        scoreboard_status = str(drift_scoreboard_summary.get("status") or "WARN")
        section_statuses.append("WARN" if scoreboard_status == "IDLE" else scoreboard_status)
    if isinstance(extensions_section, dict):
        ext_status = str(extensions_section.get("registry_status") or "WARN")
        section_statuses.append("WARN" if ext_status == "IDLE" else ext_status)
    if isinstance(airunner_section, dict):
        section_statuses.append(_airunner_status_for_overall(airunner_section))
    if isinstance(pm_suite_section, dict):
        pm_status = str(pm_suite_section.get("status") or "WARN")
        section_statuses.append("WARN" if pm_status == "IDLE" else pm_status)
    if isinstance(release_section, dict):
        rel_status = str(release_section.get("status") or "WARN")
        section_statuses.append("WARN" if rel_status == "IDLE" else rel_status)
    if read_status == "NOT_READY" or any(s == "FAIL" for s in section_statuses):
        overall = "NOT_READY"
    elif any(s == "WARN" for s in section_statuses) or read_warns > 0:
        overall = "WARN"

    report = {
        "version": "v1",
        "generated_at": _now_iso8601(),
        "workspace_root": str(workspace_root),
        "overall_status": overall,
        "sections": {
            "iso_core": {
                "status": iso_status,
                "missing": iso_missing,
                "paths": iso_paths,
            },
            "spec_core": {
                "status": spec_status,
                "paths": spec_paths,
                "examples": spec_examples,
                "notes": spec_notes,
            },
            "core_integrity": core_integrity,
            "core_lock": core_lock,
            "project_boundary": project_boundary,
            "projects": projects_section,
            "extensions": extensions_section,
            "cockpit_lite": cockpit_lite_section,
            "network_live": network_live_section,
            **({"module_delivery": module_delivery_section} if isinstance(module_delivery_section, dict) else {}),
            "error_observability": error_observability_section,
            "airunner": airunner_section,
            "airunner_proof": airunner_proof_section,
            "pm_suite": pm_suite_section,
            "release": release_section,
            "catalog": {
                "status": cat_status,
                "packs_found": len(pack_ids),
                "pack_ids": pack_ids,
            },
            "packs": {
                "status": pack_status,
                "packs_found": len(pack_index_ids),
                "pack_ids": pack_index_ids,
                "selected_pack_ids": selected_pack_ids,
                "hard_conflicts_count": int(hard_conflicts_count),
                "soft_conflicts_count": int(soft_conflicts_count),
                "index_path": pack_index_path,
                "selection_trace_path": selection_trace_path,
                "report_path": pack_report_path,
                "index_hash": str(pack_index_hash),
                "notes": sorted(set(pack_notes + selection_notes)),
            },
            "formats": {
                "status": fmt_status,
                "formats_found": len(format_ids),
                "format_ids": format_ids,
            },
            "session": {
                "status": sess_status,
                "session_id": "default",
                "ttl_seconds": int(sess_details.get("ttl_seconds", 0)),
                "expires_at": str(sess_details.get("expires_at", "")),
                "session_context_hash": str(sess_details.get("session_context_hash", "")),
            },
            "quality_gate": {
                "status": qual_status,
                "report_path": str(Path(".cache") / "index" / "quality_gate_report.v1.json"),
                "summary": qual_summary,
            },
            "integrity": integrity_section,
            "benchmark": {
                "status": bench_status,
                "catalog_path": str(bench.get("catalog_path") or ""),
                "assessment_path": str(bench.get("assessment_path") or ""),
                "last_assessment_raw_path": str(bench.get("last_assessment_raw_path") or ""),
                "last_assessment_eval_path": str(bench.get("last_assessment_eval_path") or ""),
                "last_integrity_verify_path": str(bench.get("last_integrity_verify_path") or ""),
                "scorecard_path": str(bench.get("scorecard_path") or ""),
                "gap_register_path": str(bench.get("gap_register_path") or ""),
                "gaps_summary": bench.get("gaps_summary") or {"low": 0, "medium": 0, "high": 0},
                "maturity_avg": float(bench.get("maturity_avg") or 0.0),
                "controls_count": int(bench.get("controls_count") or 0),
                "metrics_count": int(bench.get("metrics_count") or 0),
                "gaps_count": int(bench.get("gaps_count") or 0),
                "gaps_by_severity": bench.get("gaps_by_severity") or {"low": 0, "medium": 0, "high": 0},
                "eval_lenses": bench.get("eval_lenses") or {},
                "lenses": bench.get("lenses") or [],
                "lens_gaps_count": int(bench.get("lens_gaps_count") or 0),
                "lens_gaps_top": bench.get("lens_gaps_top") or [],
                "subject_plan_ab_summary": bench.get("subject_plan_ab_summary")
                or {
                    "status": "FAIL",
                    "report_path": str(Path(".cache") / "reports" / "north_star_subject_plan_ab_test.v1.json"),
                    "subject_id": "",
                    "available_profiles": [],
                    "missing_profiles": ["A", "B", "C"],
                    "best_profile": "",
                    "best_score": 0.0,
                    "last_requested_profile": "",
                    "last_run_set": "",
                },
                "profile_order_compare_summary": bench.get("profile_order_compare_summary")
                or {
                    "status": "IDLE",
                    "report_path": str(Path(".cache") / "reports" / "north_star_profile_order_ab_compare.v1.json"),
                    "subject_id": "",
                    "orders_spec": "",
                    "scenarios_count": 0,
                    "all_runs_ok": False,
                    "all_comparisons_ok": False,
                    "best_profile_counts": {"A": 0, "B": 0, "C": 0},
                    "last_best_profile": "",
                    "generated_at": "",
                    "errors_count": 0,
                    "notes": [],
                },
                "top_next_actions": bench.get("top_next_actions") or [],
                "notes": bench.get("notes") or [],
            },
            "pdca": pdca_section,
            "harvest": {
                "status": harvest_status,
                "candidates": int(candidates_count),
                "kinds": harvest_kinds,
                "report_path": str(Path(".cache") / "learning" / "public_candidates.v1.json"),
            },
            "advisor": {
                "status": adv_status,
                "suggestions": int(suggestions_count),
                "top_kinds": adv_kinds,
                "report_path": str(Path(".cache") / "learning" / "advisor_suggestions.v1.json"),
            },
            "pack_advisor": {
                "status": pack_adv_status,
                "suggestions": int(pack_adv_count),
                "top_kinds": pack_adv_kinds,
                "top_pack_ids": pack_adv_pack_ids,
                "report_path": str(Path(".cache") / "learning" / "pack_advisor_suggestions.v1.json"),
            },
            "readiness": {
                "status": read_status,
                "fails": int(read_fails),
                "warns": int(read_warns),
                "report_path": str(Path(".cache") / "ops" / "autopilot_readiness.v1.json"),
            },
            "actions": {
                "status": act_status,
                "actions_count": int(act_count),
                "top": act_top,
            },
            "managed_repo_standards": managed_repo_standards,
            "drift_scoreboard": drift_scoreboard_summary,
        },
        "notes": [],
    }
    if isinstance(auto_heal, dict):
        report["sections"]["auto_heal"] = auto_heal
    if isinstance(repo_hygiene, dict):
        report["sections"]["repo_hygiene"] = repo_hygiene
    if isinstance(doc_graph, dict):
        report["sections"]["doc_graph"] = doc_graph
    if isinstance(work_intake_section, dict):
        report["sections"]["work_intake"] = work_intake_section
    if isinstance(work_intake_exec_section, dict):
        report["sections"]["work_intake_exec"] = work_intake_exec_section
    if isinstance(doer_section, dict):
        report["sections"]["doer"] = doer_section
    doer_loop_section = _doer_loop_section(workspace_root)
    if isinstance(doer_loop_section, dict):
        report["sections"]["doer_loop"] = doer_loop_section
    if isinstance(auto_loop_section, dict):
        report["sections"]["auto_loop"] = auto_loop_section
    if isinstance(airunner_auto_run_section, dict):
        report["sections"]["airrunner_auto_run"] = airunner_auto_run_section
    if isinstance(github_ops_section, dict):
        report["sections"]["github_ops"] = github_ops_section
    if isinstance(deploy_section, dict):
        report["sections"]["deploy"] = deploy_section
    if isinstance(decisions_section, dict):
        report["sections"]["decisions"] = decisions_section
    if isinstance(context_router_section, dict):
        report["sections"]["context_router"] = context_router_section
    if isinstance(layer_boundary, dict):
        report["sections"]["layer_boundary"] = layer_boundary
    return report


def _render_md(report: dict[str, Any]) -> str:
    sections = report.get("sections") if isinstance(report, dict) else {}
    lines: list[str] = []
    lines.append("# System Status Report (v1)")
    lines.append("")
    lines.append(f"Generated at: {report.get('generated_at', '')}")
    lines.append(f"Workspace: {report.get('workspace_root', '')}")
    lines.append(f"Overall: {report.get('overall_status', '')}")
    lines.append("")

    def _section_title(title: str) -> None:
        lines.append(f"## {title}")

    iso = sections.get("iso_core") if isinstance(sections, dict) else {}
    _section_title("ISO Core")
    lines.append(f"Status: {iso.get('status', '')}")
    missing = iso.get("missing") if isinstance(iso, dict) else None
    if isinstance(missing, list) and missing:
        lines.append("Missing: " + ", ".join(str(x) for x in missing))
    lines.append("")

    spec = sections.get("spec_core") if isinstance(sections, dict) else {}
    _section_title("Spec Core")
    lines.append(f"Status: {spec.get('status', '')}")
    notes = spec.get("notes") if isinstance(spec, dict) else None
    if isinstance(notes, list) and notes:
        lines.append("Notes: " + ", ".join(str(x) for x in notes))
    lines.append("")

    core_int = sections.get("core_integrity") if isinstance(sections, dict) else {}
    _section_title("Core integrity")
    lines.append(f"Status: {core_int.get('status', '')}")
    lines.append(f"Git clean: {core_int.get('git_clean', False)}")
    lines.append(f"Dirty files: {core_int.get('dirty_files_count', 0)}")
    core_notes = core_int.get("notes") if isinstance(core_int, dict) else None
    if isinstance(core_notes, list) and core_notes:
        lines.append("Notes: " + ", ".join(str(x) for x in core_notes))
    lines.append("")

    core_lock = sections.get("core_lock") if isinstance(sections, dict) else {}
    _section_title("Core lock")
    lines.append(f"Status: {core_lock.get('status', '')}")
    lines.append(f"Enabled: {core_lock.get('enabled', False)}")
    lines.append(f"Core unlock allowed: {core_lock.get('core_unlock_allowed', False)}")
    lines.append(f"Blocked attempts: {core_lock.get('last_blocked_attempts', 0)}")
    lines.append("")

    proj = sections.get("project_boundary") if isinstance(sections, dict) else {}
    _section_title("Project boundary")
    lines.append(f"Status: {proj.get('status', '')}")
    lines.append(f"Project root: {proj.get('project_root', '')}")
    lines.append(f"Manifest present: {proj.get('manifest_present', False)}")
    proj_notes = proj.get("notes") if isinstance(proj, dict) else None
    if isinstance(proj_notes, list) and proj_notes:
        lines.append("Notes: " + ", ".join(str(x) for x in proj_notes))
    lines.append("")

    layer_boundary = sections.get("layer_boundary") if isinstance(sections, dict) else {}
    if isinstance(layer_boundary, dict) and layer_boundary:
        _section_title("Layer boundary")
        lines.append(f"Status: {layer_boundary.get('status', '')}")
        lines.append(f"Mode: {layer_boundary.get('mode', '')}")
        lines.append(f"Enforcement: {layer_boundary.get('enforcement_mode', '')}")
        lines.append(f"Would block: {layer_boundary.get('would_block_count', 0)}")
        report_path = layer_boundary.get("report_path") if isinstance(layer_boundary, dict) else None
        if isinstance(report_path, str) and report_path:
            lines.append(f"Report: {report_path}")
        notes = layer_boundary.get("notes") if isinstance(layer_boundary, dict) else None
        if isinstance(notes, list) and notes:
            lines.append("Notes: " + ", ".join(str(x) for x in notes))
        lines.append("")

    projects = sections.get("projects") if isinstance(sections, dict) else {}
    _section_title("Projects")
    lines.append(f"Status: {projects.get('status', '')}")
    lines.append(f"Projects count: {projects.get('projects_count', 0)}")
    lines.append(f"Next focus: {projects.get('next_project_focus', '')}")
    top_debts = projects.get("top_project_debts") if isinstance(projects, dict) else None
    if isinstance(top_debts, list) and top_debts:
        lines.append("Top debts:")
        for d in top_debts[:5]:
            if not isinstance(d, dict):
                continue
            lines.append(
                f"- {d.get('kind', '')} milestone={d.get('milestone_hint', '')} "
                f"severity={d.get('severity', '')}"
            )
    notes = projects.get("notes") if isinstance(projects, dict) else None
    if isinstance(notes, list) and notes:
        lines.append("Notes: " + ", ".join(str(x) for x in notes))
    lines.append("")

    managed_repo_standards = sections.get("managed_repo_standards") if isinstance(sections, dict) else {}
    if isinstance(managed_repo_standards, dict) and managed_repo_standards:
        _section_title("Managed repo standards")
        lines.append(f"Status: {managed_repo_standards.get('status', '')}")
        lines.append(f"Mode: {managed_repo_standards.get('mode', '')}")
        lines.append(f"Managed repos: {managed_repo_standards.get('managed_repo_count', 0)}")
        lines.append(f"Targets in report: {managed_repo_standards.get('target_count', 0)}")
        lines.append(f"Pending drift: {managed_repo_standards.get('drift_pending_count', 0)}")
        lines.append(f"Fixed drift: {managed_repo_standards.get('drift_fixed_count', 0)}")
        lines.append(f"Failed repos: {managed_repo_standards.get('failed_count', 0)}")
        report_path = managed_repo_standards.get("report_path")
        if isinstance(report_path, str) and report_path:
            lines.append(f"Sync report: {report_path}")
        manifest_path = managed_repo_standards.get("manifest_path")
        if isinstance(manifest_path, str) and manifest_path:
            lines.append(f"Manifest: {manifest_path}")
        notes = managed_repo_standards.get("notes")
        if isinstance(notes, list) and notes:
            lines.append("Notes: " + ", ".join(str(x) for x in notes))
        lines.append("")

    drift_scoreboard = sections.get("drift_scoreboard") if isinstance(sections, dict) else {}
    if isinstance(drift_scoreboard, dict) and drift_scoreboard:
        _section_title("Drift scoreboard")
        lines.append(f"Status: {drift_scoreboard.get('status', '')}")
        lines.append(f"Repos: {drift_scoreboard.get('repos_count', 0)}")
        lines.append(f"Pending drift: {drift_scoreboard.get('drift_pending_count', 0)}")
        lines.append(f"Failed drift: {drift_scoreboard.get('drift_failed_count', 0)}")
        lines.append(f"Lane matrix: {drift_scoreboard.get('lane_matrix_status', '')}")
        lines.append(
            "Lane config issues: "
            + f"missing={drift_scoreboard.get('repos_missing_lane_config', 0)} "
            + f"invalid={drift_scoreboard.get('repos_invalid_lane_config', 0)} "
            + f"partial={drift_scoreboard.get('repos_partial_lane_config', 0)} "
            + f"placeholders={drift_scoreboard.get('repos_with_lane_placeholders', 0)}"
        )
        lines.append(f"Branch protection: {drift_scoreboard.get('branch_protection_status', '')}")
        lines.append(
            "Branch checks: "
            + f"unverified={drift_scoreboard.get('branch_unverified_count', 0)} "
            + f"missing_required={drift_scoreboard.get('branch_missing_required_check_count', 0)}"
        )
        lines.append(
            "Rollout: "
            + f"safe={drift_scoreboard.get('rollout_safe_count', 0)} "
            + f"review={drift_scoreboard.get('rollout_review_count', 0)} "
            + f"blocked={drift_scoreboard.get('rollout_blocked_count', 0)}"
        )
        report_path = drift_scoreboard.get("report_path")
        if isinstance(report_path, str) and report_path:
            lines.append(f"Scoreboard: {report_path}")
        lines.append("")

    module_delivery = sections.get("module_delivery") if isinstance(sections, dict) else {}
    if isinstance(module_delivery, dict) and module_delivery:
        _section_title("Module delivery")
        lines.append(f"Status: {module_delivery.get('status', '')}")
        lines.append(
            "Lanes: "
            + f"total={module_delivery.get('lanes_total', 0)} "
            + f"ok={module_delivery.get('lanes_ok', 0)} "
            + f"fail={module_delivery.get('lanes_fail', 0)} "
            + f"warn={module_delivery.get('lanes_warn', 0)} "
            + f"timeout={module_delivery.get('timed_out_count', 0)} "
            + f"invalid={module_delivery.get('invalid_report_count', 0)}"
        )
        latest_finished_at = module_delivery.get("latest_finished_at")
        if isinstance(latest_finished_at, str) and latest_finished_at:
            lines.append(f"Latest run: {latest_finished_at}")
        report_dir = module_delivery.get("report_dir")
        if isinstance(report_dir, str) and report_dir:
            lines.append(f"Report dir: {report_dir}")
        failed_lane = module_delivery.get("last_failed_lane")
        if isinstance(failed_lane, str) and failed_lane:
            lines.append(
                f"Last failed lane: {failed_lane} rc={module_delivery.get('last_failed_return_code', 0)}"
            )
        failed_report = module_delivery.get("last_failed_report_path")
        if isinstance(failed_report, str) and failed_report:
            lines.append(f"Last failed report: {failed_report}")
        failed_stdout = module_delivery.get("last_failed_stdout_preview")
        if isinstance(failed_stdout, str) and failed_stdout:
            lines.append("Failed stdout preview: " + failed_stdout.replace("\n", " | "))
        failed_stderr = module_delivery.get("last_failed_stderr_preview")
        if isinstance(failed_stderr, str) and failed_stderr:
            lines.append("Failed stderr preview: " + failed_stderr.replace("\n", " | "))
        md_notes = module_delivery.get("notes")
        if isinstance(md_notes, list) and md_notes:
            lines.append("Notes: " + ", ".join(str(x) for x in md_notes))
        lines.append("")

    error_observability = sections.get("error_observability") if isinstance(sections, dict) else {}
    if isinstance(error_observability, dict) and error_observability:
        _section_title("Error observability")
        lines.append(f"Status: {error_observability.get('status', '')}")
        lines.append(
            "Signals: "
            + f"total={error_observability.get('items_total', 0)} "
            + f"build={error_observability.get('build_count', 0)} "
            + f"runner={error_observability.get('runner_count', 0)} "
            + f"browser={error_observability.get('browser_count', 0)}"
        )
        report_path = error_observability.get("report_path")
        if isinstance(report_path, str) and report_path:
            lines.append(f"Report: {report_path}")
        latest_source_type = error_observability.get("latest_source_type")
        if isinstance(latest_source_type, str) and latest_source_type:
            lines.append(
                "Latest: "
                + f"{latest_source_type}/{error_observability.get('latest_source_name', '')} "
                + f"at {error_observability.get('latest_occurred_at', '')}"
            )
        latest_message = error_observability.get("latest_message")
        if isinstance(latest_message, str) and latest_message:
            lines.append("Latest message: " + latest_message.replace("\n", " | "))
        latest_report_path = error_observability.get("latest_report_path")
        if isinstance(latest_report_path, str) and latest_report_path:
            lines.append(f"Latest source report: {latest_report_path}")
        eo_notes = error_observability.get("notes")
        if isinstance(eo_notes, list) and eo_notes:
            lines.append("Notes: " + ", ".join(str(x) for x in eo_notes))
        lines.append("")

    cockpit_lite = sections.get("cockpit_lite") if isinstance(sections, dict) else {}
    if isinstance(cockpit_lite, dict) and cockpit_lite:
        _section_title("Cockpit Lite")
        lines.append(f"Status: {cockpit_lite.get('status', '')}")
        lines.append(f"Port: {cockpit_lite.get('port', 0)}")
        healthcheck_path = cockpit_lite.get("last_healthcheck_path")
        if isinstance(healthcheck_path, str) and healthcheck_path:
            lines.append(f"Healthcheck: {healthcheck_path}")
        last_request_id = cockpit_lite.get("last_request_id")
        if isinstance(last_request_id, str) and last_request_id:
            lines.append(f"Last request id: {last_request_id}")
        chat_log_path = cockpit_lite.get("last_chat_log_path")
        if isinstance(chat_log_path, str) and chat_log_path:
            lines.append(f"Chat log: {chat_log_path}")
        lines.append(
            "Frontend telemetry: "
            + f"status={cockpit_lite.get('frontend_telemetry_status', 'IDLE')} "
            + f"runtime={cockpit_lite.get('frontend_runtime_error_count', 0)} "
            + f"console={cockpit_lite.get('frontend_console_error_count', 0)} "
            + f"unhandled={cockpit_lite.get('frontend_unhandled_rejection_count', 0)}"
        )
        frontend_summary_path = cockpit_lite.get("last_frontend_telemetry_summary_path")
        if isinstance(frontend_summary_path, str) and frontend_summary_path:
            lines.append(f"Frontend telemetry summary: {frontend_summary_path}")
        frontend_events_path = cockpit_lite.get("last_frontend_telemetry_events_path")
        if isinstance(frontend_events_path, str) and frontend_events_path:
            lines.append(f"Frontend telemetry events: {frontend_events_path}")
        last_frontend_event_type = cockpit_lite.get("last_frontend_event_type")
        if isinstance(last_frontend_event_type, str) and last_frontend_event_type:
            lines.append(
                f"Last frontend event: {last_frontend_event_type} at {cockpit_lite.get('last_frontend_event_at', '')}"
            )
        last_frontend_event_message = cockpit_lite.get("last_frontend_event_message")
        if isinstance(last_frontend_event_message, str) and last_frontend_event_message:
            lines.append("Last frontend event message: " + last_frontend_event_message.replace("\n", " | "))
        lines.append(f"Notes count: {cockpit_lite.get('notes_count', 0)}")
        last_note_id = cockpit_lite.get("last_note_id")
        if isinstance(last_note_id, str) and last_note_id:
            lines.append(f"Last note id: {last_note_id}")
        lines.append("")

    extensions = sections.get("extensions") if isinstance(sections, dict) else {}
    if isinstance(extensions, dict) and extensions:
        _section_title("Extensions")
        lines.append(f"Status: {extensions.get('registry_status', '')}")
        lines.append(f"Total: {extensions.get('count_total', 0)}")
        lines.append(f"Enabled: {extensions.get('enabled_count', 0)}")
        docs_cov = extensions.get("docs_coverage") if isinstance(extensions.get("docs_coverage"), dict) else None
        if isinstance(docs_cov, dict):
            docs_total = docs_cov.get("total", 0)
            docs_with = docs_cov.get("with_docs_ref", 0)
            ai_with = docs_cov.get("with_ai_context_refs", 0)
            lines.append(f"Docs coverage: {docs_with}/{docs_total}")
            lines.append(f"AI context coverage: {ai_with}/{docs_total}")
        tests_cov = extensions.get("tests_coverage") if isinstance(extensions.get("tests_coverage"), dict) else None
        if isinstance(tests_cov, dict):
            tests_total = tests_cov.get("total", 0)
            tests_with = tests_cov.get("with_tests_files", 0)
            lines.append(f"Tests coverage: {tests_with}/{tests_total}")
        top_ext = extensions.get("top_extensions") if isinstance(extensions, dict) else None
        if isinstance(top_ext, list) and top_ext:
            lines.append("Top: " + ", ".join(str(x) for x in top_ext))
        reg_path = extensions.get("last_registry_path") if isinstance(extensions, dict) else None
        if isinstance(reg_path, str) and reg_path:
            lines.append(f"Registry: {reg_path}")
        isolation = extensions.get("isolation_summary") if isinstance(extensions.get("isolation_summary"), dict) else None
        if isinstance(isolation, dict):
            lines.append(f"Isolation: {isolation.get('status', '')}")
            lines.append(f"Isolation root: {isolation.get('workspace_root_base', '')}")
        ext_notes = extensions.get("notes") if isinstance(extensions, dict) else None
        if isinstance(ext_notes, list) and ext_notes:
            lines.append("Notes: " + ", ".join(str(x) for x in ext_notes))
        lines.append("")

    airunner = sections.get("airunner") if isinstance(sections, dict) else {}
    if isinstance(airunner, dict) and airunner:
        _section_title("Airunner")
        lines.append(f"Status: {airunner.get('status', '')}")
        lock = airunner.get("lock") if isinstance(airunner.get("lock"), dict) else None
        if isinstance(lock, dict):
            lines.append(f"Lock: {lock.get('status', '')} stale={lock.get('stale', False)}")
        heartbeat = airunner.get("heartbeat") if isinstance(airunner.get("heartbeat"), dict) else None
        if isinstance(heartbeat, dict):
            lines.append(f"Last tick: {heartbeat.get('last_tick_id', '')}")
            lines.append(f"Heartbeat age: {heartbeat.get('age_seconds', 0)}s")
        jobs = airunner.get("jobs") if isinstance(airunner.get("jobs"), dict) else None
        if isinstance(jobs, dict):
            lines.append(f"Jobs total: {jobs.get('total', 0)}")
            by_status = jobs.get("by_status") if isinstance(jobs.get("by_status"), dict) else None
            if isinstance(by_status, dict):
                lines.append(
                    "Jobs: "
                    + ", ".join(
                        f"{k}={by_status.get(k, 0)}"
                        for k in ["QUEUED", "RUNNING", "PASS", "FAIL", "TIMEOUT", "KILLED", "SKIP"]
                    )
                )
        auto_mode = airunner.get("auto_mode") if isinstance(airunner.get("auto_mode"), dict) else None
        if isinstance(auto_mode, dict):
            last_tick = auto_mode.get("last_tick") if isinstance(auto_mode.get("last_tick"), dict) else {}
            lines.append(
                "Auto-mode: "
                + f"enabled={auto_mode.get('auto_mode_effective', False)} "
                + f"selected={last_tick.get('selected_count', 0)} "
                + f"applied={last_tick.get('applied_count', 0)} "
                + f"planned={last_tick.get('planned_count', 0)} "
                + f"idle={last_tick.get('idle_count', 0)}"
            )
        sinks = airunner.get("time_sinks") if isinstance(airunner.get("time_sinks"), dict) else None
        if isinstance(sinks, dict):
            lines.append(f"Time sinks: {sinks.get('count', 0)}")
        lines.append("")

    airunner_proof = sections.get("airunner_proof") if isinstance(sections, dict) else {}
    if isinstance(airunner_proof, dict) and airunner_proof:
        _section_title("Airrunner Proof")
        lines.append(f"Status: {airunner_proof.get('status', '')}")
        lines.append(f"Last proof bundle: {airunner_proof.get('last_proof_bundle_path', '')}")
        timestamp = airunner_proof.get("last_proof_bundle_timestamp") if isinstance(airunner_proof, dict) else None
        if isinstance(timestamp, str) and timestamp:
            lines.append(f"Last proof timestamp: {timestamp}")
        lines.append("")

    pm_suite = sections.get("pm_suite") if isinstance(sections, dict) else {}
    if isinstance(pm_suite, dict) and pm_suite:
        _section_title("PM Suite")
        lines.append(f"Status: {pm_suite.get('status', '')}")
        lines.append(f"Extension: {pm_suite.get('extension_id', '')}")
        manifest_path = pm_suite.get("manifest_path") if isinstance(pm_suite, dict) else None
        if isinstance(manifest_path, str) and manifest_path:
            lines.append(f"Manifest: {manifest_path}")
        pm_notes = pm_suite.get("notes") if isinstance(pm_suite, dict) else None
        if isinstance(pm_notes, list) and pm_notes:
            lines.append("Notes: " + ", ".join(str(x) for x in pm_notes))
        lines.append("")

    release = sections.get("release") if isinstance(sections, dict) else {}
    if isinstance(release, dict) and release:
        _section_title("Release")
        lines.append(f"Status: {release.get('status', '')}")
        lines.append(f"Next channel: {release.get('next_channel_suggestion', '')}")
        lines.append(f"Publish allowed: {release.get('publish_allowed', False)}")
        plan_path = release.get("last_plan_path") if isinstance(release, dict) else None
        manifest_path = release.get("last_manifest_path") if isinstance(release, dict) else None
        if isinstance(plan_path, str) and plan_path:
            lines.append(f"Plan: {plan_path}")
        if isinstance(manifest_path, str) and manifest_path:
            lines.append(f"Manifest: {manifest_path}")
        apply_proof = release.get("last_apply_proof_path") if isinstance(release, dict) else None
        apply_mode = release.get("last_apply_mode") if isinstance(release, dict) else None
        if isinstance(apply_proof, str) and apply_proof:
            lines.append(f"Apply proof: {apply_proof}")
        if isinstance(apply_mode, str) and apply_mode:
            lines.append(f"Apply mode: {apply_mode}")
        rel_notes = release.get("notes") if isinstance(release, dict) else None
        if isinstance(rel_notes, list) and rel_notes:
            lines.append("Notes: " + ", ".join(str(x) for x in rel_notes))
        lines.append("")

    cat = sections.get("catalog") if isinstance(sections, dict) else {}
    _section_title("Catalog")
    lines.append(f"Status: {cat.get('status', '')}")
    lines.append(f"Packs found: {cat.get('packs_found', 0)}")
    lines.append("")

    packs = sections.get("packs") if isinstance(sections, dict) else {}
    _section_title("Packs")
    lines.append(f"Status: {packs.get('status', '')}")
    lines.append(f"Packs found: {packs.get('packs_found', 0)}")
    selected_pack_ids = packs.get("selected_pack_ids") if isinstance(packs, dict) else None
    if isinstance(selected_pack_ids, list) and selected_pack_ids:
        lines.append("Selected: " + ", ".join(str(x) for x in selected_pack_ids))
    selection_trace = packs.get("selection_trace_path") if isinstance(packs, dict) else None
    if isinstance(selection_trace, str) and selection_trace:
        lines.append(f"Selection trace: {selection_trace}")
    lines.append(f"Hard conflicts: {packs.get('hard_conflicts_count', 0)}")
    lines.append(f"Soft conflicts: {packs.get('soft_conflicts_count', 0)}")
    report_path = packs.get("report_path") if isinstance(packs, dict) else None
    if isinstance(report_path, str) and report_path:
        lines.append(f"Validation report: {report_path}")
    lines.append("")

    fmt = sections.get("formats") if isinstance(sections, dict) else {}
    _section_title("Formats")
    lines.append(f"Status: {fmt.get('status', '')}")
    lines.append(f"Formats found: {fmt.get('formats_found', 0)}")
    lines.append("")

    sess = sections.get("session") if isinstance(sections, dict) else {}
    _section_title("Session")
    lines.append(f"Status: {sess.get('status', '')}")
    lines.append(f"Session ID: {sess.get('session_id', '')}")
    lines.append("")

    qual = sections.get("quality_gate") if isinstance(sections, dict) else {}
    _section_title("Quality")
    lines.append(f"Status: {qual.get('status', '')}")
    lines.append("")

    integrity = sections.get("integrity") if isinstance(sections, dict) else {}
    _section_title("Integrity")
    lines.append(f"Status: {integrity.get('status', '')}")
    lines.append(f"Verify: {integrity.get('verify_on_read_result', '')}")
    lines.append(f"Mismatch count: {integrity.get('mismatch_count', 0)}")
    last_verify = integrity.get("last_verify_path") if isinstance(integrity, dict) else None
    if isinstance(last_verify, str) and last_verify:
        lines.append(f"Report: {last_verify}")
    lines.append("")

    bench = sections.get("benchmark") if isinstance(sections, dict) else {}
    _section_title("Benchmark")
    lines.append(f"Status: {bench.get('status', '')}")
    lines.append(f"Controls: {bench.get('controls_count', 0)}")
    lines.append(f"Metrics: {bench.get('metrics_count', 0)}")
    lines.append(f"Gaps: {bench.get('gaps_count', 0)}")
    lines.append(f"Maturity avg: {bench.get('maturity_avg', 0)}")
    raw_path = bench.get("last_assessment_raw_path") if isinstance(bench, dict) else None
    if isinstance(raw_path, str) and raw_path:
        lines.append(f"Assessment raw: {raw_path}")
    eval_path = bench.get("last_assessment_eval_path") if isinstance(bench, dict) else None
    if isinstance(eval_path, str) and eval_path:
        lines.append(f"Assessment eval: {eval_path}")
    integ_path = bench.get("last_integrity_verify_path") if isinstance(bench, dict) else None
    if isinstance(integ_path, str) and integ_path:
        lines.append(f"Integrity verify: {integ_path}")
    gaps_by_sev = bench.get("gaps_by_severity") if isinstance(bench, dict) else None
    if isinstance(gaps_by_sev, dict):
        lines.append(
            "Gaps by severity: "
            + ", ".join(
                f"{k}={gaps_by_sev.get(k, 0)}" for k in ["high", "medium", "low"]
            )
        )
    top_actions = bench.get("top_next_actions") if isinstance(bench, dict) else None
    if isinstance(top_actions, list) and top_actions:
        lines.append("Top next actions:")
        for a in top_actions[:5]:
            if not isinstance(a, dict):
                continue
            lines.append(
                f"- {a.get('gap_id', '')} severity={a.get('severity', '')} "
                f"risk={a.get('risk_class', '')} effort={a.get('effort', '')}"
            )
    subject_plan_ab = bench.get("subject_plan_ab_summary") if isinstance(bench, dict) else None
    if isinstance(subject_plan_ab, dict):
        lines.append(
            "Subject-plan A/B: "
            f"status={subject_plan_ab.get('status', '')} "
            f"subject={subject_plan_ab.get('subject_id', '')} "
            f"best={subject_plan_ab.get('best_profile', '')} "
            f"score={subject_plan_ab.get('best_score', 0)}"
        )
        available = subject_plan_ab.get("available_profiles")
        if isinstance(available, list) and available:
            lines.append("Profiles available: " + ", ".join(str(item) for item in available))
        missing = subject_plan_ab.get("missing_profiles")
        if isinstance(missing, list) and missing:
            lines.append("Profiles missing: " + ", ".join(str(item) for item in missing))
        report_path = subject_plan_ab.get("report_path")
        if isinstance(report_path, str) and report_path:
            lines.append(f"Subject-plan report: {report_path}")
    profile_order_compare = bench.get("profile_order_compare_summary") if isinstance(bench, dict) else None
    if isinstance(profile_order_compare, dict):
        best_counts = profile_order_compare.get("best_profile_counts")
        best_counts_text = ""
        if isinstance(best_counts, dict):
            parts = []
            for key in ["A", "B", "C"]:
                value = best_counts.get(key, 0)
                try:
                    parts.append(f"{key}:{int(value)}")
                except Exception:
                    parts.append(f"{key}:0")
            best_counts_text = ", ".join(parts)
        lines.append(
            "Profile-order compare: "
            f"status={profile_order_compare.get('status', '')} "
            f"subject={profile_order_compare.get('subject_id', '')} "
            f"orders={profile_order_compare.get('orders_spec', '')} "
            f"scenarios={profile_order_compare.get('scenarios_count', 0)} "
            f"best_counts={best_counts_text}"
        )
        compare_report_path = profile_order_compare.get("report_path")
        if isinstance(compare_report_path, str) and compare_report_path:
            lines.append(f"Profile-order report: {compare_report_path}")
    lines.append("")

    work_intake = sections.get("work_intake") if isinstance(sections, dict) else {}
    if isinstance(work_intake, dict) and work_intake:
        _section_title("Work Intake")
        lines.append(f"Status: {work_intake.get('status', '')}")
        lines.append(f"Items: {work_intake.get('items_count', 0)}")
        lines.append(f"Next focus: {work_intake.get('next_intake_focus', '')}")
        counts = work_intake.get("counts_by_bucket") if isinstance(work_intake, dict) else None
        if isinstance(counts, dict):
            lines.append(
                "Counts by bucket: "
                + ", ".join(
                    f"{k}={counts.get(k, 0)}" for k in ["INCIDENT", "TICKET", "PROJECT", "ROADMAP"]
                )
            )
        top_intake = work_intake.get("top_next_actions") if isinstance(work_intake, dict) else None
        if isinstance(top_intake, list) and top_intake:
            lines.append("Top next:")
            for item in top_intake[:5]:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    f"- {item.get('intake_id', '')} bucket={item.get('bucket', '')} "
                    f"severity={item.get('severity', '')} priority={item.get('priority', '')}"
                )
        lines.append("")

    work_intake_exec = sections.get("work_intake_exec") if isinstance(sections, dict) else {}
    if isinstance(work_intake_exec, dict) and work_intake_exec:
        _section_title("Work Intake Exec")
        lines.append(f"Status: {work_intake_exec.get('status', '')}")
        lines.append(f"Policy source: {work_intake_exec.get('policy_source', '')}")
        lines.append(f"Policy hash: {work_intake_exec.get('policy_hash', '')}")
        lines.append(
            "Counts: "
            + ", ".join(
                [
                    f"applied={work_intake_exec.get('applied_count', 0)}",
                    f"planned={work_intake_exec.get('planned_count', 0)}",
                    f"idle={work_intake_exec.get('idle_count', 0)}",
                ]
            )
        )
        if "skipped_count" in work_intake_exec:
            lines.append(f"Skipped: {work_intake_exec.get('skipped_count', 0)}")
        if "ignored_count" in work_intake_exec:
            lines.append(f"Ignored: {work_intake_exec.get('ignored_count', 0)}")
        if "decision_needed_count" in work_intake_exec:
            lines.append(f"Decision needed: {work_intake_exec.get('decision_needed_count', 0)}")
        lines.append("")

    decisions = sections.get("decisions") if isinstance(sections, dict) else {}
    if isinstance(decisions, dict) and decisions:
        _section_title("Decisions")
        lines.append(f"Pending: {decisions.get('pending_decisions_count', 0)}")
        lines.append(f"Blocked count: {decisions.get('blocked_count', 0)}")
        inbox_path = decisions.get("last_decision_inbox_path", "")
        if inbox_path:
            lines.append(f"Inbox path: {inbox_path}")
        apply_path = decisions.get("last_decision_apply_path", "")
        if apply_path:
            lines.append(f"Last apply: {apply_path}")
        by_kind = decisions.get("pending_decisions_by_kind") if isinstance(decisions, dict) else None
        if isinstance(by_kind, dict) and by_kind:
            lines.append(
                "By kind: "
                + ", ".join(f"{k}={by_kind.get(k, 0)}" for k in sorted(by_kind))
            )
        lines.append("")

    context_router = sections.get("context_router") if isinstance(sections, dict) else {}
    if isinstance(context_router, dict) and context_router:
        _section_title("Context Router")
        lines.extend(context_router_md_lines(context_router))
        lines.append("")

    pdca = sections.get("pdca") if isinstance(sections, dict) else {}
    _section_title("PDCA")
    lines.append(f"Status: {pdca.get('status', '')}")
    lines.append(f"Regressions: {pdca.get('regressions_count', 0)}")
    lines.append(f"Quota: {pdca.get('quota_state', '')}")
    lines.append(f"Cooldown: {pdca.get('cooldown_state', '')}")
    lines.append(f"Cursor: {pdca.get('cursor_state', '')}")
    lines.append("")

    harv = sections.get("harvest") if isinstance(sections, dict) else {}
    _section_title("Harvest")
    lines.append(f"Status: {harv.get('status', '')}")
    lines.append(f"Candidates: {harv.get('candidates', 0)}")
    lines.append("")

    adv = sections.get("advisor") if isinstance(sections, dict) else {}
    _section_title("Advisor")
    lines.append(f"Status: {adv.get('status', '')}")
    lines.append(f"Suggestions: {adv.get('suggestions', 0)}")
    lines.append("")

    pack_adv = sections.get("pack_advisor") if isinstance(sections, dict) else {}
    _section_title("Pack Advisor")
    lines.append(f"Status: {pack_adv.get('status', '')}")
    lines.append(f"Suggestions: {pack_adv.get('suggestions', 0)}")
    lines.append("")

    readiness = sections.get("readiness") if isinstance(sections, dict) else {}
    _section_title("Readiness")
    lines.append(f"Status: {readiness.get('status', '')}")
    lines.append("")

    actions = sections.get("actions") if isinstance(sections, dict) else {}
    _section_title("Actions")
    lines.append(f"Status: {actions.get('status', '')}")
    lines.append(f"Unresolved actions: {actions.get('actions_count', 0)}")
    lines.append("")

    repo_hygiene = sections.get("repo_hygiene") if isinstance(sections, dict) else None
    _section_title("Repo hygiene")
    if isinstance(repo_hygiene, dict):
        lines.append(f"Status: {repo_hygiene.get('status', '')}")
        lines.append(f"Unexpected dirs: {repo_hygiene.get('unexpected_top_level_dirs', 0)}")
        lines.append(f"Tracked generated files: {repo_hygiene.get('tracked_generated_files', 0)}")
        top_findings = repo_hygiene.get("top_findings") if isinstance(repo_hygiene.get("top_findings"), list) else []
        if top_findings:
            top_lines = []
            for item in top_findings[:3]:
                if not isinstance(item, dict):
                    continue
                top_lines.append(f"{item.get('kind')}:{item.get('path')}")
            if top_lines:
                lines.append("Top findings: " + ", ".join(top_lines))
        notes = repo_hygiene.get("notes") if isinstance(repo_hygiene.get("notes"), list) else []
        if notes:
            lines.append("Notes: " + ", ".join(str(x) for x in notes))
    else:
        lines.append("No repo hygiene report found.")
    lines.append("")

    doc_graph = sections.get("doc_graph") if isinstance(sections, dict) else None
    _section_title("Doc graph")
    if isinstance(doc_graph, dict):
        lines.append(f"Status: {doc_graph.get('status', '')}")
        lines.append(f"Broken refs: {doc_graph.get('broken_refs', 0)}")
        lines.append(f"Placeholders: {doc_graph.get('placeholder_refs_count', 0)}")
        lines.append(f"Orphan critical: {doc_graph.get('orphan_critical', 0)}")
        lines.append(f"Ambiguity: {doc_graph.get('ambiguity', 0)}")
        lines.append(f"Critical nav gaps: {doc_graph.get('critical_nav_gaps', 0)}")
        report_path = doc_graph.get("report_path")
        if isinstance(report_path, str) and report_path:
            lines.append(f"Report: {report_path}")
        notes = doc_graph.get("notes") if isinstance(doc_graph.get("notes"), list) else []
        if notes:
            lines.append("Notes: " + ", ".join(str(x) for x in notes))
    else:
        lines.append("No doc graph report found.")
    lines.append("")

    auto_heal = sections.get("auto_heal") if isinstance(sections, dict) else None
    _section_title("Auto-heal")
    if isinstance(auto_heal, dict):
        lines.append(f"Status: {auto_heal.get('status', '')}")
        lines.append(f"Missing: {auto_heal.get('missing_count', 0)}")
        lines.append(f"Healed: {auto_heal.get('healed_count', 0)}")
        lines.append(f"Still missing: {auto_heal.get('still_missing_count', 0)}")
        attempted = auto_heal.get("attempted_milestones")
        if isinstance(attempted, list) and attempted:
            lines.append("Attempted milestones: " + ", ".join(str(x) for x in attempted))
        top_healed = auto_heal.get("top_healed")
        if isinstance(top_healed, list) and top_healed:
            lines.append("Top healed: " + ", ".join(str(x.get("id")) for x in top_healed if isinstance(x, dict)))
    else:
        lines.append("No recent auto-heal report found.")
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"
