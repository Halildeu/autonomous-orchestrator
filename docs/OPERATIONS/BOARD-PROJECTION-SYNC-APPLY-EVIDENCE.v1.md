# Board Projection Sync Apply Evidence (v1)

Status: REVIEW_READY  
Started: 2026-06-17  
Scope: BOG-5C operator-bound board projection sync apply implementation evidence  
Current mode: sync apply executor implemented; live mutation remains gated by
accepted projection digest, explicit confirmation, target board id, token env,
and operator-provided ProjectV2 metadata map

## 1. Summary

BOG-5C implemented the operator-bound sync apply path.

Implemented command:

```text
python3 -m src.ops.manage board-sync
```

The command consumes:

- a schema-valid `board_projection.v1` report;
- an accepted projection digest value;
- an explicit target board id;
- an operator-provided ProjectV2 metadata map;
- the BOG-3C apply confirmation string;
- a token env name;
- a `gh` executable.

It does not close issues and does not automate `Done`.

## 2. Source Window Evidence

Workspace override path:

```text
.cache/ws_customer_default/.cache/policy_overrides/policy_core_immutability.override.v1.json
```

Window metadata:

```text
enabled=true during implementation
opened_at=2026-06-17T00:56:36Z
ttl_seconds=3600
reason=BOG-5C board projection operator-bound sync apply implementation
```

Allowed source/test/fixture paths:

```text
src/ops/board/sync.py
src/ops/commands/board_cmds.py
tests/contract/test_board_sync.py
fixtures/board/board_sync_projection_status_drift.v1.json
fixtures/board/board_sync_projection_done_forbidden.v1.json
fixtures/board/board_sync_metadata_happy.v1.json
fixtures/board/board_sync_metadata_missing_ids.v1.json
```

Write authorization checks passed for source targets with:

```text
CORE_UNLOCK=1 CORE_UNLOCK_REASON='BOG-5C board projection operator-bound sync apply implementation'
```

## 3. Behavior Implemented

Implemented:

- schema validation for input projection;
- accepted digest gate;
- explicit target board id gate;
- operator-provided ProjectV2 field/item metadata map;
- token env presence gate;
- `gh` availability gate;
- fake-`gh` apply tests;
- ProjectV2 field sync for changed fields;
- label sync for missing desired labels;
- before inventory capture;
- after inventory summary;
- mutation ledger;
- recovery note;
- `Done` automation block;
- issue close omission by design.

Not implemented in BOG-5C:

- live ProjectV2 metadata discovery;
- live token scope proof against the real GitHub API;
- runtime or browser-user-path acceptance;
- human acceptance/closure of board work.

## 4. Test Evidence

Contract test:

```text
python3 -m pytest tests/contract/test_board_commands.py tests/contract/test_board_apply.py tests/contract/test_board_projection.py tests/contract/test_board_pr_merge.py tests/contract/test_board_sync.py -q
```

Observed result:

```text
30 passed in 4.47s
```

Smoke command with fake executable:

```text
BOARD_TEST_TOKEN=present python3 -m src.ops.manage board-sync \
  --projection fixtures/board/board_sync_projection_status_drift.v1.json \
  --metadata fixtures/board/board_sync_metadata_happy.v1.json \
  --accepted-digest 8888888888888888888888888888888888888888888888888888888888888888 \
  --target-board-id PVT_fixture_project \
  --mode apply \
  --apply-confirm APPLY_BOARD_GOVERNANCE_BOG_3C \
  --token-env BOARD_TEST_TOKEN \
  --gh-bin /bin/echo \
  --out none
```

Observed result:

```text
status=OK
applied_actions includes set_project_field and add_label
mutation_ledger populated
before_inventory populated
after_inventory populated
recovery_note populated
```

Blocked path evidence:

```text
digest mismatch => status=BLOCKED, no fake-gh call
missing token => status=BLOCKED, no fake-gh call
missing ProjectV2 metadata => status=BLOCKED, no fake-gh call
desired Status=Done => status=BLOCKED, no fake-gh call
```

## 5. Does Not Prove

This implementation evidence does not prove:

- live GitHub token scope is sufficient;
- live ProjectV2 metadata discovery works;
- live ProjectV2 mutation has been executed against the real board;
- runtime/live acceptance is complete;
- browser/user-path acceptance is complete;
- issue closure is appropriate.

## 6. BOG-5C Acceptance State

BOG-5C is `REVIEW_READY`.

The operator-bound sync apply path is implemented and tested with fake `gh`.
It is not `DONE` until accepted and, if required, exercised against the real
GitHub Project with explicit operator inputs.
