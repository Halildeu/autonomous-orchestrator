# Board Projection Drift Evidence (v1)

Status: REVIEW_READY  
Started: 2026-06-17  
Scope: BOG-5B dry-run board projection drift checker implementation evidence  
Current mode: source implementation completed under one-shot source window; live
GitHub Project sync apply remains blocked until BOG-5C

## 1. Summary

BOG-5B implemented a fixture-backed `board-projection` command in report/dry-run
form.

Implemented command:

```text
python3 -m src.ops.manage board-projection
```

The command reads a schema-valid local projection fixture, derives drift, prints
a wrapper report to stdout, and may write a schema-valid `board_projection.v1`
manifest under the selected workspace. It does not query live GitHub, mutate a
ProjectV2 board, close issues, change labels, or mark work `Done`.

## 2. Source Window Evidence

Workspace override path:

```text
.cache/ws_customer_default/.cache/policy_overrides/policy_core_immutability.override.v1.json
```

Window metadata:

```text
enabled=true during implementation
opened_at=2026-06-17T00:28:00Z
ttl_seconds=3600
reason=BOG-5B board projection drift dry-run implementation
```

Allowed source/test/fixture paths:

```text
src/ops/board/projection.py
src/ops/board/drift.py
src/ops/commands/board_cmds.py
tests/contract/test_board_projection.py
fixtures/board/projection_missing_field.v1.json
```

Write authorization checks passed for the source targets with:

```text
CORE_UNLOCK=1 CORE_UNLOCK_REASON='BOG-5B board projection drift dry-run implementation'
```

## 3. Implemented Files

Source:

```text
src/ops/board/drift.py
src/ops/board/projection.py
src/ops/commands/board_cmds.py
```

Tests and fixtures:

```text
tests/contract/test_board_projection.py
fixtures/board/projection_missing_field.v1.json
```

Existing fixtures reused:

```text
fixtures/board/board_projection_happy.v1.json
fixtures/board/board_projection_forbidden_done.v1.json
```

## 4. Behavior Implemented

Implemented:

- fixture-backed `board-projection` command;
- schema validation against `schemas/board-projection.schema.v1.json`;
- schema-valid projection report writing under workspace;
- happy projection with no drift returning `OK`;
- missing required board field drift as `MISSING_FIELD`;
- forbidden `Done` drift as `FORBIDDEN_DONE`;
- unexpected board item drift as `UNEXPECTED_BOARD_ITEM`;
- missing board item drift as `MISSING_BOARD_ITEM`;
- invalid Status/Track/Priority/Kind drift as `INVALID_FIELD_VALUE`;
- `Needs Verify` label mismatch drift as `NEEDS_VERIFY_LABEL_MISMATCH`;
- `Blocked` label mismatch drift as `BLOCKED_STATE_MISMATCH`;
- drift summary by severity and code;
- `applied_actions=[]` outside apply;
- `--mode apply` returns `BLOCKED` until BOG-5C.

Not implemented in BOG-5B:

- live GitHub API inventory;
- ProjectV2 mutation;
- label mutation;
- issue comment mutation;
- issue close;
- PR close-keyword parsing from live PR bodies;
- claim conflict parsing from live issue comments;
- digest mismatch recomputation;
- operator-bound sync apply.

## 5. Command Evidence

Happy fixture:

```text
python3 -m src.ops.manage board-projection --fixture fixtures/board/board_projection_happy.v1.json --out none
```

Observed result:

```text
status=OK
drift_summary.total=0
applied_actions=[]
```

Forbidden Done fixture:

```text
python3 -m src.ops.manage board-projection --fixture fixtures/board/board_projection_forbidden_done.v1.json --out none
```

Observed result:

```text
status=WARN
drift_summary.by_code.FORBIDDEN_DONE=2
drift_summary.by_severity.ERROR=2
applied_actions=[]
```

Missing field fixture:

```text
python3 -m src.ops.manage board-projection --fixture fixtures/board/projection_missing_field.v1.json --out none
```

Observed result:

```text
status=WARN
drift_summary.by_code.MISSING_FIELD=1
drift_summary.max_severity=WARN
applied_actions=[]
```

Apply mode:

```text
python3 -m src.ops.manage board-projection --fixture fixtures/board/board_projection_happy.v1.json --mode apply --out none
```

Observed result:

```text
exit=1
status=BLOCKED
blocked_reasons=["APPLY_MODE_NOT_AVAILABLE_UNTIL_BOG_5C"]
applied_actions=[]
```

## 6. Test Evidence

Contract test:

```text
python3 -m pytest tests/contract/test_board_commands.py tests/contract/test_board_projection.py -q
```

Observed result:

```text
14 passed in 1.60s
```

Required core validation:

```text
CORE_UNLOCK=1 CORE_UNLOCK_REASON='BOG-5B board projection drift dry-run implementation' \
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

## 7. Does Not Prove

This implementation evidence does not prove:

- live GitHub token/PAT behavior;
- live ProjectV2 read or mutation safety;
- issue comment idempotency against real GitHub comments;
- PR close-keyword detection against live PR bodies;
- digest mismatch detection against live observed state;
- runtime or user-path acceptance;
- BOG-5C live sync apply readiness.

## 8. BOG-5B Acceptance State

BOG-5B is `REVIEW_READY`.

The dry-run checker is implemented and tested. It is not `DONE` until the repo
owner accepts the implementation. BOG-5C remains `DEFERRED`, and apply mode
remains blocked.
