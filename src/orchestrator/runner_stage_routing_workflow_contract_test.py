from __future__ import annotations

from src.orchestrator.runner_stage_contract_test_utils import run_stage_contract_test


def main() -> None:
    run_stage_contract_test(
        test_name="runner_stage_routing_workflow_contract_test",
        stage_name="routing_workflow",
    )


if __name__ == "__main__":
    main()
