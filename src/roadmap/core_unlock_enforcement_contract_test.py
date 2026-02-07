from __future__ import annotations

import os
from pathlib import Path

from src.roadmap.exec_contracts import _CoreImmutabilityPolicy
from src.roadmap.exec_steps import RoadmapStepError, _require_writable_path


def _policy(allowlist: tuple[str, ...]) -> _CoreImmutabilityPolicy:
    return _CoreImmutabilityPolicy(
        enabled=True,
        default_mode="locked",
        allow_env_var="CORE_UNLOCK",
        allow_env_value="1",
        core_write_mode="ssot_only_when_unlocked",
        ssot_write_allowlist=allowlist,
        require_unlock_reason=True,
        evidence_required_when_unlocked=True,
        blocked_write_error_code="CORE_IMMUTABLE_WRITE_BLOCKED",
        core_git_required=True,
    )


def _assert_blocked(rel: str, policy: _CoreImmutabilityPolicy) -> None:
    try:
        _require_writable_path(
            rel=rel,
            forbidden=[],
            write_allowlist=None,
            workspace_root=Path.cwd(),
            core_root=Path.cwd(),
            core_policy=policy,
        )
    except RoadmapStepError as exc:
        if exc.error_code != policy.blocked_write_error_code:
            raise SystemExit("core_unlock_enforcement_contract_test failed: error_code mismatch")
    else:
        raise SystemExit("core_unlock_enforcement_contract_test failed: expected block")


def _assert_allowed(rel: str, policy: _CoreImmutabilityPolicy) -> None:
    _require_writable_path(
        rel=rel,
        forbidden=[],
        write_allowlist=None,
        workspace_root=Path.cwd(),
        core_root=Path.cwd(),
        core_policy=policy,
    )


def main() -> None:
    policy = _policy(("policies/",))

    os.environ.pop("CORE_UNLOCK", None)
    os.environ.pop("CORE_UNLOCK_REASON", None)
    _assert_blocked("policies/policy_core_immutability.v1.json", policy)

    os.environ["CORE_UNLOCK"] = "1"
    os.environ.pop("CORE_UNLOCK_REASON", None)
    _assert_blocked("policies/policy_core_immutability.v1.json", policy)

    os.environ["CORE_UNLOCK"] = "1"
    os.environ["CORE_UNLOCK_REASON"] = "contract_test"
    _assert_allowed("policies/policy_core_immutability.v1.json", policy)
    _assert_blocked("src/roadmap/executor.py", policy)

    print("core_unlock_enforcement_contract_test ok=true")


if __name__ == "__main__":
    main()
