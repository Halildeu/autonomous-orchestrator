from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ensure_inside_workspace(workspace_root: Path, target: Path) -> None:
    workspace_root = workspace_root.resolve()
    target = target.resolve()
    target.relative_to(workspace_root)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _seed_json_if_missing(
    *,
    workspace_root: Path,
    rel_path: Path,
    payload: dict[str, Any],
    notes: list[str],
    label: str,
) -> None:
    abs_path = workspace_root / rel_path
    if abs_path.exists():
        return
    _ensure_inside_workspace(workspace_root, abs_path)
    _write_json(abs_path, payload)
    notes.append(f"artifact_seeded:{label}")


def _seed_text_if_missing(
    *,
    workspace_root: Path,
    rel_path: Path,
    text: str,
    notes: list[str],
    label: str,
) -> None:
    abs_path = workspace_root / rel_path
    if abs_path.exists():
        return
    _ensure_inside_workspace(workspace_root, abs_path)
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(text, encoding="utf-8")
    notes.append(f"artifact_seeded:{label}")


def _seed_jobs_index_payload(*, workspace_root: Path, generated_at: str, seed_tag: str) -> dict[str, Any]:
    return {
        "version": "v1",
        "generated_at": generated_at,
        "workspace_root": str(workspace_root),
        "status": "IDLE",
        "jobs": [],
        "counts": {"total": 0, "queued": 0, "running": 0, "pass": 0, "fail": 0, "timeout": 0, "killed": 0, "skip": 0},
        "notes": [f"seed:{seed_tag}"],
        "seed": True,
    }


def seed_source_artifacts(*, workspace_root: Path, policy: dict[str, Any], notes: list[str]) -> None:
    auto = policy.get("auto_remediation") if isinstance(policy.get("auto_remediation"), dict) else {}
    if not bool(auto.get("enabled", True)):
        return

    seed_tag = str(auto.get("seed_tag") or "work_intake_auto_remediation")
    generated_at = _now_iso()
    seed_manual_request_id = "SEED-WORK-INTAKE-AUTO"

    _seed_json_if_missing(
        workspace_root=workspace_root,
        rel_path=Path(".cache") / "reports" / "doc_graph_report.strict.v1.json",
        payload={
            "version": "v1",
            "generated_at": generated_at,
            "workspace_root": str(workspace_root),
            "status": "OK",
            "mode": "strict",
            "counts": {
                "broken_refs": 0,
                "critical_nav_gaps": 0,
                "orphan_critical": 0,
                "ambiguity": 0,
                "placeholder_refs_count": 0,
                "workspace_bound_refs_count": 0,
                "external_pointer_refs_count": 0,
            },
            "notes": [f"seed:{seed_tag}"],
            "top_broken": [],
            "top_orphans": [],
            "top_ambiguity": [],
            "top_placeholders": [],
            "seed": True,
        },
        notes=notes,
        label="doc_nav_strict",
    )

    _seed_json_if_missing(
        workspace_root=workspace_root,
        rel_path=Path(".cache") / "reports" / "integrity_verify.v1.json",
        payload={
            "version": "v1",
            "generated_at": generated_at,
            "workspace_root": str(workspace_root),
            "status": "OK",
            "notes": [f"seed:{seed_tag}"],
            "seed": True,
        },
        notes=notes,
        label="integrity_verify",
    )

    _seed_json_if_missing(
        workspace_root=workspace_root,
        rel_path=Path(".cache") / "reports" / "release_plan.v1.json",
        payload={
            "version": "v1",
            "generated_at": generated_at,
            "workspace_root": str(workspace_root),
            "status": "IDLE",
            "channel": "rc",
            "notes": [f"seed:{seed_tag}"],
            "seed": True,
        },
        notes=notes,
        label="release_plan",
    )
    _seed_json_if_missing(
        workspace_root=workspace_root,
        rel_path=Path(".cache") / "reports" / "release_manifest.v1.json",
        payload={
            "version": "v1",
            "generated_at": generated_at,
            "workspace_root": str(workspace_root),
            "status": "IDLE",
            "channel": "rc",
            "publish_allowed": False,
            "notes": [f"seed:{seed_tag}"],
            "seed": True,
        },
        notes=notes,
        label="release_manifest",
    )
    _seed_text_if_missing(
        workspace_root=workspace_root,
        rel_path=Path(".cache") / "reports" / "release_notes.v1.md",
        text=f"# Release Notes\n\n- seeded_by={seed_tag}\n",
        notes=notes,
        label="release_notes",
    )

    _seed_json_if_missing(
        workspace_root=workspace_root,
        rel_path=Path(".cache") / "reports" / "github_ops_report.v1.json",
        payload={
            "version": "v1",
            "generated_at": generated_at,
            "workspace_root": str(workspace_root),
            "status": "IDLE",
            "signals": [],
            "jobs_index_path": ".cache/github_ops/jobs_index.v1.json",
            "notes": [f"seed:{seed_tag}"],
            "seed": True,
        },
        notes=notes,
        label="github_ops_report",
    )
    _seed_json_if_missing(
        workspace_root=workspace_root,
        rel_path=Path(".cache") / "github_ops" / "jobs_index.v1.json",
        payload=_seed_jobs_index_payload(workspace_root=workspace_root, generated_at=generated_at, seed_tag=seed_tag),
        notes=notes,
        label="github_ops_jobs_index",
    )
    _seed_json_if_missing(
        workspace_root=workspace_root,
        rel_path=Path(".cache") / "deploy" / "jobs_index.v1.json",
        payload=_seed_jobs_index_payload(workspace_root=workspace_root, generated_at=generated_at, seed_tag=seed_tag),
        notes=notes,
        label="deploy_jobs_index",
    )
    _seed_json_if_missing(
        workspace_root=workspace_root,
        rel_path=Path(".cache") / "airunner" / "jobs_index.v1.json",
        payload=_seed_jobs_index_payload(workspace_root=workspace_root, generated_at=generated_at, seed_tag=seed_tag),
        notes=notes,
        label="airunner_jobs_index",
    )
    _seed_json_if_missing(
        workspace_root=workspace_root,
        rel_path=Path(".cache") / "reports" / "time_sinks.v1.json",
        payload={
            "version": "v1",
            "generated_at": generated_at,
            "workspace_root": str(workspace_root),
            "status": "IDLE",
            "sinks": [],
            "notes": [f"seed:{seed_tag}"],
            "seed": True,
        },
        notes=notes,
        label="time_sinks",
    )

    _seed_json_if_missing(
        workspace_root=workspace_root,
        rel_path=Path(".cache") / "reports" / "work_intake_exec_ticket.v1.json",
        payload={
            "version": "v1",
            "generated_at": generated_at,
            "workspace_root": str(workspace_root),
            "status": "IDLE",
            "entries": [],
            "applied_count": 0,
            "planned_count": 0,
            "idle_count": 0,
            "notes": [f"seed:{seed_tag}"],
            "seed": True,
        },
        notes=notes,
        label="work_intake_exec",
    )

    _seed_json_if_missing(
        workspace_root=workspace_root,
        rel_path=Path(".cache") / "script_budget" / "report.json",
        payload={
            "version": "v1",
            "generated_at": generated_at,
            "status": "OK",
            "exceeded_soft": [],
            "exceeded_hard": [],
            "notes": [f"seed:{seed_tag}"],
            "seed": True,
        },
        notes=notes,
        label="script_budget_report",
    )

    _seed_json_if_missing(
        workspace_root=workspace_root,
        rel_path=Path(".cache") / "index" / "gap_register.v1.json",
        payload={"version": "v1", "generated_at": generated_at, "gaps": [], "seed": True, "notes": [f"seed:{seed_tag}"]},
        notes=notes,
        label="gap_register",
    )
    _seed_json_if_missing(
        workspace_root=workspace_root,
        rel_path=Path(".cache") / "index" / "regression_index.v1.json",
        payload={
            "version": "v1",
            "generated_at": generated_at,
            "regressions": [],
            "seed": True,
            "notes": [f"seed:{seed_tag}"],
        },
        notes=notes,
        label="regression_index",
    )

    _seed_json_if_missing(
        workspace_root=workspace_root,
        rel_path=Path(".cache") / "reports" / "context_pack_router_result.v1.json",
        payload={
            "version": "v1",
            "generated_at": generated_at,
            "request_id": seed_manual_request_id,
            "bucket": "TICKET",
            "severity": "S4",
            "priority": "P4",
            "seed": True,
            "notes": [f"seed:{seed_tag}"],
        },
        notes=notes,
        label="context_pack_router_result",
    )

    _seed_json_if_missing(
        workspace_root=workspace_root,
        rel_path=Path(".cache") / "index" / "manual_requests" / f"{seed_manual_request_id}.v1.json",
        payload={
            "version": "v1",
            "request_id": seed_manual_request_id,
            "created_at": generated_at,
            "kind": "seed",
            "artifact_type": "seed",
            "domain": "ops",
            "impact_scope": "workspace-only",
            "seed": True,
            "text": "Auto remediation seed to keep manual request channel structurally available.",
        },
        notes=notes,
        label="manual_request_seed",
    )


_INFO_NOTE_PREFIXES = (
    "artifact_seeded:",
    "job_status_suppressed=",
    "github_ops_suppressed=",
    "deploy_job_suppressed=",
)

_INFO_NOTES = {
    "manual_requests_missing",
    "manual_requests_empty",
    "context_router_result_missing",
    "context_router_result_incomplete",
    "work_intake_exec_missing",
    "work_intake_exec_empty",
    "release_sources_empty",
    "github_ops_sources_empty",
    "deploy_jobs_sources_empty",
}


def note_is_warning(note: str) -> bool:
    value = str(note or "")
    if not value:
        return False
    if any(value.startswith(prefix) for prefix in _INFO_NOTE_PREFIXES):
        return False
    return value not in _INFO_NOTES
