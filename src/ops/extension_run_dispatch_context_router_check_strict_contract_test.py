from __future__ import annotations

import json
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.ops.extension_run_dispatch_e2e_test_utils import run_dispatch_case
    from src.ops.extension_run_dispatch_context_router_check_preconditions import (
        seed_context_router_check_strict_preconditions,
    )

    payload = run_dispatch_case(
        test_name=Path(__file__).stem,
        extension_id="PRJ-CONTEXT-ORCHESTRATION",
        expected_gate="context-router-check",
        mode="strict",
        required_output_keys=[
            "context_router_result_path",
            "system_status_path",
            "request_intake_to_exec_trace_path",
            "context_orchestration_status_path",
        ],
        precondition_seed=seed_context_router_check_strict_preconditions,
    )
    if str(payload.get("single_gate_status") or "") != "OK":
        raise SystemExit("extension_run_dispatch_context_router_check_strict_contract_test failed: single_gate_status!=OK")
    if str(payload.get("status") or "") != "OK":
        raise SystemExit("extension_run_dispatch_context_router_check_strict_contract_test failed: run_status!=OK")
    ws_root = Path(str(payload.get("workspace_root") or ""))
    if not ws_root.is_absolute() or not ws_root.exists():
        raise SystemExit("extension_run_dispatch_context_router_check_strict_contract_test failed: workspace_root invalid")
    outputs = payload.get("single_gate_outputs") if isinstance(payload.get("single_gate_outputs"), dict) else {}
    for key in ["request_intake_to_exec_trace_path", "context_orchestration_status_path"]:
        rel = str(outputs.get(key) or "").strip()
        if not rel:
            raise SystemExit(f"extension_run_dispatch_context_router_check_strict_contract_test failed: missing {key}")
        artifact = ws_root / rel
        if not artifact.exists():
            raise SystemExit(
                f"extension_run_dispatch_context_router_check_strict_contract_test failed: artifact_not_found {key}={rel}"
            )
    print(
        json.dumps(
            {
                "status": "OK",
                "extension_id": "PRJ-CONTEXT-ORCHESTRATION",
                "mode": "strict",
                "single_gate_status": payload.get("single_gate_status"),
                "run_status": payload.get("status"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
