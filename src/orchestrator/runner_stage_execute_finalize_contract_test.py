from __future__ import annotations

from src.orchestrator.runner_stage_contract_test_utils import run_stage_contract_test


def main() -> None:
    run_stage_contract_test(
        test_name="runner_stage_execute_finalize_contract_test",
        stage_name="execute_finalize",
    )


if __name__ == "__main__":
    main()
