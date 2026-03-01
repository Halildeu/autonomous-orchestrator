from __future__ import annotations

from src.orchestrator.runner_stage_contract_test_utils import STAGE_SCENARIO_IDS, run_contract_test


def main() -> None:
    total = 0
    for stage_name, scenario_ids in STAGE_SCENARIO_IDS.items():
        run_contract_test(
            test_name=f"runner_stage_{stage_name}_contract_test",
            scenario_ids=scenario_ids,
        )
        total += len(scenario_ids)
    print(f"runner_stage_contract_suite_test ok=true stages={len(STAGE_SCENARIO_IDS)} scenarios={total}")


if __name__ == "__main__":
    main()

