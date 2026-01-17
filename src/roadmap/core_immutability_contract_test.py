from __future__ import annotations

import os
from pathlib import Path

from src.roadmap.exec_contracts import _CoreImmutabilityPolicy
from src.roadmap.exec_steps import _require_writable_path, RoadmapStepError


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


def _run_locked_blocks() -> None:
    policy = _policy(("policies/",))
    os.environ.pop("CORE_UNLOCK", None)
    os.environ.pop("CORE_UNLOCK_REASON", None)
    try:
        _require_writable_path(
            rel="policies/policy_core_immutability.v1.json",
            forbidden=[],
            write_allowlist=None,
            workspace_root=Path.cwd(),
            core_root=Path.cwd(),
            core_policy=policy,
        )
    except RoadmapStepError as exc:
        if exc.error_code != policy.blocked_write_error_code:
            raise SystemExit("core_immutability_contract_test failed: locked error_code mismatch")
    else:
        raise SystemExit("core_immutability_contract_test failed: locked must block")


def _run_reason_required_blocks() -> None:
    policy = _policy(("policies/",))
    os.environ["CORE_UNLOCK"] = "1"
    os.environ.pop("CORE_UNLOCK_REASON", None)
    try:
        _require_writable_path(
            rel="policies/policy_core_immutability.v1.json",
            forbidden=[],
            write_allowlist=None,
            workspace_root=Path.cwd(),
            core_root=Path.cwd(),
            core_policy=policy,
        )
    except RoadmapStepError as exc:
        if exc.error_code != policy.blocked_write_error_code:
            raise SystemExit("core_immutability_contract_test failed: reason error_code mismatch")
    else:
        raise SystemExit("core_immutability_contract_test failed: missing reason must block")


def _run_allowlist_blocks() -> None:
    policy = _policy(("policies/",))
    os.environ["CORE_UNLOCK"] = "1"
    os.environ["CORE_UNLOCK_REASON"] = "contract_test"
    try:
        _require_writable_path(
            rel="src/roadmap/executor.py",
            forbidden=[],
            write_allowlist=None,
            workspace_root=Path.cwd(),
            core_root=Path.cwd(),
            core_policy=policy,
        )
    except RoadmapStepError as exc:
        if exc.error_code != policy.blocked_write_error_code:
            raise SystemExit("core_immutability_contract_test failed: allowlist error_code mismatch")
    else:
        raise SystemExit("core_immutability_contract_test failed: non-allowlist must block")


def _run_allowlist_allows() -> None:
    policy = _policy(("policies/",))
    os.environ["CORE_UNLOCK"] = "1"
    os.environ["CORE_UNLOCK_REASON"] = "contract_test"
    _require_writable_path(
        rel="policies/policy_core_immutability.v1.json",
        forbidden=[],
        write_allowlist=None,
        workspace_root=Path.cwd(),
        core_root=Path.cwd(),
        core_policy=policy,
    )


def main() -> None:
    _run_locked_blocks()
    _run_reason_required_blocks()
    _run_allowlist_blocks()
    _run_allowlist_allows()
    print("core_immutability_contract_test ok=true")


if __name__ == "__main__":
    main()
