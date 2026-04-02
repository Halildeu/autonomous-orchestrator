from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

_WORKSPACE_DIRS = ("schemas", "policies", "registry")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _clone_workspace(*, root: Path, workspace: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    for rel in _WORKSPACE_DIRS:
        shutil.copytree(root / rel, workspace / rel)


def main() -> None:
    root = _repo_root()
    sys.path.insert(0, str(root))

    from src.ops.ai_entry_pack_build import build_ai_entry_pack
    from src.ops.execution_target_ops import run_execution_target_resolve, run_execution_target_status

    with tempfile.TemporaryDirectory(prefix="execution-target-ops-") as td:
        workspace = Path(td) / "ws"
        _clone_workspace(root=root, workspace=workspace)
        build_ai_entry_pack(workspace_root=workspace)

        status = run_execution_target_status(workspace_root=workspace)
        if status.get("status") not in {"OK", "WARN"}:
            raise SystemExit("execution_target_ops_contract_test failed: status command status invalid")
        if int(status.get("counts", {}).get("targets", 0)) < 1:
            raise SystemExit("execution_target_ops_contract_test failed: target count missing")

        resolution = run_execution_target_resolve(
            workspace_root=workspace,
            envelope={
                "request_id": "OPS-TEST",
                "tenant_id": "OPS",
                "intent": "urn:core:summary:summary_to_file",
                "risk_score": 0.1,
                "dry_run": False,
                "side_effect_policy": "allow",
                "idempotency_key": "OPS-TEST",
                "context": {
                    "target_id": "dev:web",
                    "launch_profile_id": "dev:web-shell",
                    "selection_reason": "execution_target_ops_contract_test",
                },
            },
        )
        resolved = resolution.get("resolved") if isinstance(resolution.get("resolved"), dict) else {}
        if str(resolved.get("target_id") or "").strip() != "dev:web":
            raise SystemExit("execution_target_ops_contract_test failed: target resolve mismatch")
        if str(resolved.get("launch_profile_id") or "").strip() != "dev:web-shell":
            raise SystemExit("execution_target_ops_contract_test failed: launch resolve mismatch")
    print("execution_target_ops_contract_test: PASS")


if __name__ == "__main__":
    main()
