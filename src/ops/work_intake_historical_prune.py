from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_DEFAULT_POLICY: dict[str, Any] = {
    "version": "v1",
    "enabled": True,
    "auto_run_on_work_intake_check": True,
    "github_ops": {
        "enabled": True,
        "prune_superseded_by_pass": True,
        "archive_reason": "SUPERSEDED_BY_PASS",
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def _term_time(job: dict[str, Any]) -> datetime:
    raw = str(job.get("updated_at") or job.get("last_poll_at") or job.get("started_at") or job.get("created_at") or "")
    return _parse_iso(raw) or datetime.fromtimestamp(0, tz=timezone.utc)


def _policy_paths(*, core_root: Path, workspace_root: Path) -> tuple[Path, Path]:
    return (
        core_root / "policies" / "policy_work_intake_historical_prune.v1.json",
        workspace_root / "policies" / "policy_work_intake_historical_prune.v1.json",
    )


def load_policy(*, core_root: Path, workspace_root: Path) -> tuple[dict[str, Any], str]:
    core_path, ws_path = _policy_paths(core_root=core_root, workspace_root=workspace_root)
    selected = ws_path if ws_path.exists() else core_path
    if not selected.exists():
        return dict(_DEFAULT_POLICY), "defaults"
    try:
        obj = _load_json(selected)
    except Exception:
        return dict(_DEFAULT_POLICY), f"fallback_invalid:{selected.as_posix()}"
    if not isinstance(obj, dict):
        return dict(_DEFAULT_POLICY), f"fallback_shape:{selected.as_posix()}"
    merged = dict(_DEFAULT_POLICY)
    merged.update(obj)
    core_block = _DEFAULT_POLICY.get("github_ops") if isinstance(_DEFAULT_POLICY.get("github_ops"), dict) else {}
    ext_block = obj.get("github_ops") if isinstance(obj.get("github_ops"), dict) else {}
    merged["github_ops"] = {**core_block, **ext_block}
    return merged, selected.relative_to(core_root).as_posix() if selected.is_relative_to(core_root) else selected.as_posix()


def _recount_jobs(jobs: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"total": 0, "queued": 0, "running": 0, "pass": 0, "fail": 0, "timeout": 0, "killed": 0, "skip": 0}
    for job in jobs:
        if bool(job.get("archived")) or str(job.get("status") or "").upper() == "ARCHIVED":
            continue
        status = str(job.get("status") or "").upper()
        counts["total"] += 1
        if status in {"QUEUED", "RUNNING", "PASS", "FAIL", "TIMEOUT", "KILLED", "SKIP"}:
            counts[status.lower()] += 1
    return counts


def _find_superseded_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    terminal = {"PASS", "FAIL", "TIMEOUT", "KILLED", "SKIP"}
    latest_by_key: dict[str, dict[str, Any]] = {}
    latest_meta: dict[str, tuple[datetime, str]] = {}
    latest_pass_by_kind: dict[str, tuple[datetime, str]] = {}

    active_jobs = [j for j in jobs if isinstance(j, dict) and not bool(j.get("archived")) and str(j.get("status") or "").upper() != "ARCHIVED"]
    for job in active_jobs:
        status = str(job.get("status") or "").upper()
        if status not in terminal:
            continue
        job_id = str(job.get("job_id") or "")
        kind = str(job.get("kind") or "")
        if not job_id or not kind:
            continue
        signature_hash = str(job.get("signature_hash") or "")
        key = f"{kind}|{signature_hash}" if signature_hash else f"id:{job_id}"
        meta = (_term_time(job), job_id)
        if status == "PASS":
            prev_pass = latest_pass_by_kind.get(kind)
            if prev_pass is None or meta > prev_pass:
                latest_pass_by_kind[kind] = meta
        prev_meta = latest_meta.get(key)
        if prev_meta is None or meta > prev_meta:
            latest_meta[key] = meta
            latest_by_key[key] = job

    candidates: list[dict[str, Any]] = []
    for key, job in sorted(latest_by_key.items(), key=lambda x: x[0]):
        status = str(job.get("status") or "").upper()
        if status not in {"FAIL", "TIMEOUT", "KILLED", "SKIP"}:
            continue
        job_id = str(job.get("job_id") or "")
        kind = str(job.get("kind") or "")
        if not job_id or not kind:
            continue
        pass_meta = latest_pass_by_kind.get(kind)
        cur_meta = (_term_time(job), job_id)
        if pass_meta and pass_meta > cur_meta:
            candidates.append(job)
    return candidates


def run_work_intake_historical_prune(
    *,
    workspace_root: Path,
    core_root: Path,
    dry_run: bool = False,
    trigger: str = "manual",
) -> dict[str, Any]:
    generated_at = _now_iso()
    report_rel = str(Path(".cache") / "reports" / "work_intake_historical_prune.v1.json")
    report_path = workspace_root / report_rel

    policy, policy_source = load_policy(core_root=core_root, workspace_root=workspace_root)
    if not bool(policy.get("enabled", True)):
        payload = {
            "status": "IDLE",
            "generated_at": generated_at,
            "workspace_root": str(workspace_root),
            "policy_source": policy_source,
            "dry_run": bool(dry_run),
            "trigger": trigger,
            "archived_count": 0,
            "candidates_count": 0,
            "jobs_index_path": str(Path(".cache") / "github_ops" / "jobs_index.v1.json"),
            "notes": ["policy_disabled"],
            "report_path": report_rel,
        }
        _write_json(report_path, payload)
        return payload

    jobs_index_rel = str(Path(".cache") / "github_ops" / "jobs_index.v1.json")
    jobs_index_path = workspace_root / jobs_index_rel
    if not jobs_index_path.exists():
        payload = {
            "status": "IDLE",
            "generated_at": generated_at,
            "workspace_root": str(workspace_root),
            "policy_source": policy_source,
            "dry_run": bool(dry_run),
            "trigger": trigger,
            "archived_count": 0,
            "candidates_count": 0,
            "jobs_index_path": jobs_index_rel,
            "notes": ["github_ops_jobs_index_missing"],
            "report_path": report_rel,
        }
        _write_json(report_path, payload)
        return payload

    try:
        index_obj = _load_json(jobs_index_path)
    except Exception:
        payload = {
            "status": "WARN",
            "generated_at": generated_at,
            "workspace_root": str(workspace_root),
            "policy_source": policy_source,
            "dry_run": bool(dry_run),
            "trigger": trigger,
            "archived_count": 0,
            "candidates_count": 0,
            "jobs_index_path": jobs_index_rel,
            "notes": ["github_ops_jobs_index_invalid"],
            "report_path": report_rel,
        }
        _write_json(report_path, payload)
        return payload

    jobs = index_obj.get("jobs") if isinstance(index_obj, dict) else None
    if not isinstance(jobs, list):
        payload = {
            "status": "IDLE",
            "generated_at": generated_at,
            "workspace_root": str(workspace_root),
            "policy_source": policy_source,
            "dry_run": bool(dry_run),
            "trigger": trigger,
            "archived_count": 0,
            "candidates_count": 0,
            "jobs_index_path": jobs_index_rel,
            "notes": ["github_ops_jobs_index_empty"],
            "report_path": report_rel,
        }
        _write_json(report_path, payload)
        return payload

    gh_policy = policy.get("github_ops") if isinstance(policy.get("github_ops"), dict) else {}
    if not bool(gh_policy.get("enabled", True)) or not bool(gh_policy.get("prune_superseded_by_pass", True)):
        payload = {
            "status": "IDLE",
            "generated_at": generated_at,
            "workspace_root": str(workspace_root),
            "policy_source": policy_source,
            "dry_run": bool(dry_run),
            "trigger": trigger,
            "archived_count": 0,
            "candidates_count": 0,
            "jobs_index_path": jobs_index_rel,
            "notes": ["github_ops_prune_disabled"],
            "report_path": report_rel,
        }
        _write_json(report_path, payload)
        return payload

    candidates = _find_superseded_jobs([j for j in jobs if isinstance(j, dict)])
    candidate_ids = sorted({str(j.get("job_id") or "") for j in candidates if str(j.get("job_id") or "")})
    archive_reason = str(gh_policy.get("archive_reason") or "SUPERSEDED_BY_PASS")

    archived_ids: list[str] = []
    if not dry_run and candidate_ids:
        archive_set = set(candidate_ids)
        for job in jobs:
            if not isinstance(job, dict):
                continue
            job_id = str(job.get("job_id") or "")
            if job_id not in archive_set:
                continue
            job["archived"] = True
            job["status"] = "ARCHIVED"
            job["archived_at"] = generated_at
            job["archived_reason"] = archive_reason
            archived_ids.append(job_id)

        index_obj["jobs"] = jobs
        index_obj["counts"] = _recount_jobs([j for j in jobs if isinstance(j, dict)])
        index_obj["generated_at"] = generated_at
        notes = index_obj.get("notes") if isinstance(index_obj.get("notes"), list) else []
        note_set = {str(n) for n in notes if isinstance(n, str)}
        note_set.add(f"github_ops_pruned_archived={len(archived_ids)}")
        index_obj["notes"] = sorted(note_set)
        _write_json(jobs_index_path, index_obj)

    status = "OK"
    if dry_run and candidate_ids:
        status = "WOULD_WRITE"
    elif not candidate_ids:
        status = "IDLE"

    payload = {
        "status": status,
        "generated_at": generated_at,
        "workspace_root": str(workspace_root),
        "policy_source": policy_source,
        "dry_run": bool(dry_run),
        "trigger": trigger,
        "archived_count": len(archived_ids),
        "candidates_count": len(candidate_ids),
        "candidate_job_ids": candidate_ids,
        "archived_job_ids": sorted(archived_ids),
        "jobs_index_path": jobs_index_rel,
        "report_path": report_rel,
        "notes": ["PROGRAM_LED=true", f"archive_reason={archive_reason}"],
    }
    _write_json(report_path, payload)
    return payload
