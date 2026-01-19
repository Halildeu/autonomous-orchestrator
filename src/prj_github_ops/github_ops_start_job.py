from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def start_github_ops_job_impl(
    *,
    workspace_root: Path,
    kind: str,
    dry_run: bool,
    request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # Note: this implementation is intentionally isolated from src/prj_github_ops/github_ops.py
    # to keep that file within script budget constraints. It relies on stable helper functions
    # that are already part of the GitHub ops surface.
    from src.prj_github_ops.github_ops import (
        _allowed_actions,
        _apply_job_retention,
        _canonical_json,
        _clean_str,
        _cooldown_active,
        _ensure_job_trace_meta,
        _gate_details,
        _gate_error,
        _git_state,
        _hash_text,
        _job_signature,
        _job_time,
        _live_gate,
        _load_jobs_index,
        _load_last_pr_open_request,
        _load_policy,
        _load_json,
        _normalize_kind,
        _normalize_pr_open_request,
        _now_iso,
        _repo_root,
        _resolve_smoke_workspace_root,
        _save_jobs_index,
        _spawn_job_process,
        _write_job_report,
        _write_pr_open_request,
    )

    policy, policy_source, policy_hash, notes = _load_policy(workspace_root)
    live_gate = _live_gate(policy, workspace_root=workspace_root)
    gate_details = _gate_details(policy, workspace_root=workspace_root)
    git_state = _git_state(_repo_root())
    now = _now_iso()
    jobs_index, job_notes = _load_jobs_index(workspace_root)
    notes.extend(job_notes)
    jobs = jobs_index.get("jobs") if isinstance(jobs_index.get("jobs"), list) else []
    normalized_kind = _normalize_kind(kind, policy=policy)
    local_only = normalized_kind in {"SMOKE_FULL", "SMOKE_FAST"}
    allowed_actions = set(_allowed_actions(policy))
    allowed_ops = {
        str(x).strip().lower()
        for x in (policy.get("allowed_ops") if isinstance(policy.get("allowed_ops"), list) else [])
        if isinstance(x, str)
    }
    allowed_aliases = {
        "pr_list": "PR_LIST",
        "pr_open": "PR_OPEN",
        "pr_update": "PR_UPDATE",
        "merge": "MERGE",
        "deploy_trigger": "DEPLOY_TRIGGER",
        "status_poll": "STATUS_POLL",
    }
    allowed_kinds = allowed_actions | {allowed_aliases.get(op, op.upper()) for op in allowed_ops}
    if normalized_kind not in allowed_kinds:
        return {
            "status": "IDLE",
            "error_code": "KIND_NOT_ALLOWED",
            "job_id": "",
            "job_kind": normalized_kind,
            "cooldown_hit": False,
            "jobs_index_path": str(Path(".cache") / "github_ops" / "jobs_index.v1.json"),
            "policy_source": policy_source,
            "decision_needed": False,
            "decision_seed_path": None,
            "decision_inbox_path": None,
            "gate_state": {
                "network_enabled": bool(gate_details.get("network_enabled", False)),
                "live_enabled": bool(gate_details.get("live_enabled", False)),
                "env_flag_set": bool(gate_details.get("env_flag_set", False)),
                "env_key_present": bool(gate_details.get("env_key_present", False)),
            },
        }

    if normalized_kind in {"RELEASE_RC", "RELEASE_FINAL"} and not dry_run:
        ahead = int(git_state.get("ahead") or 0)
        behind = int(git_state.get("behind") or 0)
        if git_state.get("dirty_tree"):
            return {
                "status": "IDLE",
                "error_code": "DIRTY_TREE",
                "job_id": "",
                "job_kind": normalized_kind,
                "cooldown_hit": False,
                "jobs_index_path": str(Path(".cache") / "github_ops" / "jobs_index.v1.json"),
                "policy_source": policy_source,
                "decision_needed": False,
                "decision_seed_path": None,
                "decision_inbox_path": None,
                "gate_state": {
                    "network_enabled": bool(gate_details.get("network_enabled", False)),
                    "live_enabled": bool(gate_details.get("live_enabled", False)),
                    "env_flag_set": bool(gate_details.get("env_flag_set", False)),
                    "env_key_present": bool(gate_details.get("env_key_present", False)),
                },
            }
        if ahead > 0:
            return {
                "status": "IDLE",
                "error_code": "AHEAD_REMOTE",
                "job_id": "",
                "job_kind": normalized_kind,
                "cooldown_hit": False,
                "jobs_index_path": str(Path(".cache") / "github_ops" / "jobs_index.v1.json"),
                "policy_source": policy_source,
                "decision_needed": False,
                "decision_seed_path": None,
                "decision_inbox_path": None,
                "gate_state": {
                    "network_enabled": bool(gate_details.get("network_enabled", False)),
                    "live_enabled": bool(gate_details.get("live_enabled", False)),
                    "env_flag_set": bool(gate_details.get("env_flag_set", False)),
                    "env_key_present": bool(gate_details.get("env_key_present", False)),
                },
            }
        if behind > 0:
            return {
                "status": "IDLE",
                "error_code": "BEHIND_REMOTE",
                "job_id": "",
                "job_kind": normalized_kind,
                "cooldown_hit": False,
                "jobs_index_path": str(Path(".cache") / "github_ops" / "jobs_index.v1.json"),
                "policy_source": policy_source,
                "decision_needed": False,
                "decision_seed_path": None,
                "decision_inbox_path": None,
                "gate_state": {
                    "network_enabled": bool(gate_details.get("network_enabled", False)),
                    "live_enabled": bool(gate_details.get("live_enabled", False)),
                    "env_flag_set": bool(gate_details.get("env_flag_set", False)),
                    "env_key_present": bool(gate_details.get("env_key_present", False)),
                },
            }
        if git_state.get("index_lock"):
            return {
                "status": "IDLE",
                "error_code": "INDEX_LOCK",
                "job_id": "",
                "job_kind": normalized_kind,
                "cooldown_hit": False,
                "jobs_index_path": str(Path(".cache") / "github_ops" / "jobs_index.v1.json"),
                "policy_source": policy_source,
                "decision_needed": False,
                "decision_seed_path": None,
                "decision_inbox_path": None,
                "gate_state": {
                    "network_enabled": bool(gate_details.get("network_enabled", False)),
                    "live_enabled": bool(gate_details.get("live_enabled", False)),
                    "env_flag_set": bool(gate_details.get("env_flag_set", False)),
                    "env_key_present": bool(gate_details.get("env_key_present", False)),
                },
            }

    gate_error = _gate_error(policy, workspace_root=workspace_root)
    pr_request_payload: dict[str, Any] | None = None
    pr_request_missing: list[str] = []
    if normalized_kind == "PR_OPEN":
        pr_request_payload, pr_request_missing = _normalize_pr_open_request(request, repo_root=_repo_root())
        if pr_request_missing:
            last_request = _load_last_pr_open_request(workspace_root, jobs)
            if isinstance(last_request, dict):
                pr_request_payload, pr_request_missing = _normalize_pr_open_request(last_request, repo_root=_repo_root())

    decision_seed_path = ""
    decision_inbox_path = ""
    decision_needed = False
    if normalized_kind == "PR_OPEN" and not dry_run and gate_error and not local_only:
        decision_needed = True
        decision_inbox_path = str(Path(".cache") / "index" / "decision_inbox.v1.json")
        try:
            from src.ops.decision_inbox import run_decision_seed

            seed = run_decision_seed(
                workspace_root=workspace_root,
                decision_kind="NETWORK_LIVE_ENABLE",
                target="github_ops:PR_OPEN",
            )
            decision_seed_path = str(seed.get("seed_path") or "")
        except Exception:
            notes.append("decision_seed_failed")

    if not local_only:
        rate_cfg = policy.get("rate_limit") if isinstance(policy.get("rate_limit"), dict) else {}
        rate_cooldown = int(rate_cfg.get("cooldown_seconds", 0) or 0)
        max_per_tick = int(rate_cfg.get("max_per_tick", 0) or 0)
        if rate_cooldown and max_per_tick:
            now_dt = datetime.now(timezone.utc)
            recent_jobs = [j for j in jobs if now_dt - _job_time(j) <= timedelta(seconds=rate_cooldown)]
            if len(recent_jobs) >= max_per_tick:
                return {
                    "status": "IDLE",
                    "error_code": "RATE_LIMIT",
                    "job_id": "",
                    "job_kind": normalized_kind,
                    "cooldown_hit": True,
                    "jobs_index_path": str(Path(".cache") / "github_ops" / "jobs_index.v1.json"),
                    "policy_source": policy_source,
                    "decision_needed": bool(decision_needed),
                    "decision_seed_path": decision_seed_path or None,
                    "decision_inbox_path": decision_inbox_path or None,
                    "request_missing": pr_request_missing if pr_request_missing else None,
                    "gate_state": {
                        "network_enabled": bool(gate_details.get("network_enabled", False)),
                        "live_enabled": bool(gate_details.get("live_enabled", False)),
                        "env_flag_set": bool(gate_details.get("env_flag_set", False)),
                        "env_key_present": bool(gate_details.get("env_key_present", False)),
                    },
                }

    if not local_only:
        cooldown_seconds = int(
            (policy.get("job") or {}).get("cooldown_seconds", 0) if isinstance(policy.get("job"), dict) else 0
        )
        cooldown_hit, recent_id = _cooldown_active(jobs, kind=normalized_kind, cooldown_seconds=cooldown_seconds)
        if cooldown_hit:
            return {
                "status": "IDLE",
                "error_code": "COOLDOWN_ACTIVE",
                "job_id": recent_id,
                "job_kind": normalized_kind,
                "cooldown_hit": True,
                "jobs_index_path": str(Path(".cache") / "github_ops" / "jobs_index.v1.json"),
                "policy_source": policy_source,
                "decision_needed": bool(decision_needed),
                "decision_seed_path": decision_seed_path or None,
                "decision_inbox_path": decision_inbox_path or None,
                "request_missing": pr_request_missing if pr_request_missing else None,
                "gate_state": {
                    "network_enabled": bool(gate_details.get("network_enabled", False)),
                    "live_enabled": bool(gate_details.get("live_enabled", False)),
                    "env_flag_set": bool(gate_details.get("env_flag_set", False)),
                    "env_key_present": bool(gate_details.get("env_key_present", False)),
                },
            }

    for job in jobs:
        if str(job.get("kind") or "") == normalized_kind and str(job.get("status") or "") in {"QUEUED", "RUNNING"}:
            return {
                "status": "IDLE",
                "error_code": "JOB_ALREADY_RUNNING",
                "job_id": str(job.get("job_id") or ""),
                "job_kind": normalized_kind,
                "cooldown_hit": False,
                "jobs_index_path": str(Path(".cache") / "github_ops" / "jobs_index.v1.json"),
                "policy_source": policy_source,
                "decision_needed": bool(decision_needed),
                "decision_seed_path": decision_seed_path or None,
                "decision_inbox_path": decision_inbox_path or None,
                "request_missing": pr_request_missing if pr_request_missing else None,
                "gate_state": {
                    "network_enabled": bool(gate_details.get("network_enabled", False)),
                    "live_enabled": bool(gate_details.get("live_enabled", False)),
                    "env_flag_set": bool(gate_details.get("env_flag_set", False)),
                    "env_key_present": bool(gate_details.get("env_key_present", False)),
                },
            }

    job_id_payload: dict[str, Any] = {"kind": normalized_kind, "policy_hash": policy_hash, "dry_run": dry_run}
    if normalized_kind in {"RELEASE_RC", "RELEASE_FINAL"} and not dry_run:
        manifest_path = workspace_root / ".cache" / "reports" / "release_manifest.v1.json"
        try:
            manifest = _load_json(manifest_path) if manifest_path.exists() else None
        except Exception:
            manifest = None
        if isinstance(manifest, dict):
            release_version = manifest.get("release_version")
            if isinstance(release_version, str) and release_version.strip():
                job_id_payload["release_version"] = release_version.strip()
            channel = manifest.get("channel")
            if isinstance(channel, str) and channel.strip():
                job_id_payload["channel"] = channel.strip()

    job_id = _hash_text(_canonical_json(job_id_payload))
    status = "RUNNING"
    skip_reason = ""
    error_code = ""
    return_status = "RUNNING"
    pid: int | None = None
    result_paths: list[str] = []
    if dry_run:
        status = "SKIP"
        skip_reason = "DRY_RUN"
        error_code = "DRY_RUN"
        return_status = "SKIP"
    elif not live_gate.get("enabled", False) and not local_only:
        status = "SKIP"
        skip_reason = gate_error or "LIVE_GATE_DISABLED"
        if skip_reason == "NETWORK_DISABLED":
            skip_reason = "NO_NETWORK"
        error_code = gate_error or "LIVE_GATE_DISABLED"
        return_status = "IDLE"
        if normalized_kind == "PR_OPEN" and gate_error:
            decision_needed = True
    else:
        if normalized_kind == "PR_OPEN" and pr_request_missing and not local_only:
            return {
                "status": "IDLE",
                "error_code": "PR_OPEN_MISSING_INPUTS",
                "job_id": "",
                "job_kind": normalized_kind,
                "cooldown_hit": False,
                "jobs_index_path": str(Path(".cache") / "github_ops" / "jobs_index.v1.json"),
                "policy_source": policy_source,
                "decision_needed": bool(decision_needed),
                "decision_seed_path": decision_seed_path or None,
                "decision_inbox_path": decision_inbox_path or None,
                "request_missing": pr_request_missing,
                "gate_state": {
                    "network_enabled": bool(gate_details.get("network_enabled", False)),
                    "live_enabled": bool(gate_details.get("live_enabled", False)),
                    "env_flag_set": bool(gate_details.get("env_flag_set", False)),
                    "env_key_present": bool(gate_details.get("env_key_present", False)),
                },
            }
        request_path = None
        request_rel = ""
        if normalized_kind == "PR_OPEN" and pr_request_payload and not local_only:
            request_path, request_rel = _write_pr_open_request(workspace_root, job_id, pr_request_payload)
        auth_cfg = policy.get("auth") if isinstance(policy.get("auth"), dict) else {}
        auth_mode = _clean_str(auth_cfg.get("mode") or "bearer") or "bearer"
        token_env = _clean_str(auth_cfg.get("token_env") or "GITHUB_TOKEN") or "GITHUB_TOKEN"
        command_fingerprint = _hash_text(_canonical_json({"kind": normalized_kind, "policy_hash": policy_hash}))
        pid, result_paths = _spawn_job_process(
            workspace_root,
            job_id,
            command_fingerprint=command_fingerprint,
            kind=normalized_kind,
            request_path=request_path,
            auth_mode=auth_mode,
            token_env=token_env,
        )
        if request_rel:
            result_paths.append(request_rel)
        if pid is None:
            status = "FAIL"
            error_code = "SPAWN_FAILED"
            return_status = "WARN"
        else:
            status = "RUNNING"

    job_workspace_root = workspace_root
    if normalized_kind == "SMOKE_FULL":
        job_workspace_root = _resolve_smoke_workspace_root()
    job = {
        "version": "v1",
        "job_id": job_id,
        "kind": normalized_kind,
        "status": status,
        "created_at": now,
        "updated_at": now,
        "workspace_root": str(job_workspace_root),
        "dry_run": bool(dry_run),
        "live_gate": bool(live_gate.get("enabled", False)),
        "attempts": 1 if status in {"RUNNING", "PASS", "FAIL"} else 0,
        "error_code": error_code,
        "skip_reason": skip_reason,
        "notes": notes,
        "evidence_paths": [],
        "result_paths": result_paths,
    }
    if pid is not None:
        job["pid"] = pid
        job["started_at"] = now
    if status == "PASS":
        job["failure_class"] = "PASS"
    elif status == "FAIL" and error_code:
        job["failure_class"] = "OTHER"
    elif status == "TIMEOUT":
        job["failure_class"] = "TIMEOUT"
    _ensure_job_trace_meta(job, workspace_root=workspace_root, policy_hash=policy_hash)
    job["signature_hash"] = _job_signature(job)
    job_report = _write_job_report(workspace_root, job)
    job["evidence_paths"].append(job_report)
    jobs = [j for j in jobs if str(j.get("job_id") or "") != job_id]
    jobs.append(job)
    jobs_index["jobs"] = _apply_job_retention(jobs, policy=policy)
    jobs_index_path = _save_jobs_index(workspace_root, jobs_index)
    return {
        "status": return_status,
        "job_id": job_id,
        "job_kind": normalized_kind,
        "job_report_path": job_report,
        "jobs_index_path": jobs_index_path,
        "policy_source": policy_source,
        "error_code": error_code or None,
        "cooldown_hit": False,
        "decision_needed": bool(decision_needed),
        "decision_seed_path": decision_seed_path or None,
        "decision_inbox_path": decision_inbox_path or None,
        "gate_state": {
            "network_enabled": bool(gate_details.get("network_enabled", False)),
            "live_enabled": bool(gate_details.get("live_enabled", False)),
            "env_flag_set": bool(gate_details.get("env_flag_set", False)),
            "env_key_present": bool(gate_details.get("env_key_present", False)),
        },
    }

