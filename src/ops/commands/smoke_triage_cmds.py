from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.ops.commands.common import warn
from src.ops.commands.extension_cmds_helpers_v2 import _resolve_workspace_root
from src.ops.reaper import parse_bool as parse_reaper_bool


def _job_report_path(workspace_root: Path, job_id: str) -> Path:
    return workspace_root / ".cache" / "reports" / "github_ops_jobs" / f"github_ops_job_{job_id}.v1.json"


def _resolve_latest_job_id(workspace_root: Path, *, kind: str | None) -> str | None:
    jobs_index_path = workspace_root / ".cache" / "github_ops" / "jobs_index.v1.json"
    if not jobs_index_path.exists():
        return None
    try:
        obj = json.loads(jobs_index_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    jobs = obj.get("jobs") if isinstance(obj, dict) else None
    if not isinstance(jobs, list):
        return None
    filtered = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        if kind:
            job_kind = str(job.get("kind") or "").upper()
            if job_kind and job_kind != kind.upper():
                continue
        filtered.append(job)
    filtered.sort(key=lambda j: (str(j.get("started_at") or ""), str(j.get("job_id") or "")), reverse=True)
    for job in filtered:
        job_id = str(job.get("job_id") or "").strip()
        if not job_id:
            continue
        if _job_report_path(workspace_root, job_id).exists():
            return job_id
    return None


def cmd_smoke_full_triage(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    job_id = str(getattr(args, "job_id", "") or "").strip()
    if job_id.lower() == "latest":
        job_id = _resolve_latest_job_id(ws, kind="SMOKE_FULL") or ""
    if not job_id:
        warn("FAIL error=JOB_ID_REQUIRED")
        return 2

    chat = parse_reaper_bool(str(getattr(args, "chat", "true")))
    detail = parse_reaper_bool(str(getattr(args, "detail", "false")))

    from src.prj_github_ops.smoke_full_triage import run_smoke_full_triage

    payload = run_smoke_full_triage(workspace_root=ws, job_id=job_id, detail=detail)
    if chat and isinstance(payload, dict):
        preview_lines = [
            "PROGRAM-LED: smoke-full-triage",
            f"workspace_root={ws}",
            f"job_id={job_id}",
        ]
        result_lines = [
            f"status={payload.get('status')}",
            f"recommended_class={payload.get('recommended_class')}",
            f"signature_hash={payload.get('signature_hash')}",
        ]
        evidence_lines = [
            str(payload.get("report_path") or ""),
            str(payload.get("catalog_parse_path") or ""),
        ]
        actions_lines = ["github-ops-job-poll", "system-status", "work-intake-check"]
        next_lines = ["Devam et", "Durumu goster", "Duraklat"]

        print("PREVIEW:")
        print("\n".join(preview_lines))
        print("RESULT:")
        print("\n".join(result_lines))
        print("EVIDENCE:")
        print("\n".join([e for e in evidence_lines if e]))
        print("ACTIONS:")
        print("\n".join(actions_lines))
        print("NEXT:")
        print("\n".join(next_lines))

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    status = payload.get("status") if isinstance(payload, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_smoke_fast_triage(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    job_id = str(getattr(args, "job_id", "") or "").strip()
    if job_id.lower() == "latest":
        job_id = _resolve_latest_job_id(ws, kind="SMOKE_FAST") or ""
    if not job_id:
        warn("FAIL error=JOB_ID_REQUIRED")
        return 2

    chat = parse_reaper_bool(str(getattr(args, "chat", "true")))
    detail = parse_reaper_bool(str(getattr(args, "detail", "false")))

    from src.prj_github_ops.smoke_fast_triage import run_smoke_fast_triage

    payload = run_smoke_fast_triage(workspace_root=ws, job_id=job_id, detail=detail)
    if chat and isinstance(payload, dict):
        preview_lines = [
            "PROGRAM-LED: smoke-fast-triage",
            f"workspace_root={ws}",
            f"job_id={job_id}",
        ]
        result_lines = [
            f"status={payload.get('status')}",
            f"recommended_class={payload.get('recommended_class')}",
            f"signature_hash={payload.get('signature_hash')}",
        ]
        evidence_lines = [str(payload.get("report_path") or "")]
        actions_lines = ["github-ops-job-poll", "system-status", "work-intake-check"]
        next_lines = ["Devam et", "Durumu goster", "Duraklat"]

        print("PREVIEW:")
        print("\n".join(preview_lines))
        print("RESULT:")
        print("\n".join(result_lines))
        print("EVIDENCE:")
        print("\n".join([e for e in evidence_lines if e]))
        print("ACTIONS:")
        print("\n".join(actions_lines))
        print("NEXT:")
        print("\n".join(next_lines))

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    status = payload.get("status") if isinstance(payload, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE"} else 2
