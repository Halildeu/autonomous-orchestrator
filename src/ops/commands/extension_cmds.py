from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root, warn
from src.ops.commands.extension_cmds_helpers_v2 import (
    _dump_json,
    _emit_planner_show_plan_chat,
    _load_json,
    _now_compact,
    _parse_csv_list,
    _resolve_workspace_root,
)
from src.ops.commands.smoke_triage_cmds import cmd_smoke_fast_triage, cmd_smoke_full_triage
from src.ops.reaper import parse_bool as parse_reaper_bool

from src.ops.commands.extension_cmds_airunner import (
    cmd_airunner_active_hours_set,
    cmd_airunner_auto_run_check,
    cmd_airunner_auto_run_poll,
    cmd_airunner_auto_run_start,
    cmd_airunner_baseline,
    cmd_airunner_jobs_seed,
    cmd_airunner_lock_clear_stale,
    cmd_airunner_lock_status,
    cmd_airunner_proof_bundle,
    cmd_airunner_run,
    cmd_airunner_status,
    cmd_airunner_tick,
    cmd_airunner_watchdog,
    cmd_extension_help,
    cmd_extension_registry,
    cmd_extension_run,
    cmd_planner_apply_selection,
    cmd_planner_build_plan,
    cmd_planner_show_plan,
)


def cmd_release_plan(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    channel = str(args.channel or "").strip().lower() or None
    detail = parse_reaper_bool(str(args.detail))

    from src.prj_release_automation.release_engine import build_release_plan

    payload = build_release_plan(workspace_root=ws, channel=channel, detail=detail)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") in {"OK", "WARN", "IDLE"} else 2


def cmd_release_prepare(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    channel = str(args.channel or "").strip().lower() or None

    from src.prj_release_automation.release_engine import prepare_release

    payload = prepare_release(workspace_root=ws, channel=channel)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") in {"OK", "WARN", "IDLE"} else 2


def cmd_release_publish(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    channel = str(args.channel or "").strip().lower() or None
    allow_network = parse_reaper_bool(str(args.allow_network))
    trusted_context = parse_reaper_bool(str(args.trusted_context))

    from src.prj_release_automation.release_engine import publish_release

    payload = publish_release(
        workspace_root=ws,
        channel=channel,
        allow_network=allow_network,
        trusted_context=trusted_context,
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") in {"OK", "WARN", "IDLE", "SKIP"} else 2


def cmd_release_check(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    channel = str(args.channel or "").strip().lower() or None
    chat = parse_reaper_bool(str(args.chat))

    from src.prj_release_automation.release_engine import run_release_check

    res = run_release_check(workspace_root=ws, channel=channel, chat=chat)
    status = res.get("status") if isinstance(res, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_release_final_e2e(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    base_branch = str(getattr(args, "base_branch", "") or "").strip() or "main"
    allow_network = parse_reaper_bool(str(getattr(args, "allow_network", "true")))
    dry_run = parse_reaper_bool(str(getattr(args, "dry_run", "false")))
    chat = parse_reaper_bool(str(getattr(args, "chat", "true")))

    from src.prj_release_automation.release_final_e2e import run_release_final_e2e

    payload = run_release_final_e2e(
        workspace_root=ws,
        base_branch=base_branch,
        allow_network=bool(allow_network),
        dry_run=bool(dry_run),
    )

    if chat and isinstance(payload, dict):
        print("PREVIEW:")
        print("PROGRAM-LED: release-final-e2e (PR open -> merge -> GitHub FINAL release)")
        print(f"workspace_root={ws}")
        print("RESULT:")
        print(f"status={payload.get('status')}")
        if payload.get("error_code"):
            print(f"error_code={payload.get('error_code')}")
        print("EVIDENCE:")
        report_path = payload.get("report_path") or ""
        if report_path:
            print(str(report_path))
        print("ACTIONS:")
        print("github-ops-check")
        print("work-intake-build")
        print("work-intake-check")
        print("NEXT:")
        print("Devam et / Durumu goster / Duraklat")

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    status = payload.get("status") if isinstance(payload, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_pr_merge_e2e(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    base_branch = str(getattr(args, "base_branch", "") or "").strip() or "main"
    allow_network = parse_reaper_bool(str(getattr(args, "allow_network", "true")))
    dry_run = parse_reaper_bool(str(getattr(args, "dry_run", "false")))
    chat = parse_reaper_bool(str(getattr(args, "chat", "true")))

    from src.prj_release_automation.pr_merge_e2e import run_pr_merge_e2e

    payload = run_pr_merge_e2e(
        workspace_root=ws,
        base_branch=base_branch,
        allow_network=bool(allow_network),
        dry_run=bool(dry_run),
    )

    if chat and isinstance(payload, dict):
        print("PREVIEW:")
        print("PROGRAM-LED: pr-merge-e2e (PR open -> merge, no release)")
        print(f"workspace_root={ws}")
        print("RESULT:")
        print(f"status={payload.get('status')}")
        if payload.get("error_code"):
            print(f"error_code={payload.get('error_code')}")
        print("EVIDENCE:")
        report_path = payload.get("report_path") or ""
        if report_path:
            print(str(report_path))
        print("ACTIONS:")
        print("github-ops-check")
        print("work-intake-build")
        print("work-intake-check")
        print("NEXT:")
        print("Devam et / Durumu goster / Duraklat")

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    status = payload.get("status") if isinstance(payload, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_deploy_check(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    chat = parse_reaper_bool(str(args.chat))

    from src.extensions.prj_deploy.deploy_jobs import run_deploy_check

    res = run_deploy_check(workspace_root=ws, chat=chat)
    status = res.get("status") if isinstance(res, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE", "SKIP"} else 2


def cmd_search_check(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    chat = parse_reaper_bool(str(args.chat))
    scope = str(getattr(args, "scope", "ssot") or "ssot")
    query = str(getattr(args, "query", "policy") or "policy")
    mode = str(getattr(args, "mode", "keyword") or "keyword")

    from src.extensions.prj_search.search_check import run_search_check

    res = run_search_check(workspace_root=ws, scope=scope, query=query, mode=mode, chat=chat)
    status = res.get("status") if isinstance(res, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_extension_run_bulk_diff(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    chat = parse_reaper_bool(str(getattr(args, "chat", "true")))
    emit_chg = parse_reaper_bool(str(getattr(args, "emit_chg", "true")))
    extension_ids = _parse_csv_list(str(getattr(args, "extension_ids", "") or ""))

    from src.ops.extension_run_bulk_diff import run_extension_run_bulk_diff

    res = run_extension_run_bulk_diff(
        workspace_root=ws,
        extension_ids=extension_ids if extension_ids else None,
        emit_chg=emit_chg,
        chat=chat,
    )
    status = res.get("status") if isinstance(res, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_deploy_job_start(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    kind = str(args.kind or "").strip()
    if not kind:
        warn("FAIL error=KIND_REQUIRED")
        return 2

    payload_ref = str(args.payload or "").strip()
    if not payload_ref:
        warn("FAIL error=PAYLOAD_REQUIRED")
        return 2

    mode_override = str(getattr(args, "mode", "") or "").strip()
    if not mode_override:
        mode_override = None

    from src.extensions.prj_deploy.deploy_jobs import deploy_job_start

    payload = deploy_job_start(workspace_root=ws, kind=kind, payload_ref=payload_ref, mode_override=mode_override)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    status = payload.get("status") if isinstance(payload, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE", "SKIP", "QUEUED", "RUNNING"} else 2


def cmd_deploy_job_poll(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    job_id = str(args.job_id or "").strip()
    if not job_id:
        warn("FAIL error=JOB_ID_REQUIRED")
        return 2

    from src.extensions.prj_deploy.deploy_jobs import deploy_job_poll

    payload = deploy_job_poll(workspace_root=ws, job_id=job_id)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    status = payload.get("status") if isinstance(payload, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE", "SKIP", "PASS", "RUNNING", "QUEUED"} else 2


def cmd_github_ops_check(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    chat = parse_reaper_bool(str(args.chat))

    from src.prj_github_ops.github_ops import run_github_ops_check

    res = run_github_ops_check(workspace_root=ws, chat=chat)
    status = res.get("status") if isinstance(res, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_github_ops_job_start(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    kind = str(args.kind or "").strip()
    if not kind:
        warn("FAIL error=KIND_REQUIRED")
        return 2

    dry_run = parse_reaper_bool(str(args.dry_run))

    from src.prj_github_ops.github_ops import start_github_ops_job

    payload = start_github_ops_job(workspace_root=ws, kind=kind, dry_run=dry_run)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    status = payload.get("status") if isinstance(payload, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE", "SKIP", "QUEUED", "RUNNING"} else 2


def cmd_github_ops_pr_open(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    dry_run = parse_reaper_bool(str(args.dry_run))
    chat = parse_reaper_bool(str(args.chat))
    draft = parse_reaper_bool(str(args.draft))

    from src.prj_github_ops.github_ops import start_github_ops_job

    request: dict[str, Any] = {
        "draft": bool(draft),
    }
    repo_owner = str(getattr(args, "repo_owner", "") or "").strip()
    repo_name = str(getattr(args, "repo_name", "") or "").strip()
    base_branch = str(getattr(args, "base_branch", "") or "").strip()
    head_branch = str(getattr(args, "head_branch", "") or "").strip()
    title = str(getattr(args, "title", "") or "").strip()
    body = str(getattr(args, "body", "") or "").strip()
    labels = _parse_csv_list(getattr(args, "labels", ""))
    reviewers = _parse_csv_list(getattr(args, "reviewers", ""))
    assignees = _parse_csv_list(getattr(args, "assignees", ""))

    if repo_owner:
        request["repo_owner"] = repo_owner
    if repo_name:
        request["repo_name"] = repo_name
    if base_branch:
        request["base_branch"] = base_branch
    if head_branch:
        request["head_branch"] = head_branch
    if title:
        request["title"] = title
    if body:
        request["body"] = body
    if labels:
        request["labels"] = labels
    if reviewers:
        request["reviewers"] = reviewers
    if assignees:
        request["assignees"] = assignees

    payload = start_github_ops_job(workspace_root=ws, kind="PR_OPEN", dry_run=dry_run, request=request)
    if chat and isinstance(payload, dict):
        gate = payload.get("gate_state") if isinstance(payload.get("gate_state"), dict) else {}
        decision_needed = bool(payload.get("decision_needed", False))
        job_id = payload.get("job_id") or ""
        status = payload.get("status") or ""
        reason = payload.get("error_code") or ""
        if payload.get("decision_seed_path"):
            reason = reason or "DECISION_SEEDED"
        preview_lines = [
            "PROGRAM-LED: github-ops-pr-open (no-wait)",
            f"workspace_root={ws}",
        ]
        result_lines = [
            f"job_id={job_id}",
            f"status={status}",
            f"reason={reason}",
            f"decision_needed={decision_needed}",
            "network_gate="
            + f"net={gate.get('network_enabled', False)}"
            + f" live={gate.get('live_enabled', False)}"
            + f" env_flag_set={gate.get('env_flag_set', False)}"
            + f" env_key_present={gate.get('env_key_present', False)}",
        ]
        evidence_lines = []
        if payload.get("job_report_path"):
            evidence_lines.append(str(payload.get("job_report_path")))
        if payload.get("jobs_index_path"):
            evidence_lines.append(str(payload.get("jobs_index_path")))
        if payload.get("decision_seed_path"):
            evidence_lines.append(str(payload.get("decision_seed_path")))
        if payload.get("decision_inbox_path"):
            evidence_lines.append(str(payload.get("decision_inbox_path")))
        actions_lines = ["github-ops-job-poll", "decision-inbox-build"]
        next_lines = ["Devam et", "Durumu göster", "Duraklat"]

        print("PREVIEW:")
        print("\n".join(preview_lines))
        print("RESULT:")
        print("\n".join(result_lines))
        print("EVIDENCE:")
        print("\n".join(evidence_lines))
        print("ACTIONS:")
        print("\n".join(actions_lines))
        print("NEXT:")
        print("\n".join(next_lines))
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    status = payload.get("status") if isinstance(payload, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE", "SKIP", "QUEUED", "RUNNING"} else 2


def cmd_github_ops_job_poll(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    job_id = str(getattr(args, "job_id", "") or "").strip()
    chat = parse_reaper_bool(str(args.chat))
    max_jobs = 1
    try:
        max_jobs = int(args.max)
    except Exception:
        max_jobs = 1

    from src.prj_github_ops.github_ops import poll_github_ops_job, poll_github_ops_jobs

    if job_id:
        payload = poll_github_ops_job(workspace_root=ws, job_id=job_id)
        if chat and isinstance(payload, dict):
            preview_lines = [
                "PROGRAM-LED: github-ops-job-poll",
                f"workspace_root={ws}",
            ]
            result_lines = [
                f"job_id={payload.get('job_id')}",
                f"status={payload.get('status')}",
                f"job_kind={payload.get('job_kind')}",
            ]
            evidence_lines = [str(payload.get("job_report_path") or ""), str(payload.get("jobs_index_path") or "")]
            actions_lines = ["github-ops-job-poll", "github-ops-check"]
            next_lines = ["Devam et", "Durumu göster", "Duraklat"]

            print("PREVIEW:")
            print("\n".join(preview_lines))
            print("RESULT:")
            print("\n".join(result_lines))
            print("EVIDENCE:")
            print("\n".join(evidence_lines))
            print("ACTIONS:")
            print("\n".join(actions_lines))
            print("NEXT:")
            print("\n".join(next_lines))
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        status = payload.get("status") if isinstance(payload, dict) else "WARN"
        return 0 if status in {"OK", "WARN", "IDLE", "SKIP", "PASS", "RUNNING", "QUEUED"} else 2

    payload = poll_github_ops_jobs(workspace_root=ws, max_jobs=max_jobs)
    if chat and isinstance(payload, dict):
        polled = payload.get("polled_jobs") if isinstance(payload.get("polled_jobs"), list) else []
        job_ids = [str(p.get("job_id") or "") for p in polled if isinstance(p, dict)]
        preview_lines = [
            "PROGRAM-LED: github-ops-job-poll (multi)",
            f"workspace_root={ws}",
        ]
        result_lines = [
            f"polled_count={payload.get('polled_count')}",
            f"job_ids={','.join([j for j in job_ids if j]) if job_ids else 'none'}",
            f"status={payload.get('status')}",
        ]
        evidence_lines = [str(payload.get("jobs_index_path") or "")]
        actions_lines = ["github-ops-job-poll", "github-ops-check"]
        next_lines = ["Devam et", "Durumu göster", "Duraklat"]

        print("PREVIEW:")
        print("\n".join(preview_lines))
        print("RESULT:")
        print("\n".join(result_lines))
        print("EVIDENCE:")
        print("\n".join(evidence_lines))
        print("ACTIONS:")
        print("\n".join(actions_lines))
        print("NEXT:")
        print("\n".join(next_lines))

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    status = payload.get("status") if isinstance(payload, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_github_ops_override(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    mode = str(args.mode or "").strip()
    chat = parse_reaper_bool(str(args.chat))
    overrides_dir = ws / ".cache" / "policy_overrides"
    override_path = overrides_dir / "policy_github_ops.override.v1.json"
    backup_path: Path | None = None
    status = "OK"
    reason = ""

    if mode == "proof_cooldown_zero":
        if override_path.exists():
            ts = _now_compact()
            backup_path = override_path.parent / f"{override_path.name}.bak.{ts}"
            backup_path.write_text(override_path.read_text(encoding="utf-8"), encoding="utf-8")
        overrides_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": "v1",
            "network_enabled": False,
            "rate_limit": {"cooldown_seconds": 0},
            "job": {"cooldown_seconds": 0},
            "notes": ["PROGRAM_LED=true", "proof_nonce=v0.7.4", "cooldown_zero=true"],
        }
        override_path.write_text(_dump_json(payload), encoding="utf-8")
        reason = "OVERRIDE_WRITTEN"
    elif mode == "restore_backup":
        backups = sorted(override_path.parent.glob(f"{override_path.name}.bak.*"))
        if backups:
            backup_path = backups[-1]
            override_path.write_text(backup_path.read_text(encoding="utf-8"), encoding="utf-8")
            reason = "BACKUP_RESTORED"
        else:
            if override_path.exists():
                override_path.unlink()
                reason = "OVERRIDE_REMOVED_NO_BACKUP"
            else:
                status = "IDLE"
                reason = "NO_BACKUP"
    else:
        warn("FAIL error=INVALID_MODE")
        return 2

    report_path = ws / ".cache" / "reports" / "github_ops_override.v1.json"
    report_payload = {
        "status": status,
        "mode": mode,
        "override_path": str(Path(".cache") / "policy_overrides" / "policy_github_ops.override.v1.json"),
        "backup_path": str(backup_path.relative_to(ws)) if isinstance(backup_path, Path) else None,
        "reason": reason,
        "notes": ["PROGRAM_LED=true"],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_dump_json(report_payload), encoding="utf-8")

    if chat:
        print("PREVIEW:")
        print("PROGRAM-LED: github-ops-override (workspace-only)")
        print(f"workspace_root={ws}")
        print("RESULT:")
        print(f"status={status} mode={mode} reason={reason}")
        print("EVIDENCE:")
        print(str(report_payload.get("override_path")))
        if report_payload.get("backup_path"):
            print(str(report_payload.get("backup_path")))
        print(str(Path(".cache") / "reports" / "github_ops_override.v1.json"))
        print("ACTIONS:")
        print("github-ops-job-start")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(report_payload, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_github_ops_proof(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    kind = str(args.kind or "").strip()
    if not kind:
        warn("FAIL error=KIND_REQUIRED")
        return 2

    expects = [str(x) for x in (args.expect or []) if isinstance(x, str)]
    expects = sorted({x for x in expects if x})
    chat = parse_reaper_bool(str(args.chat))

    jobs_index_path = ws / ".cache" / "github_ops" / "jobs_index.v1.json"
    jobs: list[dict[str, Any]] = []
    if jobs_index_path.exists():
        try:
            idx = _load_json(jobs_index_path)
        except Exception:
            idx = {}
        jobs = idx.get("jobs") if isinstance(idx, dict) and isinstance(idx.get("jobs"), list) else []

    def _parse_ts(raw: str) -> datetime:
        try:
            if raw.endswith("Z"):
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return datetime.fromisoformat(raw)
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)

    kind_jobs = [j for j in jobs if isinstance(j, dict) and str(j.get("kind") or "") == kind]
    kind_jobs.sort(
        key=lambda j: (_parse_ts(str(j.get("updated_at") or "")), str(j.get("job_id") or "")),
        reverse=True,
    )
    job = kind_jobs[0] if kind_jobs else {}
    job_id = str(job.get("job_id") or "")
    job_status = str(job.get("status") or "")
    job_report_path = ""
    evidence_paths = {str(Path(".cache") / "github_ops" / "jobs_index.v1.json")}
    if isinstance(job.get("evidence_paths"), list) and job.get("evidence_paths"):
        job_report_path = str(job.get("evidence_paths")[0])
        if job_report_path:
            evidence_paths.add(job_report_path)

    baseline_path = ws / ".cache" / "reports" / "v0_7_3_network_live_pr_proof_closeout.v1.json"
    baseline_job_id = ""
    if baseline_path.exists():
        try:
            baseline = _load_json(baseline_path)
        except Exception:
            baseline = {}
        if isinstance(baseline, dict):
            gh = baseline.get("github_pr") if isinstance(baseline.get("github_pr"), dict) else {}
            baseline_job_id = str(gh.get("job_id") or "")
    if baseline_path.exists():
        evidence_paths.add(str(Path(".cache") / "reports" / baseline_path.name))

    dry_run = job.get("dry_run")
    live_gate = job.get("live_gate")
    network_used = bool(job_status not in {"SKIP", "IDLE"} and dry_run is False and live_gate is not False)

    failures: list[str] = []
    for expect in expects:
        if expect == "fresh_job_id":
            if not job_id or (baseline_job_id and job_id == baseline_job_id):
                failures.append("fresh_job_id")
        elif expect.startswith("network_used="):
            desired = expect.split("=", 1)[-1].strip().lower()
            desired_val = desired in {"1", "true", "yes", "on"}
            if bool(network_used) != desired_val:
                failures.append(f"network_used={desired}")
        elif expect.startswith("status="):
            desired_status = expect.split("=", 1)[-1].strip().upper()
            if job_status != desired_status:
                failures.append(f"status={desired_status}")

    status = "OK" if not failures else "WARN"
    report_payload = {
        "status": status,
        "kind": kind,
        "job_id": job_id,
        "job_status": job_status,
        "baseline_job_id": baseline_job_id,
        "network_used": bool(network_used),
        "expectations": expects,
        "failed_expectations": sorted(failures),
        "job_report_path": job_report_path,
        "evidence_paths": sorted(evidence_paths),
    }
    report_path = ws / ".cache" / "reports" / "github_ops_proof.v1.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_dump_json(report_payload), encoding="utf-8")

    if chat:
        print("PREVIEW:")
        print("PROGRAM-LED: github-ops-proof (workspace-only)")
        print(f"workspace_root={ws}")
        print("RESULT:")
        print(f"status={status} kind={kind} job_id={job_id}")
        if failures:
            print(f"failed={','.join(sorted(failures))}")
        print("EVIDENCE:")
        print(str(Path(".cache") / "reports" / "github_ops_proof.v1.json"))
        print("ACTIONS:")
        print("github-ops-job-start")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(report_payload, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def register_extension_subcommands(parent: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    ap_ext = parent.add_parser("extension-registry", help="Build extension registry (workspace, program-led).")
    ap_ext.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_ext.add_argument("--mode", default="report", help="report|strict (default: report).")
    ap_ext.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_ext.set_defaults(func=cmd_extension_registry)

    ap_help = parent.add_parser("extension-help", help="Summarize extensions for humans + AI (program-led).")
    ap_help.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_help.add_argument("--detail", default="false", help="true|false (default: false).")
    ap_help.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_help.set_defaults(func=cmd_extension_help)

    ap_run = parent.add_parser("extension-run", help="Run extension in isolated workspace (program-led).")
    ap_run.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_run.add_argument("--extension-id", required=True, help="Extension id.")
    ap_run.add_argument("--mode", default="report", help="report|strict (default: report).")
    ap_run.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_run.set_defaults(func=cmd_extension_run)

    ap_run_bulk = parent.add_parser(
        "extension-run-bulk-diff",
        help="Run report/strict for ops_single_gate extensions and write diff matrix + CHG drafts.",
    )
    ap_run_bulk.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_run_bulk.add_argument(
        "--extension-ids",
        default="",
        help="Optional comma-separated extension ids filter (default: all ops_single_gate extensions).",
    )
    ap_run_bulk.add_argument("--emit-chg", default="true", help="true|false (default: true).")
    ap_run_bulk.add_argument("--chat", default="true", help="true|false (default: true).")
    ap_run_bulk.set_defaults(func=cmd_extension_run_bulk_diff)

    ap_airunner_status = parent.add_parser("airunner-status", help="Airunner status (program-led).")
    ap_airunner_status.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_airunner_status.set_defaults(func=cmd_airunner_status)

    ap_airunner_lock_status = parent.add_parser("airunner-lock-status", help="Airunner lock status (program-led).")
    ap_airunner_lock_status.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_airunner_lock_status.set_defaults(func=cmd_airunner_lock_status)

    ap_airunner_lock_clear = parent.add_parser("airunner-lock-clear-stale", help="Clear stale airunner lock (program-led).")
    ap_airunner_lock_clear.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_airunner_lock_clear.add_argument("--max-age-seconds", required=True, help="Max heartbeat age in seconds.")
    ap_airunner_lock_clear.set_defaults(func=cmd_airunner_lock_clear_stale)

    ap_airunner_baseline = parent.add_parser("airunner-baseline", help="Airunner baseline snapshot (program-led).")
    ap_airunner_baseline.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_airunner_baseline.set_defaults(func=cmd_airunner_baseline)

    ap_airunner_proof = parent.add_parser("airunner-proof-bundle", help="Build airrunner proof bundle (program-led).")
    ap_airunner_proof.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_airunner_proof.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_airunner_proof.set_defaults(func=cmd_airunner_proof_bundle)

    ap_airunner_run = parent.add_parser("airunner-run", help="Airunner tick (program-led).")
    ap_airunner_run.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_airunner_run.add_argument("--ticks", default="2", help="Number of ticks (default: 2).")
    ap_airunner_run.add_argument("--mode", default="no_wait", help="no_wait (default: no_wait).")
    ap_airunner_run.add_argument("--budget-seconds", default="0", help="Budget seconds (default: 0=disabled).")
    ap_airunner_run.add_argument("--budget_seconds", dest="budget_seconds", default="0", help="Alias for --budget-seconds.")
    ap_airunner_run.add_argument(
        "--force-active-hours",
        default="false",
        help="true|false (default: false). Bypass active-hours gate for manual proof.",
    )
    ap_airunner_run.set_defaults(func=cmd_airunner_run)

    ap_airunner_active_hours = parent.add_parser(
        "airrunner-active-hours-set",
        help="Set airrunner active hours (start optional, end required) and persist override.",
    )
    ap_airunner_active_hours.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_airunner_active_hours.add_argument("--end", required=True, help="End time HH:MM (same-day).")
    ap_airunner_active_hours.add_argument("--start", default="", help="Optional start time HH:MM (default: now).")
    ap_airunner_active_hours.add_argument("--tz", default="Europe/Istanbul", help="Timezone (default: Europe/Istanbul).")
    ap_airunner_active_hours.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_airunner_active_hours.set_defaults(func=cmd_airunner_active_hours_set)

    ap_auto_run_start = parent.add_parser("airunner-auto-run-start", help="Start auto-run job (program-led).")
    ap_auto_run_start.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_auto_run_start.add_argument("--stop-at", default="", help="Stop at local time HH:MM (default: policy).")
    ap_auto_run_start.add_argument("--timezone", default="", help="Timezone (default: UTC).")
    ap_auto_run_start.add_argument("--mode", default="", help="Mode (default: policy auto_decision_mode).")
    ap_auto_run_start.add_argument("--job-kind", default="", help="Optional job kind (proof hint).")
    ap_auto_run_start.add_argument("--dry-run", default="false", help="true|false (default: false).")
    ap_auto_run_start.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_auto_run_start.set_defaults(func=cmd_airunner_auto_run_start)

    ap_auto_run_poll = parent.add_parser("airunner-auto-run-poll", help="Poll auto-run job (program-led).")
    ap_auto_run_poll.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_auto_run_poll.add_argument("--job-id", default="", help="Job id (optional).")
    ap_auto_run_poll.add_argument("--max", default="1", help="Max polls per call (default: 1).")
    ap_auto_run_poll.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_auto_run_poll.set_defaults(func=cmd_airunner_auto_run_poll)

    ap_auto_run_check = parent.add_parser("airunner-auto-run-check", help="Auto-run status (program-led).")
    ap_auto_run_check.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_auto_run_check.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_auto_run_check.set_defaults(func=cmd_airunner_auto_run_check)

    ap_airunner_seed = parent.add_parser("airunner-jobs-seed", help="Seed airunner jobs (workspace-only).")
    ap_airunner_seed.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_airunner_seed.add_argument("--kind", required=True, help="Job kind (SMOKE_FULL etc.).")
    ap_airunner_seed.add_argument("--state", default="queued", help="queued|running (default: queued).")
    ap_airunner_seed.add_argument("--count", default="1", help="Number of jobs to seed (default: 1).")
    ap_airunner_seed.set_defaults(func=cmd_airunner_jobs_seed)

    ap_airunner_tick = parent.add_parser("airunner-tick", help="Airunner tick (program-led, chat-aware).")
    ap_airunner_tick.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_airunner_tick.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_airunner_tick.set_defaults(func=cmd_airunner_tick)

    ap_airunner_watchdog = parent.add_parser("airunner-watchdog", help="Airunner watchdog (program-led).")
    ap_airunner_watchdog.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_airunner_watchdog.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_airunner_watchdog.set_defaults(func=cmd_airunner_watchdog)

    ap_planner_build = parent.add_parser("planner-build-plan", help="Build planner plan (program-led, local).")
    ap_planner_build.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_planner_build.add_argument("--mode", default="plan_first", help="Plan mode (default: plan_first).")
    ap_planner_build.add_argument("--out", default="latest", help="latest|<plan_id> (default: latest).")
    ap_planner_build.set_defaults(func=cmd_planner_build_plan)

    ap_planner_show = parent.add_parser("planner-show-plan", help="Show planner plan (program-led, local).")
    ap_planner_show.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_planner_show.add_argument("--plan-id", dest="plan_id", default="", help="Optional plan id.")
    ap_planner_show.add_argument("--latest", default="true", help="true|false (default: true).")
    ap_planner_show.add_argument("--chat", default="true", help="true|false (default: true).")
    ap_planner_show.set_defaults(func=cmd_planner_show_plan)

    ap_planner_apply = parent.add_parser(
        "planner-apply-selection",
        help="Apply selected intake ids from planner plan (workspace-only).",
    )
    ap_planner_apply.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_planner_apply.add_argument("--plan-id", dest="plan_id", default="", help="Optional plan id.")
    ap_planner_apply.add_argument("--latest", default="true", help="true|false (default: true).")
    ap_planner_apply.set_defaults(func=cmd_planner_apply_selection)

    ap_plan = parent.add_parser("release-plan", help="Build release plan (workspace, program-led).")
    ap_plan.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_plan.add_argument("--channel", default="", help="rc|final (default: policy default).")
    ap_plan.add_argument("--detail", default="false", help="true|false (default: false).")
    ap_plan.set_defaults(func=cmd_release_plan)

    ap_prepare = parent.add_parser("release-prepare", help="Prepare release manifest + notes (workspace).")
    ap_prepare.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_prepare.add_argument("--channel", default="", help="rc|final (default: plan channel).")
    ap_prepare.set_defaults(func=cmd_release_prepare)

    ap_publish = parent.add_parser(
        "release-publish",
        help="Publish release (policy-gated; network/trust on by default for this command).",
    )
    ap_publish.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_publish.add_argument("--channel", default="", help="rc|final (default: plan channel).")
    ap_publish.add_argument(
        "--allow-network",
        default="true",
        help="true|false (default: true). Policy gate still applies.",
    )
    ap_publish.add_argument(
        "--trusted-context",
        default="true",
        help="true|false (default: true). Policy gate still applies.",
    )
    ap_publish.set_defaults(func=cmd_release_publish)

    ap_check = parent.add_parser("release-check", help="Single gate: release plan + system + portfolio.")
    ap_check.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_check.add_argument("--channel", default="", help="rc|final (default: policy default).")
    ap_check.add_argument("--chat", default="true", help="true|false (default: true).")
    ap_check.set_defaults(func=cmd_release_check)

    ap_release_final_e2e = parent.add_parser(
        "release-final-e2e",
        help="One-button: PR open -> merge -> publish FINAL release (policy-gated, program-led).",
    )
    ap_release_final_e2e.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_release_final_e2e.add_argument("--base-branch", default="main", help="Base branch (default: main).")
    ap_release_final_e2e.add_argument(
        "--allow-network",
        default="true",
        help="true|false (default: true). Policy gate still applies.",
    )
    ap_release_final_e2e.add_argument("--dry-run", default="false", help="true|false (default: false).")
    ap_release_final_e2e.add_argument("--chat", default="true", help="true|false (default: true).")
    ap_release_final_e2e.set_defaults(func=cmd_release_final_e2e)

    ap_pr_merge_e2e = parent.add_parser(
        "pr-merge-e2e",
        help="One-button: PR open -> merge (no release) (policy-gated, program-led).",
    )
    ap_pr_merge_e2e.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_pr_merge_e2e.add_argument("--base-branch", default="main", help="Base branch (default: main).")
    ap_pr_merge_e2e.add_argument(
        "--allow-network",
        default="true",
        help="true|false (default: true). Policy gate still applies.",
    )
    ap_pr_merge_e2e.add_argument("--dry-run", default="false", help="true|false (default: false).")
    ap_pr_merge_e2e.add_argument("--chat", default="true", help="true|false (default: true).")
    ap_pr_merge_e2e.set_defaults(func=cmd_pr_merge_e2e)

    ap_deploy_check = parent.add_parser("deploy-check", help="Deploy check (program-led, local).")
    ap_deploy_check.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_deploy_check.add_argument("--chat", default="true", help="true|false (default: true).")
    ap_deploy_check.set_defaults(func=cmd_deploy_check)

    ap_search_check = parent.add_parser("search-check", help="Search adapter check + report (program-led, local).")
    ap_search_check.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_search_check.add_argument("--scope", default="ssot", help="ssot|repo (default: ssot).")
    ap_search_check.add_argument("--query", default="policy", help="Probe query (default: policy).")
    ap_search_check.add_argument("--mode", default="keyword", help="keyword|semantic|auto (default: keyword).")
    ap_search_check.add_argument("--chat", default="true", help="true|false (default: true).")
    ap_search_check.set_defaults(func=cmd_search_check)

    ap_deploy_start = parent.add_parser("deploy-job-start", help="Start deploy job (program-led).")
    ap_deploy_start.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_deploy_start.add_argument(
        "--kind",
        required=True,
        help="Job kind (DEPLOY_STATIC_FE|DEPLOY_SELFHOST_BE).",
    )
    ap_deploy_start.add_argument("--payload", required=True, help="Payload ref (path or id).")
    ap_deploy_start.add_argument("--mode", default="", help="dry_run|dry_run_only|live (default: policy).")
    ap_deploy_start.set_defaults(func=cmd_deploy_job_start)

    ap_deploy_poll = parent.add_parser("deploy-job-poll", help="Poll deploy job (program-led).")
    ap_deploy_poll.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_deploy_poll.add_argument("--job-id", required=True, help="Job id.")
    ap_deploy_poll.set_defaults(func=cmd_deploy_job_poll)

    ap_gh_check = parent.add_parser("github-ops-check", help="GitHub ops check (program-led, local).")
    ap_gh_check.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_gh_check.add_argument("--chat", default="true", help="true|false (default: true).")
    ap_gh_check.set_defaults(func=cmd_github_ops_check)

    ap_gh_start = parent.add_parser("github-ops-job-start", help="Start GitHub ops job (program-led).")
    ap_gh_start.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_gh_start.add_argument(
        "--kind",
        required=True,
        help="Job kind (pr_list|pr_open|pr_update|merge|deploy_trigger|status_poll|PR_OPEN|PR_POLL|CI_POLL|MERGE|RELEASE_RC|RELEASE_FINAL).",
    )
    ap_gh_start.add_argument("--dry-run", default="true", help="true|false (default: true).")
    ap_gh_start.set_defaults(func=cmd_github_ops_job_start)

    ap_gh_pr_open = parent.add_parser("github-ops-pr-open", help="Open PR (program-led, live-gated).")
    ap_gh_pr_open.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_gh_pr_open.add_argument("--repo-owner", default="", help="GitHub repo owner (optional).")
    ap_gh_pr_open.add_argument("--repo-name", default="", help="GitHub repo name (optional).")
    ap_gh_pr_open.add_argument("--base-branch", default="", help="Base branch (default: main).")
    ap_gh_pr_open.add_argument("--head-branch", default="", help="Head branch (default: current).")
    ap_gh_pr_open.add_argument("--title", default="", help="PR title (optional).")
    ap_gh_pr_open.add_argument("--body", default="", help="PR body (optional).")
    ap_gh_pr_open.add_argument("--draft", default="true", help="true|false (default: true).")
    ap_gh_pr_open.add_argument("--labels", default="", help="Comma-separated labels (optional).")
    ap_gh_pr_open.add_argument("--reviewers", default="", help="Comma-separated reviewers (optional).")
    ap_gh_pr_open.add_argument("--assignees", default="", help="Comma-separated assignees (optional).")
    ap_gh_pr_open.add_argument("--dry-run", default="false", help="true|false (default: false).")
    ap_gh_pr_open.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_gh_pr_open.set_defaults(func=cmd_github_ops_pr_open)

    ap_gh_poll = parent.add_parser("github-ops-job-poll", help="Poll GitHub ops job (program-led).")
    ap_gh_poll.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_gh_poll.add_argument("--job-id", default="", help="Job id (optional).")
    ap_gh_poll.add_argument("--max", default="1", help="Max jobs to poll when job-id missing (default: 1).")
    ap_gh_poll.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_gh_poll.set_defaults(func=cmd_github_ops_job_poll)

    ap_smoke_triage = parent.add_parser("smoke-full-triage", help="Smoke full triage (program-led).")
    ap_smoke_triage.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_smoke_triage.add_argument("--job-id", required=True, help="Job id.")
    ap_smoke_triage.add_argument("--detail", default="false", help="true|false (default: false).")
    ap_smoke_triage.add_argument("--chat", default="true", help="true|false (default: true).")
    ap_smoke_triage.set_defaults(func=cmd_smoke_full_triage)

    ap_smoke_fast_triage = parent.add_parser("smoke-fast-triage", help="Smoke fast triage (program-led).")
    ap_smoke_fast_triage.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_smoke_fast_triage.add_argument("--job-id", required=True, help="Job id.")
    ap_smoke_fast_triage.add_argument("--detail", default="false", help="true|false (default: false).")
    ap_smoke_fast_triage.add_argument("--chat", default="true", help="true|false (default: true).")
    ap_smoke_fast_triage.set_defaults(func=cmd_smoke_fast_triage)

    ap_gh_override = parent.add_parser("github-ops-override", help="Write/restore GitHub ops overrides (workspace-only).")
    ap_gh_override.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_gh_override.add_argument(
        "--mode",
        default="proof_cooldown_zero",
        help="proof_cooldown_zero|restore_backup (default: proof_cooldown_zero).",
    )
    ap_gh_override.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_gh_override.set_defaults(func=cmd_github_ops_override)

    ap_gh_proof = parent.add_parser("github-ops-proof", help="Verify GitHub ops proof expectations (program-led).")
    ap_gh_proof.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_gh_proof.add_argument("--kind", required=True, help="Job kind to verify (e.g., PR_OPEN).")
    ap_gh_proof.add_argument(
        "--expect",
        action="append",
        default=[],
        help="Expectation like fresh_job_id, network_used=false, status=SKIP.",
    )
    ap_gh_proof.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_gh_proof.set_defaults(func=cmd_github_ops_proof)
