"""Content drift detection for managed repo context management.

Compares SHA256 hashes of context artifacts, session decisions, and policy files
between orchestrator (source) and managed repo (target) workspaces.

Output: .cache/reports/context_drift_report.v1.json
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


_CONTEXT_ARTIFACT_PATHS = [
    ".cache/index/gap_register.v1.json",
    ".cache/index/work_intake.v1.json",
    ".cache/reports/system_status.v1.json",
    ".cache/index/extension_registry.v1.json",
    ".cache/index/session_cross_context.v1.json",
]

_DEFAULT_POLICY_PATHS = [
    "policies/policy_context_orchestration.v1.json",
    "policies/policy_work_intake.v1.json",
    "policies/policy_pm_suite.v1.json",
    "policies/policy_llm_providers_guardrails.v1.json",
    "policies/policy_security.v1.json",
    "policies/policy_ui_design_system.v1.json",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _file_sha256(path: Path) -> str | None:
    """Compute SHA256 hash of a file. Returns None if file doesn't exist."""
    if not path.exists() or not path.is_file():
        return None
    return sha256(path.read_bytes()).hexdigest()


def detect_context_drift(
    *,
    source_workspace: Path,
    target_workspace: Path,
    artifact_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Compare SHA256 hashes of context artifacts between workspaces.

    Returns drift report with per-artifact status.
    """
    paths = artifact_paths if artifact_paths is not None else _CONTEXT_ARTIFACT_PATHS
    artifacts: list[dict[str, Any]] = []
    drifted = 0
    missing_in_target = 0
    missing_in_source = 0

    for rel in paths:
        src = source_workspace / rel
        tgt = target_workspace / rel
        src_hash = _file_sha256(src)
        tgt_hash = _file_sha256(tgt)

        if src_hash is None and tgt_hash is None:
            action = "both_missing"
        elif src_hash is None:
            action = "missing_in_source"
            missing_in_source += 1
        elif tgt_hash is None:
            action = "missing_in_target"
            missing_in_target += 1
            drifted += 1
        elif src_hash != tgt_hash:
            action = "drifted"
            drifted += 1
        else:
            action = "in_sync"

        artifacts.append({
            "path": rel,
            "source_hash": src_hash or "",
            "target_hash": tgt_hash or "",
            "action": action,
        })

    status = "OK" if drifted == 0 else ("WARN" if drifted <= 2 else "FAIL")
    return {
        "drift_type": "artifact",
        "status": status,
        "generated_at": _now_iso(),
        "source_workspace": str(source_workspace),
        "target_workspace": str(target_workspace),
        "total_checked": len(paths),
        "drifted_count": drifted,
        "missing_in_target": missing_in_target,
        "missing_in_source": missing_in_source,
        "in_sync_count": len(paths) - drifted - missing_in_source,
        "artifacts": artifacts,
    }


def detect_session_drift(
    *,
    parent_workspace: Path,
    child_workspace: Path,
    session_id: str = "default",
) -> dict[str, Any]:
    """Compare parent vs child session decisions for coherence.

    Checks: missing decisions in child, stale decisions, key conflicts.
    """
    from src.session.context_store import SessionContextError, SessionPaths, is_expired, load_context

    parent_sp = SessionPaths(workspace_root=parent_workspace, session_id=session_id)
    child_sp = SessionPaths(workspace_root=child_workspace, session_id=session_id)
    now_iso = _now_iso()

    result: dict[str, Any] = {
        "drift_type": "session",
        "status": "OK",
        "generated_at": now_iso,
        "parent_workspace": str(parent_workspace),
        "child_workspace": str(child_workspace),
        "session_id": session_id,
        "parent_exists": parent_sp.context_path.exists(),
        "child_exists": child_sp.context_path.exists(),
        "parent_expired": False,
        "child_expired": False,
        "parent_linked": False,
        "missing_in_child": 0,
        "stale_in_child": 0,
        "conflict_count": 0,
        "child_only_count": 0,
        "details": [],
    }

    if not parent_sp.context_path.exists():
        result["status"] = "WARN"
        result["details"].append("parent session not found")
        return result

    try:
        parent_ctx = load_context(parent_sp.context_path)
    except SessionContextError:
        result["status"] = "WARN"
        result["details"].append("parent session load failed")
        return result

    result["parent_expired"] = is_expired(parent_ctx, now_iso)

    if not child_sp.context_path.exists():
        result["status"] = "FAIL"
        result["child_exists"] = False
        result["details"].append("child session not found")
        parent_decisions = parent_ctx.get("ephemeral_decisions", [])
        result["missing_in_child"] = len([d for d in parent_decisions if isinstance(d, dict)])
        return result

    try:
        child_ctx = load_context(child_sp.context_path)
    except SessionContextError:
        result["status"] = "FAIL"
        result["details"].append("child session load failed")
        return result

    result["child_expired"] = is_expired(child_ctx, now_iso)

    # Check parent link
    parent_ref = child_ctx.get("parent_session_ref")
    result["parent_linked"] = isinstance(parent_ref, dict) and bool(parent_ref.get("workspace_root"))

    # Compare decisions
    parent_decisions = parent_ctx.get("ephemeral_decisions", [])
    child_decisions = child_ctx.get("ephemeral_decisions", [])

    if not isinstance(parent_decisions, list):
        parent_decisions = []
    if not isinstance(child_decisions, list):
        child_decisions = []

    parent_keys = {str(d.get("key") or ""): d for d in parent_decisions if isinstance(d, dict) and d.get("key")}
    child_keys = {str(d.get("key") or ""): d for d in child_decisions if isinstance(d, dict) and d.get("key")}

    missing = 0
    stale = 0
    conflicts = 0
    child_only = 0

    for key, pd in parent_keys.items():
        if key not in child_keys:
            missing += 1
        else:
            cd = child_keys[key]
            p_val = json.dumps(pd.get("value"), sort_keys=True, ensure_ascii=True)
            c_val = json.dumps(cd.get("value"), sort_keys=True, ensure_ascii=True)
            if p_val != c_val:
                conflicts += 1

    for key in child_keys:
        if key not in parent_keys:
            child_only += 1

    result["missing_in_child"] = missing
    result["stale_in_child"] = stale
    result["conflict_count"] = conflicts
    result["child_only_count"] = child_only

    if result["child_expired"]:
        result["status"] = "FAIL"
    elif missing > len(parent_keys) // 2 and len(parent_keys) > 0:
        result["status"] = "FAIL"
    elif missing > 0:
        result["status"] = "WARN"

    return result


def detect_policy_drift(
    *,
    source_root: Path,
    target_root: Path,
    policy_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Compare policy file hashes between repos."""
    paths = policy_paths if policy_paths is not None else _DEFAULT_POLICY_PATHS
    drifted_policies: list[dict[str, Any]] = []
    checked = 0

    for rel in paths:
        src = source_root / rel
        tgt = target_root / rel
        src_hash = _file_sha256(src)
        tgt_hash = _file_sha256(tgt)

        if src_hash is None:
            continue  # Source doesn't have it, skip
        checked += 1

        if tgt_hash is None:
            drifted_policies.append({"path": rel, "source_hash": src_hash, "target_hash": "", "action": "missing_in_target"})
        elif src_hash != tgt_hash:
            drifted_policies.append({"path": rel, "source_hash": src_hash, "target_hash": tgt_hash, "action": "drifted"})

    status = "OK" if not drifted_policies else ("WARN" if len(drifted_policies) <= 2 else "FAIL")
    return {
        "drift_type": "policy",
        "status": status,
        "generated_at": _now_iso(),
        "source_root": str(source_root),
        "target_root": str(target_root),
        "total_checked": checked,
        "drifted_count": len(drifted_policies),
        "drifted_policies": drifted_policies,
    }


def run_full_drift_detection(
    *,
    orchestrator_root: Path,
    orchestrator_workspace: Path,
    target_root: Path,
    target_workspace: Path,
) -> dict[str, Any]:
    """Run all three drift detection types and produce combined report."""
    artifact_drift = detect_context_drift(
        source_workspace=orchestrator_workspace,
        target_workspace=target_workspace,
    )
    session_drift = detect_session_drift(
        parent_workspace=orchestrator_workspace,
        child_workspace=target_workspace,
    )
    policy_drift = detect_policy_drift(
        source_root=orchestrator_root,
        target_root=target_root,
    )

    # Combined status: worst of all three
    statuses = [artifact_drift["status"], session_drift["status"], policy_drift["status"]]
    if "FAIL" in statuses:
        overall = "FAIL"
    elif "WARN" in statuses:
        overall = "WARN"
    else:
        overall = "OK"

    total_drifted = (
        artifact_drift.get("drifted_count", 0)
        + session_drift.get("missing_in_child", 0)
        + policy_drift.get("drifted_count", 0)
    )

    # Drift score: 0 (full drift) to 100 (clean)
    total_checked = (
        artifact_drift.get("total_checked", 0)
        + len([k for k in session_drift if k.startswith("missing") or k.startswith("conflict")])
        + policy_drift.get("total_checked", 0)
    )
    drift_score = max(0, 100 - (total_drifted * 20)) if total_checked > 0 else 0

    report = {
        "version": "v1",
        "generated_at": _now_iso(),
        "status": overall,
        "drift_score": min(100, max(0, drift_score)),
        "total_drifted": total_drifted,
        "artifact_drift": artifact_drift,
        "session_drift": session_drift,
        "policy_drift": policy_drift,
    }

    # Write report
    out_path = orchestrator_workspace / ".cache" / "reports" / "context_drift_report.v1.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    return report
