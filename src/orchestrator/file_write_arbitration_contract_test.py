from __future__ import annotations

import sys
import tempfile
from pathlib import Path

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main() -> None:
    root = _repo_root()
    sys.path.insert(0, str(root))

    from src.orchestrator.file_write_arbitration import (
        acquire_path_write_lease,
        release_path_write_lease,
        summarize_path_write_leases,
    )

    with tempfile.TemporaryDirectory(prefix="file-write-arbitration-") as td:
        workspace = Path(td) / "ws"
        workspace.mkdir(parents=True, exist_ok=True)
        target = workspace / "reports" / "same-file.md"

        first = acquire_path_write_lease(
            workspace_root=workspace,
            target_path=target,
            run_id="RUN-A",
            owner_tag="MOD_B",
            owner_session="SESSION-A",
            evidence_paths=["evidence/RUN-A/request.json"],
        )
        if first.get("status") != "ACQUIRED":
            raise SystemExit("file_write_arbitration_contract_test failed: first acquire")

        second = acquire_path_write_lease(
            workspace_root=workspace,
            target_path=target,
            run_id="RUN-B",
            owner_tag="MOD_B",
            owner_session="SESSION-B",
            evidence_paths=["evidence/RUN-B/request.json"],
        )
        if second.get("status") != "LOCKED":
            raise SystemExit("file_write_arbitration_contract_test failed: second writer must lock")

        summary = summarize_path_write_leases(workspace_root=workspace)
        if int(summary.get("active_lease_count", 0)) != 1:
            raise SystemExit("file_write_arbitration_contract_test failed: active lease count mismatch")

        release = release_path_write_lease(workspace_root=workspace, target_path=target, run_id="RUN-A")
        if release.get("status") != "RELEASED":
            raise SystemExit("file_write_arbitration_contract_test failed: release")

        third = acquire_path_write_lease(
            workspace_root=workspace,
            target_path=target,
            run_id="RUN-B",
            owner_tag="MOD_B",
            owner_session="SESSION-B",
            evidence_paths=["evidence/RUN-B/request.json"],
        )
        if third.get("status") != "ACQUIRED":
            raise SystemExit("file_write_arbitration_contract_test failed: acquire after release")

    print("file_write_arbitration_contract_test: PASS")


if __name__ == "__main__":
    main()
