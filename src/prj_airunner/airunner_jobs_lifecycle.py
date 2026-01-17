from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

TERMINAL_STATUSES = {"PASS", "FAIL", "TIMEOUT", "KILLED", "SKIP"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    for key in ("updated_at", "started_at", "created_at"):
        ts = _parse_iso(str(job.get(key) or ""))
        if ts:
            return ts
    return datetime.fromtimestamp(0, tz=timezone.utc)


def _rel_to_workspace(path: Path, workspace_root: Path) -> str | None:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        return None


def _archive_root(workspace_root: Path, date_key: str, job_id: str) -> Path:
    return workspace_root / ".cache" / "airunner" / "archive" / date_key / job_id


def _archive_paths(
    *,
    workspace_root: Path,
    job_id: str,
    date_key: str,
    paths: list[str],
) -> list[str]:
    archived: list[str] = []
    archive_root = _archive_root(workspace_root, date_key, job_id)
    archive_root.mkdir(parents=True, exist_ok=True)

    for rel_path in paths:
        if not isinstance(rel_path, str) or not rel_path:
            continue
        abs_path = (workspace_root / rel_path).resolve() if not Path(rel_path).is_absolute() else Path(rel_path).resolve()
        rel = _rel_to_workspace(abs_path, workspace_root)
        if not rel:
            continue
        target = archive_root / abs_path.name
        try:
            if abs_path.exists():
                shutil.move(str(abs_path), str(target))
        except Exception:
            continue
        archived_rel = _rel_to_workspace(target, workspace_root)
        if archived_rel:
            archived.append(archived_rel)
    return archived


def closeout_jobs(
    *,
    workspace_root: Path,
    jobs: list[dict[str, Any]],
    closeout_ttl_days: int,
    keep_last_n: int,
) -> tuple[list[dict[str, Any]], dict[str, int], list[str]]:
    now = datetime.now(timezone.utc)
    ttl_days = max(0, int(closeout_ttl_days))
    limit = max(0, int(keep_last_n))

    archived_count = 0
    pruned_count = 0
    archive_paths: list[str] = []

    jobs_by_type: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for job in jobs:
        if not isinstance(job, dict):
            continue
        job_type = str(job.get("job_type") or job.get("kind") or "")
        bucket = "terminal" if str(job.get("status") or "") in TERMINAL_STATUSES else "active"
        jobs_by_type.setdefault(job_type, {"active": [], "terminal": []})
        jobs_by_type[job_type][bucket].append(job)

    kept: list[dict[str, Any]] = []

    for job_type, grouped in sorted(jobs_by_type.items(), key=lambda kv: kv[0]):
        active = grouped.get("active", [])
        terminal = grouped.get("terminal", [])
        terminal_sorted = sorted(
            terminal,
            key=lambda j: (-int(_job_time(j).timestamp()), str(j.get("job_id") or "")),
        )
        keep_terminal = terminal_sorted[:limit] if limit else terminal_sorted
        prune_terminal = terminal_sorted[len(keep_terminal) :] if limit else []

        kept.extend(active)
        kept.extend(keep_terminal)

        for job in prune_terminal:
            pruned_count += 1
            if str(job.get("status") or "") not in TERMINAL_STATUSES:
                continue
            if job.get("archived") is True:
                continue
            job_time = _job_time(job)
            if ttl_days and now - job_time < timedelta(days=ttl_days):
                continue
            date_key = job_time.date().isoformat()
            job_id = str(job.get("job_id") or "")
            evidence_paths = [str(p) for p in job.get("evidence_paths") if isinstance(p, str)] if isinstance(job.get("evidence_paths"), list) else []
            result_paths = [str(p) for p in job.get("result_paths") if isinstance(p, str)] if isinstance(job.get("result_paths"), list) else []
            archived = _archive_paths(
                workspace_root=workspace_root,
                job_id=job_id,
                date_key=date_key,
                paths=sorted({*evidence_paths, *result_paths}),
            )
            if archived:
                archive_paths.extend(archived)
                archived_count += 1
            job["archived"] = True
            job["archived_at"] = _now_iso()
            job["archive_root"] = _rel_to_workspace(_archive_root(workspace_root, date_key, job_id), workspace_root)

        for job in keep_terminal:
            if str(job.get("status") or "") not in TERMINAL_STATUSES:
                continue
            if job.get("archived") is True:
                continue
            job_time = _job_time(job)
            if ttl_days and now - job_time < timedelta(days=ttl_days):
                continue
            date_key = job_time.date().isoformat()
            job_id = str(job.get("job_id") or "")
            evidence_paths = [str(p) for p in job.get("evidence_paths") if isinstance(p, str)] if isinstance(job.get("evidence_paths"), list) else []
            result_paths = [str(p) for p in job.get("result_paths") if isinstance(p, str)] if isinstance(job.get("result_paths"), list) else []
            archived = _archive_paths(
                workspace_root=workspace_root,
                job_id=job_id,
                date_key=date_key,
                paths=sorted({*evidence_paths, *result_paths}),
            )
            if archived:
                archive_paths.extend(archived)
            job["archived"] = True
            job["archived_at"] = _now_iso()
            job["archive_root"] = _rel_to_workspace(_archive_root(workspace_root, date_key, job_id), workspace_root)
            archived_count += 1

    stats = {
        "archived": archived_count,
        "pruned": pruned_count,
    }
    return kept, stats, sorted(set(archive_paths))


def apply_poll_first(
    *,
    jobs: list[dict[str, Any]],
    max_poll: int,
) -> list[dict[str, Any]]:
    candidates = [j for j in jobs if isinstance(j, dict) and str(j.get("status") or "") in {"RUNNING", "QUEUED"}]
    candidates.sort(key=lambda j: (0 if str(j.get("status") or "") == "RUNNING" else 1, str(j.get("job_id") or "")))
    return candidates[: max(0, int(max_poll))]


def detect_stuck(
    *,
    job: dict[str, Any],
    now: datetime,
    max_polls_without_progress: int,
    stale_after_seconds: int,
) -> str | None:
    polls = int(job.get("polls_without_progress", 0) or 0)
    if max_polls_without_progress and polls >= max_polls_without_progress:
        return "MAX_POLLS"
    last_progress = _parse_iso(str(job.get("last_progress_at") or ""))
    if stale_after_seconds and last_progress and now - last_progress > timedelta(seconds=stale_after_seconds):
        return "STALE_AGE"
    return None


def cleanup_stuck_jobs(
    *,
    workspace_root: Path,
    jobs: list[dict[str, Any]],
    action_on_stale: str,
    max_polls_without_progress: int,
    stale_after_seconds: int,
) -> tuple[list[dict[str, Any]], dict[str, int], list[str]]:
    now = datetime.now(timezone.utc)
    archived = 0
    skipped = 0
    archive_paths: list[str] = []
    action = str(action_on_stale or "ARCHIVE").upper()

    for job in jobs:
        if not isinstance(job, dict):
            continue
        status = str(job.get("status") or "")
        if status not in {"QUEUED", "RUNNING"}:
            continue
        reason = detect_stuck(
            job=job,
            now=now,
            max_polls_without_progress=max_polls_without_progress,
            stale_after_seconds=stale_after_seconds,
        )
        if not reason:
            continue
        job["status"] = "SKIP"
        job["skip_reason"] = "STUCK_JOB"
        job["stale_reason"] = reason
        job["updated_at"] = _now_iso()
        job["last_poll_at"] = _now_iso()
        skipped += 1

        if action == "ARCHIVE":
            job_time = _job_time(job)
            date_key = job_time.date().isoformat()
            job_id = str(job.get("job_id") or "")
            evidence_paths = [str(p) for p in job.get("evidence_paths") if isinstance(p, str)] if isinstance(job.get("evidence_paths"), list) else []
            result_paths = [str(p) for p in job.get("result_paths") if isinstance(p, str)] if isinstance(job.get("result_paths"), list) else []
            archived_paths = _archive_paths(
                workspace_root=workspace_root,
                job_id=job_id,
                date_key=date_key,
                paths=sorted({*evidence_paths, *result_paths}),
            )
            if archived_paths:
                archive_paths.extend(archived_paths)
            job["archived"] = True
            job["archived_at"] = _now_iso()
            job["archive_root"] = _rel_to_workspace(_archive_root(workspace_root, date_key, job_id), workspace_root)
            archived += 1

    stats = {"archived": archived, "skipped": skipped}
    return jobs, stats, sorted(set(archive_paths))
