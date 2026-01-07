from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from src.prj_airunner.airunner_perf import append_perf_event


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


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
        "jobs": {
            "max_running": 3,
            "max_poll_per_tick": 3,
            "poll_interval_seconds": 300,
            "keep_last_n": 50,
            "ttl_seconds": 604800,
            "timeout_seconds": 3600,
            "stale_after_seconds": 3600,
            "smoke_full": {
                "enabled": True,
                "timeout_seconds": 900,
                "poll_interval_seconds": 30,
                "max_concurrent": 1,
                "cooldown_seconds": 3600,
            },
            "smoke_full_cmd": [],
            "allowed_job_types": [
                "SMOKE_FULL",
                "RELEASE_PREPARE",
                "RELEASE_PUBLISH",
                "GITHUB_CHECKS_POLL",
                "GITHUB_MERGE_POLL",
            ],
            "network_required_job_types": [
                "RELEASE_PUBLISH",
                "GITHUB_CHECKS_POLL",
                "GITHUB_MERGE_POLL",
            ],
        },
        "perf": {
            "enable": True,
            "event_log_max_lines": 5000,
            "time_sinks_window": 200,
            "thresholds_ms": {
                "smoke_full_p95_warn": 240000,
                "smoke_fast_p95_warn": 60000,
                "release_prepare_p95_warn": 180000,
            },
        },
        "intake_mapping": {"time_sink_bucket": "TICKET", "time_sink_escalate_to_incident_after": 3},
    }


def load_jobs_policy(*, core_root: Path, workspace_root: Path) -> tuple[dict[str, Any], str, list[str]]:
    notes: list[str] = []
    policy = _policy_defaults()
    core_path = core_root / "policies" / "policy_airunner_jobs.v1.json"
    override_path = workspace_root / ".cache" / "policy_overrides" / "policy_airunner_jobs.override.v1.json"
    if core_path.exists():
        try:
            obj = json.loads(core_path.read_text(encoding="utf-8"))
            if isinstance(obj, dict):
                policy = _deep_merge(policy, obj)
        except Exception:
            notes.append("policy_invalid")
    else:
        notes.append("policy_missing")
    if override_path.exists():
        try:
            obj = json.loads(override_path.read_text(encoding="utf-8"))
            if isinstance(obj, dict):
                policy = _deep_merge(policy, obj)
                notes.append("policy_override_loaded")
        except Exception:
            notes.append("policy_override_invalid")
    policy_hash = _hash_text(_canonical_json(policy))
    return policy, policy_hash, notes


def _jobs_index_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "airunner" / "jobs_index.v1.json"


def _default_index(workspace_root: Path) -> dict[str, Any]:
    return {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "status": "IDLE",
        "jobs": [],
        "counts": {"total": 0, "queued": 0, "running": 0, "pass": 0, "fail": 0, "timeout": 0, "killed": 0, "skip": 0},
        "notes": [],
    }


def load_jobs_index(workspace_root: Path) -> tuple[dict[str, Any], list[str]]:
    path = _jobs_index_path(workspace_root)
    if not path.exists():
        return _default_index(workspace_root), ["jobs_index_missing"]
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _default_index(workspace_root), ["jobs_index_invalid"]
    if not isinstance(obj, dict):
        return _default_index(workspace_root), ["jobs_index_invalid"]
    return obj, []


def _job_id(job_type: str, tick_id: str) -> str:
    return _hash_text(f"{job_type}|{tick_id}")


def _job_report_path(workspace_root: Path, job_id: str) -> Path:
    return workspace_root / ".cache" / "reports" / "airunner_jobs" / f"airunner_job_{job_id}.v1.json"


def _write_job_report(workspace_root: Path, payload: dict[str, Any]) -> str:
    path = _job_report_path(workspace_root, str(payload.get("job_id", "unknown")))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_json(payload), encoding="utf-8")
    return str(Path(".cache") / "reports" / "airunner_jobs" / path.name)


def _jobs_report_dir(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "reports" / "jobs"


def _jobs_archive_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "reports" / "jobs_archive.v1.json"


def _smoke_full_paths(workspace_root: Path, job_id: str) -> tuple[Path, Path, Path]:
    base = _jobs_report_dir(workspace_root)
    return (
        base / f"smoke_full_{job_id}.stdout.log",
        base / f"smoke_full_{job_id}.stderr.log",
        base / f"smoke_full_{job_id}.rc.json",
    )


def _rel_job_path(path: Path) -> str:
    return str(Path(".cache") / "reports" / "jobs" / path.name)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _job_time(job: dict[str, Any]) -> datetime:
    for key in ("started_at", "updated_at", "created_at"):
        ts = _parse_iso(str(job.get(key) or ""))
        if ts:
            return ts
    return datetime.fromtimestamp(0, tz=timezone.utc)


def _archive_pruned_jobs(workspace_root: Path, jobs: list[dict[str, Any]]) -> str:
    if not jobs:
        return ""
    archive_path = _jobs_archive_path(workspace_root)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "archived_at": _now_iso(),
        "count": len(jobs),
        "jobs": sorted(jobs, key=lambda j: str(j.get("job_id") or "")),
    }
    if archive_path.exists():
        try:
            payload = json.loads(archive_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
    else:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    entries = payload.get("entries") if isinstance(payload.get("entries"), list) else []
    entries.append(entry)
    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "entries": entries,
        "notes": [],
    }
    archive_path.write_text(_dump_json(payload), encoding="utf-8")
    return str(Path(".cache") / "reports" / archive_path.name)


def _prune_jobs(
    jobs: list[dict[str, Any]],
    *,
    keep_last_n: int,
    ttl_seconds: int,
    now: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pruned: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    ttl = max(0, ttl_seconds)
    for job in jobs:
        if not isinstance(job, dict):
            continue
        if ttl:
            job_time = _job_time(job)
            if now - job_time > timedelta(seconds=ttl):
                pruned.append(job)
                continue
        kept.append(job)

    by_type: dict[str, list[dict[str, Any]]] = {}
    for job in kept:
        job_type = str(job.get("job_type") or job.get("kind") or "")
        by_type.setdefault(job_type, []).append(job)

    final: list[dict[str, Any]] = []
    limit = max(0, keep_last_n)
    for job_type, items in sorted(by_type.items(), key=lambda kv: kv[0]):
        items_sorted = sorted(
            items,
            key=lambda j: (-int(_job_time(j).timestamp()), str(j.get("job_id") or "")),
        )
        final.extend(items_sorted[:limit] if limit else [])
        if limit and len(items_sorted) > limit:
            pruned.extend(items_sorted[limit:])
        elif not limit:
            pruned.extend(items_sorted)

    return final, pruned


def _pid_running(pid: int | None) -> bool:
    if not isinstance(pid, int):
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _read_text_tail(path: Path, max_bytes: int = 20000) -> str:
    try:
        data = path.read_bytes()
    except Exception:
        return ""
    if len(data) > max_bytes:
        data = data[-max_bytes:]
    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _detect_demo_prereq_failure(text: str) -> bool:
    return "prerequisite apply failed" in text and "ws_integration_demo" in text


def _detect_demo_catalog_parse(text: str) -> bool:
    if "catalog parse error" in text:
        return True
    if "catalog" in text and "parse" in text and "ws_integration_demo" in text:
        return True
    if "catalog" in text and "valid json" in text and "ws_integration_demo" in text:
        return True
    return False


def _detect_core_break(text: str) -> bool:
    return "schema validation" in text or "integrity verify" in text


def _normalize_signature_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip().lower())


def _signature_hash(*, failure_class: str, lines: list[str]) -> str:
    payload = "|".join([failure_class] + lines)
    return _hash_text(payload)


def _classify_smoke_full_failure(stdout_path: Path, stderr_path: Path) -> tuple[str, str]:
    stdout_text = _read_text_tail(stdout_path)
    stderr_text = _read_text_tail(stderr_path)
    combined = (stderr_text + "\n" + stdout_text).lower()
    if _detect_demo_prereq_failure(combined):
        failure_class = "DEMO_PREREQ_FAIL"
    elif _detect_demo_catalog_parse(combined):
        failure_class = "DEMO_CATALOG_PARSE"
    elif _detect_core_break(combined):
        failure_class = "CORE_BREAK"
    else:
        failure_class = "OTHER"

    lines: list[str] = []
    for raw in (stderr_text + "\n" + stdout_text).splitlines():
        norm = _normalize_signature_line(raw)
        if not norm:
            continue
        lines.append(norm)
        if len(lines) >= 10:
            break
    return failure_class, _signature_hash(failure_class=failure_class, lines=lines)


def _smoke_full_cmd(*, policy: dict[str, Any], workspace_root: Path, rc_path: Path) -> list[str]:
    jobs_cfg = policy.get("jobs") if isinstance(policy.get("jobs"), dict) else {}
    override_cmd = jobs_cfg.get("smoke_full_cmd")
    if isinstance(override_cmd, list) and override_cmd and all(isinstance(x, str) and x for x in override_cmd):
        rendered: list[str] = []
        for arg in override_cmd:
            rendered.append(
                str(arg)
                .replace("{rc_path}", str(rc_path))
                .replace("{workspace_root}", str(workspace_root))
            )
        return rendered
    repo_root = _repo_root()
    venv_py = repo_root / ".venv" / "bin" / "python"
    python_bin = str(venv_py) if venv_py.exists() else sys.executable
    job_path = repo_root / "src" / "prj_airunner" / "smoke_full_job.py"
    return [
        python_bin,
        str(job_path),
        "--workspace-root",
        str(workspace_root),
        "--rc-path",
        str(rc_path),
    ]


def _start_smoke_full_job(workspace_root: Path, job: dict[str, Any], policy: dict[str, Any]) -> None:
    stdout_path, stderr_path, rc_path = _smoke_full_paths(workspace_root, str(job.get("job_id") or "unknown"))
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = _smoke_full_cmd(policy=policy, workspace_root=workspace_root, rc_path=rc_path)
    env = os.environ.copy()
    env["SMOKE_LEVEL"] = "full"
    repo_root = _repo_root()
    with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open("w", encoding="utf-8") as stderr_file:
        proc = subprocess.Popen(
            cmd,
            cwd=str(repo_root),
            env=env,
            stdout=stdout_file,
            stderr=stderr_file,
        )
    job["pid"] = int(proc.pid)
    job["status"] = "RUNNING"
    job["started_at"] = _now_iso()
    job["updated_at"] = _now_iso()
    job["last_poll_at"] = _now_iso()
    job["attempts"] = int(job.get("attempts", 0)) + 1
    evidence = job.get("evidence_paths") if isinstance(job.get("evidence_paths"), list) else []
    evidence.extend([_rel_job_path(stdout_path), _rel_job_path(stderr_path), _rel_job_path(rc_path)])
    job["evidence_paths"] = sorted({str(x) for x in evidence if isinstance(x, str) and x})


def _poll_smoke_full_job(
    workspace_root: Path,
    job: dict[str, Any],
    policy: dict[str, Any],
    *,
    timeout_seconds: int,
) -> None:
    stdout_path, stderr_path, rc_path = _smoke_full_paths(workspace_root, str(job.get("job_id") or "unknown"))
    jobs_cfg = policy.get("jobs") if isinstance(policy.get("jobs"), dict) else {}
    started_at = _parse_iso(str(job.get("started_at") or ""))
    now = datetime.now(timezone.utc)

    if timeout_seconds and started_at and now - started_at > timedelta(seconds=timeout_seconds):
        pid = job.get("pid")
        if isinstance(pid, int):
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass
        job["status"] = "TIMEOUT"
        job["error_code"] = "JOB_TIMEOUT"
        job["failure_class"] = "TIMEOUT"
        job["signature_hash"] = _signature_hash(failure_class="TIMEOUT", lines=[])
        job["updated_at"] = _now_iso()
        job["last_poll_at"] = _now_iso()
        return

    if rc_path.exists():
        try:
            rc_obj = json.loads(rc_path.read_text(encoding="utf-8"))
        except Exception:
            rc_obj = {}
        rc_val = rc_obj.get("rc")
        try:
            rc = int(rc_val)
        except Exception:
            rc = 1
        job["rc"] = rc
        job["pid"] = None
        if rc == 0:
            job["status"] = "PASS"
            job.pop("error_code", None)
            job["failure_class"] = "PASS"
            job["signature_hash"] = _signature_hash(failure_class="PASS", lines=[])
        else:
            job["status"] = "FAIL"
            job["error_code"] = "SMOKE_FULL_FAIL"
            failure_class, signature_hash = _classify_smoke_full_failure(stdout_path, stderr_path)
            job["failure_class"] = failure_class
            job["signature_hash"] = signature_hash
        job["updated_at"] = _now_iso()
        job["last_poll_at"] = _now_iso()
        return

    pid = job.get("pid")
    if _pid_running(pid if isinstance(pid, int) else None):
        job["status"] = "RUNNING"
        job["updated_at"] = _now_iso()
        job["last_poll_at"] = _now_iso()
        return

    job["status"] = "FAIL"
    job["error_code"] = "JOB_NO_RESULT"
    failure_class, signature_hash = _classify_smoke_full_failure(stdout_path, stderr_path)
    job["failure_class"] = failure_class
    job["signature_hash"] = signature_hash
    job["updated_at"] = _now_iso()
    job["last_poll_at"] = _now_iso()


def _run_cmd_json(func, args: argparse.Namespace) -> dict[str, Any]:
    from io import StringIO
    from contextlib import redirect_stdout, redirect_stderr

    buf = StringIO()
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            rc = func(args)
    except Exception:
        return {"status": "FAIL", "error_code": "COMMAND_EXCEPTION"}

    lines = [line for line in buf.getvalue().splitlines() if line.strip()]
    if not lines:
        return {"status": "WARN", "error_code": "COMMAND_NO_OUTPUT", "return_code": rc}
    try:
        payload = json.loads(lines[-1])
    except Exception:
        return {"status": "WARN", "error_code": "COMMAND_OUTPUT_INVALID", "return_code": rc}
    if isinstance(payload, dict):
        payload["return_code"] = rc
    return payload if isinstance(payload, dict) else {"status": "WARN", "return_code": rc}


def _run_release_prepare(workspace_root: Path) -> tuple[str, str | None, list[str], list[str]]:
    from src.ops.commands.extension_cmds import cmd_release_prepare

    payload = _run_cmd_json(
        cmd_release_prepare,
        argparse.Namespace(workspace_root=str(workspace_root), channel=""),
    )
    status = str(payload.get("status") or "WARN") if isinstance(payload, dict) else "WARN"
    error_code = payload.get("error_code") if isinstance(payload, dict) else None
    result_paths: list[str] = []
    if status in {"OK", "WARN"}:
        result_paths.append(str(Path(".cache") / "reports" / "release_manifest.v1.json"))
        result_paths.append(str(Path(".cache") / "reports" / "release_notes.v1.md"))
    return status, str(error_code) if error_code else None, [], result_paths


def update_jobs(
    *,
    workspace_root: Path,
    tick_id: str,
    policy_hash: str,
    policy: dict[str, Any],
) -> tuple[dict[str, Any], list[str], dict[str, Any]]:
    notes: list[str] = []
    index, idx_notes = load_jobs_index(workspace_root)
    notes.extend(idx_notes)

    now = datetime.now(timezone.utc)
    jobs_cfg = policy.get("jobs") if isinstance(policy.get("jobs"), dict) else {}
    smoke_full_cfg = jobs_cfg.get("smoke_full") if isinstance(jobs_cfg.get("smoke_full"), dict) else {}
    smoke_full_enabled = bool(smoke_full_cfg.get("enabled", True))
    smoke_full_timeout = int(smoke_full_cfg.get("timeout_seconds", jobs_cfg.get("timeout_seconds", 0) or 0) or 0)
    smoke_full_poll_interval = int(
        smoke_full_cfg.get("poll_interval_seconds", jobs_cfg.get("poll_interval_seconds", 0) or 0) or 0
    )
    smoke_full_max_concurrent = int(smoke_full_cfg.get("max_concurrent", 1) or 1)
    smoke_full_cooldown = int(smoke_full_cfg.get("cooldown_seconds", 0) or 0)
    allowed_types = [str(x) for x in jobs_cfg.get("allowed_job_types", []) if isinstance(x, str)]
    network_required = {str(x) for x in jobs_cfg.get("network_required_job_types", []) if isinstance(x, str)}
    max_poll = int(jobs_cfg.get("max_poll_per_tick", 1) or 1)
    max_running = int(jobs_cfg.get("max_running", 1) or 1)
    default_poll_interval = int(jobs_cfg.get("poll_interval_seconds", 0) or 0)
    keep_last_n = int(jobs_cfg.get("keep_last_n", 0) or 0)
    ttl_seconds = int(jobs_cfg.get("ttl_seconds", 0) or 0)
    stale_after = int(jobs_cfg.get("stale_after_seconds", 0) or 0)

    jobs = [j for j in index.get("jobs", []) if isinstance(j, dict)]
    active_by_type = {str(j.get("job_type") or j.get("kind") or "") for j in jobs if j.get("status") in {"QUEUED", "RUNNING"}}
    smoke_full_running = len(
        [
            j
            for j in jobs
            if str(j.get("job_type") or j.get("kind") or "") == "SMOKE_FULL" and str(j.get("status") or "") == "RUNNING"
        ]
    )
    last_smoke_full_started = None
    for job in jobs:
        if str(job.get("job_type") or job.get("kind") or "") != "SMOKE_FULL":
            continue
        started_at = _parse_iso(str(job.get("started_at") or job.get("created_at") or ""))
        if started_at and (last_smoke_full_started is None or started_at > last_smoke_full_started):
            last_smoke_full_started = started_at

    def _job_sort_key(job: dict[str, Any]) -> tuple[int, str, str]:
        job_type = str(job.get("job_type") or job.get("kind") or "")
        priority = 0 if job_type == "SMOKE_FULL" else 1
        return (priority, job_type, str(job.get("job_id") or ""))

    if str(index.get("last_tick_id") or "") != tick_id:
        for job_type in sorted(allowed_types):
            if job_type in active_by_type:
                continue
            if job_type == "SMOKE_FULL":
                if not smoke_full_enabled:
                    notes.append("smoke_full_disabled")
                    continue
                if smoke_full_cooldown and last_smoke_full_started and now - last_smoke_full_started < timedelta(seconds=smoke_full_cooldown):
                    notes.append("smoke_full_cooldown_active")
                    continue
                if smoke_full_running >= smoke_full_max_concurrent:
                    notes.append("smoke_full_max_concurrent")
                    continue
            job_id = _job_id(job_type, tick_id)
            if any(j.get("job_id") == job_id for j in jobs):
                continue
            now_iso = _now_iso()
            jobs.append(
                {
                    "version": "v1",
                    "job_id": job_id,
                    "job_type": job_type,
                    "kind": job_type,
                    "workspace_root": str(workspace_root),
                    "status": "QUEUED",
                    "created_at": now_iso,
                    "started_at": now_iso,
                    "last_poll_at": now_iso,
                    "updated_at": now_iso,
                    "attempts": 0,
                    "pid": None,
                    "rc": None,
                    "policy_hash": policy_hash,
                    "evidence_paths": [],
                    "notes": ["enqueued"],
                }
            )
        index["last_tick_id"] = tick_id

    jobs_sorted = sorted(jobs, key=_job_sort_key)
    polled = 0
    perf_cfg = policy.get("perf") if isinstance(policy.get("perf"), dict) else {}
    perf_enabled = bool(perf_cfg.get("enable", True))
    perf_max = int(perf_cfg.get("event_log_max_lines", 0) or 0)
    run_stats = {"started": 0, "polled": 0, "running": 0, "failed": 0, "passed": 0, "last_smoke_full_job_id": ""}

    running_count = len([j for j in jobs_sorted if j.get("status") == "RUNNING"])
    for job in jobs_sorted:
        if polled >= max_poll:
            break
        status = str(job.get("status") or "")
        if status not in {"QUEUED", "RUNNING"}:
            continue
        job_type = str(job.get("job_type") or job.get("kind") or "")
        poll_interval = smoke_full_poll_interval if job_type == "SMOKE_FULL" else default_poll_interval
        last_poll = job.get("last_poll_at")
        if status == "RUNNING" and poll_interval and last_poll:
            try:
                last_poll_dt = datetime.fromisoformat(str(last_poll).replace("Z", "+00:00"))
            except Exception:
                last_poll_dt = None
            if last_poll_dt and now - last_poll_dt < timedelta(seconds=poll_interval):
                continue
        updated_at = job.get("updated_at")
        if status == "RUNNING" and stale_after and updated_at:
            try:
                upd_dt = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
            except Exception:
                upd_dt = None
            if upd_dt and now - upd_dt > timedelta(seconds=stale_after):
                job["status"] = "FAIL"
                job["error_code"] = "JOB_STALE"
                job["failure_class"] = "OTHER"
                job["updated_at"] = _now_iso()
                job["last_poll_at"] = _now_iso()
                polled += 1
                continue

        if not job_type:
            job_type = "UNKNOWN"
        job["job_type"] = job_type
        job["kind"] = job_type
        if not job.get("workspace_root"):
            job["workspace_root"] = str(workspace_root)
        now_iso = _now_iso()
        if not job.get("created_at"):
            job["created_at"] = now_iso
        if not job.get("started_at"):
            job["started_at"] = job.get("created_at", now_iso)
        if not job.get("last_poll_at"):
            job["last_poll_at"] = job.get("created_at", now_iso)
        if not job.get("updated_at"):
            job["updated_at"] = job.get("created_at", now_iso)
        if not isinstance(job.get("attempts"), int):
            job["attempts"] = int(job.get("attempts", 0) or 0)
        if "pid" not in job:
            job["pid"] = None
        if "rc" not in job:
            job["rc"] = None
        if not isinstance(job.get("evidence_paths"), list):
            job["evidence_paths"] = []
        if not isinstance(job.get("notes"), list):
            job["notes"] = []
        if status == "QUEUED" and running_count >= max_running:
            continue
        if status == "QUEUED" and job_type in network_required:
            job["status"] = "SKIP"
            job["skip_reason"] = "NO_NETWORK"
            job["updated_at"] = _now_iso()
            job["last_poll_at"] = _now_iso()
            job["attempts"] = int(job.get("attempts", 0)) + 1
            polled += 1
        else:
            start_iso = _now_iso()
            started = time.monotonic()
            if job_type == "SMOKE_FULL":
                if status == "QUEUED":
                    _start_smoke_full_job(workspace_root, job, policy)
                    running_count += 1
                    run_stats["started"] += 1
                else:
                    _poll_smoke_full_job(workspace_root, job, policy, timeout_seconds=smoke_full_timeout)
                    run_stats["polled"] += 1
                polled += 1
                run_stats["last_smoke_full_job_id"] = str(job.get("job_id") or "")
                new_status = str(job.get("status") or "")
                if perf_enabled and new_status in {"PASS", "FAIL", "TIMEOUT", "KILLED"}:
                    started_at = _parse_iso(str(job.get("started_at") or "")) or now
                    duration_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
                    end_iso = _now_iso()
                    perf_status = "OK" if new_status == "PASS" else "FAIL"
                    append_perf_event(
                        workspace_root,
                        event={
                            "event_type": "JOB_RUN",
                            "op_name": job_type,
                            "started_at": started_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                            "ended_at": end_iso,
                            "duration_ms": max(duration_ms, 0),
                            "status": perf_status,
                            "job_id": job.get("job_id"),
                            "notes": ["PROGRAM_LED=true"],
                        },
                        max_lines=perf_max,
                    )
            elif status == "RUNNING":
                job["status"] = "FAIL"
                job["error_code"] = "JOB_NO_HANDLER"
                job["updated_at"] = _now_iso()
                job["last_poll_at"] = _now_iso()
                polled += 1
            else:
                job["status"] = "RUNNING"
                job["updated_at"] = _now_iso()
                if job_type == "RELEASE_PREPARE":
                    run_status, error_code, run_notes, result_paths = _run_release_prepare(workspace_root)
                    if run_status in {"OK", "WARN"}:
                        job["status"] = "PASS"
                    elif run_status == "IDLE":
                        job["status"] = "SKIP"
                        job["skip_reason"] = "NO_PLAN"
                    else:
                        job["status"] = "FAIL"
                    if error_code:
                        job["error_code"] = error_code
                    job["notes"] = list(job.get("notes", [])) + run_notes
                    if result_paths:
                        job["result_paths"] = sorted({*(job.get("result_paths") or []), *result_paths})
                else:
                    job["status"] = "SKIP"
                    job["skip_reason"] = "POLICY_DISABLED"

                duration_ms = int((time.monotonic() - started) * 1000)
                end_iso = _now_iso()
                job["attempts"] = int(job.get("attempts", 0)) + 1
                job["updated_at"] = _now_iso()
                job["last_poll_at"] = _now_iso()
                if job["status"] == "RUNNING":
                    job["status"] = "FAIL"
                    job["error_code"] = "JOB_NO_RESULT"

                if perf_enabled:
                    perf_status = "OK" if job["status"] == "PASS" else ("SKIP" if job["status"] == "SKIP" else "FAIL")
                    append_perf_event(
                        workspace_root,
                        event={
                            "event_type": "JOB_RUN",
                            "op_name": job_type,
                            "started_at": start_iso,
                            "ended_at": end_iso,
                            "duration_ms": duration_ms,
                            "status": perf_status,
                            "job_id": job.get("job_id"),
                            "notes": ["PROGRAM_LED=true"],
                        },
                        max_lines=perf_max,
                    )
                polled += 1

        result_payload = {
            "version": "v1",
            "job_id": job.get("job_id"),
            "job_type": job_type,
            "kind": job.get("kind"),
            "workspace_root": job.get("workspace_root"),
            "status": job.get("status"),
            "error_code": job.get("error_code"),
            "skip_reason": job.get("skip_reason"),
            "failure_class": job.get("failure_class"),
            "signature_hash": job.get("signature_hash"),
            "pid": job.get("pid"),
            "rc": job.get("rc"),
            "evidence_paths": job.get("evidence_paths", []),
            "result_paths": job.get("result_paths", []),
            "updated_at": job.get("updated_at"),
        }
        report_rel = _write_job_report(workspace_root, result_payload)
        job["result_paths"] = sorted({*(job.get("result_paths") or []), report_rel})

    jobs_sorted = sorted(jobs_sorted, key=_job_sort_key)
    pruned_jobs = []
    if keep_last_n or ttl_seconds:
        jobs_sorted, pruned_jobs = _prune_jobs(
            jobs_sorted,
            keep_last_n=keep_last_n,
            ttl_seconds=ttl_seconds,
            now=now,
        )
        if pruned_jobs:
            _archive_pruned_jobs(workspace_root, pruned_jobs)
            notes.append(f"jobs_pruned={len(pruned_jobs)}")
    counts = {
        "total": len(jobs_sorted),
        "queued": len([j for j in jobs_sorted if j.get("status") == "QUEUED"]),
        "running": len([j for j in jobs_sorted if j.get("status") == "RUNNING"]),
        "pass": len([j for j in jobs_sorted if j.get("status") == "PASS"]),
        "fail": len([j for j in jobs_sorted if j.get("status") == "FAIL"]),
        "timeout": len([j for j in jobs_sorted if j.get("status") == "TIMEOUT"]),
        "killed": len([j for j in jobs_sorted if j.get("status") == "KILLED"]),
        "skip": len([j for j in jobs_sorted if j.get("status") == "SKIP"]),
    }
    status = "OK" if counts["total"] else "IDLE"
    if counts["fail"] or counts["timeout"] or counts["killed"] or counts["skip"]:
        status = "WARN"
    run_stats["running"] = counts["running"]
    run_stats["failed"] = counts["fail"] + counts["timeout"] + counts["killed"]
    run_stats["passed"] = counts["pass"]

    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "status": status,
        "jobs": jobs_sorted,
        "counts": counts,
        "last_tick_id": index.get("last_tick_id"),
        "notes": sorted(set(notes)),
    }

    out_path = _jobs_index_path(workspace_root)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_dump_json(payload), encoding="utf-8")

    return payload, notes, run_stats
