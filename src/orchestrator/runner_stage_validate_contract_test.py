from __future__ import annotations

from src.orchestrator.runner_stage_contract_test_utils import STAGE_SCENARIO_IDS, run_contract_test


def main() -> None:
    run_contract_test(
        test_name="runner_stage_validate_contract_test",
        scenario_ids=STAGE_SCENARIO_IDS["validate"],
    )


if __name__ == "__main__":
    main()

