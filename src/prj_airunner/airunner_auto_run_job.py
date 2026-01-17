from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover - zoneinfo missing fallback
    ZoneInfo = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


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


def _policy_defaults() -> dict[str, Any]:
    return {
        "version": "v1",
        "enabled": True,
        "default_deadline_local": "07:00",
        "tick_interval_seconds": 120,
        "budget_seconds_per_poll": 60,
        "max_polls_per_call": 1,
        "max_actions_per_tick": 5,
        "auto_decision_mode": "autopilot",
        "network_default_off": True,
    }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_policy(*, core_root: Path, workspace_root: Path) -> dict[str, Any]:
    policy = _policy_defaults()
    core_path = core_root / "policies" / "policy_airunner_auto_run.v1.json"
    override_path = workspace_root / ".cache" / "policy_overrides" / "policy_airunner_auto_run.override.v1.json"
    for path in (core_path, override_path):
        if not path.exists():
            continue
        try:
            obj = _load_json(path)
        except Exception:
            continue
        if isinstance(obj, dict):
            policy = _deep_merge(policy, obj)
    return policy


def _parse_stop_at(raw: str | None, notes: list[str]) -> tuple[str, int, int]:
    value = str(raw or "").strip()
    if not value:
        value = "07:00"
    if not re.match(r"^[0-2][0-9]:[0-5][0-9]$", value):
        notes.append("stop_at_invalid")
        value = "07:00"
    hour = int(value.split(":", 1)[0])
    minute = int(value.split(":", 1)[1])
    return value, hour, minute


def _resolve_timezone(raw: str | None, notes: list[str]) -> tuple[str, timezone | Any]:
    name = str(raw or "").strip() or "UTC"
    if ZoneInfo is None:
        notes.append("timezone_fallback=UTC")
        return "UTC", timezone.utc
    try:
        tz = ZoneInfo(name)
        return name, tz
    except Exception:
        notes.append("timezone_fallback=UTC")
        return "UTC", timezone.utc


def _compute_deadline(now_utc: datetime, tz, hour: int, minute: int) -> datetime:
    now_local = now_utc.astimezone(tz)
    stop_local = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now_local > stop_local:
        stop_local = stop_local + timedelta(days=1)
    return stop_local


def _job_id(
    *,
    workspace_root: Path,
    stop_at_date: str,
    stop_at_local: str,
    timezone_name: str,
    mode: str,
    job_kind: str,
    dry_run: bool,
) -> str:
    payload = {
        "workspace_root": str(workspace_root),
        "stop_at_date": stop_at_date,
        "stop_at_local": stop_at_local,
        "timezone": timezone_name,
        "mode": mode,
        "job_kind": job_kind or "",
        "dry_run": bool(dry_run),
    }
    return f"auto-run-{_hash_text(_canonical_json(payload))[:16]}"


def _job_store_dir(workspace_root: Path, job_id: str) -> Path:
    return workspace_root / ".cache" / "airunner" / "auto_run_jobs" / job_id


def _job_state_path(workspace_root: Path, job_id: str) -> Path:
    return _job_store_dir(workspace_root, job_id) / "state.v1.json"


def _index_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "airunner" / "auto_run_jobs" / "index.v1.json"


def _default_index(workspace_root: Path) -> dict[str, Any]:
    return {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "jobs": [],
        "counts": {"total": 0, "running": 0, "done": 0, "skip": 0, "fail": 0},
        "notes": [],
    }


def _summarize_counts(jobs: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"total": len(jobs), "running": 0, "done": 0, "skip": 0, "fail": 0}
    for job in jobs:
        status = str(job.get("status") or "").upper()
        if status in {"RUNNING", "QUEUED"}:
            counts["running"] += 1
        elif status == "DONE":
            counts["done"] += 1
        elif status == "FAIL":
            counts["fail"] += 1
        elif status == "SKIP":
            counts["skip"] += 1
    return counts


def _load_index(workspace_root: Path) -> tuple[dict[str, Any], list[str]]:
    path = _index_path(workspace_root)
    if not path.exists():
        return _default_index(workspace_root), ["index_missing"]
    try:
        obj = _load_json(path)
    except Exception:
        return _default_index(workspace_root), ["index_invalid"]
    return obj if isinstance(obj, dict) else _default_index(workspace_root), []


def _write_index(workspace_root: Path, index: dict[str, Any]) -> None:
    path = _index_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    index["generated_at"] = _now_iso()
    jobs = index.get("jobs") if isinstance(index.get("jobs"), list) else []
    index["jobs"] = sorted(
        [j for j in jobs if isinstance(j, dict)], key=lambda j: str(j.get("job_id") or "")
    )
    index["counts"] = _summarize_counts(index["jobs"])
    path.write_text(_dump_json(index), encoding="utf-8")


def _job_summary(job: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "job_id": str(job.get("job_id") or ""),
        "status": str(job.get("status") or ""),
        "stop_at_local": str(job.get("stop_at_local") or ""),
        "timezone": str(job.get("timezone") or ""),
        "mode": str(job.get("mode") or ""),
        "created_at": str(job.get("created_at") or ""),
        "updated_at": str(job.get("updated_at") or ""),
        "last_poll_at": str(job.get("last_poll_at") or ""),
        "last_poll_path": str(job.get("last_poll_path") or ""),
        "last_closeout_path": str(job.get("last_closeout_path") or ""),
        "notes": list(job.get("notes") or []),
    }
    return summary


def _upsert_job(index: dict[str, Any], summary: dict[str, Any]) -> None:
    jobs = index.get("jobs") if isinstance(index.get("jobs"), list) else []
    filtered = [j for j in jobs if isinstance(j, dict) and j.get("job_id") != summary.get("job_id")]
    filtered.append(summary)
    index["jobs"] = filtered


def _extract_note_value(notes: list[str], key: str) -> str:
    prefix = f"{key}="
    for note in notes:
        if isinstance(note, str) and note.startswith(prefix):
            return note[len(prefix) :].strip()
    return ""


def _deadline_from_job(job: dict[str, Any]) -> datetime | None:
    stop_at_local = str(job.get("stop_at_local") or "").strip()
    timezone_name = str(job.get("timezone") or "").strip() or "UTC"
    notes = job.get("notes") if isinstance(job.get("notes"), list) else []
    stop_at_date = _extract_note_value(notes, "stop_at_date")
    if not stop_at_date:
        return None
    if ZoneInfo is None:
        tz = timezone.utc
    else:
        try:
            tz = ZoneInfo(timezone_name)
        except Exception:
            tz = timezone.utc
    try:
        return datetime.fromisoformat(f"{stop_at_date}T{stop_at_local}:00").replace(tzinfo=tz)
    except Exception:
        return None


def _write_job_state(path: Path, job: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_json(job), encoding="utf-8")


def start_auto_run(
    *,
    workspace_root: Path,
    stop_at_local: str | None = None,
    timezone_name: str | None = None,
    mode: str | None = None,
    job_kind: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    core_root = _repo_root()
    policy = _load_policy(core_root=core_root, workspace_root=workspace_root)
    if not bool(policy.get("enabled", True)):
        return {
            "status": "IDLE",
            "error_code": "POLICY_DISABLED",
            "workspace_root": str(workspace_root),
        }

    notes: list[str] = ["PROGRAM_LED=true", "NO_WAIT=true"]
    stop_at_local, stop_hour, stop_minute = _parse_stop_at(
        stop_at_local or str(policy.get("default_deadline_local") or ""), notes
    )
    mode = str(mode or policy.get("auto_decision_mode") or "autopilot")
    tz_name, tz = _resolve_timezone(timezone_name, notes)
    now = datetime.now(timezone.utc)
    stop_at_dt = _compute_deadline(now, tz, stop_hour, stop_minute)
    stop_at_date = stop_at_dt.date().isoformat()
    job_kind = str(job_kind or "").strip()

    job_id = _job_id(
        workspace_root=workspace_root,
        stop_at_date=stop_at_date,
        stop_at_local=stop_at_local,
        timezone_name=tz_name,
        mode=mode,
        job_kind=job_kind,
        dry_run=dry_run,
    )

    state_path = _job_state_path(workspace_root, job_id)
    index, idx_notes = _load_index(workspace_root)
    notes.extend(idx_notes)

    if state_path.exists():
        try:
            existing = _load_json(state_path)
        except Exception:
            existing = {}
        if isinstance(existing, dict):
            summary = _job_summary(existing)
            _upsert_job(index, summary)
            _write_index(workspace_root, index)
            return {
                "status": "OK",
                "workspace_root": str(workspace_root),
                "job_id": summary.get("job_id"),
                "job_status": summary.get("status"),
                "job_path": str(state_path.relative_to(workspace_root)),
                "jobs_index_path": str(_index_path(workspace_root).relative_to(workspace_root)),
                "notes": sorted(set(notes + ["job_exists"])),
            }

    if job_kind:
        notes.append(f"job_kind={job_kind}")
    notes.append(f"stop_at_date={stop_at_date}")
    if dry_run:
        notes.append("skip_reason=DRY_RUN")
    elif job_kind and bool(policy.get("network_default_off", True)):
        notes.append("skip_reason=NETWORK_DISABLED")

    job_status = "SKIP" if dry_run or (job_kind and bool(policy.get("network_default_off", True))) else "QUEUED"
    now_iso = _now_iso()
    job = {
        "version": "v1",
        "job_id": job_id,
        "status": job_status,
        "workspace_root": str(workspace_root),
        "created_at": now_iso,
        "updated_at": now_iso,
        "timezone": tz_name,
        "stop_at_local": stop_at_local,
        "mode": mode,
        "poll_count": 0,
        "notes": sorted({n for n in notes if isinstance(n, str) and n}),
    }
    _write_job_state(state_path, job)
    _upsert_job(index, _job_summary(job))
    _write_index(workspace_root, index)

    return {
        "status": "OK",
        "workspace_root": str(workspace_root),
        "job_id": job_id,
        "job_status": job_status,
        "job_path": str(state_path.relative_to(workspace_root)),
        "jobs_index_path": str(_index_path(workspace_root).relative_to(workspace_root)),
        "notes": sorted(set(notes)),
    }


def _run_tick(workspace_root: Path, budget_seconds: int | None) -> dict[str, Any]:
    from src.prj_airunner.airunner_run import run_airunner_run

    return run_airunner_run(
        workspace_root=workspace_root,
        ticks=1,
        mode="no_wait",
        budget_seconds=budget_seconds if budget_seconds and budget_seconds > 0 else None,
    )


def _write_poll_report(
    *,
    workspace_root: Path,
    job: dict[str, Any],
    poll_count: int,
    tick_payload: dict[str, Any] | None,
    evidence_paths: list[str],
) -> str:
    report = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "job_id": str(job.get("job_id") or ""),
        "status": str(job.get("status") or ""),
        "poll_count": int(poll_count),
        "tick_status": tick_payload.get("status") if isinstance(tick_payload, dict) else None,
        "tick_run_path": tick_payload.get("run_path") if isinstance(tick_payload, dict) else None,
        "tick_reports": tick_payload.get("tick_reports") if isinstance(tick_payload, dict) else None,
        "evidence_paths": sorted({p for p in evidence_paths if isinstance(p, str) and p}),
        "notes": ["PROGRAM_LED=true", "NO_WAIT=true"],
    }
    rel_path = Path(".cache") / "reports" / f"airunner_auto_run_poll_{job.get('job_id')}_p{poll_count:03d}.v1.json"
    abs_path = workspace_root / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(_dump_json(report), encoding="utf-8")
    return str(rel_path)


def _write_closeout(
    *,
    workspace_root: Path,
    job: dict[str, Any],
    last_poll_path: str,
) -> str:
    report = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "job_id": str(job.get("job_id") or ""),
        "status": str(job.get("status") or ""),
        "poll_count": int(job.get("poll_count") or 0),
        "last_poll_path": last_poll_path,
        "notes": ["PROGRAM_LED=true", "NO_WAIT=true"],
    }
    rel_path = Path(".cache") / "reports" / "airrunner_full_auto_until_0700_closeout.v1.json"
    abs_path = workspace_root / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(_dump_json(report), encoding="utf-8")
    return str(rel_path)


def poll_auto_run(
    *,
    workspace_root: Path,
    job_id: str,
    max_polls: int = 1,
) -> dict[str, Any]:
    core_root = _repo_root()
    policy = _load_policy(core_root=core_root, workspace_root=workspace_root)
    if not bool(policy.get("enabled", True)):
        return {"status": "IDLE", "error_code": "POLICY_DISABLED", "workspace_root": str(workspace_root)}

    max_polls = max(1, int(max_polls or 1))
    policy_max = int(policy.get("max_polls_per_call", 1) or 1)
    if policy_max > 0:
        max_polls = min(max_polls, policy_max)

    index, idx_notes = _load_index(workspace_root)
    jobs = index.get("jobs") if isinstance(index.get("jobs"), list) else []
    if not job_id:
        jobs_sorted = sorted([j for j in jobs if isinstance(j, dict)], key=lambda j: str(j.get("job_id") or ""))
        job_id = str(jobs_sorted[-1].get("job_id") or "") if jobs_sorted else ""
    if not job_id:
        return {"status": "IDLE", "error_code": "JOB_ID_REQUIRED", "workspace_root": str(workspace_root)}

    state_path = _job_state_path(workspace_root, job_id)
    if not state_path.exists():
        return {"status": "IDLE", "error_code": "JOB_NOT_FOUND", "workspace_root": str(workspace_root), "job_id": job_id}

    poll_reports: list[str] = []
    job_status = ""
    last_poll_path = ""
    for _ in range(max_polls):
        job = _load_json(state_path)
        if not isinstance(job, dict):
            return {"status": "FAIL", "error_code": "JOB_STATE_INVALID", "job_id": job_id}

        status = str(job.get("status") or "")
        poll_count = int(job.get("poll_count") or 0) + 1
        now_iso = _now_iso()
        job["poll_count"] = poll_count
        job["last_poll_at"] = now_iso
        job["updated_at"] = now_iso

        evidence_paths: list[str] = []
        tick_payload: dict[str, Any] | None = None
        if status not in {"SKIP", "DONE", "FAIL"}:
            tick_payload = _run_tick(
                workspace_root,
                budget_seconds=int(policy.get("budget_seconds_per_poll", 0) or 0),
            )
            if isinstance(tick_payload, dict):
                run_path = tick_payload.get("run_path")
                if isinstance(run_path, str) and run_path:
                    evidence_paths.append(run_path)
                if isinstance(tick_payload.get("tick_reports"), list):
                    evidence_paths.extend([str(p) for p in tick_payload.get("tick_reports") if isinstance(p, str)])

        deadline = _deadline_from_job(job)
        if deadline is not None:
            now_local = datetime.now(timezone.utc).astimezone(deadline.tzinfo or timezone.utc)
            if now_local >= deadline:
                status = "DONE"
        if isinstance(tick_payload, dict) and str(tick_payload.get("status") or "") == "FAIL":
            status = "FAIL"
        job["status"] = status

        poll_rel = _write_poll_report(
            workspace_root=workspace_root,
            job=job,
            poll_count=poll_count,
            tick_payload=tick_payload,
            evidence_paths=evidence_paths,
        )
        job["last_poll_path"] = poll_rel
        last_poll_path = poll_rel
        poll_reports.append(poll_rel)

        if status == "DONE":
            closeout_rel = _write_closeout(workspace_root=workspace_root, job=job, last_poll_path=poll_rel)
            job["last_closeout_path"] = closeout_rel

        job["notes"] = sorted({n for n in job.get("notes", []) if isinstance(n, str) and n})
        _write_job_state(state_path, job)
        _upsert_job(index, _job_summary(job))
        _write_index(workspace_root, index)
        job_status = status
        if status in {"SKIP", "DONE", "FAIL"}:
            break

    return {
        "status": "OK",
        "workspace_root": str(workspace_root),
        "job_id": job_id,
        "job_status": job_status,
        "poll_reports": poll_reports,
        "job_path": str(state_path.relative_to(workspace_root)),
        "jobs_index_path": str(_index_path(workspace_root).relative_to(workspace_root)),
        "notes": sorted(set(idx_notes)),
        "last_poll_path": last_poll_path,
    }


def check_auto_run(*, workspace_root: Path) -> dict[str, Any]:
    index, idx_notes = _load_index(workspace_root)
    jobs = index.get("jobs") if isinstance(index.get("jobs"), list) else []
    jobs = [j for j in jobs if isinstance(j, dict)]
    jobs.sort(key=lambda j: str(j.get("job_id") or ""))
    latest = jobs[-1] if jobs else {}
    payload = {
        "status": "OK" if latest else "IDLE",
        "workspace_root": str(workspace_root),
        "job_id": latest.get("job_id") if isinstance(latest, dict) else "",
        "job_status": latest.get("status") if isinstance(latest, dict) else "",
        "last_poll_path": latest.get("last_poll_path") if isinstance(latest, dict) else "",
        "last_closeout_path": latest.get("last_closeout_path") if isinstance(latest, dict) else "",
        "jobs_index_path": str(_index_path(workspace_root).relative_to(workspace_root)),
        "notes": sorted(set(idx_notes)),
    }
    return payload
