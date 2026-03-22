"""Context reconciliation controller for managed repo context management.

Implements the Kubernetes-style reconciliation loop:
  OBSERVE → COMPARE → ACT → REPORT

Designed to run within sync_managed_repo_standards.py when --sync-context is enabled.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


_CONTEXT_PUSH_ARTIFACTS = [
    ".cache/index/gap_register.v1.json",
    ".cache/index/work_intake.v1.json",
    ".cache/reports/system_status.v1.json",
    ".cache/index/extension_registry.v1.json",
    ".cache/index/session_cross_context.v1.json",
]


def reconcile_managed_repo(
    *,
    orchestrator_workspace: Path,
    target_workspace: Path,
    target_repo_root: Path,
    orchestrator_root: Path | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    """Full reconciliation cycle for a managed repo.

    Steps:
      1. OBSERVE: Detect drift (artifact, session, policy)
      2. COMPARE: Compute health score before
      3. ACT: Fix issues if apply=True
      4. REPORT: Compute health score after, generate report
    """
    actions_taken: list[dict[str, Any]] = []
    orch_root = orchestrator_root or orchestrator_workspace.parent.parent

    # ── STEP 1: OBSERVE ──
    from src.ops.context_drift import run_full_drift_detection

    drift_report = run_full_drift_detection(
        orchestrator_root=orch_root,
        orchestrator_workspace=orchestrator_workspace,
        target_root=target_repo_root,
        target_workspace=target_workspace,
    )

    # ── STEP 2: COMPARE (health before) ──
    from src.benchmark.eval_runner_runtime import _compute_context_health_lens

    health_before = _compute_context_health_lens(
        workspace_root=target_workspace,
        lenses_policy={},
    )

    # ── STEP 3: ACT (if apply) ──
    if apply:
        # 3a. Session reconciliation
        session_action = _reconcile_session(
            orchestrator_workspace=orchestrator_workspace,
            target_workspace=target_workspace,
        )
        if session_action:
            actions_taken.append(session_action)

        # 3b. Artifact push (stale or missing)
        artifact_drift = drift_report.get("artifact_drift", {})
        for art in artifact_drift.get("artifacts", []):
            if art.get("action") in ("drifted", "missing_in_target"):
                push_action = _push_artifact(
                    source_workspace=orchestrator_workspace,
                    target_workspace=target_workspace,
                    rel_path=art["path"],
                )
                if push_action:
                    actions_taken.append(push_action)

    # ── STEP 4: REPORT ──
    health_after = _compute_context_health_lens(
        workspace_root=target_workspace,
        lenses_policy={},
    )

    # Determine overall status
    if health_after.get("score", 0) >= 0.8:
        overall_status = "OK"
    elif health_after.get("score", 0) >= 0.5:
        overall_status = "WARN"
    else:
        overall_status = "FAIL"

    report = {
        "version": "v1",
        "generated_at": _now_iso(),
        "status": overall_status,
        "target_repo_root": str(target_repo_root),
        "target_workspace": str(target_workspace),
        "applied": apply,
        "drift_before": {
            "status": drift_report.get("status"),
            "drift_score": drift_report.get("drift_score"),
            "total_drifted": drift_report.get("total_drifted"),
        },
        "health_before": {
            "score": health_before.get("score"),
            "status": health_before.get("status"),
            "components": health_before.get("components"),
        },
        "health_after": {
            "score": health_after.get("score"),
            "status": health_after.get("status"),
            "components": health_after.get("components"),
        },
        "health_delta": round(
            float(health_after.get("score", 0)) - float(health_before.get("score", 0)), 4
        ),
        "actions_taken": actions_taken,
        "actions_count": len(actions_taken),
        "recommendations": _build_recommendations(health_after, drift_report),
    }

    # Write reconciliation report
    report_path = orchestrator_workspace / ".cache" / "reports" / "context_reconciliation_report.v1.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    return report


def _reconcile_session(
    *,
    orchestrator_workspace: Path,
    target_workspace: Path,
    session_id: str = "default",
) -> dict[str, Any] | None:
    """Reconcile session: renew if expired, link to parent, inherit decisions."""
    try:
        from src.session.context_store import (
            SessionContextError,
            SessionPaths,
            inherit_parent_decisions,
            is_expired,
            link_to_parent,
            load_context,
            new_context,
            renew_context,
            save_context_atomic,
        )
    except ImportError:
        return None

    parent_sp = SessionPaths(workspace_root=orchestrator_workspace, session_id=session_id)
    child_sp = SessionPaths(workspace_root=target_workspace, session_id=session_id)
    now_iso = _now_iso()

    if not parent_sp.context_path.exists():
        return {"action": "session_skip", "reason": "parent_not_found"}

    try:
        parent_ctx = load_context(parent_sp.context_path)
    except SessionContextError:
        return {"action": "session_skip", "reason": "parent_load_failed"}

    # Load or create child
    created = False
    try:
        if child_sp.context_path.exists():
            child_ctx = load_context(child_sp.context_path)
        else:
            child_ctx = new_context(session_id, str(target_workspace), 604800)
            created = True
    except SessionContextError:
        child_ctx = new_context(session_id, str(target_workspace), 604800)
        created = True

    # Renew if expired
    renewed = False
    if is_expired(child_ctx, now_iso):
        child_ctx = renew_context(child_ctx, 604800)
        renewed = True

    # Link to parent
    child_ctx = link_to_parent(child_ctx, parent_workspace_root=str(orchestrator_workspace))

    # Inherit decisions
    before = len(child_ctx.get("ephemeral_decisions", []))
    child_ctx = inherit_parent_decisions(child_ctx, parent_context=parent_ctx)
    inherited = len(child_ctx.get("ephemeral_decisions", [])) - before

    try:
        save_context_atomic(child_sp.context_path, child_ctx)
    except SessionContextError as e:
        return {"action": "session_save_failed", "error": e.error_code}

    return {
        "action": "session_reconciled",
        "created": created,
        "renewed": renewed,
        "inherited_decisions": inherited,
    }


def _push_artifact(
    *,
    source_workspace: Path,
    target_workspace: Path,
    rel_path: str,
) -> dict[str, Any] | None:
    """Push a single artifact from source to target workspace."""
    src = source_workspace / rel_path
    dst = target_workspace / rel_path
    if not src.exists():
        return None
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
        return {"action": "artifact_pushed", "path": rel_path}
    except Exception as e:
        return {"action": "artifact_push_failed", "path": rel_path, "error": str(e)[:100]}


def _build_recommendations(health: dict[str, Any], drift: dict[str, Any]) -> list[str]:
    """Generate actionable recommendations based on health and drift state."""
    recs: list[str] = []
    components = health.get("components", {})

    if components.get("session_freshness", {}).get("score", 0) < 20:
        recs.append("Renew or create session context (run session-init or sync --sync-context)")
    if components.get("decision_coverage", {}).get("score", 0) < 10:
        recs.append("Inherit parent decisions (run session-link-parent)")
    if components.get("artifact_completeness", {}).get("score", 0) < 20:
        recs.append("Push missing artifacts from orchestrator (run sync --sync-context --apply)")
    if drift.get("total_drifted", 0) > 0:
        recs.append(f"Resolve {drift['total_drifted']} drifted items (run sync --sync-context --apply)")

    return recs
