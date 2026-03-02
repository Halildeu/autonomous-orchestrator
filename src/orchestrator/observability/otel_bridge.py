from __future__ import annotations

from pathlib import Path
from typing import Any

from src.ops.trace_meta import build_trace_meta
from src.orchestrator.runner_utils import hash_json_dir


def _rel_to_workspace(path: Path, workspace: Path) -> str:
    try:
        return path.resolve().relative_to(workspace.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _default_evidence_paths(*, workspace: Path, out_dir: Path, run_id: str) -> list[str]:
    base_rel = _rel_to_workspace(out_dir, workspace)
    prefix = run_id if base_rel in {"", "."} else f"{base_rel}/{run_id}"
    return [
        f"{prefix}/request.json",
        f"{prefix}/summary.json",
        f"{prefix}/provenance.v1.json",
        f"{prefix}/integrity.manifest.v1.json",
    ]


def attach_trace_meta(
    summary: dict[str, Any],
    *,
    workspace: Path,
    out_dir: Path,
    run_id: str,
) -> dict[str, Any]:
    existing = summary.get("trace_meta")
    if isinstance(existing, dict) and str(existing.get("run_id") or "") == str(run_id or ""):
        return existing

    policy_hash = None
    try:
        policy_hash = hash_json_dir(workspace, "policies")
    except Exception:
        policy_hash = None

    trace_meta = build_trace_meta(
        work_item_id=str(run_id or ""),
        work_item_kind="RUN",
        run_id=str(run_id or ""),
        policy_hash=policy_hash,
        evidence_paths=_default_evidence_paths(workspace=workspace, out_dir=out_dir, run_id=str(run_id or "")),
        workspace_root=str(workspace),
    )
    summary["trace_meta"] = trace_meta
    return trace_meta
