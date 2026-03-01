from __future__ import annotations

from src.orchestrator.runner_stage_contract_test_utils import all_scenario_ids, run_stage_contract_test, stage_names


def main() -> None:
    stages = stage_names()
    for stage_name in stages:
        run_stage_contract_test(
            test_name=f"runner_stage_{stage_name}_contract_test",
            stage_name=stage_name,
        )
    print(f"runner_stage_contract_suite_test ok=true stages={len(stages)} scenarios={len(all_scenario_ids())}")


if __name__ == "__main__":
    main()
