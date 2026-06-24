from __future__ import annotations

from typing import Any

from .system_status_context_router import context_router_md_lines

def _render_md_impl(report: dict[str, Any]) -> str:
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

    execution_target_governance = sections.get("execution_target_governance") if isinstance(sections, dict) else {}
    if isinstance(execution_target_governance, dict) and execution_target_governance:
        _section_title("Execution target governance")
        lines.append(f"Status: {execution_target_governance.get('status', '')}")
        lines.append(
            "Registries: "
            + f"repos={execution_target_governance.get('repo_count', 0)} "
            + f"targets={execution_target_governance.get('target_count', 0)} "
            + f"launch_profiles={execution_target_governance.get('launch_profile_count', 0)} "
            + f"version_targets={execution_target_governance.get('version_target_count', 0)}"
        )
        lines.append(
            "AI entry pack: "
            + f"status={execution_target_governance.get('ai_entry_pack', {}).get('status', '')} "
            + f"valid={execution_target_governance.get('ai_entry_pack', {}).get('valid', False)} "
            + f"auto_refreshed={execution_target_governance.get('ai_entry_pack', {}).get('auto_refreshed', False)}"
        )
        lines.append(
            "File write arbitration: "
            + f"active={execution_target_governance.get('file_write_arbitration', {}).get('active_lease_count', 0)} "
            + f"stale={execution_target_governance.get('file_write_arbitration', {}).get('stale_lease_count', 0)}"
        )
        resolution_report = execution_target_governance.get("last_resolution_report_path")
        if isinstance(resolution_report, str) and resolution_report:
            lines.append(f"Resolution report: {resolution_report}")
        guard_report = execution_target_governance.get("last_guard_report_path")
        if isinstance(guard_report, str) and guard_report:
            lines.append(f"Guard report: {guard_report}")
        notes = execution_target_governance.get("notes")
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
            + f"active={error_observability.get('active_items_total', 0)} "
            + f"acked={error_observability.get('acked_items_total', 0)} "
            + f"build={error_observability.get('build_count', 0)} "
            + f"runner={error_observability.get('runner_count', 0)} "
            + f"browser={error_observability.get('browser_count', 0)}"
        )
        lines.append(
            "Active by source: "
            + f"build={error_observability.get('active_build_count', 0)} "
            + f"runner={error_observability.get('active_runner_count', 0)} "
            + f"browser={error_observability.get('active_browser_count', 0)}"
        )
        report_path = error_observability.get("report_path")
        if isinstance(report_path, str) and report_path:
            lines.append(f"Report: {report_path}")
        ack_state_path = error_observability.get("ack_state_path")
        if isinstance(ack_state_path, str) and ack_state_path:
            lines.append(f"Ack state: {ack_state_path}")
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
