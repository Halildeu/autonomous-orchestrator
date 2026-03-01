from __future__ import annotations

from src.orchestrator.runner_stage_contract_test_utils import STAGE_SCENARIO_IDS, run_contract_test


def main() -> None:
    run_contract_test(
        test_name="runner_stage_governor_contract_test",
        scenario_ids=STAGE_SCENARIO_IDS["governor"],
    )


if __name__ == "__main__":
    main()

