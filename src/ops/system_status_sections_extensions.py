from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from src.ops.system_status_sections_extensions_helpers_v2 import (
    _find_auto_heal_report,
    _job_time,
    _load_json,
    _normalize_core_path,
    _parse_iso,
    _repo_root,
)

from src.ops.system_status_sections_airunner import (
    _airunner_auto_run_section,
    _airunner_proof_section,
    _airunner_section,
    _auto_loop_section,
)


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
    healthcheck_rel = str(Path(".cache") / "reports" / "cockpit_healthcheck.v1.json")
    healthcheck_path = workspace_root / healthcheck_rel
    last_cockpit_healthcheck_path = healthcheck_rel if healthcheck_path.exists() else ""

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
        "last_cockpit_healthcheck_path": last_cockpit_healthcheck_path,
        "notes": notes,
    }
def _cockpit_lite_section(workspace_root: Path) -> dict[str, Any]:
    healthcheck_rel = Path(".cache") / "reports" / "cockpit_healthcheck.v1.json"
    healthcheck_path = workspace_root / healthcheck_rel
    chat_rel = Path(".cache") / "chat_console" / "chat_log.v1.jsonl"
    chat_path = workspace_root / chat_rel
    notes_root = workspace_root / ".cache" / "notes" / "planner"
    notes_index_path = notes_root / "notes_index.v1.json"
    status = "MISSING"
    port = 0
    last_request_id = ""
    last_chat_log_path = ""
    notes_count = 0
    last_note_id = ""
    if healthcheck_path.exists():
        try:
            obj = _load_json(healthcheck_path)
        except Exception:
            status = "WARN"
            obj = {}
        else:
            raw_status = obj.get("status") if isinstance(obj, dict) else ""
            status = raw_status if raw_status in {"OK", "WARN", "FAIL", "IDLE"} else "OK"
        if isinstance(obj, dict) and isinstance(obj.get("port"), int):
            port = int(obj.get("port"))
        if isinstance(obj, dict) and isinstance(obj.get("request_id"), str):
            last_request_id = str(obj.get("request_id") or "")
    if chat_path.exists():
        last_chat_log_path = str(chat_rel)

    if notes_index_path.exists():
        try:
            index_obj = _load_json(notes_index_path)
        except Exception:
            index_obj = {}
        if isinstance(index_obj, dict):
            if isinstance(index_obj.get("notes_count"), int):
                notes_count = int(index_obj.get("notes_count") or 0)
            notes = index_obj.get("notes") if isinstance(index_obj.get("notes"), list) else []
            if notes:
                last = notes[-1]
                if isinstance(last, dict) and isinstance(last.get("note_id"), str):
                    last_note_id = str(last.get("note_id") or "")
    elif notes_root.exists():
        note_files = sorted(notes_root.glob("NOTE-*.v1.json"))
        notes_count = len(note_files)
        if note_files:
            last_note_id = note_files[-1].name.replace(".v1.json", "")

    return {
        "status": status,
        "port": port,
        "last_healthcheck_path": str(healthcheck_rel) if healthcheck_path.exists() else "",
        "last_request_id": last_request_id,
        "last_chat_log_path": last_chat_log_path,
        "notes_count": notes_count,
        "last_note_id": last_note_id,
    }


def _network_live_section(workspace_root: Path) -> dict[str, Any]:
    override_rel = Path(".cache") / "policy_overrides" / "policy_network_live.override.v1.json"
    override_path = workspace_root / override_rel
    enabled = False
    enabled_by_decision = False
    allow_domains_count = 0
    allow_actions_count = 0
    policy_source = "core"
    reason_code = ""
    last_override_path = ""
    if override_path.exists():
        policy_source = "workspace"
        last_override_path = str(override_rel)
        try:
            obj = _load_json(override_path)
        except Exception:
            reason_code = "OVERRIDE_INVALID"
        else:
            if isinstance(obj, dict):
                raw_enabled = bool(obj.get("enabled", False))
                enabled_by_decision = bool(obj.get("enabled_by_decision", False))
                enabled = bool(raw_enabled and enabled_by_decision)
                if isinstance(obj.get("allow_domains_count"), int):
                    allow_domains_count = int(obj.get("allow_domains_count") or 0)
                else:
                    allow_domains = obj.get("allow_domains") if isinstance(obj.get("allow_domains"), list) else []
                    allow_domains_count = len({str(x) for x in allow_domains if isinstance(x, str) and x.strip()})
                if isinstance(obj.get("allow_actions_count"), int):
                    allow_actions_count = int(obj.get("allow_actions_count") or 0)
                else:
                    allow_actions = obj.get("allow_actions") if isinstance(obj.get("allow_actions"), list) else []
                    allow_actions_count = len({str(x) for x in allow_actions if isinstance(x, str) and x.strip()})
                if raw_enabled and not enabled_by_decision:
                    reason_code = "DECISION_REQUIRED"
            else:
                reason_code = "OVERRIDE_INVALID"
    else:
        reason_code = "OVERRIDE_MISSING"
    decision_pending = 0
    inbox_path = workspace_root / ".cache" / "index" / "decision_inbox.v1.json"
    if inbox_path.exists():
        try:
            inbox = _load_json(inbox_path)
        except Exception:
            inbox = {}
        counts = inbox.get("counts") if isinstance(inbox, dict) else None
        by_kind = counts.get("by_kind") if isinstance(counts, dict) else None
        if isinstance(by_kind, dict) and isinstance(by_kind.get("NETWORK_LIVE_ENABLE"), int):
            decision_pending = int(by_kind.get("NETWORK_LIVE_ENABLE") or 0)
        else:
            items = inbox.get("items") if isinstance(inbox, dict) else None
            items_list = items if isinstance(items, list) else []
            decision_pending = len(
                [item for item in items_list if isinstance(item, dict) and str(item.get("decision_kind") or "") == "NETWORK_LIVE_ENABLE"]
            )
    payload = {
        "enabled": enabled,
        "enabled_by_decision": enabled_by_decision,
        "policy_source": policy_source,
        "allow_domains_count": int(allow_domains_count),
        "allow_actions_count": int(allow_actions_count),
        "decision_pending": int(decision_pending),
    }
    if last_override_path:
        payload["last_override_path"] = last_override_path
    if reason_code:
        payload["reason_code"] = reason_code
    return payload


def _github_ops_section(workspace_root: Path) -> dict[str, Any] | None:
    jobs_index_rel = Path(".cache") / "github_ops" / "jobs_index.v1.json"
    jobs_index_path = workspace_root / jobs_index_rel
    report_rel = Path(".cache") / "reports" / "github_ops_report.v1.json"
    report_path = workspace_root / report_rel
    if not jobs_index_path.exists() and not report_path.exists():
        return None

    status = "IDLE"
    notes: list[str] = []
    jobs: list[dict[str, Any]] = []
    if jobs_index_path.exists():
        try:
            idx = _load_json(jobs_index_path)
        except Exception:
            notes.append("github_ops_jobs_index_invalid")
            status = "WARN"
        else:
            loaded = idx.get("jobs") if isinstance(idx, dict) else None
            jobs = [j for j in loaded if isinstance(j, dict)] if isinstance(loaded, list) else []
            if jobs:
                status = "OK"
    else:
        notes.append("github_ops_jobs_index_missing")

    last_pr_open = {"job_id": "", "status": ""}
    pr_jobs = [j for j in jobs if str(j.get("kind") or "") == "PR_OPEN"]
    if pr_jobs:
        pr_jobs.sort(key=lambda j: (_job_time(j), str(j.get("job_id") or "")), reverse=True)
        job = pr_jobs[0]
        last_pr_open = {
            "job_id": str(job.get("job_id") or ""),
            "status": str(job.get("status") or ""),
        }
        pr_url = job.get("pr_url")
        if isinstance(pr_url, str) and pr_url:
            last_pr_open["pr_url"] = pr_url
        pr_number = job.get("pr_number")
        if isinstance(pr_number, int) and pr_number > 0:
            last_pr_open["pr_number"] = pr_number
        reason = job.get("skip_reason") or job.get("error_code")
        if isinstance(reason, str) and reason:
            last_pr_open["reason"] = reason

    failure_classes = [
        "AUTH",
        "PERMISSION",
        "VALIDATION",
        "NOT_FOUND",
        "CONFLICT",
        "RATE_LIMIT",
        "NETWORK",
        "POLICY_TIME_LIMIT",
        "DEMO_PUBLIC_CANDIDATES_POINTER_MISSING",
        "DEMO_PACK_CAPABILITY_INDEX_MISSING",
        "DEMO_M9_3_APPLY_MUST_WRITE_PACK_SELECTION_TRACE_V1_JSON",
        "DEMO_OTHER_MARKER_2472D115C490",
        "DEMO_QUALITY_GATE_REPORT_MISSING",
        "DEMO_SESSION_CONTEXT_HASH_MISMATCH",
        "OTHER",
    ]
    failure_counts = {cls: 0 for cls in failure_classes}
    total_fail = 0
    for job in jobs:
        if str(job.get("status") or "") != "FAIL":
            continue
        total_fail += 1
        cls = str(job.get("failure_class") or "OTHER")
        if cls not in failure_counts:
            cls = "OTHER"
        failure_counts[cls] += 1

    section = {
        "status": status,
        "jobs_index_path": str(jobs_index_rel),
        "last_pr_open": last_pr_open,
        "notes": notes,
    }
    if total_fail > 0:
        section["failure_summary"] = {"total_fail": total_fail, "by_class": failure_counts}
    if report_path.exists():
        section["last_report_path"] = str(report_rel)
    triage_rel = Path(".cache") / "reports" / "smoke_full_triage.v1.json"
    triage_path = workspace_root / triage_rel
    if triage_path.exists():
        section["last_smoke_full_triage_path"] = str(triage_rel)
    triage_fast_rel = Path(".cache") / "reports" / "smoke_fast_triage.v1.json"
    triage_fast_path = workspace_root / triage_fast_rel
    if triage_fast_path.exists():
        section["last_smoke_fast_triage_path"] = str(triage_fast_rel)
    return section


def _deploy_targets_summary() -> tuple[dict[str, Any] | None, list[str]]:
    notes: list[str] = []
    core_root = _repo_root()
    policy_path = core_root / "policies" / "policy_deploy_targets.v1.json"
    if not policy_path.exists():
        notes.append("deploy_targets_policy_missing")
        return None, notes
    try:
        obj = _load_json(policy_path)
    except Exception:
        notes.append("deploy_targets_policy_invalid")
        return None, notes
    if not isinstance(obj, dict):
        notes.append("deploy_targets_policy_invalid")
        return None, notes
    envs = obj.get("environments") if isinstance(obj.get("environments"), list) else []
    kinds = obj.get("deploy_job_kinds") if isinstance(obj.get("deploy_job_kinds"), list) else []
    env_count = len({str(x) for x in envs if isinstance(x, str) and x.strip()})
    kind_count = len({str(x) for x in kinds if isinstance(x, str) and x.strip()})
    summary = {
        "policy_path": str(policy_path.relative_to(core_root)),
        "environments_count": int(env_count),
        "deploy_kinds_count": int(kind_count),
    }
    return summary, notes


def _deploy_section(workspace_root: Path) -> dict[str, Any] | None:
    rel_path = str(Path(".cache") / "reports" / "deploy_report.v1.json")
    report_path = workspace_root / rel_path
    targets_summary, targets_notes = _deploy_targets_summary()
    if not report_path.exists() and targets_summary is None:
        return None

    notes: list[str] = []
    status = "IDLE"
    job_id = ""
    job_status = ""
    if report_path.exists():
        try:
            report = _load_json(report_path)
        except Exception:
            report = {}
            status = "WARN"
            notes.append("deploy_report_invalid")
        if isinstance(report, dict):
            report_status = str(report.get("status") or "")
            if report_status in {"OK", "WARN", "IDLE"}:
                status = report_status
            last_job = report.get("last_job") if isinstance(report.get("last_job"), dict) else {}
            job_id = str(last_job.get("job_id") or "")
            job_status = str(last_job.get("status") or "")
    else:
        notes.append("deploy_report_missing")
    notes.extend(targets_notes)
    section = {
        "status": status,
        "last_deploy_job_id": job_id,
        "last_deploy_job_status": job_status,
        "last_deploy_report_path": rel_path,
        "notes": notes,
    }
    if isinstance(targets_summary, dict):
        section["deploy_targets"] = targets_summary
    return section


def _release_section(workspace_root: Path) -> dict[str, Any]:
    plan_rel = str(Path(".cache") / "reports" / "release_plan.v1.json")
    manifest_rel = str(Path(".cache") / "reports" / "release_manifest.v1.json")
    notes_rel = str(Path(".cache") / "reports" / "release_notes.v1.md")
    proof_rel = str(Path(".cache") / "reports" / "release_apply_proof.v1.json")
    plan_path = workspace_root / plan_rel
    manifest_path = workspace_root / manifest_rel
    notes_path = workspace_root / notes_rel
    proof_path = workspace_root / proof_rel

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
    apply_mode = ""
    apply_generated_at = ""

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

    if proof_path.exists():
        try:
            proof = _load_json(proof_path)
        except Exception:
            notes.append("apply_proof_invalid_json")
            proof = {}
        if isinstance(proof, dict):
            mode = str(proof.get("apply_mode") or "")
            if mode in {"NOOP", "APPLIED"}:
                apply_mode = mode
            generated_at = str(proof.get("generated_at") or "")
            if generated_at:
                apply_generated_at = generated_at
        evidence_paths.append(proof_rel)

    try:
        from src.prj_release_automation.release_engine import publish_release

        publish = publish_release(workspace_root=workspace_root, channel=channel, allow_network=False, trusted_context=False)
        if isinstance(publish, dict):
            publish_status = str(publish.get("status", publish_status))
            publish_reason = str(publish.get("error_code") or publish_reason)
    except Exception:
        publish_status = "WARN"
        publish_reason = "PUBLISH_STATUS_UNAVAILABLE"

    release_section = {
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

    if apply_mode:
        release_section["last_apply_proof_path"] = proof_rel
        release_section["last_apply_mode"] = apply_mode
        if apply_generated_at:
            release_section["last_apply_generated_at"] = apply_generated_at

    return release_section


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
