from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged.get(key, {}), value)
        else:
            merged[key] = value
    return merged


def _policy_defaults() -> dict[str, Any]:
    return {
        "version": "v1",
        "network_enabled": False,
        "allowed_kinds": ["DEPLOY_STATIC_FE", "DEPLOY_SELFHOST_BE"],
        "mode": "dry_run_only",
        "job_store": {
            "jobs_index_path": ".cache/deploy/jobs_index.v1.json",
            "keep_last_n": 50,
            "ttl_seconds": 604800,
            "poll_interval_seconds": 300,
            "cooldown_seconds": 0,
        },
        "retry_count": 0,
        "notes": ["network_default_off", "dry_run_only"],
    }


def _load_policy(workspace_root: Path) -> tuple[dict[str, Any], str, str, list[str]]:
    notes: list[str] = []
    policy = _policy_defaults()
    policy_source = "core"

    core_path = _repo_root() / "policies" / "policy_deploy.v1.json"
    ws_path = workspace_root / "policies" / "policy_deploy.v1.json"
    override_path = workspace_root / ".cache" / "policy_overrides" / "policy_deploy.override.v1.json"

    for path, source_label in [(core_path, "core"), (ws_path, "workspace"), (override_path, "workspace_override")]:
        if not path.exists():
            continue
        try:
            obj = _load_json(path)
        except Exception:
            notes.append(f"policy_invalid:{source_label}")
            continue
        if isinstance(obj, dict):
            policy = _deep_merge(policy, obj)
            if source_label != "core":
                policy_source = "core+workspace_override"

    policy_hash = _hash_text(_canonical_json(policy))
    return policy, policy_source, policy_hash, notes


def _job_time(job: dict[str, Any]) -> datetime:
    for key in ("updated_at", "last_poll_at", "started_at", "created_at"):
        ts = _parse_iso(str(job.get(key) or ""))
        if ts:
            return ts
    return datetime.fromtimestamp(0, tz=timezone.utc)


def _jobs_index_rel(workspace_root: Path, policy: dict[str, Any]) -> str:
    job_store = policy.get("job_store") if isinstance(policy.get("job_store"), dict) else {}
    raw = str(job_store.get("jobs_index_path") or ".cache/deploy/jobs_index.v1.json")
    path = Path(raw)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(workspace_root.resolve()).as_posix()
        except Exception:
            return path.as_posix()
    return path.as_posix()


def _jobs_index_path(workspace_root: Path, policy: dict[str, Any]) -> Path:
    rel = _jobs_index_rel(workspace_root, policy)
    path = Path(rel)
    if path.is_absolute():
        return path
    return (workspace_root / path).resolve()


def _default_jobs_index(workspace_root: Path) -> dict[str, Any]:
    return {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "status": "IDLE",
        "jobs": [],
        "counts": {"total": 0, "queued": 0, "running": 0, "pass": 0, "fail": 0, "timeout": 0, "killed": 0, "skip": 0},
        "notes": [],
    }


def _load_jobs_index(workspace_root: Path, policy: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    path = _jobs_index_path(workspace_root, policy)
    if not path.exists():
        return _default_jobs_index(workspace_root), ["jobs_index_missing"]
    try:
        obj = _load_json(path)
    except Exception:
        return _default_jobs_index(workspace_root), ["jobs_index_invalid"]
    if not isinstance(obj, dict):
        return _default_jobs_index(workspace_root), ["jobs_index_invalid"]
    if not isinstance(obj.get("jobs"), list):
        obj["jobs"] = []
    return obj, []


def _apply_job_retention(jobs: list[dict[str, Any]], policy: dict[str, Any]) -> list[dict[str, Any]]:
    job_store = policy.get("job_store") if isinstance(policy.get("job_store"), dict) else {}
    keep_last_n = int(job_store.get("keep_last_n", 0) or 0)
    jobs = [j for j in jobs if isinstance(j, dict)]
    jobs.sort(key=lambda j: (_job_time(j), str(j.get("job_id") or "")))
    if keep_last_n and len(jobs) > keep_last_n:
        jobs = jobs[-keep_last_n:]
    return jobs


def _save_jobs_index(workspace_root: Path, policy: dict[str, Any], index: dict[str, Any]) -> str:
    jobs = index.get("jobs") if isinstance(index.get("jobs"), list) else []
    jobs = [j for j in jobs if isinstance(j, dict)]
    jobs.sort(key=lambda j: (str(j.get("created_at") or ""), str(j.get("job_id") or "")))

    counts = {"total": 0, "queued": 0, "running": 0, "pass": 0, "fail": 0, "timeout": 0, "killed": 0, "skip": 0}
    for job in jobs:
        status = str(job.get("status") or "").upper()
        counts["total"] += 1
        if status == "QUEUED":
            counts["queued"] += 1
        elif status == "RUNNING":
            counts["running"] += 1
        elif status == "PASS":
            counts["pass"] += 1
        elif status == "FAIL":
            counts["fail"] += 1
        elif status == "TIMEOUT":
            counts["timeout"] += 1
        elif status == "KILLED":
            counts["killed"] += 1
        elif status == "SKIP":
            counts["skip"] += 1

    index["jobs"] = jobs
    index["counts"] = counts
    status = "IDLE"
    if counts["total"] > 0:
        status = "OK"
    if counts["fail"] > 0 or counts["timeout"] > 0 or counts["killed"] > 0:
        status = "WARN"
    elif counts["running"] > 0 or counts["queued"] > 0:
        status = "WARN"
    index["status"] = status
    index["generated_at"] = _now_iso()
    index.setdefault("version", "v1")
    index.setdefault("workspace_root", str(workspace_root))

    path = _jobs_index_path(workspace_root, policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_json(index), encoding="utf-8")
    return _jobs_index_rel(workspace_root, policy)


def _job_report_path(workspace_root: Path, job_id: str) -> Path:
    return workspace_root / ".cache" / "reports" / "deploy_jobs" / f"deploy_job_{job_id}.v1.json"


def _write_job_report(workspace_root: Path, job: dict[str, Any]) -> str:
    path = _job_report_path(workspace_root, str(job.get("job_id") or "unknown"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_json(job), encoding="utf-8")
    return (Path(".cache") / "reports" / "deploy_jobs" / path.name).as_posix()


def _job_signature(kind: str, payload_hash: str, policy_hash: str, mode: str) -> str:
    return _hash_text(
        _canonical_json({"kind": kind, "payload_hash": payload_hash, "policy_hash": policy_hash, "mode": mode})
    )


def _normalize_kind(kind: str, policy: dict[str, Any]) -> str:
    raw = str(kind or "").strip().upper()
    allowed = policy.get("allowed_kinds") if isinstance(policy.get("allowed_kinds"), list) else []
    allowed = [str(x).strip().upper() for x in allowed if isinstance(x, str) and x.strip()]
    if allowed and raw in allowed:
        return raw
    return raw


def _normalize_mode(mode: str) -> str:
    raw = str(mode or "").strip().lower()
    if raw in {"dry_run", "dry_run_only"}:
        return "dry_run_only"
    if raw in {"live"}:
        return "live"
    return ""


def build_deploy_report(*, workspace_root: Path) -> dict[str, Any]:
    policy, policy_source, policy_hash, notes = _load_policy(workspace_root)
    index, job_notes = _load_jobs_index(workspace_root, policy)
    notes.extend(job_notes)

    jobs = index.get("jobs") if isinstance(index.get("jobs"), list) else []
    counts = index.get("counts") if isinstance(index.get("counts"), dict) else {}
    counts = {
        "total": int(counts.get("total", 0) or 0),
        "queued": int(counts.get("queued", 0) or 0),
        "running": int(counts.get("running", 0) or 0),
        "pass": int(counts.get("pass", 0) or 0),
        "fail": int(counts.get("fail", 0) or 0),
        "timeout": int(counts.get("timeout", 0) or 0),
        "killed": int(counts.get("killed", 0) or 0),
        "skip": int(counts.get("skip", 0) or 0),
    }

    status = "IDLE"
    if counts["total"] > 0:
        status = "OK"
    if counts["fail"] > 0 or counts["timeout"] > 0 or counts["killed"] > 0:
        status = "WARN"

    last_job: dict[str, Any] | None = None
    if jobs:
        jobs_sorted = sorted([j for j in jobs if isinstance(j, dict)], key=lambda j: (_job_time(j), str(j.get("job_id") or "")))
        if jobs_sorted:
            last = jobs_sorted[-1]
            last_job_id = str(last.get("job_id") or "")
            evidence_paths = last.get("evidence_paths") if isinstance(last.get("evidence_paths"), list) else []
            job_report_path = ""
            if evidence_paths:
                first_path = evidence_paths[0]
                if isinstance(first_path, str) and first_path:
                    job_report_path = first_path
            if not job_report_path and last_job_id:
                job_report_path = (Path(".cache") / "reports" / "deploy_jobs" / f"deploy_job_{last_job_id}.v1.json").as_posix()
            last_job = {
                "job_id": last_job_id,
                "kind": str(last.get("kind") or ""),
                "status": str(last.get("status") or ""),
                "job_report_path": job_report_path,
                "skip_reason": str(last.get("skip_reason") or ""),
                "error_code": str(last.get("error_code") or ""),
                "updated_at": str(last.get("updated_at") or ""),
            }

    report = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "status": status,
        "policy_source": policy_source,
        "policy_hash": policy_hash,
        "network_enabled": bool(policy.get("network_enabled", False)),
        "mode": str(policy.get("mode") or ""),
        "allowed_kinds": sorted({str(x) for x in policy.get("allowed_kinds", []) if isinstance(x, str) and x.strip()}),
        "jobs_summary": {
            "total": counts["total"],
            "by_status": {
                "QUEUED": counts["queued"],
                "RUNNING": counts["running"],
                "PASS": counts["pass"],
                "FAIL": counts["fail"],
                "TIMEOUT": counts["timeout"],
                "KILLED": counts["killed"],
                "SKIP": counts["skip"],
            },
        },
        "jobs_index_path": _jobs_index_rel(workspace_root, policy),
        "notes": notes,
    }
    if last_job is not None:
        report["last_job"] = last_job

    report_path = workspace_root / ".cache" / "reports" / "deploy_report.v1.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_dump_json(report), encoding="utf-8")
    return report


def deploy_job_start(
    *,
    workspace_root: Path,
    kind: str,
    payload_ref: str,
    mode_override: str | None = None,
) -> dict[str, Any]:
    policy, policy_source, policy_hash, notes = _load_policy(workspace_root)
    now = _now_iso()

    jobs_index, job_notes = _load_jobs_index(workspace_root, policy)
    notes.extend(job_notes)
    jobs = jobs_index.get("jobs") if isinstance(jobs_index.get("jobs"), list) else []

    normalized_kind = _normalize_kind(kind, policy)
    allowed = policy.get("allowed_kinds") if isinstance(policy.get("allowed_kinds"), list) else []
    allowed = {str(x).strip().upper() for x in allowed if isinstance(x, str) and x.strip()}
    if allowed and normalized_kind not in allowed:
        return {
            "status": "IDLE",
            "error_code": "KIND_NOT_ALLOWED",
            "job_id": "",
            "job_kind": normalized_kind,
            "jobs_index_path": _jobs_index_rel(workspace_root, policy),
            "policy_source": policy_source,
        }

    for job in jobs:
        if str(job.get("kind") or "") == normalized_kind and str(job.get("status") or "") in {"QUEUED", "RUNNING"}:
            return {
                "status": "IDLE",
                "error_code": "JOB_ALREADY_RUNNING",
                "job_id": str(job.get("job_id") or ""),
                "job_kind": normalized_kind,
                "jobs_index_path": _jobs_index_rel(workspace_root, policy),
                "policy_source": policy_source,
            }

    payload_hash = _hash_text(payload_ref)

    mode = str(policy.get("mode") or "dry_run_only")
    if mode_override is not None:
        normalized_override = _normalize_mode(mode_override)
        if normalized_override:
            mode = normalized_override
        else:
            notes.append("mode_override_invalid")
    network_enabled = bool(policy.get("network_enabled", False))
    dry_run = bool(mode == "dry_run_only" or not network_enabled)
    signature_hash = _job_signature(normalized_kind, payload_hash, policy_hash, mode)
    job_id = _hash_text(
        _canonical_json({"kind": normalized_kind, "payload_hash": payload_hash, "policy_hash": policy_hash, "mode": mode})
    )

    status = "QUEUED"
    skip_reason = ""
    error_code = ""
    failure_class = ""
    if dry_run:
        status = "SKIP"
        error_code = "POLICY_BLOCKED"
        failure_class = "POLICY_BLOCKED"
        if mode == "dry_run_only":
            skip_reason = "DRYRUN_OK"
        else:
            skip_reason = "NETWORK_DISABLED"

    job = {
        "version": "v1",
        "job_id": job_id,
        "kind": normalized_kind,
        "status": status,
        "created_at": now,
        "updated_at": now,
        "workspace_root": str(workspace_root),
        "dry_run": bool(dry_run),
        "network_enabled": bool(network_enabled),
        "mode": mode,
        "payload_ref": payload_ref,
        "payload_hash": payload_hash,
        "attempts": 0,
        "error_code": error_code,
        "skip_reason": skip_reason,
        "failure_class": failure_class,
        "notes": notes,
        "evidence_paths": [],
        "result_paths": [],
        "signature_hash": signature_hash,
    }

    job_report = _write_job_report(workspace_root, job)
    job["evidence_paths"].append(job_report)

    jobs = [j for j in jobs if str(j.get("job_id") or "") != job_id]
    jobs.append(job)
    jobs_index["jobs"] = _apply_job_retention(jobs, policy)
    jobs_index_path = _save_jobs_index(workspace_root, policy, jobs_index)

    return {
        "status": status,
        "job_id": job_id,
        "job_kind": normalized_kind,
        "job_report_path": job_report,
        "jobs_index_path": jobs_index_path,
        "policy_source": policy_source,
        "error_code": error_code or None,
        "skip_reason": skip_reason or None,
        "mode": mode,
        "network_enabled": bool(network_enabled),
    }


def deploy_job_poll(*, workspace_root: Path, job_id: str) -> dict[str, Any]:
    policy, policy_source, policy_hash, notes = _load_policy(workspace_root)
    _ = policy_hash
    jobs_index, job_notes = _load_jobs_index(workspace_root, policy)
    notes.extend(job_notes)

    jobs = jobs_index.get("jobs") if isinstance(jobs_index.get("jobs"), list) else []
    target: dict[str, Any] | None = None
    for job in jobs:
        if str(job.get("job_id") or "") == job_id:
            target = job
            break

    if target is None:
        return {"status": "FAIL", "error_code": "JOB_NOT_FOUND", "job_id": job_id}

    status = str(target.get("status") or "")
    now = _now_iso()
    if status in {"QUEUED", "RUNNING"}:
        mode = str(target.get("mode") or policy.get("mode") or "dry_run_only")
        network_enabled_raw = target.get("network_enabled")
        network_enabled = bool(network_enabled_raw) if isinstance(network_enabled_raw, bool) else bool(policy.get("network_enabled", False))
        dry_run = bool(mode == "dry_run_only")
        if dry_run:
            skip_reason = "DRYRUN_OK"
        elif not network_enabled:
            skip_reason = "NETWORK_DISABLED"
        else:
            skip_reason = "DRYRUN_OK"
        target["status"] = "SKIP"
        target["skip_reason"] = skip_reason
        target["error_code"] = "POLICY_BLOCKED"
        target["failure_class"] = "POLICY_BLOCKED"
        target["attempts"] = int(target.get("attempts", 0)) + 1
        target["last_poll_at"] = now
        target["updated_at"] = now
        target["notes"] = notes

    elif status in {"PASS", "FAIL", "TIMEOUT", "KILLED", "SKIP"}:
        target["last_poll_at"] = now
        target["updated_at"] = now
        target["notes"] = notes

    job_report = _write_job_report(workspace_root, target)
    evidence_paths = target.get("evidence_paths") if isinstance(target.get("evidence_paths"), list) else []
    if job_report not in evidence_paths:
        evidence_paths.append(job_report)
        target["evidence_paths"] = evidence_paths

    jobs = [j for j in jobs if str(j.get("job_id") or "") != job_id]
    jobs.append(target)
    jobs_index["jobs"] = _apply_job_retention(jobs, policy)
    jobs_index_path = _save_jobs_index(workspace_root, policy, jobs_index)

    _ = build_deploy_report(workspace_root=workspace_root)
    deploy_report_path = str(Path(".cache") / "reports" / "deploy_report.v1.json")

    return {
        "status": str(target.get("status") or "OK"),
        "job_id": job_id,
        "job_kind": str(target.get("kind") or ""),
        "job_report_path": job_report,
        "jobs_index_path": jobs_index_path,
        "deploy_report_path": deploy_report_path,
        "policy_source": policy_source,
        "error_code": target.get("error_code") or None,
    }


def run_deploy_check(*, workspace_root: Path, chat: bool = True) -> dict[str, Any]:
    policy, policy_source, _, notes = _load_policy(workspace_root)
    allowed_kinds = sorted({str(x) for x in policy.get("allowed_kinds", []) if isinstance(x, str) and x.strip()})
    default_kind = allowed_kinds[0] if allowed_kinds else "DEPLOY_STATIC_FE"

    plan_path = workspace_root / ".cache" / "reports" / "deploy_plan.v1.json"
    plan_payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "kind": default_kind,
        "mode": str(policy.get("mode") or ""),
        "network_enabled": bool(policy.get("network_enabled", False)),
        "notes": ["PROGRAM_LED=true", "LOCAL_DRYRUN=true"],
    }
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(_dump_json(plan_payload), encoding="utf-8")

    jobs_index, _ = _load_jobs_index(workspace_root, policy)
    jobs = jobs_index.get("jobs") if isinstance(jobs_index.get("jobs"), list) else []
    running_jobs = [j for j in jobs if isinstance(j, dict) and str(j.get("status") or "") in {"QUEUED", "RUNNING"}]

    action = "start"
    job_payload: dict[str, Any] = {}
    if running_jobs:
        running_jobs.sort(key=lambda j: (_job_time(j), str(j.get("job_id") or "")))
        job_id = str(running_jobs[0].get("job_id") or "")
        if job_id:
            job_payload = deploy_job_poll(workspace_root=workspace_root, job_id=job_id)
            action = "poll"
    if action == "start":
        job_payload = deploy_job_start(
            workspace_root=workspace_root,
            kind=default_kind,
            payload_ref=str(Path(".cache") / "reports" / "deploy_plan.v1.json"),
        )

    report = build_deploy_report(workspace_root=workspace_root)
    report_path = str(Path(".cache") / "reports" / "deploy_report.v1.json")

    from src.ops.work_intake_from_sources import run_work_intake_build
    from src.ops.system_status_report import run_system_status

    intake_res = run_work_intake_build(workspace_root=workspace_root)
    work_intake_path = intake_res.get("work_intake_path") if isinstance(intake_res, dict) else ""
    sys_res = run_system_status(workspace_root=workspace_root, core_root=_repo_root(), dry_run=False)
    sys_path = sys_res.get("out_json") if isinstance(sys_res, dict) else ""

    status = report.get("status", "WARN") if isinstance(report, dict) else "WARN"
    job_status = job_payload.get("status") if isinstance(job_payload, dict) else ""
    job_id = job_payload.get("job_id") if isinstance(job_payload, dict) else ""

    preview_lines = [
        "PROGRAM-LED: deploy-check; user_command=false",
        f"workspace_root={workspace_root}",
    ]
    result_lines = [
        f"status={status}",
        f"job_action={action}",
        f"job_status={job_status}",
        f"job_id={job_id}",
        f"network_enabled={policy.get('network_enabled', False)}",
    ]
    evidence_lines = [
        str(Path(".cache") / "reports" / "deploy_plan.v1.json"),
        report_path,
        job_payload.get("job_report_path") if isinstance(job_payload, dict) else "",
        job_payload.get("jobs_index_path") if isinstance(job_payload, dict) else "",
        sys_path,
        work_intake_path,
    ]
    actions_lines = ["deploy-job-poll", "deploy-job-start", "work-intake-check"]
    next_lines = ["Devam et", "Durumu goster", "Duraklat"]

    final_json = {
        "status": status,
        "deploy_plan_path": str(Path(".cache") / "reports" / "deploy_plan.v1.json"),
        "deploy_report_path": report_path,
        "job_action": action,
        "job_id": job_id,
        "job_status": job_status,
        "job_report_path": job_payload.get("job_report_path") if isinstance(job_payload, dict) else "",
        "jobs_index_path": job_payload.get("jobs_index_path") if isinstance(job_payload, dict) else "",
        "system_status_path": sys_path,
        "work_intake_path": work_intake_path,
        "policy_source": policy_source,
        "notes": notes,
    }

    if chat:
        print("PREVIEW:")
        print("\n".join(preview_lines))
        print("RESULT:")
        print("\n".join(result_lines))
        print("EVIDENCE:")
        print("\n".join(str(x) for x in evidence_lines if x))
        print("ACTIONS:")
        print("\n".join(actions_lines))
        print("NEXT:")
        print("\n".join(next_lines))
        print(json.dumps(final_json, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(final_json, ensure_ascii=False, sort_keys=True))

    return final_json
