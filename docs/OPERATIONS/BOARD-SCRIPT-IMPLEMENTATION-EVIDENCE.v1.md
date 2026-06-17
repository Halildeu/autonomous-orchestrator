# Board Script Implementation Evidence (v1)

Status: REVIEW_READY  
Started: 2026-06-17  
Scope: BOG-3B dry-run/report-only board command implementation evidence  
Current mode: source implementation completed under one-shot source window; live
GitHub apply remains blocked until BOG-3C

## 1. Summary

BOG-3B implemented the minimal board command surface in report/dry-run form.

Implemented commands:

```text
python3 -m src.ops.manage board-list
python3 -m src.ops.manage board-claim
python3 -m src.ops.manage board-heartbeat
python3 -m src.ops.manage board-release
python3 -m src.ops.manage board-verify
python3 -m src.ops.manage board-backlog-add
```

The implementation is fixture-backed and local. It does not call live GitHub,
does not mutate GitHub Project state, does not close issues, and does not mark
runtime/governance work `Done`.

## 2. Source Window Evidence

Workspace override path:

```text
.cache/ws_customer_default/.cache/policy_overrides/policy_core_immutability.override.v1.json
```

Window metadata:

```text
enabled=true during implementation; closed after validation
opened_at=2026-06-17T00:15:44Z
closed_at=2026-06-17T00:23:08Z
ttl_seconds=3600
reason=BOG-3B board governance dry-run/report-only implementation
```

Restore evidence:

```text
.cache/ws_customer_default/.cache/reports/core_unlock_compliance.v1.json
```

Post-close write authorization check:

```text
python3 -m src.ops.manage write-authorize --workspace-root .cache/ws_customer_default --target-path src/ops/commands/board_cmds.py
```

Observed result:

```text
status=BLOCKED
core_unlock_active=false
deny_reasons=["CORE_UNLOCK=1 required for src/ writes"]
```

Write authorization command:

```text
CORE_UNLOCK=1 CORE_UNLOCK_REASON='BOG-3B board governance dry-run/report-only implementation' \
python3 -m src.ops.manage write-authorize --workspace-root .cache/ws_customer_default --target-path src/ops/commands/board_cmds.py
```

Observed result:

```text
status=PASS
core_unlock_required=true
core_unlock_active=true
required_validations=["python3 ci/core_ops_contract_test.py"]
```

## 3. Implemented Files

Source:

```text
src/ops/board/__init__.py
src/ops/board/models.py
src/ops/board/fixtures.py
src/ops/board/reports.py
src/ops/board/rules.py
src/ops/commands/board_cmds.py
src/ops/manage.py
```

Tests and fixtures:

```text
tests/contract/test_board_commands.py
fixtures/board/board_list_happy.v1.json
fixtures/board/board_claim_conflict.v1.json
fixtures/board/board_needs_verify_drift.v1.json
fixtures/board/board_malformed_gh_json.v1.json
```

## 4. Behavior Implemented

Implemented:

- fixture-backed `board-list` drift report;
- fixture-backed `board-claim` claim planning;
- fixture-backed `board-heartbeat` heartbeat planning;
- fixture-backed `board-release` claim release planning;
- fixture-backed `board-verify` evidence planning;
- fixture-backed `board-backlog-add` issue creation planning;
- report JSON output shape with non-empty `does_not_prove`;
- `applied_actions=[]` outside `apply`;
- `--mode apply` returns `BLOCKED` until BOG-3C;
- malformed fixture/GitHub JSON simulation returns `ERROR`;
- active competing claim returns `BLOCKED`;
- forbidden close keyword and `Needs Verify` label drift are reported.

Not implemented in BOG-3B:

- live GitHub API calls;
- GitHub ProjectV2 mutation;
- issue comments;
- issue close;
- `Done` transition;
- workflow automation;
- projection drift checker implementation.

## 5. Test Evidence

Contract test:

```text
python3 -m pytest tests/contract/test_board_commands.py -q
```

Observed result:

```text
10 passed in 1.11s
```

Required core validation:

```text
CORE_UNLOCK=1 CORE_UNLOCK_REASON='BOG-3B board governance dry-run/report-only implementation' \
python3 ci/core_ops_contract_test.py
```

Observed result:

```text
{"status": "OK", "tests_passed": 10, "tests_failed": 0}
```

Additional gates:

```text
python3 ci/validate_schemas.py
python3 -m src.ops.manage policy-check --source both
python3 -m src.ops.manage doc-nav-check --workspace-root .cache/ws_customer_default
```

Observed results:

```text
validate_schemas=OK
policy-check=OK
doc-nav-check=OK
```

## 6. Does Not Prove

This implementation evidence does not prove:

- live GitHub token/PAT behavior;
- live ProjectV2 field mutation safety;
- issue comment idempotency against real GitHub comments;
- PR merge workflow behavior;
- board projection drift checker behavior;
- runtime or user-path acceptance;
- BOG-3C live apply readiness.

## 7. BOG-3B Acceptance State

BOG-3B is `REVIEW_READY`.

The one-shot source window is closed/restored with evidence. BOG-3B is not
`DONE` until the repo owner accepts the implementation.
