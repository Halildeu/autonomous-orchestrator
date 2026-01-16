from __future__ import annotations

import argparse
import json

from src.ops.commands.common import warn
from src.ops.commands.extension_cmds_helpers_v2 import _resolve_workspace_root
from src.ops.reaper import parse_bool as parse_reaper_bool


def cmd_smoke_full_triage(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    job_id = str(getattr(args, "job_id", "") or "").strip()
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
