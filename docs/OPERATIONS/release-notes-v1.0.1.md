# v1.0.1 Release Notes

Release date: **2026-03-01**

## Summary

This release consolidates six delivery packages in a single integration line:
- P0 (`a672712`)
- P1 (`7d8cde0`)
- P2 (`2c62c73`)
- P2.1 (`5b0ed8a`)
- P3 (`cb68dc1`)
- P3.1 (`eb98a8f`)

Branch state at release cut:
- `codex/fts5-rg-search` is aligned with `origin/codex/fts5-rg-search`.

## Package Breakdown

| Package | Commit | Scope | Key Outcome |
|---|---|---|---|
| P0 | `a672712` | smoke deprecation gate, script-budget baseline, policy report contracts | Stabilized smoke/script-budget quality gates with contract coverage and safer policy reporting behavior. |
| P1 | `7d8cde0` | context-pack routing split, tenant/session context schemas, cross-session context contracts | Reduced router coupling and introduced explicit tenant/session context artifacts and validation path. |
| P2 | `2c62c73` | runner stage pipeline refactor, stage modules, freeze contracts/snapshots | Moved runner execution to stage-based flow (`validate -> governor -> routing_workflow -> idempotency -> quota_autonomy -> execute_finalize`) with stronger behavior lock tests. |
| P2.1 | `5b0ed8a` | stage snapshot split + compatibility map | Replaced monolithic stage snapshot usage with per-stage snapshot files while preserving legacy scenario-map compatibility. |
| P3 | `cb68dc1` | smoke root-cause schema+engine, 3-phase execution scripts, workflow/docs updates | Added root-cause reporting and operations tooling for managed multi-repo 3-phase execution, plus CI/doc/cockpit integration updates. |
| P3.1 | `eb98a8f` | CI blocker aggregation contract, stage-level test-run reporting | Added `phase_all_blocking_reasons` contract test and stage-level PASS/FAIL visibility in `test-run` outputs. |

## Highlights

- Runner architecture is now explicitly stage-driven and contract-guarded.
- Stage-level behavior is testable both individually and as an aggregate suite.
- Smoke pipeline now emits explicit root-cause reports (`NONE` when healthy).
- Managed multi-repo operations gained a dedicated 3-phase execution tooling path.
- CI now validates phase-all blocker aggregation contract and surfaces stage-level quality signals.

## Validation Summary

Primary verification commands executed during packaging:

```bash
python3 ci/validate_schemas.py
python3 src/ops/smoke_root_cause_contract_test.py
python3 -m src.ops.manage doc-nav-check --workspace-root .cache/ws_customer_default
python3 -m src.ops.manage smoke --level fast
python3 src/ops/phase_all_blocking_reasons_contract_test.py
python3 -m src.orchestrator.runner_stage_contract_suite_test
python3 -m src.orchestrator.runner_execute_behavior_freeze_contract_test
python3 -m src.ops.manage test-run --workspace-root .cache/ws_customer_default --out .cache/reports/test_run_p3_1.v1.json
```

Observed release-line outcomes:
- `runner_stage_contract_suite_test ok=true stages=6 scenarios=12`
- `runner_execute_behavior_freeze_contract_test ok=true scenarios=12`
- `SMOKE_OK` and `SMOKE_ROOT_CAUSE_REPORT ... code=NONE`
- `test-run status=OK`, `failures=[]`, stage contracts all `PASS`

## Change Volume

Cumulative package-level delta:
- `98 files changed`
- `8468 insertions(+)`
- `1825 deletions(-)`

## PR Description (ready to paste)

### What changed
- Consolidated P0, P1, P2, P2.1, P3, and P3.1 into a single tested release line.
- Refactored runner into stage-based execution with freeze contracts and per-stage snapshots.
- Added smoke root-cause reporting and multi-repo 3-phase execution tooling.
- Extended CI with phase-all blocker aggregation contract and stage-level test-run reporting.

### Why
- Improve determinism, debuggability, and failure localization across orchestrator execution and CI quality loops.
- Reduce coupling in context and runner flows while preserving backward compatibility where needed.

### How verified
- Schema/policy/roadmap validations passed.
- Runner stage suite and freeze behavior contracts passed.
- Smoke fast path passed with root-cause classification `NONE`.
- Test-run passed with stage-level contract map all `PASS`.

### Risk and rollback
- Main behavioral shift is stage-based runner execution; guarded by freeze contracts and stage suites.
- Rollback strategy: revert commits in reverse order (`eb98a8f` -> `cb68dc1` -> `5b0ed8a` -> `2c62c73` -> `7d8cde0` -> `a672712`) if regression is detected.
