from __future__ import annotations

from src.orchestrator.runner_stage_contract_test_utils import all_scenario_ids, run_contract_test


def main() -> None:
    run_contract_test(
        test_name="runner_execute_behavior_freeze_contract_test",
        scenario_ids=all_scenario_ids(),
    )


if __name__ == "__main__":
    main()

