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
    _execution_target_governance_section,
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
    _provider_capability_section,
    _role_handoff_section,
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
    execution_target_governance = _execution_target_governance_section(
        workspace_root,
        allow_write=not dry_run,
    )
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
    if isinstance(execution_target_governance, dict):
        etg_status = str(execution_target_governance.get("status") or "WARN")
        section_statuses.append("WARN" if etg_status == "IDLE" else etg_status)
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
            "execution_target_governance": execution_target_governance,
            "provider_capability": _provider_capability_section(workspace_root),
            "role_handoff": _role_handoff_section(workspace_root),
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

    # Context health + drift sections (self-healing triad)
    try:
        from src.benchmark.eval_runner_runtime import _compute_context_health_lens

        ctx_health = _compute_context_health_lens(workspace_root=workspace_root, lenses_policy={})
        report["sections"]["context_health"] = {
            "status": ctx_health.get("status", "UNKNOWN"),
            "score": int(float(ctx_health.get("score", 0)) * 100),
            "components": ctx_health.get("components", {}),
            "reasons": ctx_health.get("reasons", []),
        }
    except Exception:
        report["sections"]["context_health"] = {"status": "SKIP", "score": 0}

    drift_report_path = workspace_root / ".cache" / "reports" / "context_drift_report.v1.json"
    if drift_report_path.exists():
        try:
            import json as _json

            drift_data = _json.loads(drift_report_path.read_text(encoding="utf-8"))
            report["sections"]["context_drift"] = {
                "status": drift_data.get("status", "UNKNOWN"),
                "drift_score": drift_data.get("drift_score", 0),
                "total_drifted": drift_data.get("total_drifted", 0),
            }
        except Exception:
            pass

    return report


def _render_md(report: dict[str, Any]) -> str:
    from .system_status_render import _render_md_impl

    return _render_md_impl(report)
