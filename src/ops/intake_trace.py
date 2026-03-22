"""Build request intake-to-execution trace artifact.

Output: .cache/reports/request_intake_to_exec_trace.v1.json
Referenced by: policy_context_orchestration.v1.json → outputs.workspace_reports
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_intake_to_exec_trace(
    *,
    workspace_root: Path,
    request_id: str,
    routing_result: dict[str, Any],
    exec_summary: dict[str, Any],
) -> dict[str, Any]:
    """Build end-to-end trace from intake to execution."""
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    trace: dict[str, Any] = {
        "version": "v1",
        "generated_at": now,
        "request_id": request_id,
        "routing": {
            "bucket": str(routing_result.get("bucket") or ""),
            "action": str(routing_result.get("action") or ""),
        },
        "execution": {
            "run_id": str(exec_summary.get("run_id") or ""),
            "result_state": str(exec_summary.get("result_state") or ""),
            "workflow_id": str(exec_summary.get("workflow_id") or ""),
            "provider_used": str(exec_summary.get("provider_used") or ""),
        },
        "session_id": "default",
    }
    return trace


def write_intake_to_exec_trace(
    *,
    workspace_root: Path,
    request_id: str,
    routing_result: dict[str, Any],
    exec_summary: dict[str, Any],
) -> Path | None:
    """Build and write intake-to-exec trace. Returns path on success, None on failure."""
    try:
        trace = build_intake_to_exec_trace(
            workspace_root=workspace_root,
            request_id=request_id,
            routing_result=routing_result,
            exec_summary=exec_summary,
        )
        out_path = workspace_root / ".cache" / "reports" / "request_intake_to_exec_trace.v1.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(trace, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return out_path
    except Exception:
        return None
