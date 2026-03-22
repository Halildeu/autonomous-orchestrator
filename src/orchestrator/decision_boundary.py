"""Decision boundary enforcement for AI-driven orchestration.

Resolves whether an operation should be FULL_AUTO, HUMAN_REVIEW, or STRICT_DENY
based on operation type, risk score, and policy configuration.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.tools.gateway import PolicyViolation

_BOUNDARY_LEVELS = ("full_auto", "human_review", "strict_deny")


def _load_boundary_policy(workspace_root: Path | None = None) -> dict[str, Any]:
    """Load decision boundary policy with fallback to repo root."""
    candidates = []
    if workspace_root:
        candidates.append(workspace_root / "policies" / "policy_decision_boundaries.v1.json")
    repo_root = Path(__file__).resolve().parents[2]
    candidates.append(repo_root / "policies" / "policy_decision_boundaries.v1.json")

    for path in candidates:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
    return {"version": "v1", "default_mode": "human_review", "boundaries": {}}


def resolve_decision_boundary(
    *,
    operation: str,
    risk_score: float = 0.0,
    provider: str = "",
    policy: dict[str, Any] | None = None,
) -> str:
    """Resolve decision boundary for an operation.

    Returns: 'full_auto' | 'human_review' | 'strict_deny'
    """
    if policy is None:
        policy = _load_boundary_policy()

    boundaries = policy.get("boundaries", {})
    default_mode = str(policy.get("default_mode", "human_review"))
    operation_norm = str(operation).strip().lower()

    # Check each level in strictness order (strict_deny first)
    for level in ("strict_deny", "human_review", "full_auto"):
        level_cfg = boundaries.get(level, {})
        operations = level_cfg.get("operations", [])
        if not isinstance(operations, list):
            continue
        if operation_norm in [str(op).strip().lower() for op in operations]:
            # Check conditions
            conditions = level_cfg.get("conditions", {})
            max_risk = conditions.get("max_risk_score")

            if level == "full_auto" and isinstance(max_risk, (int, float)):
                if risk_score > float(max_risk):
                    return "human_review"  # Risk too high for full_auto → escalate

            return level

    return default_mode


def enforce_decision_boundary(
    *,
    operation: str,
    risk_score: float = 0.0,
    provider: str = "",
    workspace_root: Path | None = None,
) -> str:
    """Enforce decision boundary. Raises PolicyViolation for strict_deny.

    Returns the resolved boundary level for logging.
    """
    policy = _load_boundary_policy(workspace_root)
    boundary = resolve_decision_boundary(
        operation=operation,
        risk_score=risk_score,
        provider=provider,
        policy=policy,
    )

    if boundary == "strict_deny":
        raise PolicyViolation(
            "DECISION_BOUNDARY_STRICT_DENY",
            f"Operation '{operation}' is STRICT_DENY — requires human execution, AI cannot perform this.",
        )

    return boundary
