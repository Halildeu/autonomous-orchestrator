from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _jobs_index_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "doc_nav" / "jobs_index.v1.json"


def _job_store_dir(workspace_root: Path, job_id: str) -> Path:
    return workspace_root / ".cache" / "doc_nav" / "jobs" / job_id


def _job_report_path(workspace_root: Path, job_id: str) -> Path:
    return workspace_root / ".cache" / "reports" / "doc_nav_jobs" / f"doc_nav_job_{job_id}.v1.json"


def _load_jobs_index(workspace_root: Path) -> dict[str, Any]:
    path = _jobs_index_path(workspace_root)
    if not path.exists():
        return {"version": "v1", "workspace_root": str(workspace_root), "jobs": [], "counts": {}}
    try:
        obj = _load_json(path)
    except Exception:
        return {"version": "v1", "workspace_root": str(workspace_root), "jobs": [], "counts": {}}
    if not isinstance(obj, dict):
        return {"version": "v1", "workspace_root": str(workspace_root), "jobs": [], "counts": {}}
    if not isinstance(obj.get("jobs"), list):
        obj["jobs"] = []
    return obj


def _job_time(job: dict[str, Any]) -> str:
    for key in ("updated_at", "last_poll_at", "started_at", "created_at"):
        val = job.get(key)
        if isinstance(val, str) and val:
            return val
    return ""


def _save_jobs_index(workspace_root: Path, index: dict[str, Any]) -> str:
    jobs = [j for j in index.get("jobs") if isinstance(j, dict)]
    jobs.sort(key=lambda j: (str(j.get("created_at") or ""), str(j.get("job_id") or "")))
    counts = {"total": 0, "running": 0, "ok": 0, "warn": 0, "fail": 0, "unknown": 0}
    for job in jobs:
        status = str(job.get("status") or "").upper()
        counts["total"] += 1
        if status == "RUNNING":
            counts["running"] += 1
        elif status == "OK":
            counts["ok"] += 1
        elif status == "WARN":
            counts["warn"] += 1
        elif status == "FAIL":
            counts["fail"] += 1
        else:
            counts["unknown"] += 1
    index["jobs"] = jobs
    index["counts"] = counts
    index["generated_at"] = _now_iso()
    index.setdefault("version", "v1")
    index.setdefault("workspace_root", str(workspace_root))
    path = _jobs_index_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_json(index), encoding="utf-8")
    rel = Path(".cache") / "doc_nav" / path.name
    return rel.as_posix()


def _write_job_report(workspace_root: Path, job: dict[str, Any]) -> str:
    path = _job_report_path(workspace_root, str(job.get("job_id") or "unknown"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_json(job), encoding="utf-8")
    return (Path(".cache") / "reports" / "doc_nav_jobs" / path.name).as_posix()


def _pid_running(pid: int | None) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def doc_nav_job_start(*, workspace_root: Path, strict: bool, detail: bool) -> dict[str, Any]:
    index = _load_jobs_index(workspace_root)
    jobs = [j for j in index.get("jobs") if isinstance(j, dict)]
    for job in jobs:
        if str(job.get("kind") or "") == "DOC_NAV" and str(job.get("status") or "") == "RUNNING":
            return {
                "status": "ALREADY_RUNNING",
                "job_id": job.get("job_id"),
                "job_report_path": job.get("job_report_path"),
                "jobs_index_path": str(Path(".cache") / "doc_nav" / "jobs_index.v1.json"),
            }

    created_at = _now_iso()
    job_id = _hash_text(f"DOC_NAV|{created_at}|{strict}|{detail}")[:32]
    report_rel = ".cache/reports/doc_graph_report.strict.v1.json" if strict else ".cache/reports/doc_graph_report.v1.json"

    store_dir = _job_store_dir(workspace_root, job_id)
    store_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = store_dir / "stdout.log"
    stderr_path = store_dir / "stderr.log"

    cmd = [
        sys.executable,
        "-m",
        "src.ops.manage",
        "doc-nav-check",
        "--workspace-root",
        str(workspace_root),
        "--strict",
        "true" if strict else "false",
        "--detail",
        "true" if detail else "false",
        "--chat",
        "false",
    ]

    try:
        stdout_handle = stdout_path.open("w", encoding="utf-8")
        stderr_handle = stderr_path.open("w", encoding="utf-8")
        proc = subprocess.Popen(cmd, cwd=repo_root(), text=True, stdout=stdout_handle, stderr=stderr_handle)
    except Exception as exc:
        return {"status": "FAIL", "error_code": "JOB_START_FAILED", "message": str(exc)[:200]}

    job = {
        "job_id": job_id,
        "kind": "DOC_NAV",
        "status": "RUNNING",
        "created_at": created_at,
        "started_at": created_at,
        "pid": int(proc.pid),
        "strict": bool(strict),
        "detail": bool(detail),
        "report_path": report_rel,
        "stdout_path": str(Path(".cache") / "doc_nav" / "jobs" / job_id / "stdout.log"),
        "stderr_path": str(Path(".cache") / "doc_nav" / "jobs" / job_id / "stderr.log"),
    }
    job["job_report_path"] = _write_job_report(workspace_root, job)
    jobs.append(job)
    index["jobs"] = jobs
    jobs_index_rel = _save_jobs_index(workspace_root, index)

    return {
        "status": "OK",
        "job_id": job_id,
        "job_report_path": job["job_report_path"],
        "jobs_index_path": jobs_index_rel,
        "report_path": report_rel,
    }


def doc_nav_job_poll(*, workspace_root: Path, job_id: str) -> dict[str, Any]:
    job_id = str(job_id or "").strip()
    if not job_id:
        return {"status": "FAIL", "error_code": "JOB_ID_REQUIRED"}
    report_path = _job_report_path(workspace_root, job_id)
    if not report_path.exists():
        return {"status": "FAIL", "error_code": "JOB_REPORT_MISSING", "job_id": job_id}
    try:
        job = _load_json(report_path)
    except Exception:
        return {"status": "FAIL", "error_code": "JOB_REPORT_INVALID", "job_id": job_id}
    if not isinstance(job, dict):
        return {"status": "FAIL", "error_code": "JOB_REPORT_INVALID", "job_id": job_id}

    job.setdefault("job_id", job_id)
    job.setdefault("kind", "DOC_NAV")
    job.setdefault("status", "RUNNING")
    job["last_poll_at"] = _now_iso()

    status = str(job.get("status") or "")
    if status != "RUNNING":
        job["job_report_path"] = _write_job_report(workspace_root, job)
        index = _load_jobs_index(workspace_root)
        jobs = [j for j in index.get("jobs") if isinstance(j, dict)]
        replaced = False
        for idx, existing in enumerate(jobs):
            if str(existing.get("job_id") or "") == job_id:
                jobs[idx] = job
                replaced = True
                break
        if not replaced:
            jobs.append(job)
        index["jobs"] = jobs
        job["jobs_index_path"] = _save_jobs_index(workspace_root, index)
        return job

    pid = int(job.get("pid") or 0) or None
    if _pid_running(pid):
        job["job_report_path"] = _write_job_report(workspace_root, job)
        index = _load_jobs_index(workspace_root)
        jobs = [j for j in index.get("jobs") if isinstance(j, dict)]
        for idx, existing in enumerate(jobs):
            if str(existing.get("job_id") or "") == job_id:
                jobs[idx] = job
                break
        index["jobs"] = jobs
        job["jobs_index_path"] = _save_jobs_index(workspace_root, index)
        return job

    report_rel = str(job.get("report_path") or "")
    report_abs = (workspace_root / report_rel).resolve() if report_rel else None
    result_status = "WARN"
    error_code = None
    if report_abs and report_abs.exists():
        try:
            obj = _load_json(report_abs)
            if isinstance(obj, dict):
                result_status = str(obj.get("status") or "WARN")
        except Exception:
            result_status = "WARN"
            error_code = "DOC_NAV_REPORT_INVALID"
    else:
        error_code = "DOC_NAV_REPORT_MISSING"

    job["status"] = result_status
    job["completed_at"] = _now_iso()
    if error_code:
        job["error_code"] = error_code

    job["job_report_path"] = _write_job_report(workspace_root, job)
    index = _load_jobs_index(workspace_root)
    jobs = [j for j in index.get("jobs") if isinstance(j, dict)]
    replaced = False
    for idx, existing in enumerate(jobs):
        if str(existing.get("job_id") or "") == job_id:
            jobs[idx] = job
            replaced = True
            break
    if not replaced:
        jobs.append(job)
    index["jobs"] = jobs
    job["jobs_index_path"] = _save_jobs_index(workspace_root, index)
    return job
